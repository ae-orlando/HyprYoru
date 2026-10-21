#!/usr/bin/env python3
"""Installer regression tests: temporary homes and mocks, never a real install/VM."""

import os
import json
import fcntl
import hashlib
import io
from pathlib import Path
import pty
import re
import select
import shutil
import stat
import struct
import subprocess
import tarfile
import tempfile
import termios
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path("/tmp/opencode")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="hypryoru-tests-",
            dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None,
        )
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.home),
            CASE_ROOT=str(self.root),
            INSTALLER=str(REPO / "install.sh"),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            XDG_STATE_HOME=str(self.home / ".local/state"),
            XDG_CACHE_HOME=str(self.home / ".cache"),
            XDG_DATA_HOME=str(self.home / ".local/share"),
            XDG_DATA_DIRS=str(self.root / "data"),
            XDG_RUNTIME_DIR=str(self.root / "runtime"),
            TMPDIR=str(self.root),
            TERM="dumb",
            NO_COLOR="1",
            NO_EMOJI="1",
            PATH=f"{self.bin}:/usr/bin:/bin",
        )
        # Do not let shell syntax checks source the caller's personal zsh setup.
        self.env.pop("ZDOTDIR", None)
        self.env.pop("ZSH_CUSTOM", None)
        self.env.pop("BASH_ENV", None)
        self.env.pop("ENV", None)

    def bash(self, body, *, input=None):
        return subprocess.run(
            ["bash", "-c", 'source "$INSTALLER"\nsetup_ui\n' + body],
            env=self.env,
            cwd=self.root,
            input=input,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def cli(self, *args):
        return subprocess.run(
            ["bash", self.env["INSTALLER"], *args],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def terminal(self, body='main', replies=(), *, rows=24, columns=100, timeout=15):
        """Run only sandboxed/mocked actions with real terminal file descriptors."""
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        process = subprocess.Popen(
            ["bash", "-c", 'source "$INSTALLER"\n' + body],
            stdin=slave, stdout=slave, stderr=slave, env=self.env, cwd=self.root,
        )
        os.close(slave)
        output = b""
        pending = b""
        deadline = time.monotonic() + timeout

        def receive():
            nonlocal output, pending
            self.assertLess(time.monotonic(), deadline, output.decode(errors="replace"))
            if not select.select([master], [], [], 0.2)[0]:
                return True
            try:
                data = os.read(master, 65536)
            except OSError:
                return False
            output += data
            pending += data
            return bool(data)

        try:
            for prompt, answer in replies:
                while prompt not in pending:
                    self.assertTrue(receive(), output.decode(errors="replace"))
                pending = pending.split(prompt, 1)[1]
                os.write(master, answer)
            while receive():
                pass
            code = process.wait(timeout=2)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        return subprocess.CompletedProcess(process.args, code, output.decode(errors="replace"), "")

    def mock_gum(self, replies):
        """Mock only widget IO, with the same flags/exit statuses as real Gum."""
        (self.root / "gum-replies.json").write_text(json.dumps(replies))
        target = self.bin / "gum"
        target.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
root = Path(os.environ["CASE_ROOT"])
args = sys.argv[1:]
if args == ["choose", "--help"]:
    (root / "gum-help-called").touch()
    print("--no-limit --selected --output-delimiter --header --height")
    sys.exit(0)
record = {"args": args, "no_color": os.environ.get("NO_COLOR")}
if args[0] == "pager":
    record["body"] = sys.stdin.read()
with (root / "gum-calls.jsonl").open("a") as log:
    log.write(json.dumps(record) + "\\n")
if args[0] == "pager":
    sys.exit(0)
queue_path = root / "gum-replies.json"
queue = json.loads(queue_path.read_text())
if not queue:
    print("unexpected extra Gum prompt", file=sys.stderr)
    sys.exit(2)
reply = queue.pop(0)
queue_path.write_text(json.dumps(queue))
if isinstance(reply, dict):
    sys.exit(reply["code"])
if isinstance(reply, list):
    print("\\n".join(reply))
else:
    print(reply)
''')
        target.chmod(0o755)
        self.env["TERM"] = "xterm-256color"

    def gum_calls(self):
        path = self.root / "gum-calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def mock_gum_runtime(self, replies=("Exit",), *, bad_binary=False):
        """Pinned local fixture, never a real network request or system install."""
        if os.geteuid() == 0:
            self.skipTest("Gum runtime preparation requires a normal user, just as in production")
        self.mock_gum(list(replies))
        binary = (self.bin / "gum").read_bytes()
        (self.bin / "gum").unlink()
        payload = binary
        if bad_binary:
            payload = b'#!/bin/sh\ntouch "$HOME/unverified-executed"\n'
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as tar:
            member = tarfile.TarInfo("fixture/gum")
            member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))
        contents = archive.getvalue()
        (self.root / "gum-runtime.tar.gz").write_bytes(contents)
        self.stub("curl", '''
printf 'download\\n' >>"$CASE_ROOT/download-calls"
target=''
while (( $# > 0 )); do
  if [[ "$1" == --output ]]; then target="$2"; shift 2; else shift; fi
done
[[ -n "$target" && "$target" == "$HOME/.cache/hypryoru/"* ]] || exit 98
cp -- "$CASE_ROOT/gum-runtime.tar.gz" "$target"
''')
        self.stub("wget", 'printf "unexpected network fallback\\n" >&2; exit 98')
        prefix = f'''
find_system_gum() {{ return 1; }}
gum_runtime_release() {{
  GUM_VERSION=fixture
  GUM_ARCH=fixture
  GUM_ARCHIVE_SHA256={hashlib.sha256(contents).hexdigest()}
  GUM_BINARY_SHA256={hashlib.sha256(binary).hexdigest()}
  GUM_ARCHIVE_MEMBER=fixture/gum
  GUM_DOWNLOAD_URL=https://example.invalid/gum-fixture.tar.gz
}}
'''
        cache = self.home / ".cache/hypryoru/tools/gum/fixture/fixture/gum"
        return prefix, cache, binary

    def home_snapshot(self):
        prefix = str(self.home.relative_to(self.root)) + "/"
        return {path: value for path, value in self.snapshot().items() if path.startswith(prefix)}

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def stub(self, name, body):
        target = self.bin / name
        target.write_text("#!/usr/bin/env bash\n" + body + "\n")
        target.chmod(0o755)

    def forbid_mutations(self):
        for name in (
            "sudo", "git", "makepkg", "yay", "paru", "matugen", "chsh", "systemctl",
            "fc-cache", "xdg-user-dirs-update", "gsettings", "xdg-mime", "ln", "mv",
            "cp", "chmod", "mkdir", "flock", "rm", "curl", "wget",
        ):
            self.stub(name, 'printf "%s\\n" "$0 $*" >>"$CASE_ROOT/unexpected"; exit 97')
        self.stub("systemctl", '''
case "$*" in
  *is-enabled*) printf 'disabled\\n'; exit 1 ;;
  *is-active*) exit 3 ;;
esac
printf '%s\\n' "$0 $*" >>"$CASE_ROOT/unexpected"; exit 97
''')
        self.stub("pacman", '''
case "$1" in -Q|-Qq) exit 0 ;; esac
printf '%s\\n' "$0 $*" >>"$CASE_ROOT/unexpected"; exit 97
''')
        self.stub("zsh", '''
[[ "$*" == *'-f -n'* ]] && exit 0
printf '%s\\n' "$0 $*" >>"$CASE_ROOT/unexpected"; exit 97
''')

    def snapshot(self):
        entries = {}
        for path in self.root.rglob("*"):
            info = path.lstat()
            value = None
            if path.is_symlink():
                value = os.readlink(path)
            elif stat.S_ISREG(info.st_mode):
                value = path.read_bytes()
            entries[str(path.relative_to(self.root))] = (
                info.st_mode, info.st_mtime_ns, value,
            )
        return entries

    def test_source_and_help_do_not_write(self):
        before = self.snapshot()
        self.success(self.bash(":"))
        result = self.cli("--help")
        self.success(result)
        self.assertIn("--check", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_manifests_and_profile_boundaries(self):
        result = self.bash("""
load_packages
selected_packages
[[ "$PROFILE" == core && ${#SEL_AUR[@]} -eq ${#AUR_CORE[@]} ]]
[[ " ${SEL_OFFICIAL[*]} " != *' fnm '* ]]
core_count=${#SEL_OFFICIAL[@]}
PROFILE=full
selected_packages
(( ${#SEL_OFFICIAL[@]} > core_count ))
for excluded in linux grub vulkan-intel tlp gdm; do
  [[ " ${SEL_OFFICIAL[*]} " != *" $excluded "* ]]
done
[[ " ${SEL_AUR[*]} " != *' yay '* && " ${SEL_AUR[*]} " != *' paru '* ]]
NO_AUR=1
WITH_GDM=1
WITH_WWAN=1
selected_packages
[[ ${#SEL_AUR[@]} -eq 0 && " ${SEL_OFFICIAL[*]} " == *' gdm '* ]]
[[ " ${SEL_OFFICIAL[*]} " == *' modemmanager '* ]]
""")
        self.success(result)

    def test_manifest_comments_crlf_and_no_final_newline(self):
        manifest = self.root / "packages.txt"
        manifest.write_bytes(b" # comment\r\n\r\n  kitty # terminal\r\nzsh")
        self.success(self.bash('read_manifest items "$CASE_ROOT/packages.txt"\n[[ ${items[*]} == "kitty zsh" ]]'))

    def test_invalid_duplicate_and_empty_manifests_are_rejected(self):
        for content in ("kitty\nkitty\n", "--noconfirm\n", "kitty; touch marker\n", "# empty\n"):
            with self.subTest(content=content):
                (self.root / "packages.txt").write_text(content)
                result = self.bash('read_manifest items "$CASE_ROOT/packages.txt"')
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "marker").exists())

    def test_conflicting_options_are_rejected_without_writes(self):
        for args in (
            ("--quiet", "--verbose"), ("--check", "--dry-run"),
            ("--only-dotfiles", "--with-gdm"), ("--link-only", "--change-shell"),
            ("--link-only", "--set-defaults"), ("--profile", "unknown"),
            ("--log-file=",), ("--profile",), ("--quiet",),
            ("--ui", "unknown"), ("--ui",), ("--no-shell", "--change-shell"),
        ):
            with self.subTest(args=args):
                before = self.snapshot()
                self.assertEqual(self.cli(*args).returncode, 2)
                self.assertEqual(before, self.snapshot())

    def test_noninteractive_install_requires_yes(self):
        before = self.snapshot()
        result = self.cli("--link-only")
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --yes", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_terminal_wizard_validates_input_and_cancels_without_writes(self):
        if os.geteuid() == 0 or not Path("/etc/arch-release").exists():
            self.skipTest("Interactive apply preflight requires a normal Arch user")
        self.forbid_mutations()
        before = self.snapshot()
        master, slave = pty.openpty()
        process = subprocess.Popen(
            ["bash", "-c", 'source "$INSTALLER"; DISPLAY_MANAGER_LINK="$CASE_ROOT/no-manager"; main'],
            stdin=slave, stdout=slave, stderr=slave, env=self.env, cwd=self.root,
        )
        os.close(slave)
        output = b""
        pending = b""
        deadline = time.monotonic() + 10

        def receive():
            nonlocal output, pending
            self.assertLess(time.monotonic(), deadline, output.decode(errors="replace"))
            if not select.select([master], [], [], 0.2)[0]:
                return True
            try:
                data = os.read(master, 65536)
            except OSError:
                return False
            output += data
            pending += data
            return bool(data)

        try:
            for question, answer in (
                (b"Choose [1], or q to cancel: ", b"invalid\n"),
                (b"Choose [1], or q to cancel: ", b"1\n"),
                (b"Choose [1], or q to cancel: ", b"1\n"),
            ):
                while question not in pending:
                    self.assertTrue(receive(), output.decode(errors="replace"))
                pending = pending.split(question, 1)[1]
                os.write(master, answer)
            while receive():
                pass
            self.assertEqual(process.wait(timeout=2), 0, output.decode(errors="replace"))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        self.assertIn(b"Choose a number from 1 to 5", output)
        self.assertIn(b"Cancelled. No files or settings changed.", output)
        self.assertNotIn(b"\x1b", output)
        self.assertEqual(before, self.snapshot())

    def test_dry_run_has_zero_writes_and_runs_no_mutating_commands(self):
        self.forbid_mutations()
        logs = self.home / ".local/state/dotfiles-install/logs"
        logs.mkdir(parents=True)
        for index in range(15):
            (logs / f"install-old-{index}.log").write_text("keep me")
        for args in (
            ("--dry-run",), ("--dry-run", "--no-aur", "--profile", "full"),
            ("--dry-run", "--only-dotfiles", "--set-defaults"),
            ("--dry-run", "--link-only", "--log-file", str(self.root / "not-created.log")),
            ("--dry-run", "--no-shell", "--no-aur"),
            ("--dry-run", "--no-shell", "--link-only"),
        ):
            with self.subTest(args=args):
                before = self.snapshot()
                result = self.cli(*args)
                self.success(result)
                self.assertIn("nothing changed", result.stdout)
                self.assertEqual(before, self.snapshot())
                self.assertNotIn("\x1b", result.stdout + result.stderr)

    def test_read_only_check_reports_failures_without_writes(self):
        self.forbid_mutations()
        before = self.snapshot()
        result = self.cli("--check", "--link-only")
        self.assertEqual(result.returncode, 1)
        self.assertIn("incorrect config link", result.stderr)
        self.assertIn("Needs attention", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_full_diagnostics_are_read_only_even_with_an_explicit_log(self):
        self.forbid_mutations()
        log = self.root / "existing.log"
        log.write_text("do not replace")
        before = self.snapshot()
        result = self.cli("--check", "--no-aur", "--log-file", str(log))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing/empty generated theme", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_runner_preserves_arguments_and_does_not_eval(self):
        result = self.bash("""
run printf '%s\n' 'a b' '$(touch "$CASE_ROOT/should-not-exist")' 'semi;colon'
""")
        self.success(result)
        self.assertEqual(result.stdout, 'a b\n$(touch "$CASE_ROOT/should-not-exist")\nsemi;colon\n')
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_runner_preserves_stdin_stderr_and_exit_status_with_logging(self):
        result = self.bash("""
LOG_FILE="$CASE_ROOT/command.log"
LOG_ENABLED=1
run bash -c 'IFS= read -r reply; printf "reply=%s\\n" "$reply"; printf "visible error\\n" >&2'
if run bash -c 'exit 17'; then exit 99; else [[ $? -eq 17 ]]; fi
warn 'warning is still visible'
""", input="hello world\n")
        self.success(result)
        self.assertIn("reply=hello world", result.stdout)
        self.assertIn("visible error", result.stdout)
        self.assertIn("warning is still visible", result.stderr)
        self.assertIn("[exit] 17", (self.root / "command.log").read_text())

    def test_quiet_hides_status_but_keeps_warnings_and_errors(self):
        result = self.bash("""
QUIET=1
LOG_FILE="$CASE_ROOT/quiet.log"
LOG_ENABLED=1
banner
step 'Hidden stage'
ok 'Hidden success'
run printf 'Hidden command output'
warn 'Visible warning'
fail 'Visible error'
""")
        self.success(result)
        self.assertEqual(result.stdout, "")
        self.assertIn("Visible warning", result.stderr)
        self.assertIn("Visible error", result.stderr)

    def test_no_aur_never_bootstraps_a_helper(self):
        self.success(self.bash("""
NO_AUR=1
PACMAN_CORE=(kitty)
build_plan
pacman() { [[ "$1" == -Qq ]] && printf '%s\n' kitty; }
ensure_aur_helper() { printf 'unexpected helper\n' >&2; return 99; }
phase_packages
[[ "$FAIL_COUNT" -eq 0 ]]
"""))

    def test_helper_bootstrap_itself_honors_no_aur(self):
        self.success(self.bash("""
NO_AUR=1
find_aur_helper() { return 99; }
ensure_aur_helper
[[ -z "$AUR_HELPER" && ${#TEMP_DIRS[@]} -eq 0 ]]
"""))

    def test_successful_retry_does_not_leave_a_failure_count(self):
        self.success(self.bash("""
ASSUME_YES=1
sudo() { "$@"; }
pacman() {
  [[ "$1" != -Qq ]] || return 0
  [[ "$*" != *'alpha beta'* ]]
}
install_package_set Official pacman alpha beta
[[ "$FAIL_COUNT" -eq 0 && ${#FAILED_PACKAGES[@]} -eq 0 ]]
"""))

    def test_unresolved_required_package_stops_before_links(self):
        result = self.bash("""
ASSUME_YES=1
NO_AUR=1
PACMAN_CORE=(alpha)
build_plan
sudo() { "$@"; }
pacman() { [[ "$1" == -Qq ]]; }
phase_packages
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no existing configs have been replaced", result.stderr)
        self.assertFalse((self.home / ".config").exists())

    def fixture_config(self):
        source = self.root / "repo/demo"
        source.mkdir(parents=True)
        (source / "new.conf").write_text("new config")
        target = self.home / ".config/demo"
        target.parent.mkdir(parents=True)
        return source, target

    def test_directory_backup_and_repeated_linking(self):
        source, target = self.fixture_config()
        target.mkdir()
        (target / "custom.conf").write_text("precious user config")
        result = self.bash("""
DOTFILES_ROOT="$CASE_ROOT/repo"
link_one .config/demo demo
link_one .config/demo demo
printf '%s\n' "$BACKUP_DIR"
""")
        self.success(result)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), source)
        backup = Path(result.stdout.strip().splitlines()[-1])
        self.assertEqual((backup / "home/.config/demo/custom.conf").read_text(), "precious user config")
        self.assertEqual((backup / "manifest.tsv").read_text().count("moved\t"), 1)

    def test_wrong_and_broken_symlinks_are_preserved(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                if (self.root / "repo").exists():
                    shutil.rmtree(self.root / "repo")
                    shutil.rmtree(self.home / ".config")
                _, target = self.fixture_config()
                previous = self.root / ("missing" if broken else "previous")
                if not broken:
                    previous.mkdir()
                target.symlink_to(previous)
                result = self.bash('DOTFILES_ROOT="$CASE_ROOT/repo"\nlink_one .config/demo demo\nprintf "%s\\n" "$BACKUP_DIR"')
                self.success(result)
                backup = Path(result.stdout.strip().splitlines()[-1]) / "home/.config/demo"
                self.assertTrue(backup.is_symlink())
                self.assertEqual(os.readlink(backup), str(previous))

    def test_correct_relative_symlink_is_not_replaced(self):
        source, target = self.fixture_config()
        relative = os.path.relpath(source, target.parent)
        target.symlink_to(relative)
        self.success(self.bash('DOTFILES_ROOT="$CASE_ROOT/repo"\nlink_one .config/demo demo\n[[ "$BACKUP_READY" -eq 0 ]]'))
        self.assertEqual(os.readlink(target), relative)

    def test_failed_backup_leaves_original_untouched(self):
        _, target = self.fixture_config()
        target.mkdir()
        (target / "precious").write_text("safe")
        result = self.bash("""
DOTFILES_ROOT="$CASE_ROOT/repo"
mv() { return 1; }
if link_one .config/demo demo; then exit 99; fi
[[ -d "$HOME/.config/demo" && ! -L "$HOME/.config/demo" ]]
""")
        self.success(result)
        self.assertEqual((target / "precious").read_text(), "safe")

    def test_failed_link_restores_moved_original(self):
        _, target = self.fixture_config()
        target.mkdir()
        (target / "precious").write_text("safe")
        result = self.bash("""
DOTFILES_ROOT="$CASE_ROOT/repo"
ln() { return 1; }
if link_one .config/demo demo; then exit 99; fi
[[ -d "$HOME/.config/demo" && ! -L "$HOME/.config/demo" ]]
""")
        self.success(result)
        self.assertEqual((target / "precious").read_text(), "safe")

    def test_file_backup_failure_prevents_overwrite(self):
        target = self.home / ".zshenv"
        target.write_text("export CUSTOM=precious\n")
        result = self.bash("""
cp() { return 1; }
if ensure_zshenv; then exit 99; fi
cleanup_exit
""")
        self.success(result)
        self.assertEqual(target.read_text(), "export CUSTOM=precious\n")

    def test_existing_backup_directory_is_never_reused(self):
        backup = self.root / "existing-backup"
        backup.mkdir()
        (backup / "manifest.tsv").write_text("precious old manifest")
        result = self.bash('BACKUP_DIR="$CASE_ROOT/existing-backup"\nprepare_backup')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((backup / "manifest.tsv").read_text(), "precious old manifest")

    def test_zshenv_symlink_is_backed_up_without_editing_its_original(self):
        previous = self.root / "external-zshenv"
        previous.write_text("export PERSONAL=kept\n")
        (self.home / ".zshenv").symlink_to(previous)
        result = self.bash('ensure_zshenv\nprintf "%s\\n" "$BACKUP_DIR"')
        self.success(result)
        self.assertFalse((self.home / ".zshenv").is_symlink())
        self.assertEqual(previous.read_text(), "export PERSONAL=kept\n")
        backup = Path(result.stdout.strip().splitlines()[-1]) / "edited/.zshenv"
        self.assertTrue(backup.is_symlink())
        self.assertEqual(backup.resolve(), previous)

    def test_zshenv_is_preserved_and_idempotent(self):
        target = self.home / ".zshenv"
        original = '# ZDOTDIR is personal\nexport CUSTOM="a b"\nexport ZDOTDIR="/old/path"\n'
        target.write_text(original)
        result = self.bash("ensure_zshenv\nensure_zshenv\nprintf '%s\\n' \"$BACKUP_DIR\"")
        self.success(result)
        content = target.read_text()
        self.assertTrue(content.startswith(original))
        self.assertEqual(content.count("# >>> HyprYoru >>>"), 1)
        backup = Path(result.stdout.strip().splitlines()[-1]) / "edited/.zshenv"
        self.assertEqual(backup.read_text(), original)

    def test_unbalanced_zshenv_marker_does_not_discard_user_content(self):
        target = self.home / ".zshenv"
        original = '# >>> HyprYoru >>>\nexport PERSONAL="do not lose this"\n'
        target.write_text(original)
        result = self.bash('if ensure_zshenv; then exit 99; fi\ncleanup_exit')
        self.success(result)
        self.assertEqual(target.read_text(), original)

    def test_existing_bookmarks_are_never_rewritten(self):
        target = self.home / ".config/gtk-3.0/bookmarks"
        target.parent.mkdir(parents=True)
        target.write_text("file:///some/custom/location Custom\n")
        before = self.snapshot()
        self.success(self.bash("seed_bookmarks"))
        self.assertEqual(before, self.snapshot())

    def test_bookmark_uri_encoding(self):
        result = self.bash("path_uri '/home/a b/Pictures/#night%雪'")
        self.success(result)
        self.assertEqual(result.stdout, "file:///home/a%20b/Pictures/%23night%25%E9%9B%AA")

    def test_display_manager_conflict_is_rejected(self):
        unit = self.root / "sddm.service"
        unit.write_text("[Unit]\n")
        link = self.root / "display-manager.service"
        link.symlink_to(unit)
        result = self.bash('WITH_GDM=1\nDISPLAY_MANAGER_LINK="$CASE_ROOT/display-manager.service"\ncheck_display_manager')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("will not be replaced", result.stderr)
        self.assertEqual(link.resolve(), unit)

    def test_desktop_services_do_not_override_other_network_power_or_login_choices(self):
        result = self.bash('''
USER_SERVICES=()
build_plan
systemctl() {
  case "$*" in
    'is-enabled systemd-networkd.service'|'is-enabled tlp.service') printf 'enabled\\n' ;;
    'is-enabled bluetooth.service') printf 'masked\\n'; return 1 ;;
    *) printf 'unexpected service call: %s\\n' "$*" >&2; return 97 ;;
  esac
}
sudo() { printf 'unexpected sudo call\\n' >&2; return 98; }
phase_services
[[ "$FAIL_COUNT" -eq 0 && "$WARN_COUNT" -eq 3 ]]
''')
        self.success(result)
        self.assertNotIn("unexpected", result.stdout + result.stderr)

    def test_mime_defaults_only_use_installed_apps_and_preserve_original(self):
        applications = self.home / ".local/share/applications"
        applications.mkdir(parents=True)
        (applications / "chromium.desktop").write_text("[Desktop Entry]\n")
        target = self.home / ".config/mimeapps.list"
        target.parent.mkdir(parents=True)
        target.write_text("[Default Applications]\napplication/pdf=personal.desktop\n")
        result = self.bash('''
