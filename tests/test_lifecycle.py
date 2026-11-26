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
           "sys.boot_completed": os.environ.get("MOCK_BOOT_READY", "1")}.get(args[0], ""))
    sys.exit(0)
if name == "sleep":
    sys.exit(0)
state["calls"].append([name] + args)
path.write_text(json.dumps(state))
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
        for name in ["settings", "pm", "getprop", "sleep"]:
            file = bin_dir / name
            file.write_text(MOCK)
            file.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                        MOCK_ANDROID_STATE=str(self.state_file), BOOTMODE="true", KSU="true", API="37")
        self.pending = self.adb / "soli_motion-uninstall"
        self.cleanup_script = self.adb / "service.d/soli_motion-cleanup.sh"

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
            file.write_text(file.read_text().replace("/data/adb", str(self.adb)))
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

    def add_legacy_snapshot(self, path):
        (path / "state/settings").mkdir(parents=True)
        (path / "state/settings/doze_always_on").write_text("0\n")
        (path / "state/snapshot.complete").touch()
        (path / "settings-keys.txt").write_text("doze_always_on\n")

    def test_uninstall_removes_owned_adapter_and_its_one_off_task(self):
        self.schedule_uninstall(self.installed())
        self.assertEqual(self.run_script(self.cleanup_script).returncode, 0)
        self.assertNotIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.cleanup_script.exists())

    def test_upgrade_preserves_ownership_without_copying_legacy_settings(self):
        active = self.installed()
        self.add_legacy_snapshot(active)
        lock = self.adb / "soli_motion-lifecycle.lock"
        lock.touch()
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        self.assertTrue((update / "state/adapter.owned").exists())
        self.assertFalse((update / "state/settings").exists())
        self.assertFalse((update / "state/snapshot.complete").exists())
        self.assertFalse(lock.exists())
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

    def test_failed_reinstall_replaces_legacy_settings_cleanup(self):
        self.schedule_uninstall(self.installed())
        self.add_legacy_snapshot(self.pending)
        self.cleanup_script.write_text("settings --user 0 put secure doze_always_on 0\n")
        update = self.stage()
        result = self.install(update, MOCK_INSTALL_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", result.stdout)
        self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", (update / "state/install.log").read_text())
        self.assertEqual(self.cleanup_script.read_text(), (update / "cleanup-once.sh").read_text())
        self.assertFalse((self.pending / "state/settings").exists())
        self.assertFalse((self.pending / "settings-keys.txt").exists())
        self.assertFalse((self.pending / "state/snapshot.complete").exists())
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
        # v0.1 could schedule a settings-only task even for a user-owned adapter.
        self.add_legacy_snapshot(self.pending)
        self.cleanup_script.parent.mkdir(exist_ok=True)
        self.cleanup_script.write_text("settings --user 0 put secure doze_always_on 0\n")
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


if __name__ == "__main__":
    unittest.main()
