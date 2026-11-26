"""Run the real installer/uninstaller against a temporary, mocked Android state."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = "io.github.mrmetatron.soli.adapter"
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, stat, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
path = pathlib.Path(os.environ["MOCK_ANDROID_STATE"])
state = json.loads(path.read_text())
if name == "getprop":
    print({"ro.product.device": "flame",
           "ro.vendor.aware_available": "true",
           "sys.boot_completed": os.environ.get("MOCK_BOOT_READY", "1")}.get(args[0], ""))
    sys.exit(0)
if name == "sleep":
    sys.exit(0)
state["calls"].append([name] + args)
path.write_text(json.dumps(state))
if name == "ps":
    if os.environ.get("MOCK_PS_FAIL"):
        sys.exit(1)
    print("LABEL USER PID NAME")
    context = os.environ.get("MOCK_OSLO_CONTEXT")
    if context:
        print(context, "u0_a123", "123", "com.google.oslo")
    sys.exit(0)
if name == "dalvikvm":
    source, target = map(pathlib.Path, args[-3:-1])
    target.write_text(source.read_text() + "<!-- mocked project signer -->")
    if os.environ.get("MOCK_IDENTITY_FAIL"):
        pathlib.Path(str(target) + ".tmp").write_text("partial")
        sys.exit(1)
    print("Merged project signer for com.google.oslo; existing ROM entries preserved.")
    sys.exit(0)
if name == "ls":
    print("u:object_r:system_file:s0", args[-1])
    sys.exit(0)
if name in ("chcon", "chown"):
    sys.exit(0)
if name == "settings":
    sys.exit("Module lifecycle must leave settings alone")
if name == "pm":
    # Binder passes all three standard FDs to system_server. Module-private
    # files cannot be passed directly; pipes and /dev/null are usable here.
    if any(stat.S_ISREG(os.fstat(fd).st_mode) for fd in (0, 1, 2)):
        sys.exit("cmd: Failure calling service package: Failed transaction (2147483646)")
    if args[0] == "path":
        if args[-1] in state["packages"]:
            print("package:/data/app/mock/base.apk")
    elif args[0] == "install":
        # makeInstallParams parses a bare '-' as an option before the input
        # path is examined. With -S and no path, doRunInstall reads stdin.
        if "-" in args:
            sys.exit("java.lang.IllegalArgumentException: Unknown option -")
        if "-S" not in args or any(arg.endswith(".apk") for arg in args):
            sys.exit("APK must be streamed rather than opened from the module directory")
        payload = sys.stdin.buffer.read()
        if len(payload) != int(args[args.index("-S") + 1]) or payload != b"mock-apk":
            sys.exit("APK stream or declared size differs from the source")
        if os.environ.get("MOCK_INSTALL_FAIL"):
            print("Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]", file=sys.stderr)
            sys.exit(1)
        if "io.github.mrmetatron.soli.adapter" not in state["packages"]:
            state["packages"].append("io.github.mrmetatron.soli.adapter")
        print("Success")
    elif args[0:2] == ["list", "packages"]:
        if os.environ.get("MOCK_QUERY_FAIL"):
            sys.exit(1)
        for p in state["packages"]:
            if args[-1] in p:
                print("package:" + p)
    elif args[0] == "uninstall":
        if os.environ.get("MOCK_UNINSTALL_FAIL"):
            sys.exit(1)
        if args[-1] in state["packages"]:
            state["packages"].remove(args[-1])
        print("Success")
    elif args[0] == "grant":
        if os.environ.get("MOCK_GRANT_FAIL") == args[-1]:
            print("Operation not allowed", file=sys.stderr)
            sys.exit(1)
        state.setdefault("grants", []).append(args[-2:])
path.write_text(json.dumps(state))
'''


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.adb = self.root / "adb"
        self.adb.mkdir()
        self.state_file = self.root / "android.json"
        self.save({"packages": [], "calls": []})
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name in ["settings", "pm", "getprop", "sleep", "ps", "dalvikvm", "ls", "chcon", "chown"]:
            file = bin_dir / name
            file.write_text(MOCK)
            file.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                        MOCK_ANDROID_STATE=str(self.state_file), BOOTMODE="true", KSU="true", API="37")
        self.pending = self.adb / "soli_motion-uninstall"
        self.cleanup_script = self.adb / "service.d/soli_motion-cleanup.sh"
        self.seapp = self.root / "vendor_seapp_contexts"
        self.oslo_rule = "user=_app seinfo=platform name=com.google.oslo domain=oslo_app type=app_data_file levelFrom=all\n"
        self.seapp.write_text(self.oslo_rule)
        self.rom_xml = self.root / "system_ext_mac_permissions.xml"
        self.rom_xml.write_text("<policy><signer signature='ROM'/></policy>\n")
        self.dalvikvm = bin_dir / "dalvikvm"

    def tearDown(self):
        self.assertFalse(any(call[0] == "settings" for call in self.read()["calls"]),
                         "Installation and removal must never read or write settings")

    def save(self, value):
        self.state_file.write_text(json.dumps(value))

    def read(self):
        return json.loads(self.state_file.read_text())

    def stage(self, area="modules_update"):
        path = self.adb / area / "soli_motion"
        shutil.copytree(ROOT / "module", path)
        for file in path.glob("*.sh"):
            source = file.read_text().replace("/data/adb", str(self.adb))
            source = source.replace("/vendor/etc/selinux/vendor_seapp_contexts", str(self.seapp))
            source = source.replace(" /system_ext/etc/selinux/system_ext_mac_permissions.xml", " " + str(self.rom_xml))
            source = source.replace("SOURCE=/system_ext/etc/selinux/system_ext_mac_permissions.xml", "SOURCE=" + str(self.rom_xml))
            source = source.replace("/apex/com.android.art/bin/dalvikvm", str(self.dalvikvm))
            source = source.replace("/system/bin/dalvikvm", str(self.dalvikvm))
            file.write_text(source)
        (path / "adapter").mkdir(exist_ok=True)
        (path / "adapter/SoliAdapter.apk").write_bytes(b"mock-apk")
        return path

    def install(self, path, **extra):
        prelude = 'abort() { echo "$*" >&2; exit 1; }; ui_print() { :; }; '
        prelude += 'set_perm() { :; }; set_perm_recursive() { :; }; . "$MODPATH/customize.sh"'
        with (path / "customize.sh").open("rb") as private_stdin:
            return subprocess.run(["bash", "-c", prelude], env=dict(self.env, MODPATH=str(path), **extra),
                                  stdin=private_stdin, capture_output=True, text=True, timeout=20)

    def run_script(self, path, **extra):
        with path.open("rb") as private_stdin:
            return subprocess.run(["bash", str(path)], env=dict(self.env, **extra),
                                  stdin=private_stdin, capture_output=True, text=True, timeout=20)

    def installed(self, preexisting_adapter=False):
        if preexisting_adapter:
            state = self.read(); state["packages"] = [ADAPTER]; self.save(state)
        stage = self.stage()
        result = self.install(stage)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((stage / "system.prop").exists(), "Only post-fs-data generates system.prop")
        active = self.adb / "modules/soli_motion"
        active.parent.mkdir(exist_ok=True)
        stage.rename(active)
        return active

    def schedule_uninstall(self, active):
        calls_before = self.read()["calls"]
        owned = (active / "state/adapter.owned").exists()
        result = self.run_script(active / "uninstall.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read()["calls"], calls_before, "post-fs-data must not call Android services")
        self.assertEqual(self.cleanup_script.exists(), owned)
        shutil.rmtree(active)  # KernelSU prune_modules removes the directory next.

    def test_uninstall_removes_owned_adapter_and_its_one_off_task(self):
        self.schedule_uninstall(self.installed())
        self.assertEqual(self.run_script(self.cleanup_script).returncode, 0)
        self.assertNotIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.cleanup_script.exists())

    def test_upgrade_preserves_ownership(self):
        active = self.installed()
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        self.assertTrue((update / "state/adapter.owned").exists())
        shutil.rmtree(active); update.rename(active)
        self.schedule_uninstall(active)
        self.run_script(self.cleanup_script)
        self.assertNotIn(ADAPTER, self.read()["packages"])

    def test_reinstall_inherits_ownership_and_cancels_pending_cleanup(self):
        self.schedule_uninstall(self.installed())
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        self.assertTrue((update / "state/adapter.owned").exists())
        self.assertFalse(self.cleanup_script.exists())
        self.assertFalse(self.pending.exists())
        self.assertIn(ADAPTER, self.read()["packages"])

    def test_failed_reinstall_preserves_pending_adapter_cleanup(self):
        self.schedule_uninstall(self.installed())
        pending_script = self.cleanup_script.read_text()
        update = self.stage()
        result = self.install(update, MOCK_INSTALL_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", result.stdout)
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", (update / "state/install.log").read_text())
        self.assertEqual(self.cleanup_script.read_text(), pending_script)
        self.assertTrue((self.pending / "state/adapter.owned").exists())
        self.assertFalse((update / "state/adapter.owned").exists())
        self.run_script(self.cleanup_script)
        self.assertNotIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())

    def test_failed_package_commands_preserve_cleanup_for_retry(self):
        self.schedule_uninstall(self.installed())
        for failure in ["MOCK_QUERY_FAIL", "MOCK_UNINSTALL_FAIL"]:
            self.run_script(self.cleanup_script, **{failure: "1"})
            self.assertTrue(self.cleanup_script.exists())
            self.assertTrue((self.pending / "state/adapter.owned").exists())
            self.assertIn(ADAPTER, self.read()["packages"])
        self.run_script(self.cleanup_script)
        self.assertNotIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())

    def test_uninstaller_keeps_preexisting_adapter_without_scheduling_cleanup(self):
        self.schedule_uninstall(self.installed(preexisting_adapter=True))
        self.assertIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())
        self.assertNotEqual(self.install(self.stage(), MOCK_INSTALL_FAIL="1").returncode, 0)
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.cleanup_script.exists())
        self.assertIn(ADAPTER, self.read()["packages"])

    def test_stale_cleanup_retains_successfully_reinstalled_adapter(self):
        active = self.installed()
        # A stale task left after an interrupted cancellation must see ownership.
        self.assertEqual(self.run_script(active / "uninstall.sh").returncode, 0)
        self.run_script(self.cleanup_script)
        self.assertIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.cleanup_script.exists())

    def test_incomplete_boot_keeps_task_and_does_not_contact_android_services(self):
        self.schedule_uninstall(self.installed())
        before = self.read()
        self.run_script(self.cleanup_script, MOCK_BOOT_READY="0")
        self.assertEqual(self.read(), before)
        self.assertTrue(self.cleanup_script.exists())

    def test_boot_completed_grants_oslo_runtime_permissions_once(self):
        active = self.installed()
        state = self.read()
        state["packages"].append("com.google.oslo")
        self.save(state)
        self.assertEqual(self.run_script(active / "boot-completed.sh").returncode, 0)
        self.assertTrue((active / "state/oslo-permissions.granted").exists())
        self.assertEqual(
            self.read().get("grants"),
            [["com.google.oslo", "android.permission.RECORD_AUDIO"],
             ["com.google.oslo", "android.permission.POST_NOTIFICATIONS"]],
        )
        calls_after_first = [call for call in self.read()["calls"] if call[0] == "pm"]
        # Subsequent boots respect any later user revocation and do not call pm again.
        self.assertEqual(self.run_script(active / "boot-completed.sh").returncode, 0)
        self.assertEqual([call for call in self.read()["calls"] if call[0] == "pm"], calls_after_first)

    def test_boot_completed_retries_when_oslo_missing_or_record_audio_grant_fails(self):
        active = self.installed()
        # Oslo not mounted yet -> marker stays absent.
        self.assertEqual(self.run_script(active / "boot-completed.sh").returncode, 0)
        self.assertFalse((active / "state/oslo-permissions.granted").exists())
        state = self.read()
        state["packages"].append("com.google.oslo")
        self.save(state)
        # RECORD_AUDIO failure -> marker stays absent for next-boot retry.
        self.assertEqual(
            self.run_script(active / "boot-completed.sh",
                            MOCK_GRANT_FAIL="android.permission.RECORD_AUDIO").returncode,
            0,
        )
        self.assertFalse((active / "state/oslo-permissions.granted").exists())

    def test_upgrade_preserves_oslo_permission_grant_marker(self):
        active = self.installed()
        (active / "state/oslo-permissions.granted").touch()
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        self.assertTrue((update / "state/oslo-permissions.granted").exists())

    def test_pre_mount_accepts_reordered_rule_but_rejects_comments_and_nonmatching_selectors(self):
        active = self.installed()
        target = active / "system/system_ext/etc/selinux/system_ext_mac_permissions.xml"
        original = self.rom_xml.read_bytes()
        cases = [
            (self.oslo_rule, True),
            ("\t domain=oslo_app  name=com.google.oslo\tseinfo=platform user=_app # Oslo\n", True),
            ("# " + self.oslo_rule, False),
            (self.oslo_rule.replace("name=com.google.oslo", "name=com.google.oslo.fake"), False),
            (self.oslo_rule.replace("domain=oslo_app", "domain=platform_app_36"), False),
            (self.oslo_rule.replace("seinfo=platform", "seinfo=default"), False),
            (self.oslo_rule.rstrip() + " minTargetSdkVersion=37\n", False),
            (self.oslo_rule.rstrip() + " user=system\n", False),
        ]
        for rule, allowed in cases:
            with self.subTest(rule=rule):
                self.seapp.write_text(rule)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("stale identity")
                Path(str(target) + ".tmp").write_text("stale temporary")
                before = sum(call[0] == "dalvikvm" for call in self.read()["calls"])
                result = self.run_script(active / "post-fs-data.sh")
                self.assertEqual(result.returncode, 0, result.stderr)
                after = sum(call[0] == "dalvikvm" for call in self.read()["calls"])
                self.assertEqual(after - before, int(allowed))
                self.assertEqual(target.exists(), allowed)
                self.assertEqual(target.parent.stat().st_mode & 0o777, 0o755)
                self.assertFalse(Path(str(target) + ".tmp").exists())
                self.assertEqual(self.rom_xml.read_bytes(), original)
                log = active / "state/identity.log"
                self.assertEqual(log.stat().st_mode & 0o777, 0o600)
                if not allowed:
                    self.assertIn("no identity file mounted", log.read_text())

    def test_pre_mount_removes_previous_identity_when_vendor_rule_file_disappears(self):
        active = self.installed()
        target = active / "system/system_ext/etc/selinux/system_ext_mac_permissions.xml"
        self.assertEqual(self.run_script(active / "post-fs-data.sh").returncode, 0)
        self.assertTrue(target.exists())
        self.seapp.unlink()
        self.assertEqual(self.run_script(active / "post-fs-data.sh").returncode, 0)
        self.assertFalse(target.exists())
        self.assertIn("no identity file mounted", (active / "state/identity.log").read_text())

    def test_pre_mount_removes_partial_files_after_merge_failure(self):
        active = self.installed()
        result = self.run_script(active / "post-fs-data.sh", MOCK_IDENTITY_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = active / "system/system_ext/etc/selinux/system_ext_mac_permissions.xml"
        self.assertFalse(target.exists())
        self.assertFalse(Path(str(target) + ".tmp").exists())
        self.assertIn("Identity merge failed", (active / "state/identity.log").read_text())

    def test_health_is_refreshed_after_permission_marker_without_contacting_package_manager(self):
        active = self.installed()
        (active / "state/oslo-permissions.granted").touch()
        before = [call for call in self.read()["calls"] if call[0] == "pm"]
        self.run_script(active / "post-fs-data.sh")
        target = active / "system/system_ext/etc/selinux/system_ext_mac_permissions.xml"
        self.run_script(active / "boot-completed.sh", MOCK_OSLO_CONTEXT="u:r:oslo_app:s0:c123,c456")
        health = active / "state/health.log"
        self.assertIn("oslo_domain_rule=present", health.read_text())
        self.assertIn("identity_file=differs_from_visible_file", health.read_text())
        self.assertIn("domain=expected", health.read_text())
        self.assertIn("Merged project signer", health.read_text())
        self.rom_xml.write_bytes(target.read_bytes())  # Simulate Magic Mount exposing the new file.
        self.run_script(active / "boot-completed.sh", MOCK_OSLO_CONTEXT="u:r:platform_app_36:s0:c123,c456")
        self.assertIn("identity_file=matches_visible_file", health.read_text())
        self.assertIn("domain=unexpected", health.read_text())
        self.assertNotIn("domain=expected", health.read_text())
        self.assertEqual(health.stat().st_mode & 0o777, 0o600)
        self.assertEqual([call for call in self.read()["calls"] if call[0] == "pm"], before)

    def test_health_distinguishes_no_process_from_query_failure(self):
        active = self.installed()
        (active / "state/oslo-permissions.granted").touch()
        self.seapp.unlink()
        self.run_script(active / "boot-completed.sh")
        health = active / "state/health.log"
        self.assertIn("oslo_domain_rule=missing_or_incompatible", health.read_text())
        self.assertIn("identity_file=not_prepared", health.read_text())
        self.assertIn("oslo_process=not_running (may not have started yet)", health.read_text())
        self.run_script(active / "boot-completed.sh", MOCK_PS_FAIL="1")
        self.assertIn("oslo_process=query_failed", health.read_text())


if __name__ == "__main__":
    unittest.main()
