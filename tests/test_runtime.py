import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "tools/prepare-android.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="opencode android ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.log = self.base / "calls"
        self.env = dict(os.environ, HOME=str(self.home), CALL_LOG=str(self.log),
                        PATH=f"{self.bin}:{os.environ['PATH']}")

    def fake(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
        path.chmod(0o755)

    def run_script(self, name):
        return subprocess.run(["/bin/bash", str(ROOT / "runtime" / name)],
                              env=self.env, text=True, capture_output=True, timeout=10)

    def guest_fakes(self):
        self.fake("apk", 'printf "apk\\n" >> "$CALL_LOG"')
        self.fake("curl", '''printf 'curl\n' >> "$CALL_LOG"
[ "${FAIL_DOWNLOAD:-0}" = 0 ] || exit 22
while [ "$1" != -o ]; do shift; done
printf '# mock installer\n' > "$2"''')
        self.fake("bash", '''printf 'install\n' >> "$CALL_LOG"
mkdir -p "$HOME/.opencode/bin"
printf '#!/bin/sh\nexit %s\n' "${FAIL_BINARY:-0}" > "$HOME/.opencode/bin/opencode"
chmod +x "$HOME/.opencode/bin/opencode"''')

    def test_guest_installs_once_and_handles_spaced_home(self):
        self.guest_fakes()
        first = self.run_script("guest-setup.sh")
        self.assertEqual(first.returncode, 0, first.stderr)
        calls = self.log.read_text()
        self.assertEqual(calls, "apk\ncurl\ninstall\n")
        self.assertEqual(self.run_script("guest-setup.sh").returncode, 0)
        self.assertEqual(self.log.read_text(), calls)

    def test_failed_download_never_executes_installer_or_marks_ready(self):
        self.guest_fakes()
        self.env["FAIL_DOWNLOAD"] = "1"
        result = self.run_script("guest-setup.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("install", self.log.read_text())
        self.assertFalse((self.home / ".local/state/opencode-android/ready-v1").exists())

    def test_broken_binary_does_not_mark_ready(self):
        self.guest_fakes()
        self.env["FAIL_BINARY"] = "1"
        self.assertNotEqual(self.run_script("guest-setup.sh").returncode, 0)
        self.assertFalse((self.home / ".local/state/opencode-android/ready-v1").exists())

    def test_guest_runner_preserves_arguments_and_cwd(self):
        binary = self.home / ".opencode/bin/opencode"
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\n')
        binary.chmod(0o755)
        result = subprocess.run(["/bin/bash", str(ROOT / "runtime/guest-run.sh"),
                                 "hello world", "$(do-not-execute)"],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.home / "projects"),
                                                      "hello world", "$(do-not-execute)"])

    def host_fakes(self, mode):
        self.fake("pkg", 'printf "pkg %s\\n" "$*" >> "$CALL_LOG"; exit 99')
        self.fake("proot-distro", '''printf '%s\n' "$*" >> "$CALL_LOG"
case "$1" in
  install)
    if [ "${2:-}" = --help ]; then
      printf '%s\n' "$INSTALL_MODE"
    else
      touch "$HOME/installed"
    fi ;;
  login)
    case "$*" in
      */bin/true*) test -f "$HOME/installed" ;;
      *) exit "${FAIL_GUEST:-0}" ;;
    esac ;;
  *) exit 88 ;;
esac''')
        self.env["INSTALL_MODE"] = mode

    def test_host_supports_current_and_legacy_install_commands(self):
        for mode, expected in [("--name", "install alpine:3.23 --name opencode-android-alpine"),
                               ("--override-alias", "install --override-alias opencode-android-alpine alpine")]:
            with self.subTest(mode=mode):
                (self.home / "installed").unlink(missing_ok=True)
                self.log.unlink(missing_ok=True)
                self.host_fakes(mode)
                first = self.run_script("start.sh")
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assertIn(expected, self.log.read_text())
                self.log.write_text("")
                self.assertEqual(self.run_script("start.sh").returncode, 0)
                self.assertNotIn("install", self.log.read_text())

    def test_guest_failure_stops_host_before_launch(self):
        self.host_fakes("--name")
        self.env["FAIL_GUEST"] = "12"
        result = self.run_script("start.sh")
        self.assertEqual(result.returncode, 12)
        self.assertIn("kode 12", result.stderr)
        self.assertNotIn("guest-run.sh", self.log.read_text())

    def test_duplicate_host_does_not_start_another_guest(self):
        import fcntl
        self.host_fakes("--name")
        state = self.home / ".local/state/opencode-android"
        state.mkdir(parents=True)
        with (state / "session.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script("start.sh")
            self.assertEqual(result.returncode, 0)
            self.assertIn("sesi lain", result.stdout)
            self.assertFalse(self.log.exists())


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.cpp = self.source / "app/src/main/cpp"
        self.cpp.mkdir(parents=True)
        self.archive = self.cpp / "bootstrap-aarch64.zip"
        with zipfile.ZipFile(self.archive, "w") as out:
            out.writestr("etc/profile", b"# upstream profile\n")
            out.writestr("bin/bash", b"unchanged native binary")
            out.writestr("SYMLINKS.txt", "target←link\n".encode())
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.gradle = self.source / "app/build.gradle"
        self.gradle.write_text(f'downloadBootstrap("aarch64", "{digest}", version)\n')

    def test_brand_uses_actual_upstream_application_resource(self):
        path = self.source / "app/src/main/res/values/strings.xml"
        path.parent.mkdir(parents=True)
        path.write_text('''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE resources [<!ENTITY TERMUX_APP_NAME "Termux">]>
<resources><string name="application_name">&TERMUX_APP_NAME;</string>
<string name="shared_user_label">&TERMUX_APP_NAME; user</string></resources>''')
        for _ in range(2):
            prepare.brand(self.source)
            self.assertIn('<string name="application_name">OpenCode Android</string>', path.read_text())
            self.assertIn('<string name="shared_user_label">&TERMUX_APP_NAME; user</string>', path.read_text())

    def test_inject_preserves_binary_and_refreshes_checksum(self):
        for _ in range(2):
            prepare.inject(self.source)
            with zipfile.ZipFile(self.archive) as archive:
                self.assertEqual(archive.read("bin/bash"), b"unchanged native binary")
                self.assertEqual(archive.read("etc/profile").count(prepare.MARKER), 1)
                self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                self.assertIn("libexec/opencode-android/start.sh", archive.namelist())
            digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
            self.assertIn(digest, self.gradle.read_text())

    def test_tampered_bootstrap_is_rejected_before_patch(self):
        before = self.gradle.read_text()
        with self.archive.open("ab") as out:
            out.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            prepare.inject(self.source)
        self.assertEqual(self.gradle.read_text(), before)


if __name__ == "__main__":
    unittest.main()