xdg-mime() { printf '%s\\n' "$*" >>"$CASE_ROOT/mime-commands"; }
set_mime_group not-installed.desktop application/pdf
set_mime_group chromium.desktop text/html x-scheme-handler/https
printf '%s\\n' "$BACKUP_DIR"
''')
        self.success(result)
        calls = (self.root / "mime-commands").read_text()
        self.assertNotIn("not-installed", calls)
        self.assertEqual(calls.count("default chromium.desktop"), 2)
        backup = Path(result.stdout.strip().splitlines()[-1]) / "edited/.config/mimeapps.list"
        self.assertEqual(backup.read_bytes(), target.read_bytes())

    def fixture_repository(self):
        """Small independent repo: no test writes through links into the real repo."""
        fixture = self.root / "fixture-repo"
        fixture.mkdir()
        for name in ("install.sh", "lib/install-ui.sh", "lib/install-plan.sh", "lib/install-wizard.sh", "lib/gum-runtime.sh", "matugen/config.toml"):
            target = fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, target)
        shutil.copytree(REPO / "packages", fixture / "packages")
        mappings = self.bash('printf "%s\\n" "${LINK_MAP[@]}"')
        self.success(mappings)
        for mapping in mappings.stdout.splitlines():
            (fixture / mapping.split(":", 1)[1]).mkdir(parents=True, exist_ok=True)
        for name, content in {
            "hyprland/hyprland.lua": "-- fixture config\n",
            "waybar/config.jsonc": "{}\n",
            "zsh/.zshrc": "# fixture shell\n",
            "waypaper/config.ini.example": "[Settings]\nbackend=none\n",
            "qt6ct/qt6ct.conf": "[Appearance]\ncolor_scheme_path=/home/previous/palette.conf\n",
            "hyprland/wallpapers/mystical-night-in-town.jpg": "fixture wallpaper\n",
        }.items():
            target = fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        config = (fixture / "matugen/config.toml").read_text()
        for relative in re.findall(r'^input_path = "~/.config/(.*?)"', config, re.M):
            target = fixture / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# fixture template\n")
        self.env["INSTALLER"] = str(fixture / "install.sh")
        return fixture

    def mock_installation(self):
        if os.geteuid() == 0 or not Path("/etc/arch-release").exists():
            self.skipTest("Installation preflight requires a normal Arch user")
        if not Path("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1").is_file():
            self.skipTest("Fixture integration needs the host's read-only polkit path check")
        fixture = self.fixture_repository()
        self.stub("sudo", '''
