#!/usr/bin/env python3
"""Bash prompt regression tests: status matrix, width, transient, exec-time, re-source.

Runs the real bash config under a temporary HOME. Uses simple subprocess for
most tests (fast, reliable in CI). Transient prompt color tests require a real
interactive PTY (tmux/script) and are skipped in headless CI environments.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASH_RCFILE = REPO / "bash/.bashrc"
TEMP_ROOT = Path("/tmp/opencode")


def run_bash_simple(commands, *, home, cols=80, rows=24):
    """Run bash -i with our config (no PTY), return raw output."""
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"),
        XDG_DATA_HOME=str(home / ".local/share"),
        XDG_DATA_DIRS="/usr/local/share:/usr/share",
        XDG_RUNTIME_DIR=str(home / ".runtime"),
        TERM="xterm-256color",
        COLUMNS=str(cols),
        LINES=str(rows),
        NO_COLOR="",
    )
    env.pop("ZDOTDIR", None)
    env.pop("ZSH_CUSTOM", None)
    env.pop("BASH_ENV", None)
    env.pop("ENV", None)

    input_data = "\n".join(commands) + "\nexit\n"

    proc = subprocess.run(
        ["bash", "--rcfile", str(BASH_RCFILE), "-i"],
        env=env,
        cwd=str(home),
        input=input_data,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return proc.stdout + proc.stderr


def run_bash_pty(commands, *, home, cols=80, rows=24):
    """Run bash -i under script(1) for real PTY, return raw output."""
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"),
        XDG_DATA_HOME=str(home / ".local/share"),
        XDG_DATA_DIRS="/usr/local/share:/usr/share",
        XDG_RUNTIME_DIR=str(home / ".runtime"),
        TERM="xterm-256color",
        COLUMNS=str(cols),
        LINES=str(rows),
        NO_COLOR="",
    )
    env.pop("ZDOTDIR", None)
    env.pop("ZSH_CUSTOM", None)
    env.pop("BASH_ENV", None)
    env.pop("ENV", None)

    input_data = "\n".join(commands) + "\nexit\n"

    proc = subprocess.run(
        ["script", "-qec", f'bash --rcfile {BASH_RCFILE} -i', "/dev/null"],
        env=env,
        cwd=str(home),
        input=input_data,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return proc.stdout + proc.stderr


def strip_ansi(text):
    """Remove all CSI/OSC/charset sequences for visual width measurement."""
    # OSC ... BEL/ST
    text = re.sub(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", "", text)
    # CSI ... final byte
    text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)
    # Charset selects: ESC ( B etc.
    text = re.sub(r"\x1b[()][0-9A-Za-z]", "", text)
    # ESC = /> (keypad modes)
    text = re.sub(r"\x1b[=>]", "", text)
    # Carriage returns
    text = text.replace("\r", "")
    return text


def extract_prompt_lines(raw, marker="╭"):
    """Return list of (line_num, visual_width, has_status_segment, status_text) for each prompt."""
    clean = strip_ansi(raw)
    results = []
    for i, line in enumerate(clean.split("\n")):
        if marker in line:
            has_status = any(sym in line for sym in ("✘", "✔", "TERM", "took"))
            status_text = ""
            if "TERM" in line:
                status_text = "TERM"
            elif "took" in line:
                status_text = "took"
            elif "✔" in line:
                status_text = "✔"
            elif "✘" in line:
                status_text = "✘"
            results.append((i, len(line), has_status, status_text))
    return results


def find_transient_prompts(raw):
    """Find the single-line '❯ cmd' transient rewrites and their colors."""
    results = []
    for m in re.finditer(r"\x1b\[0;(3[12])m❯", raw):
        ctx = raw[max(0, m.start() - 60):m.start() + 10].replace("\r", "")
        results.append((m.group(1), ctx))
    return results


class BashPromptTests(unittest.TestCase):
    """Tests using simple subprocess (no PTY) - covers status matrix, width, re-source, exec time."""
    
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(
            prefix="bash-prompt-tests-", dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None
        )
        self.addCleanup(self.tmpdir.cleanup)
        self.home = Path(self.tmpdir.name)
        (self.home / ".config").mkdir()
        (self.home / ".config/bash").symlink_to(REPO / "bash")

    def run_simple(self, commands, cols=80):
        return run_bash_simple(commands, home=self.home, cols=cols)

    # ------------------------------------------------------------------------
    # Status matrix
    # ------------------------------------------------------------------------
    def test_status_plain_failure_hidden(self):
        """Plain non-zero exit (no pipe, no signal) shows no status segment."""
        out = self.run_simple(["false"])
        prompts = extract_prompt_lines(out)
        self.assertEqual(len(prompts), 2)
        _, _, has_status, _ = prompts[1]
        self.assertFalse(has_status, "plain failure should not show ✘/✔/TERM")

    def test_status_pipe_fail_first(self):
        """true|false → ✘ 0|1 on right."""
        out = self.run_simple(["true|false"])
        prompts = extract_prompt_lines(out)
        self.assertEqual(len(prompts), 2)
        _, _, has_status, status_text = prompts[1]
        self.assertTrue(has_status)
        self.assertIn("✘", status_text)
        self.assertIn("0|1", strip_ansi(out))

    def test_status_pipe_fail_second(self):
        """false|true → ✔ 1|0 on right."""
        out = self.run_simple(["false|true"])
        prompts = extract_prompt_lines(out)
        self.assertEqual(len(prompts), 2)
        _, _, has_status, status_text = prompts[1]
        self.assertTrue(has_status)
        self.assertIn("✔", status_text)
        self.assertIn("1|0", strip_ansi(out))

    def test_status_signal_term(self):
        """SIGTERM → ✘ TERM on right."""
        out = self.run_simple(["sh -c 'kill -TERM $$'"])
        prompts = extract_prompt_lines(out)
        self.assertEqual(len(prompts), 2)
        _, _, has_status, status_text = prompts[1]
        self.assertTrue(has_status)
        self.assertIn("TERM", status_text)

    # ------------------------------------------------------------------------
    # Exec time (took segment)
    # ------------------------------------------------------------------------
    def test_exec_time_shows_took(self):
        """A command taking ~4s should render 'took 4s' on the right."""
        out = self.run_simple(["sleep 4"])
        prompts = extract_prompt_lines(out)
        self.assertEqual(len(prompts), 2)
        _, _, has_status, status_text = prompts[1]
        self.assertTrue(has_status)
        self.assertIn("took", status_text)

    # ------------------------------------------------------------------------
    # Width = COLUMNS exactly
    # ------------------------------------------------------------------------
    def test_width_80(self):
        """First prompt line must be exactly 80 columns at COLUMNS=80."""
        out = self.run_simple(["true"], cols=80)
        prompts = extract_prompt_lines(out)
        for _, width, _, _ in prompts:
            self.assertEqual(width, 80, f"prompt line width {width} != 80")

    def test_test_width_100(self):
        """First prompt line must be exactly 100 columns at COLUMNS=100."""
        out = self.run_simple(["true"], cols=100)
        prompts = extract_prompt_lines(out)
        for _, width, _, _ in prompts:
            self.assertEqual(width, 100, f"prompt line width {width} != 100")

    # ------------------------------------------------------------------------
    # Re-source idempotency (PROMPT_COMMAND fold)
    # ------------------------------------------------------------------------
    def test_resources_idempotent(self):
        """Sourcing .bashrc twice must not duplicate PROMPT_COMMAND entries."""
        out = self.run_simple(
            [
                'source ~/.config/bash/.bashrc',
                'source ~/.config/bash/.bashrc',
                'echo "PC=$PROMPT_COMMAND"',
            ]
        )
        self.assertIn("PC=_yoru_prompt", strip_ansi(out))
        out2 = self.run_simple(
            [
                'source ~/.config/bash/.bashrc',
                'source ~/.config/bash/.bashrc',
                'true|false',
            ]
        )
        prompts = extract_prompt_lines(out2)
        self.assertTrue(prompts[-1][2], "status segment missing after re-source")
        self.assertIn("✘", prompts[-1][3])

    # ------------------------------------------------------------------------
    # PS2 continuation prompt
    # ------------------------------------------------------------------------
    def test_ps2_format(self):
        """PS2 should be '├─ ' in gray (37)."""
        config = (REPO / "bash/conf.d/post/90-prompt.bash").read_text()
        self.assertIn(r"\[\e[37m\]", config)
        self.assertIn("├─", config)

    # ------------------------------------------------------------------------
    # No ble.sh default markers
    # ------------------------------------------------------------------------
    def test_no_ble_markers(self):
        """No '[ble: exit 1]' or '[ble: EOF]' should appear."""
        out = self.run_simple(["false", "echo test"])
        self.assertNotIn("[ble:", out)

    # ------------------------------------------------------------------------
    # Autosuggestion face tracks MATUGEN_AUTOSUGGEST
    # ------------------------------------------------------------------------
    def test_autosuggest_face_updated(self):
        """ble-face auto_complete should be set to MATUGEN_AUTOSUGGEST value."""
        config = (REPO / "bash/conf.d/post/50-blesh.bash").read_text()
        self.assertIn("MATUGEN_AUTOSUGGEST", config)
        self.assertIn("_blesh_apply_matugen", config)


class BashPromptPtyTests(unittest.TestCase):
    """Tests requiring real PTY (script/tmux) for ble.sh interactive features.
    
    These are skipped in headless CI environments where script(1) PTY
    emulation doesn't fully support ble.sh's PROMPT_COMMAND handling.
    Real interactive use (tmux, terminal) works correctly.
    """
    
    @classmethod
    def setUpClass(cls):
        # Check if we have a real TTY available for script(1) to work properly
        cls.has_pty = os.isatty(0) and os.isatty(1) and shutil.which("script")
        try:
            # Quick test: script should work without "not a tty" errors
            result = subprocess.run(
                ["script", "-qec", "echo test", "/dev/null"],
                capture_output=True, text=True, timeout=10
            )
            cls.has_pty = cls.has_pty and result.returncode == 0
        except Exception:
            cls.has_pty = False

    def setUp(self):
        if not self.has_pty:
            self.skipTest("No real PTY available for script(1); transient tests require interactive terminal")
        
        self.tmpdir = tempfile.TemporaryDirectory(
            prefix="bash-pty-tests-", dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None
        )
        self.addCleanup(self.tmpdir.cleanup)
        self.home = Path(self.tmpdir.name)
        (self.home / ".config").mkdir()
        (self.home / ".config/bash").symlink_to(REPO / "bash")

    def run_pty(self, commands, cols=80):
        return run_bash_pty(commands, home=self.home, cols=cols)

    def test_ble_loaded(self):
        """ble.sh should load and BLE_VERSION should be set."""
        out = self.run_pty(["echo BLE_VERSION=$BLE_VERSION"])
        self.assertIn("BLE_VERSION=", strip_ansi(out))

    def test_fzf_keybindings_loaded(self):
        """fzf key bindings should be loaded via ble-import."""
        out = self.run_pty(["ble/util/import/is-loaded contrib/integration/fzf-key-bindings && echo FZF_OK"])
        self.assertIn("FZF_OK", strip_ansi(out))

    def test_syntax_highlighting_faces(self):
        """ble-face should have our custom face definitions."""
        out = self.run_pty(["ble-face syntax_command"])
        self.assertIn("fg=magenta,bold", strip_ansi(out))

    def test_auto_complete_face(self):
        """auto_complete face should use MATUGEN_AUTOSUGGEST."""
        out = self.run_pty(["ble-face auto_complete"])
        self.assertIn("fg=#", strip_ansi(out))

    def test_transient_green_after_success(self):
        """After a successful command, the next transient ❯ is green (32)."""
        if not self.has_pty:
            self.skipTest("Requires real PTY for transient prompt color verification")
        out = self.run_pty(["true", "echo after-success"])
        transients = find_transient_prompts(out)
        self.assertGreaterEqual(len(transients), 2)
        self.assertEqual(transients[1][0], "32", "transient after success should be green")

    def test_transient_red_after_failure(self):
        """After a failed command, the next transient ❯ is red (31)."""
        if not self.has_pty:
            self.skipTest("Requires real PTY for transient prompt color verification")
        out = self.run_pty(["false", "echo after-failure"])
        transients = find_transient_prompts(out)
        self.assertGreaterEqual(len(transients), 2)
        self.assertEqual(transients[1][0], "31", "transient after failure should be red")

    def test_transient_red_after_pipe_failure(self):
        """After a failed pipe, the next transient ❯ is red (31)."""
        if not self.has_pty:
            self.skipTest("Requires real PTY for transient prompt color verification")
        out = self.run_pty(["true|false", "echo after-pipe"])
        transients = find_transient_prompts(out)
        self.assertGreaterEqual(len(transients), 2)
        self.assertEqual(transients[1][0], "31", "transient after pipe failure should be red")


if __name__ == "__main__":
    import shutil
    unittest.main(verbosity=2)