#!/usr/bin/env python3
"""Clipboard regression tests; never inspect the real clipboard or history.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("yoru_clipboard", Path(__file__).parents[1] / "clipboard.py")
clipboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clipboard)


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="clipboard-test-", dir="/tmp/opencode")
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.temp.name,
                                         "XDG_STATE_HOME": str(self.root / "state"),
                                         "CLIPBOARD_STATE": "data"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp.cleanup)

    def test_sensitive_nil_and_clear_are_never_stored(self):
        with patch.object(clipboard, "cliphist") as backend:
            for state in ("sensitive", "nil", "clear", ""):
                with patch.dict(os.environ, {"CLIPBOARD_STATE": state}):
                    clipboard.store(io.BytesIO(b"synthetic password"))
            backend.assert_not_called()

    def test_store_preserves_bytes_and_limits_size(self):
        data = b"  image\x00or text\n\n"
        with patch.object(clipboard, "cliphist") as backend:
            clipboard.store(io.BytesIO(data))
            backend.assert_called_once_with("store", data)
            backend.reset_mock()
            clipboard.store(io.BytesIO(b"x" * (clipboard.MAX_BYTES + 1)))
            backend.assert_not_called()

    def test_pause_persists_and_resume_does_not_read_current_clipboard(self):
        with patch.object(clipboard, "cliphist") as backend:
            clipboard.set_paused(True)
            self.assertTrue(clipboard.paused())
            clipboard.store(io.BytesIO(b"not stored"))
            clipboard.set_paused(False)
            self.assertFalse(clipboard.paused())
            backend.assert_not_called()

    def test_pause_wins_race_after_input_is_read(self):
        class PausingStream(io.BytesIO):
            def read(self, size):
                result = super().read(size)
                clipboard.set_paused(True)
                return result
        with patch.object(clipboard, "cliphist") as backend:
            clipboard.store(PausingStream(b"never stored"))
            backend.assert_not_called()

    def test_private_runtime_and_nonblocking_singleton(self):
        with clipboard.locked("watch.lock"):
            with self.assertRaises(BlockingIOError):
                with clipboard.locked("watch.lock", blocking=False):
                    self.fail("duplicate watcher obtained the singleton lock")
        self.assertEqual(clipboard.runtime_dir().stat().st_mode & 0o777, 0o700)
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": ""}):
            with self.assertRaises(RuntimeError):
                clipboard.runtime_dir()

    def test_existing_watchers_are_detected(self):
        proc = self.root / "proc"
        entry = proc / "123"
        entry.mkdir(parents=True)
        (entry / "cmdline").write_bytes(b"/usr/bin/wl-paste\0--type\0text\0--watch\0cliphist\0store\0")
        self.assertTrue(clipboard.foreign_watchers(proc))
        (entry / "cmdline").write_bytes(b"wl-paste\0--list-types\0")
        self.assertFalse(clipboard.foreign_watchers(proc))

    def test_runtime_symlinks_are_rejected(self):
        target = self.root / "not-runtime"
        target.mkdir(mode=0o700)
        (self.root / "yoru-clipboard").symlink_to(target)
        with self.assertRaises(RuntimeError):
            clipboard.runtime_dir()

    def test_untrusted_preview_cannot_add_rofi_metadata(self):
        with patch.object(clipboard, "cliphist", return_value=b"17\t<b>literal</b>\x00icon\x1fsecret\ninvalid\n"):
            self.assertEqual(clipboard.history(), [(b"17", "<b>literal</b> icon secret")])

    def test_empty_database_is_not_created_by_listing(self):
        error = subprocess.CalledProcessError(1, "cliphist", stderr=b"please store something first")
        with patch.object(clipboard, "cliphist", side_effect=error):
            self.assertEqual(clipboard.history(), [])

    def test_decode_copies_binary_payload_without_shell_interpolation(self):
        payload = b"\x89PNG\r\n\x1a\n\x00\xff"
        with patch.object(clipboard, "cliphist", return_value=payload) as backend:
            with patch.object(clipboard.subprocess, "run") as run:
                clipboard.restore(b"7")
                backend.assert_called_once_with("decode", b"7")
                self.assertEqual(run.call_args.args[0], ["wl-copy"])
                self.assertEqual(run.call_args.kwargs["input"], payload)

    def test_clear_requires_explicit_confirmation(self):
        with patch.object(clipboard, "history", return_value=[]):
            with patch.object(clipboard, "choose", side_effect=[2, 0, None]):
                with patch.object(clipboard, "cliphist") as backend:
                    clipboard.picker()
                    backend.assert_not_called()
            with patch.object(clipboard, "choose", side_effect=[2, 1, None]):
                with patch.object(clipboard, "cliphist") as backend:
                    clipboard.picker()
                    backend.assert_called_once_with("wipe")

    def test_delete_uses_stable_id_not_preview_text(self):
        with patch.object(clipboard, "history", return_value=[(b"42", "$(do not execute)")]):
            with patch.object(clipboard, "choose", side_effect=[1, 0, None]):
                with patch.object(clipboard, "cliphist") as backend:
                    clipboard.picker()
                    backend.assert_called_once_with("delete", b"42")

    def test_rofi_is_index_only_and_markup_is_disabled(self):
        with patch.object(clipboard.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"1\n")) as run:
            self.assertEqual(clipboard.choose(["first", "second"]), 1)
            self.assertIn("-no-custom", run.call_args.args[0])
            self.assertIn("-no-markup-rows", run.call_args.args[0])
        with patch.object(clipboard.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"99\n")):
            self.assertIsNone(clipboard.choose(["only one"]))


if __name__ == "__main__":
    unittest.main()