case "$1" in
  -v|-n) exit 0 ;;
  pacman|systemctl) "$@" ;;
  *) printf 'unexpected sudo: %s\\n' "$*" >&2; exit 97 ;;
esac
''')
        self.stub("pacman", '''
case "$1" in
  -Q|-Qq) exit 0 ;;
  -S|-Syu) printf '%s\\n' "$*" >>"$CASE_ROOT/package-commands" ;;
  *) exit 97 ;;
esac
''')
        self.stub("systemctl", '''
case "$*" in
  *is-enabled*) printf 'disabled\\n'; exit 1 ;;
  *is-active*) exit 3 ;;
  *enable*) printf '%s\\n' "$*" >>"$CASE_ROOT/service-commands" ;;
  *) exit 97 ;;
esac
''')
        self.stub("git", '''
[[ "$1" == clone ]] || exit 97
target="${!#}"
[[ "$target" == "$HOME/"* ]] || exit 98
mkdir -p -- "$target"
case "$*" in
  *ohmyzsh*) printf '# fixture\\n' >"$target/oh-my-zsh.sh" ;;
  *powerlevel10k*) printf '# fixture\\n' >"$target/powerlevel10k.zsh-theme" ;;
  *) exit 97 ;;
esac
''')
        self.stub("matugen", """
python3 - <<'PY'
import os
from pathlib import Path
import re
home = Path(os.environ['HOME'])
root = Path(os.environ['CASE_ROOT'])
config = (home / '.config/matugen/config.toml').read_text()
for name in re.findall(r'^output_path = "(.*?)"', config, re.M):
    path = Path(name).expanduser()
    assert path.resolve().is_relative_to(root), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# fixture palette\\n')
PY
""")
        self.stub("xdg-user-dirs-update", 'printf \'XDG_PICTURES_DIR="$HOME/Pictures"\\n\' >"$HOME/.config/user-dirs.dirs"')
        self.stub("xdg-user-dir", 'printf "%s/%s\\n" "$HOME" "$1"')
        for name in ("fc-cache", "zsh", "makepkg", "chsh", "gsettings", "xdg-mime"):
            self.stub(name, 'case "${0##*/}" in fc-cache|zsh) exit 0 ;; *) exit 97 ;; esac')
        for name in (
            "Hyprland", "kitty", "nautilus", "chromium", "imv", "rofi", "hyprctl",
            "hyprlock", "hypridle", "hyprsunset", "waybar", "swaync", "swaync-client",
            "nm-applet", "awww", "awww-daemon", "grim", "slurp", "wl-copy", "playerctl",
            "wpctl", "brightnessctl", "magick", "pavucontrol", "bluetoothctl", "nmcli",
            "checkupdates", "jq", "notify-send", "xdg-open",
        ):
            self.stub(name, 'printf "verification must not execute desktop apps\\n" >&2; exit 97')
        return fixture

    def test_mocked_install_and_rerun_in_an_independent_repository(self):
        fixture = self.mock_installation()
        for _ in range(2):
            result = self.cli("--no-aur", "--yes")
            self.success(result)
            self.assertIn("0 failures", result.stdout)
        qt = fixture / "qt6ct/qt6ct.conf"
        self.assertIn(f"color_scheme_path={self.home}/.config/qt6ct/colors/matugen.conf", qt.read_text())
        self.assertEqual((self.home / ".zshenv").read_text().count("# >>> HyprYoru >>>"), 1)
        self.assertEqual(len(list((self.home / ".local/state/dotfiles-install/logs").glob("*.log"))), 2)
        services = (self.root / "service-commands").read_text()
        for forbidden in ("gdm", "wwan", "ufw", "postgresql", "disable", "restart"):
            self.assertNotIn(forbidden, services)

    def test_no_shell_component_is_real_and_survives_repeated_palette_runs(self):
        fixture = self.mock_installation()
        zsh = self.home / ".config/zsh"
        zsh.mkdir(parents=True)
        (zsh / ".zshrc").write_text("# precious personal shell\n")
        (zsh / "generated").mkdir()
        (zsh / "generated/colors.sh").write_text("# personal palette, not installer-owned\n")
        zshenv = self.home / ".zshenv"
        zshenv.write_text('export ZDOTDIR="$HOME/.personal-zsh"\n')
        canonical = (fixture / "matugen/config.toml").read_bytes()
        for _ in range(2):
            self.success(self.cli("--no-shell", "--no-aur", "--yes"))
        self.assertFalse(zsh.is_symlink())
        self.assertEqual((zsh / ".zshrc").read_text(), "# precious personal shell\n")
        self.assertEqual((zsh / "generated/colors.sh").read_text(), "# personal palette, not installer-owned\n")
        self.assertEqual(zshenv.read_text(), 'export ZDOTDIR="$HOME/.personal-zsh"\n')
        self.assertFalse((self.home / ".oh-my-zsh").exists())
        runtime = self.home / ".config/matugen/config.toml"
        self.assertNotIn("[templates.shell]", runtime.read_text())
        self.assertIn("[templates.hypr]", runtime.read_text())
        self.assertEqual((fixture / "matugen/config.toml").read_bytes(), canonical)
        runtime.unlink()
        before_check = self.home_snapshot()
        broken = self.cli("--check", "--no-shell", "--no-aur")
        self.assertEqual(broken.returncode, 1)
        self.assertIn("Private Matugen config is missing", broken.stderr)
        self.assertEqual(before_check, self.home_snapshot())
        self.success(self.cli("--no-shell", "--no-aur", "--yes"))
        package_calls = (self.root / "package-commands").read_text()
        for excluded in ("zsh", "zsh-autosuggestions", "eza", "figlet"):
            self.assertNotIn(excluded, package_calls.split())
        # The later wallpaper pipeline reads the same private config by default.
        self.success(self.bash('matugen image fixture'))
        self.assertEqual((zsh / "generated/colors.sh").read_text(), "# personal palette, not installer-owned\n")
        # Opting in again restores the normal directory map, with originals saved.
        self.success(self.cli("--no-aur", "--yes"))
        self.assertTrue(zsh.is_symlink())
        self.assertTrue((self.home / ".config/matugen").is_symlink())
        generated = (zsh / "generated/colors.sh").read_bytes()
        self.success(self.cli("--no-shell", "--no-aur", "--yes"))
        self.assertEqual((zsh / "generated/colors.sh").read_bytes(), generated)

    def test_plan_drives_execution_and_restores_reviewed_choices(self):
        result = self.bash('''
