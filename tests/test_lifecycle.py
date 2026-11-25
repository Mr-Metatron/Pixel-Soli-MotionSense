"""Run the real installer/uninstaller against a temporary, mocked Android state."""

import fcntl
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
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
path = pathlib.Path(os.environ["MOCK_ANDROID_STATE"])
state = json.loads(path.read_text())
if name == "getprop":
    print({"ro.product.device": "flame", "ro.vendor.aware_available": "false",
           "sys.boot_completed": os.environ.get("MOCK_BOOT_READY", "1")}.get(args[0], ""))
    sys.exit(0)
if name == "sleep":
    sys.exit(0)
state["calls"].append([name] + args)
if name == "settings":
    args = args[2:]
    action = args[0]
    if len(args) > 2 and args[2] == os.environ.get("MOCK_FAIL_KEY"):
        path.write_text(json.dumps(state)); sys.exit(1)
    if action == "list":
        print("\n".join(k + "=" + v for k, v in state["settings"].items()))
    elif action == "get":
        print(state["settings"].get(args[2], "null"))
    elif action == "put":
        state["settings"][args[2]] = args[3]
    elif action == "delete":
        state["settings"].pop(args[2], None)
elif name == "pm":
    if args[0] == "path":
        if args[-1] in state["packages"]:
            print("package:/data/app/mock/base.apk")
    elif args[0] == "install":
        if os.environ.get("MOCK_INSTALL_FAIL"):
            path.write_text(json.dumps(state)); sys.exit(1)
        if "io.github.mrmetatron.soli.adapter" not in state["packages"]:
            state["packages"].append("io.github.mrmetatron.soli.adapter")
        print("Success")
    elif args[0:2] == ["list", "packages"]:
        for p in state["packages"]:
            if args[-1] in p:
                print("package:" + p)
    elif args[0] == "uninstall":
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
        self.initial = {"aware_enabled": "0", "doze_always_on": "0",
                        "aware_media_apps": "example.one,example.two", "unrelated_setting": "42"}
        self.save({"settings": dict(self.initial), "packages": [], "calls": []})
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
        prelude = "abort() { echo \"$*\" >&2; exit 1; }; ui_print() { :; }; "
        prelude += "set_perm() { :; }; set_perm_recursive() { :; }; . \"$MODPATH/customize.sh\""
        return subprocess.run(["bash", "-c", prelude], env=dict(self.env, MODPATH=str(path), **extra),
                              capture_output=True, text=True, timeout=20)

    def run_script(self, path, **extra):
        return subprocess.run(["bash", str(path)], env=dict(self.env, **extra),
                              capture_output=True, text=True, timeout=20)

    def installed(self, preexisting_adapter=False):
        if preexisting_adapter:
            state = self.read(); state["packages"] = [ADAPTER]; self.save(state)
        stage = self.stage()
        result = self.install(stage)
        self.assertEqual(result.returncode, 0, result.stderr)
        active = self.adb / "modules/soli_motion"
        active.parent.mkdir(exist_ok=True)
        stage.rename(active)
        return active

    def schedule_uninstall(self, active):
        calls_before = self.read()["calls"]
        result = self.run_script(active / "uninstall.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read()["calls"], calls_before, "post-fs-data must not call Android services")
        self.assertTrue(self.cleanup_script.exists())
        shutil.rmtree(active)  # KernelSU prune_modules removes the directory next.

    def change_settings(self):
        state = self.read()
        state["settings"].update(aware_enabled="1", skip_gesture="1", doze_always_on="1")
        self.save(state)

    def test_uninstall_restores_values_and_absence_then_removes_owned_adapter(self):
        active = self.installed()
        self.change_settings()
        self.schedule_uninstall(active)
        self.assertEqual(self.run_script(self.cleanup_script).returncode, 0)
        self.assertEqual(self.read()["settings"], self.initial)
        self.assertNotIn(ADAPTER, self.read()["packages"])
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.cleanup_script.exists())

    def test_upgrade_retains_first_snapshot(self):
        active = self.installed()
        self.change_settings()
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        shutil.rmtree(active); update.rename(active)
        self.schedule_uninstall(active)
        self.run_script(self.cleanup_script)
        self.assertEqual(self.read()["settings"], self.initial)

    def test_reinstall_inherits_pending_snapshot_and_cancels_old_cleanup(self):
        active = self.installed()
        self.change_settings()
        self.schedule_uninstall(active)
        update = self.stage()
        self.assertEqual(self.install(update).returncode, 0)
        self.assertFalse(self.cleanup_script.exists())
        self.assertFalse(self.pending.exists())
        self.assertEqual((update / "state/settings/aware_enabled").read_text().strip(), "0")
        self.assertIn(ADAPTER, self.read()["packages"])
        self.assertEqual(self.read()["settings"]["aware_enabled"], "1")

    def test_failed_reinstall_keeps_pending_cleanup(self):
        active = self.installed()
        self.change_settings()
        self.schedule_uninstall(active)
        update = self.stage()
        self.assertNotEqual(self.install(update, MOCK_INSTALL_FAIL="1").returncode, 0)
        self.assertTrue(self.cleanup_script.exists())
        self.assertTrue((self.pending / "state/snapshot.complete").exists())
        # An aborted staging directory must not masquerade as a successful reinstall.
        self.run_script(self.cleanup_script)
        self.assertEqual(self.read()["settings"], self.initial)
        self.assertFalse(self.pending.exists())

    def test_failed_restore_retries_without_losing_snapshot(self):
        active = self.installed()
        self.change_settings()
        self.schedule_uninstall(active)
        self.run_script(self.cleanup_script, MOCK_FAIL_KEY="aware_enabled")
        self.assertTrue(self.pending.exists())
        self.assertTrue(self.cleanup_script.exists())
        self.assertEqual(self.read()["settings"]["aware_enabled"], "1")
        self.run_script(self.cleanup_script)
        self.assertEqual(self.read()["settings"], self.initial)
        self.assertFalse(self.pending.exists())

    def test_uninstaller_keeps_preexisting_adapter(self):
        active = self.installed(preexisting_adapter=True)
        self.schedule_uninstall(active)
        self.run_script(self.cleanup_script)
        self.assertIn(ADAPTER, self.read()["packages"])

    def test_cleanup_defers_while_installer_holds_lock(self):
        active = self.installed()
        self.change_settings()
        self.schedule_uninstall(active)
        before = self.read()
        with (self.adb / "soli_motion-lifecycle.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.run_script(self.cleanup_script)
        self.assertEqual(self.read(), before)
        self.assertTrue(self.cleanup_script.exists())

    def test_incomplete_boot_keeps_work_and_does_not_contact_android_services(self):
        active = self.installed()
        self.schedule_uninstall(active)
        before = self.read()
        self.run_script(self.cleanup_script, MOCK_BOOT_READY="0")
        self.assertEqual(self.read(), before)
        self.assertTrue(self.cleanup_script.exists())


if __name__ == "__main__":
    unittest.main()
