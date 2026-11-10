"""Exercise script safety with fake Termux commands; no network or packages."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "termux"


class TermuxScriptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="local-desktop-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.prefix = self.root / "usr"
        self.bin = self.root / "bin"
        self.app = self.home / "local-linux-desktop"
        self.app.mkdir(parents=True)
        self.bin.mkdir()
        (self.app / "start.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        self.env = dict(os.environ, HOME=str(self.home), PREFIX=str(self.prefix),
                        PATH=f"{self.bin}:{os.environ['PATH']}")
        self.fake("pkg", 'printf "pkg %s\\n" "$*" >> "$HOME/calls"\n')
        self.fake("proot-distro", '''
printf "proot %s\\n" "$*" >> "$HOME/calls"
if [ "$1" = install ]; then
  mkdir -p "$PREFIX/var/lib/proot-distro/installed-rootfs/local-linux-desktop"
fi
''')
        self.fake("am", 'printf "am %s\\n" "$*" >> "$HOME/calls"\n')
        self.fake("termux-x11", "exit 0\n")

    def fake(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def run_script(self, name):
        return subprocess.run(["bash", str(SCRIPTS / name)], env=self.env,
                              text=True, capture_output=True, timeout=20)

    def calls(self):
        path = self.home / "calls"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_setup_is_repeatable_and_preserves_other_distros(self):
        other = self.prefix / "var/lib/proot-distro/installed-rootfs/existing"
        other.mkdir(parents=True)
        (other / "my-data").write_text("keep", encoding="utf-8")
        for _ in range(2):
            result = self.run_script("setup.sh")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls().count("proot install"), 1)
        self.assertEqual((other / "my-data").read_text(encoding="utf-8"), "keep")
        self.assertTrue((self.app / ".setup-complete").exists())
        self.assertFalse((self.app / ".setup-lock").exists())

    def test_setup_refuses_an_unowned_distro_without_installing_anything(self):
        existing = self.prefix / "var/lib/proot-distro/installed-rootfs/local-linux-desktop"
        existing.mkdir(parents=True)
        (existing / "my-data").write_text("keep", encoding="utf-8")
        result = self.run_script("setup.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.calls(), "")
        self.assertEqual((existing / "my-data").read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.app / ".setup-lock").exists())

    def test_setup_refuses_unowned_distro_in_new_layout(self):
        existing = self.prefix / "var/lib/proot-distro/containers/local-linux-desktop/rootfs"
        existing.mkdir(parents=True)
        (existing / "my-data").write_text("keep", encoding="utf-8")
        result = self.run_script("setup.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.calls(), "")
        self.assertEqual((existing / "my-data").read_text(encoding="utf-8"), "keep")

    def test_start_refuses_incomplete_setup(self):
        result = self.run_script("start.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Setup is incomplete", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_successful_exit_without_display_is_not_reported_as_ready(self):
        (self.app / ".managed-distro").write_text("local-linux-desktop\n", encoding="utf-8")
        (self.app / ".setup-complete").write_text("ready\n", encoding="utf-8")
        result = self.run_script("start.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Termux:X11 stopped", result.stderr)
        self.assertIn("am start", self.calls())
        self.assertNotIn("proot login", self.calls())
        self.assertFalse((self.app / ".session-lock").exists())


if __name__ == "__main__":
    unittest.main()