load_packages
WITH_SHELL=0
NO_AUR=1
ONLY_DOTFILES=1
build_plan
[[ " ${PLAN_COMPONENTS[*]} " != *' shell '* ]]
[[ " ${PLAN_OFFICIAL[*]} " != *' zsh '* ]]
[[ " ${PLAN_LINKS[*]} " != *'.config/zsh:zsh'* ]]
[[ " ${PLAN_COMMANDS[*]} " != *' zsh '* ]]
reviewed=("${PLAN_PHASES[@]}")
WITH_SHELL=1
PROFILE=full
calls=()
init_runtime() { :; }
phase_preflight() { calls+=(phase_preflight); [[ "$WITH_SHELL" -eq 0 && "$PROFILE" == core ]]; }
phase_dotfiles() { calls+=(phase_dotfiles); }
phase_theming() { calls+=(phase_theming); }
phase_verify() { calls+=(phase_verify); }
phase_shell() { return 99; }
execute_plan
[[ "${calls[*]}" == "${reviewed[*]}" && "$COMPLETED_PHASES" -eq 4 ]]
''')
        self.success(result)

    def test_plan_counts_installed_packages_without_writing(self):
        before = self.snapshot()
        result = self.bash('''
PACMAN_CORE=(kitty)
PACMAN_SHELL=(zsh)
NO_AUR=1
pacman() { printf 'kitty\\nzsh\\n'; }
systemctl() { printf 'enabled\\n'; }
build_plan
inspect_plan
[[ "$PLAN_PACKAGE_STATE" == known && "$PLAN_INSTALLED_COUNT" -eq 2 ]]
[[ ${#PLAN_MISSING_OFFICIAL[@]} -eq 0 ]]
''')
        self.success(result)
        self.assertEqual(before, self.snapshot())

    def test_plain_component_selection_and_review_navigation_are_read_only(self):
        self.forbid_mutations()
        before = self.snapshot()
        prompt = b"Choose [1], or q to cancel: "
        toggle = b"Toggle numbers (e.g. 1 3), Enter to continue, q to cancel: "
        result = self.terminal(replies=(
            (prompt, b"2\n"),  # Customize, not recommended defaults.
            (toggle, b"1 2\n"),  # Omit Zsh and AUR; extra apps stay off.
            (toggle, b"\n"),
            (toggle, b"\n"),  # No GDM/WWAN/login/default-app changes.
            (prompt, b"5\n"),  # Inspect config actions.
            (prompt, b"1\n"),  # Cancel.
        ))
        self.success(result)
        self.assertIn("Zsh stays untouched", result.stdout)
        self.assertIn("private palette config", result.stdout)
        self.assertIn("LEAVE ~/.config/zsh", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_gum_menu_review_details_and_cancel_are_read_only(self):
        self.forbid_mutations()
        self.mock_gum(["Recommended installation", "View package list", "Cancel"])
        before = self.home_snapshot()
        result = self.terminal()
        self.success(result)
        self.assertIn("Cancelled", result.stdout)
        self.assertEqual(before, self.home_snapshot())
        calls = self.gum_calls()
        self.assertTrue(any(call["args"][0] == "pager" and "OFFICIAL" in call["body"] for call in calls))
        for call in calls:
            if call["args"][0] == "choose" and "--no-limit" not in call["args"]:
                self.assertEqual(call["args"][call["args"].index("--selected") + 1], "")
            self.assertEqual(call["no_color"], "1")

    def test_gum_empty_component_selection_does_not_reenable_defaults(self):
        self.forbid_mutations()
        self.mock_gum(["Customize installation", [], [], "Cancel"])
        before = self.home_snapshot()
        result = self.terminal()
        self.success(result)
        self.assertIn("Zsh stays untouched", result.stdout)
        self.assertIn("Skipping AUR", result.stdout)
        self.assertEqual(before, self.home_snapshot())
        calls = [call["args"] for call in self.gum_calls() if call["args"][0] == "choose"]
        self.assertNotIn("Use Zsh as my account login shell", calls[2])

    def test_gum_back_to_components_updates_the_same_plan(self):
        self.forbid_mutations()
        self.mock_gum([
            "Recommended installation", "Customize components",
            ["Zsh setup (config + plugins + prompt)", "Extra apps + development tools"],
            ["GDM graphical login"], "View service actions", "Cancel",
        ])
        before = self.home_snapshot()
        result = self.terminal()
        self.success(result)
        self.assertIn("extra apps", result.stdout)
        self.assertIn("Enable GDM", result.stdout)
        pager = [call["body"] for call in self.gum_calls() if call["args"][0] == "pager"]
        self.assertTrue(any("gdm.service" in body for body in pager))
        self.assertEqual(before, self.home_snapshot())

    def test_gum_single_optional_component_can_be_skipped(self):
        self.forbid_mutations()
        self.mock_gum([
            "Customize components", "Skip Zsh setup (config + plugins + prompt)",
            "Skip Apply application defaults and GTK preferences", "Cancel",
        ])
        before = self.home_snapshot()
        result = self.terminal('main --only-dotfiles')
        self.success(result)
        self.assertIn("Zsh stays untouched", result.stdout)
        self.assertEqual(before, self.home_snapshot())

    def test_gum_escape_interrupt_and_error_never_start_installation(self):
        self.forbid_mutations()
        for code, expected in ((1, 0), (130, 130), (2, 1)):
            with self.subTest(code=code):
                self.mock_gum([{"code": code}])
                before = self.home_snapshot()
                result = self.terminal()
                self.assertEqual(result.returncode, expected, result.stdout)
                self.assertEqual(before, self.home_snapshot())

    def test_noninteractive_flags_do_not_invoke_gum(self):
        self.forbid_mutations()
        self.mock_gum([])
        for args, expected in ((("--dry-run", "--ui", "gum"), 0), (("--check", "--link-only", "--ui", "gum"), 1)):
            self.assertEqual(self.cli(*args).returncode, expected)
        self.assertEqual(self.gum_calls(), [])
        self.assertFalse((self.root / "gum-help-called").exists())

    def test_small_terminal_uses_plain_prompts_even_with_gum(self):
        self.forbid_mutations()
        self.mock_gum([])
        before = self.home_snapshot()
        result = self.terminal(replies=((b"Choose [1], or q to cancel: ", b"q\n"),), rows=10, columns=30)
        self.success(result)
        self.assertIn("small or unreported terminal", result.stdout)
        self.assertEqual(self.gum_calls(), [])
        self.assertEqual(before, self.home_snapshot())

    def test_interactive_preview_uses_gum_but_does_not_write_home(self):
        self.forbid_mutations()
        self.mock_gum(["Preview changes", "Run preview (no changes)", "Exit"])
        before = self.home_snapshot()
        result = self.terminal()
        self.success(result)
        self.assertIn("nothing changed", result.stdout)
        self.assertEqual(before, self.home_snapshot())

    def test_result_actions_keep_checks_read_only_and_do_not_add_logs(self):
        if os.geteuid() == 0 or not Path("/etc/arch-release").exists():
            self.skipTest("Link-only apply requires a normal Arch user")
        for name in ("sudo", "git", "makepkg", "matugen", "chsh", "systemctl", "fc-cache"):
            self.stub(name, 'printf "unexpected desktop command\\n" >&2; exit 97')
        self.mock_gum([
            "Install this plan", "View warnings and failures", "View full log",
            "Inspect backup manifest", "Run read-only verification", "Exit",
        ])
        result = self.terminal('main --link-only')
        self.success(result)
        self.assertIn("Checks complete", result.stdout)
        pages = [call["body"] for call in self.gum_calls() if call["args"][0] == "pager"]
        self.assertTrue(any("No warnings or failures" in page for page in pages))
        self.assertTrue(any("[start]" in page for page in pages))
        self.assertTrue(any("linked\t" in page for page in pages))
        self.assertEqual(len(list((self.home / ".local/state/dotfiles-install/logs").glob("*.log"))), 1)

    def test_real_gum_widgets_when_explicitly_provided(self):
        binary = os.environ.get("HYPRYORU_TEST_GUM")
        if not binary:
            self.skipTest("Set HYPRYORU_TEST_GUM to an existing Gum binary for real widget checks")
        self.assertTrue(Path(binary).is_file(), binary)
        self.forbid_mutations()
        (self.bin / "gum").symlink_to(Path(binary).resolve())
        self.env["TERM"] = "xterm-256color"
        self.env["GUM_CHOOSE_SELECTED"] = "Install this plan"
        before = self.home_snapshot()
        scenarios = (
            ('main', ((b"01 / Welcome", b"\x1b"),), 'Cancelled.'),
            ('setup_ui; UI_BACKEND=gum; UI_SESSION=1; ui_choose "Widget review" Cancel "Install this plan"; printf "REPLY=%s\\n" "$UI_REPLY"',
             ((b"Widget review", b"\r"),), 'REPLY=Cancel'),
            ('setup_ui; UI_BACKEND=gum; UI_SESSION=1; initial=(); choices=("Shell" "Themes"); ui_multiselect "Widget components" initial choices; printf "SELECTED=%s\\n" "${#UI_SELECTED[@]}"',
             ((b"Widget components", b"\r"),), 'SELECTED=0'),
            ('setup_ui; UI_BACKEND=gum; UI_SESSION=1; initial=(); choices=("Shell"); ui_multiselect "Widget single component" initial choices; printf "SELECTED=%s\\n" "${#UI_SELECTED[@]}"',
             ((b"Widget single component", b"\r"),), 'SELECTED=0'),
        )
        for body, replies, expected in scenarios:
            result = self.terminal(body, replies)
            self.success(result)
            self.assertIn(expected, result.stdout)
        self.assertEqual(before, self.home_snapshot())

    def test_unsupported_gum_falls_back_to_numbered_prompts(self):
        self.forbid_mutations()
        self.env["TERM"] = "xterm-256color"
        self.stub("gum", 'exit 2')
        before = self.snapshot()
        replies = []
        if os.geteuid() != 0 and os.uname().sysname == "Linux" and os.uname().machine in ("x86_64", "amd64", "aarch64", "arm64"):
            replies.append((b"Download the verified Gum runtime? [y/N]: ", b"n\n"))
        replies.append((b"Choose [1], or q to cancel: ", b"q\n"))
        result = self.terminal(replies=replies)
        self.success(result)
        self.assertIn("Using numbered prompts", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_runtime_download_requires_consent_and_does_not_precreate_cache(self):
        prefix, cache, _ = self.mock_gum_runtime()
        before = self.snapshot()
        result = self.terminal(prefix + 'main', replies=(
            (b"Download the verified Gum runtime? [y/N]: ", b"n\n"),
            (b"Choose [1], or q to cancel: ", b"q\n"),
        ))
        self.success(result)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(cache.parent.exists())
        self.assertFalse((self.root / "download-calls").exists())

    def test_runtime_download_precedes_first_menu_and_is_reused(self):
        prefix, cache, binary = self.mock_gum_runtime()
        result = self.terminal(prefix + 'main', replies=((b"Download the verified Gum runtime? [y/N]: ", b"y\n"),))
        self.success(result)
        self.assertIn("Enhanced interface ready", result.stdout)
        self.assertNotIn("Using numbered prompts", result.stdout)
        self.assertIn("No desktop settings or packages changed", result.stdout)
        self.assertEqual(cache.read_bytes(), binary)
        self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o700)
        self.assertEqual(list(cache.parent.glob(".download.*")), [])
        self.assertFalse((self.home / ".config").exists())
        self.assertTrue(self.gum_calls())
        (self.root / "gum-replies.json").write_text(json.dumps(["Exit"]))
        before = self.home_snapshot()
        again = self.terminal(prefix + 'main')
        self.success(again)
        self.assertNotIn("Download the verified", again.stdout)
        self.assertEqual(before, self.home_snapshot())
        self.assertEqual((self.root / "download-calls").read_text().count("download"), 1)

    def test_pinned_cache_is_used_without_download_or_permission_prompt(self):
        prefix, cache, binary = self.mock_gum_runtime()
        cache.parent.mkdir(parents=True)
        cache.write_bytes(binary)
        cache.chmod(0o700)
        before = self.home_snapshot()
        result = self.terminal(prefix + 'main')
        self.success(result)
        self.assertNotIn("Download the verified", result.stdout)
        self.assertFalse((self.root / "download-calls").exists())
        self.assertEqual(before, self.home_snapshot())

    def test_modified_cache_is_not_executed_without_consent(self):
        prefix, cache, _ = self.mock_gum_runtime()
        cache.parent.mkdir(parents=True)
        cache.write_text('#!/bin/sh\ntouch "$HOME/unverified-executed"\n')
        cache.chmod(0o700)
        before = self.home_snapshot()
        result = self.terminal(prefix + 'main', replies=(
            (b"Download the verified Gum runtime? [y/N]: ", b"n\n"),
            (b"Choose [1], or q to cancel: ", b"q\n"),
        ))
        self.success(result)
        self.assertIn("Cached Gum was not verified", result.stdout)
        self.assertFalse((self.home / "unverified-executed").exists())
        self.assertEqual(before, self.home_snapshot())

    def test_approved_replacement_preserves_an_unverified_cached_file(self):
        prefix, cache, binary = self.mock_gum_runtime()
        cache.parent.mkdir(parents=True)
        old = b'#!/bin/sh\ntouch "$HOME/unverified-executed"\n'
        cache.write_bytes(old)
        cache.chmod(0o700)
        result = self.terminal(prefix + 'main', replies=((b"Download the verified Gum runtime? [y/N]: ", b"y\n"),))
        self.success(result)
        self.assertEqual(cache.read_bytes(), binary)
        preserved = list(cache.parent.glob("gum.unverified-*"))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_bytes(), old)
        self.assertFalse((self.home / "unverified-executed").exists())

    def test_bad_runtime_archive_is_rejected_and_staging_is_cleaned(self):
        prefix, cache, _ = self.mock_gum_runtime()
        (self.root / "gum-runtime.tar.gz").write_bytes(b"not the pinned archive")
        result = self.terminal(prefix + 'main', replies=(
            (b"Download the verified Gum runtime? [y/N]: ", b"y\n"),
            (b"Choose [1], or q to cancel: ", b"q\n"),
        ))
        self.success(result)
        self.assertIn("archive verification failed", result.stdout)
        self.assertFalse(cache.exists())
        self.assertFalse((self.root / "gum-help-called").exists())
        self.assertEqual(list(cache.parent.glob(".download.*")), [])

    def test_runtime_executable_hash_is_checked_before_execution(self):
        prefix, cache, _ = self.mock_gum_runtime(bad_binary=True)
        result = self.terminal(prefix + 'main', replies=(
            (b"Download the verified Gum runtime? [y/N]: ", b"y\n"),
            (b"Choose [1], or q to cancel: ", b"q\n"),
        ))
        self.success(result)
        self.assertIn("executable verification failed", result.stdout)
        self.assertFalse(cache.exists())
        self.assertFalse((self.home / "unverified-executed").exists())
        self.assertEqual(list(cache.parent.glob(".download.*")), [])

    def test_runtime_network_failure_falls_back_without_partial_executable(self):
        prefix, cache, _ = self.mock_gum_runtime()
        self.stub("curl", 'printf "simulated offline\\n" >&2; exit 22')
        result = self.terminal(prefix + 'main', replies=(
            (b"Download the verified Gum runtime? [y/N]: ", b"y\n"),
            (b"Choose [1], or q to cancel: ", b"q\n"),
        ))
        self.success(result)
        self.assertIn("Could not prepare the enhanced interface", result.stdout)
        self.assertFalse(cache.exists())
        self.assertEqual(list(cache.parent.glob(".download.*")), [])

    def test_runtime_cache_symlink_is_not_followed_or_replaced(self):
        prefix, _, _ = self.mock_gum_runtime()
        outside = self.root / "outside-cache"
        outside.mkdir()
        (self.home / ".cache").mkdir()
        (self.home / ".cache/hypryoru").symlink_to(outside)
        before = self.home_snapshot()
        result = self.terminal(prefix + 'main', replies=((b"Choose [1], or q to cancel: ", b"q\n"),))
        self.success(result)
        self.assertIn("not safely owned", result.stdout)
        self.assertEqual(before, self.home_snapshot())
        self.assertEqual(list(outside.iterdir()), [])

    def test_runtime_cache_writable_by_others_is_not_executed(self):
        prefix, cache, binary = self.mock_gum_runtime()
        cache.parent.mkdir(parents=True)
        cache.write_bytes(binary)
        cache.chmod(0o700)
        cache.parent.chmod(0o777)
        before = self.home_snapshot()
        result = self.terminal(prefix + 'main', replies=((b"Choose [1], or q to cancel: ", b"q\n"),))
        self.success(result)
        self.assertIn("not safely owned", result.stdout)
        self.assertFalse((self.root / "gum-help-called").exists())
        self.assertEqual(before, self.home_snapshot())

    def test_runtime_resolver_itself_bypasses_plain_readonly_and_automation(self):
        result = self.bash('''
find_system_gum() { printf unexpected >"$CASE_ROOT/should-not-run"; return 1; }
for disabled in plain dry check yes quiet; do
  UI_SESSION=1; UI_MODE=auto; DRY_RUN=0; CHECK_ONLY=0; ASSUME_YES=0; QUIET=0
  case "$disabled" in
    plain) UI_MODE=plain ;; dry) DRY_RUN=1 ;; check) CHECK_ONLY=1 ;;
    yes) ASSUME_YES=1 ;; quiet) QUIET=1 ;;
  esac
  if prepare_gum_runtime; then exit 99; fi
