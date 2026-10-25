#!/usr/bin/env python3
"""Exercise maintenance safety without touching real daemons or the inbox.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from contextlib import nullcontext, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("yoru_desktop", Path(__file__).parents[1] / "desktop-binaries.py")
desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="desktop-test-", dir="/tmp/opencode")
        self.root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data"),
                                         "XDG_CONFIG_HOME": str(self.root / "config"),
                                         "XDG_STATE_HOME": str(self.root / "state")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.directory.cleanup)

    def test_select_local_or_system_without_running_either(self):
        self.assertEqual(desktop.selected_binary("waybar"), Path("/usr/bin/waybar"))
        binary = desktop.local_binary("waybar")
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"synthetic binary, not executed")
        binary.chmod(0o755)
        self.assertEqual(desktop.selected_binary("waybar"), binary)

    def test_manifest_detects_changed_binary(self):
        binary = desktop.local_binary("waybar")
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"synthetic binary")
        binary.chmod(0o755)
        binary.with_name("manifest.json").write_text(json.dumps({"binary_sha256": desktop.digest(binary)}))
        desktop.verify_local("waybar")
        binary.write_bytes(b"modified")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            desktop.verify_local("waybar")

    def test_inbox_is_checked_only_for_a_running_swaync(self):
        with patch.object(desktop, "notification_count", return_value=1) as count:
            desktop.require_safe_inbox("waybar", [100])
            desktop.require_safe_inbox("swaync", [])
            count.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "Nothing was cleared or restarted"):
                desktop.require_safe_inbox("swaync", [100])
            count.assert_called_once()

    def test_nonempty_inbox_refuses_before_any_signal_or_start(self):
        with patch.object(desktop, "restart_lock", return_value=nullcontext()), \
             patch.object(desktop, "process_ids", return_value=[123]), \
             patch.object(desktop, "verify_local"), patch.object(desktop, "version"), \
             patch.object(desktop, "notification_count", return_value=1), \
             patch.object(desktop.os, "kill") as kill, \
             patch.object(desktop, "unit_active") as unit, \
             patch.object(desktop.subprocess, "Popen") as start:
            with self.assertRaises(RuntimeError):
                desktop.restart("swaync")
            kill.assert_not_called()
            unit.assert_not_called()
            start.assert_not_called()

    def test_multiple_instances_are_not_guessed(self):
        with patch.object(desktop, "restart_lock", return_value=nullcontext()), \
             patch.object(desktop, "process_ids", return_value=[1, 2]), \
             patch.object(desktop.os, "kill") as kill:
            with self.assertRaisesRegex(RuntimeError, "Multiple"):
                desktop.restart("waybar")
            kill.assert_not_called()

    def test_waybar_restart_targets_only_the_old_bar(self):
        with patch.object(desktop, "restart_lock", return_value=nullcontext()), \
             patch.object(desktop, "process_ids", side_effect=[[111], [], [222]]), \
             patch.object(desktop, "verify_local"), patch.object(desktop, "version"), \
             patch.object(desktop, "digest", return_value="identical"), \
             patch.object(desktop, "unit_active", return_value=False), \
             patch.object(desktop, "notification_count") as count, \
             patch.object(desktop.os, "kill") as kill, \
             patch.object(desktop.subprocess, "Popen", return_value=SimpleNamespace(poll=lambda: None)) as start, \
             redirect_stdout(io.StringIO()):
            desktop.restart("waybar")
            kill.assert_called_once_with(111, signal.SIGTERM)
            count.assert_not_called()
            self.assertEqual(start.call_args.args[0], [str(desktop.launcher("waybar"))])

    def test_zombie_and_other_processes_are_ignored(self):
        for pid, name, state in [(11, "waybar", "S"), (12, "waybar", "Z"), (13, "cc1plus", "S")]:
            directory = self.root / str(pid)
            directory.mkdir()
            (directory / "comm").write_text(name + "\n")
            (directory / "stat").write_text(f"{pid} ({name}) {state} 0 0 0\n")
        self.assertEqual(desktop.process_ids("waybar", self.root), [11])


if __name__ == "__main__":
    unittest.main()
