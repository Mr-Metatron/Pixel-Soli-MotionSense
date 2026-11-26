"""Exercise the real signing preflight before any download or Android compilation."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseSigningTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/build.sh", self.root / "scripts/build.sh")
        shutil.copytree(ROOT / "signing", self.root / "signing")
        binaries = self.root / "bin"
        binaries.mkdir()
        # Preflight only checks javac's presence. curl is a sentinel: it must
        # never be reached when release signing is missing or incorrect.
        for name, body in (("javac", "exit 0"), ("curl", "echo DOWNLOAD_REACHED; exit 91")):
            command = binaries / name
            command.write_text("#!/bin/sh\n" + body + "\n")
            command.chmod(0o755)
        build_tools = self.root / "sdk/build-tools/35.0.0"
        build_tools.mkdir(parents=True)
        for name in ("apksigner", "d8"):
            command = build_tools / name
            command.write_text("#!/bin/sh\nexit 92\n")
            command.chmod(0o755)
        self.env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                        ANDROID_HOME=str(self.root / "sdk"), SOLI_SIGNING_KEY="",
                        SOLI_REQUIRE_RELEASE_SIGNING="true")

    def run_build(self, **environment):
        return subprocess.run(["bash", str(self.root / "scripts/build.sh")],
                              env=dict(self.env, **environment), capture_output=True,
                              text=True, timeout=20)

    def test_release_rejects_missing_secret_before_download(self):
        result = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires SOLI_SIGNING_KEY", result.stderr)
        self.assertNotIn("DOWNLOAD_REACHED", result.stdout)
        self.assertFalse((self.root / ".build/signing/project.p12").exists())

    def test_release_rejects_a_valid_but_wrong_key_before_download(self):
        result = self.run_build(SOLI_SIGNING_KEY=(ROOT / "signing/default.p12.base64").read_text())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("certificate mismatch", result.stderr)
        self.assertNotIn("DOWNLOAD_REACHED", result.stdout)

    def test_release_rejects_malformed_secret(self):
        result = self.run_build(SOLI_SIGNING_KEY="not-a-base64-keystore")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DOWNLOAD_REACHED", result.stdout)

    def test_local_development_can_still_use_public_key(self):
        result = self.run_build(SOLI_REQUIRE_RELEASE_SIGNING="false")
        self.assertEqual(result.returncode, 91, result.stderr)
        self.assertIn("public development key", result.stderr)
        self.assertIn("DOWNLOAD_REACHED", result.stdout)


if __name__ == "__main__":
    unittest.main()