done
''')
        self.success(result)
        self.assertFalse((self.root / "should-not-run").exists())
        self.assertFalse((self.home / ".cache").exists())

    def test_runtime_download_helper_cannot_skip_consent(self):
        before = self.snapshot()
        result = self.bash('if download_gum_runtime; then exit 99; fi\n[[ "$GUM_CACHE_CHANGED" -eq 0 ]]')
        self.success(result)
        self.assertEqual(before, self.snapshot())

    def test_runtime_uses_wget_when_curl_is_unavailable(self):
        result = self.bash('''
command() {
  if [[ "$1" == -v && "$2" == curl ]]; then return 1; fi
  builtin command "$@"
}
wget() { printf '%s\\n' "$@"; }
GUM_DOWNLOAD_URL=https://example.invalid/gum.tar.gz
gum_fetch_archive "$CASE_ROOT/archive with spaces.tar.gz"
''')
        self.success(result)
        self.assertIn("--https-only\n", result.stdout)
        self.assertIn(f"--output-document={self.root}/archive with spaces.tar.gz\n", result.stdout)
        self.assertTrue(result.stdout.endswith("https://example.invalid/gum.tar.gz\n"))

    def test_missing_download_tools_fall_back_without_a_permission_prompt(self):
        prefix, _, _ = self.mock_gum_runtime()
        prefix += '''
command() {
  if [[ "$1" == -v && ( "$2" == curl || "$2" == wget ) ]]; then return 1; fi
  builtin command "$@"
}
'''
        before = self.home_snapshot()
        result = self.terminal(prefix + 'main', replies=((b"Choose [1], or q to cancel: ", b"q\n"),))
        self.success(result)
        self.assertIn("needs curl or wget", result.stdout)
        self.assertNotIn("Download the verified", result.stdout)
        self.assertEqual(before, self.home_snapshot())

    def test_preview_after_an_approved_runtime_download_reports_cache_changes(self):
        prefix, cache, _ = self.mock_gum_runtime(["Preview changes", "Run preview (no changes)", "Exit"])
        result = self.terminal(prefix + 'main', replies=((b"Download the verified Gum runtime? [y/N]: ", b"y\n"),))
        self.success(result)
        self.assertIn("Plan complete — no desktop changes", result.stdout)
        self.assertNotIn("Plan complete — nothing changed", result.stdout)
        self.assertIn("approved cache; retained", result.stdout)
        self.assertTrue(cache.exists())
        self.assertFalse((self.home / ".config").exists())
        self.assertFalse((self.home / ".local/state").exists())

    def test_unsupported_runtime_platform_does_not_download(self):
        prefix, _, _ = self.mock_gum_runtime()
        before = self.home_snapshot()
        result = self.terminal(prefix + 'gum_runtime_release() { return 1; }\nmain', replies=((b"Choose [1], or q to cancel: ", b"q\n"),))
        self.success(result)
        self.assertIn("No pinned Gum runtime", result.stdout)
        self.assertFalse((self.root / "download-calls").exists())
        self.assertEqual(before, self.home_snapshot())

    def test_palette_plan_omits_only_the_unselected_shell_output(self):
        original = (REPO / "matugen/config.toml").read_bytes()
        result = self.bash('WITH_SHELL=0\nbuild_plan\nrender_palette_config')
        self.success(result)
        self.assertNotIn("[templates.shell]", result.stdout)
        for section in ("hypr", "hyprlock", "waybar", "kitty", "gtk3", "qt6ct", "opencode"):
            self.assertIn(f"[templates.{section}]", result.stdout)
        self.assertEqual(original, (REPO / "matugen/config.toml").read_bytes())

    def test_link_only_cli_touches_only_sandbox_home(self):
        if os.geteuid() == 0 or not Path("/etc/arch-release").exists():
            self.skipTest("Applying even link-only mode requires a normal Arch user")
        for name in ("sudo", "git", "makepkg", "matugen", "chsh", "systemctl", "fc-cache"):
            self.stub(name, 'printf "unexpected command: %s\\n" "$0" >&2; exit 97')
        result = self.cli("--link-only", "--yes")
        self.success(result)
        self.assertTrue((self.home / ".config/hypr").is_symlink())
        self.assertFalse((self.home / "Pictures").exists())
        result = self.cli("--check", "--link-only")
        self.success(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
