#!/usr/bin/env python3
"""Kill publishers at transaction boundaries; recover only a disposable HOME."""

import json
import os
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "hyprland/scripts"
TEMP_ROOT = Path("/tmp/opencode")
sys.path.insert(0, str(SCRIPTS))

from palette_store import PaletteStore, atomic_text


# SIGSTOP is a deterministic handshake, then the test sends SIGKILL. Unlike a
# raised exception, neither signal lets Python run transaction cleanup.
PUBLISHER = r'''
import json
import os
from pathlib import Path
import signal
import sys

import palette_store as module

home = Path.home()
store = module.PaletteStore(home / ".cache/matugen")
targets = [(Path(a), Path(b)) for a, b in json.loads(os.environ["RECOVERY_TARGETS"])]
point = os.environ["RECOVERY_POINT"]
marker = home / "stopped"

def stop():
    marker.write_text("stopped")
    os.kill(os.getpid(), signal.SIGSTOP)

replace = os.replace
def replace_and_stop(source, target):
    if point == "rollback" and Path(target) == targets[1][1] and str(source).endswith(".new"):
        raise OSError("trigger rollback")
    replace(source, target)
    if Path(target) == targets[0][1]:
        if point == "first" and str(source).endswith(".new"):
            stop()
        if point == "rollback" and str(source).endswith(".restore"):
            stop()
os.replace = replace_and_stop

copy_sync = module.copy_sync
def copy_and_stop(source, target):
    copy_sync(source, target)
    if point == "preparing":
        stop()
module.copy_sync = copy_and_stop

write_journal = store._write_journal
def write_and_stop(directory, journal):
    if point == "all" and journal["phase"] == "committed":
        stop()
    write_journal(directory, journal)
store._write_journal = write_and_stop

cleanup = store._cleanup
def cleanup_and_stop(directory, journal):
    if point == "committed" and journal["phase"] == "committed":
        stop()
    cleanup(directory, journal)
store._cleanup = cleanup_and_stop

with store.operation(lambda: None):
    with store.workspace("render") as work:
        (work / "partial.css").write_text("abandoned render")
        store.publish(targets)
'''


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hypryoru-recovery-", dir=TEMP_ROOT)
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / "home"
        self.home.mkdir()
        self.cache = self.home / ".cache/matugen"
        self.cache.mkdir(parents=True)
        self.store = PaletteStore(self.cache)
        self.consumer = self.home / ".config/test"
        self.consumer.mkdir(parents=True)
        self.outputs = [self.consumer / f"{name}.css" for name in ("one", "two", "new")]
        for path in self.outputs[:2]:
            path.write_text("last good\n")
        self.before = {"id": "a" * 32, "wall": str(self.home / "old.png"),
                       "mode": "dark", "gtk_update": False}
        self.after = {"id": "b" * 32, "wall": str(self.home / "new.png"),
                      "mode": "light", "gtk_update": False}
        for name, text in (("committed.json", json.dumps(self.before)),
                           ("current-wallpaper", self.before["wall"]),
                           ("current-mode", "dark"), ("current-request", self.before["id"]),
                           ("intent.json", json.dumps(self.after))):
            atomic_text(self.cache / name, text + "\n")
        self.targets = []
        sources = self.home / "sources"
        sources.mkdir()
        for index, destination in enumerate(self.outputs):
            source = sources / f"{index}.css"
            source.write_text("new palette\n")
            self.targets.append((source, destination))
        for name, text in (("current-wallpaper", self.after["wall"]), ("current-mode", "light"),
                           ("current-request", self.after["id"]),
                           ("committed.json", json.dumps(self.after))):
            source = sources / name
            source.write_text(text + "\n")
            self.targets.append((source, self.cache / name))
        self.env = os.environ | {
            "HOME": str(self.home), "PYTHONPATH": str(SCRIPTS),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "RECOVERY_TARGETS": json.dumps([(str(a), str(b)) for a, b in self.targets]),
        }

    def kill_publisher(self, point):
        process = subprocess.Popen([sys.executable, "-B", "-c", PUBLISHER],
                                   env=self.env | {"RECOVERY_POINT": point},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(200):
                if (self.home / "stopped").exists() or process.poll() is not None:
                    break
                time.sleep(0.01)
            self.assertTrue((self.home / "stopped").is_file(), "Publisher did not reach crash point")
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, -9, stdout + stderr)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def recover(self):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "palette.py"), "recover"],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def assert_old(self):
        for path in self.outputs[:2]:
            self.assertEqual(path.read_text(), "last good\n")
        self.assertFalse(self.outputs[2].exists())
        self.assertEqual(json.loads((self.cache / "committed.json").read_text()), self.before)
        self.assertEqual((self.cache / "current-mode").read_text().strip(), "dark")

    def assert_clean(self):
        self.assertEqual(list((self.cache / "transactions").iterdir()), [])
        self.assertEqual(list((self.cache / "work").iterdir()), [])
        self.assertEqual(list(self.home.rglob(".yoru-palette-*")), [])

    def test_killed_during_preparation_keeps_old_palette_and_removes_debris(self):
        self.kill_publisher("preparing")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_old()
        self.assert_clean()

    def test_killed_between_replacements_rolls_back_and_resets_uncommitted_intent(self):
        self.kill_publisher("first")
        self.assertEqual(self.outputs[0].read_text(), "new palette\n")
        self.assertEqual(self.outputs[1].read_text(), "last good\n")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_old()
        self.assertEqual(json.loads((self.cache / "intent.json").read_text()), self.before)
        self.assert_clean()
        self.assertEqual(self.recover().returncode, 0, "Recovery must be idempotent")

    def test_killed_after_last_replacement_but_before_commit_still_rolls_back(self):
        self.kill_publisher("all")
        self.assertEqual(self.outputs[2].read_text(), "new palette\n")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_old()
        self.assert_clean()

    def test_killed_after_durable_commit_keeps_new_palette_and_cleans_backups(self):
        self.kill_publisher("committed")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in self.outputs:
            self.assertEqual(path.read_text(), "new palette\n")
        self.assertEqual(json.loads((self.cache / "committed.json").read_text()), self.after)
        self.assertEqual(json.loads((self.cache / "intent.json").read_text()), self.after)
        self.assert_clean()

    def test_killed_rollback_can_be_repeated_without_consuming_backups(self):
        self.kill_publisher("rollback")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_old()
        self.assert_clean()

    def test_normal_invocations_recover_without_a_manual_recover_command(self):
        self.kill_publisher("first")
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "palette.py"),
                                 "wallpaper", str(self.home / "missing.png")],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)  # Invalid image, after recovery.
        self.assertIn("Wallpaper not found", result.stderr)
        self.assert_old()
        self.assert_clean()

    def test_external_edits_are_preserved_and_journal_is_retained(self):
        self.kill_publisher("first")
        self.outputs[0].write_text("a user edit\n")
        result = self.recover()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed outside the transaction", result.stderr)
        self.assertEqual(self.outputs[0].read_text(), "a user edit\n")
        self.assertTrue(list((self.cache / "transactions").glob("*/journal.json")))

    def test_missing_backup_blocks_recovery_without_deleting_evidence(self):
        self.kill_publisher("first")
        journal = next((self.cache / "transactions").glob("*/journal.json"))
        metadata = json.loads(journal.read_text())
        backup = self.store._sibling(metadata["entries"][0], metadata["id"], "old")
        backup.unlink()
        result = self.recover()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.outputs[0].read_text(), "new palette\n")
        self.assertEqual(self.outputs[1].read_text(), "last good\n")
        self.assertTrue(journal.is_file())

    def test_incomplete_first_journal_write_is_cleaned_without_touching_outputs(self):
        directory = self.cache / "transactions" / ("e" * 32)
        directory.mkdir(parents=True)
        temporary = directory / (".yoru-palette-write-" + "f" * 32 + ".tmp")
        temporary.write_text('{"version":')
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_old()
        self.assertFalse(directory.exists())

    def test_committed_snapshot_repairs_missing_state_mirrors(self):
        (self.cache / "current-mode").write_text("light\n")
        (self.cache / "current-wallpaper").unlink()
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.cache / "current-mode").read_text().strip(), "dark")
        self.assertEqual((self.cache / "current-wallpaper").read_text().strip(), self.before["wall"])

    def test_files_and_directories_are_flushed_before_publication_and_commit(self):
        events = []
        fsync = os.fsync
        replace = os.replace
        write_journal = self.store._write_journal
        destinations = {str(target) for _, target in self.targets}

        def sync_and_record(fd):
            fsync(fd)
            events.append(("sync", os.readlink(f"/proc/self/fd/{fd}")))

        def replace_and_record(source, target):
            if str(target) in destinations:
                self.assertIn(("journal", "ready"), events)
            replace(source, target)
            events.append(("replace", str(target)))

        def journal_and_check(directory, journal):
            if journal["phase"] == "ready":
                for entry in journal["entries"]:
                    for suffix in ("new", "old") if entry["existed"] else ("new",):
                        path = self.store._sibling(entry, journal["id"], suffix)
                        self.assertIn(("sync", str(path)), events)
            elif journal["phase"] == "committed":
                for _, target in self.targets:
                    replaced_at = events.index(("replace", str(target)))
                    self.assertIn(("sync", str(target.parent)), events[replaced_at + 1:])
            write_journal(directory, journal)
            events.append(("journal", journal["phase"]))

        with patch("palette_store.os.fsync", side_effect=sync_and_record), \
                patch("palette_store.os.replace", side_effect=replace_and_record), \
                patch.object(self.store, "_write_journal", side_effect=journal_and_check):
            self.store.publish(self.targets)
        self.assertIn(("journal", "committed"), events)

    def test_cleanup_does_not_touch_unrelated_files_or_symlinked_workspaces(self):
        self.kill_publisher("preparing")
        unrelated = self.consumer / "tmp-personal"
        unrelated.write_text("keep me\n")
        personal = self.cache / "work/personal"
        personal.mkdir()
        link = self.cache / "work" / ("render-" + "c" * 32)
        link.symlink_to(personal, target_is_directory=True)
        leftover = self.cache / (".yoru-palette-write-" + "d" * 32 + ".tmp")
        leftover.write_text("interrupted state write")
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unrelated.read_text(), "keep me\n")
        self.assertTrue(personal.is_dir())
        self.assertTrue(link.is_symlink())
        self.assertFalse(leftover.exists())

    def test_recovery_waits_for_a_live_workspace_then_cleans_it_after_process_death(self):
        code = '''
from pathlib import Path
from palette_store import PaletteStore
import sys
store = PaletteStore(Path.home() / ".cache/matugen")
with store.operation(lambda: None):
    with store.workspace("render") as work:
        (Path.home() / "active-work").write_text(str(work))
        sys.stdin.read(1)
'''
        worker = subprocess.Popen([sys.executable, "-B", "-c", code], env=self.env,
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE)
        recovery = None
        try:
            for _ in range(200):
                if (self.home / "active-work").exists():
                    break
                time.sleep(0.01)
            workspace = Path((self.home / "active-work").read_text())
            recovery = subprocess.Popen(
                [sys.executable, "-B", str(SCRIPTS / "palette.py"), "recover"],
                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            with self.assertRaises(subprocess.TimeoutExpired):
                recovery.wait(timeout=0.2)
            self.assertTrue(workspace.is_dir())
            worker.kill()
            worker.communicate(timeout=5)
            stdout, stderr = recovery.communicate(timeout=5)
            self.assertEqual(recovery.returncode, 0, stdout + stderr)
            self.assertFalse(workspace.exists())
        finally:
            for process in (worker, recovery):
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)

    def test_render_child_keeps_workspace_protected_after_parent_dies(self):
        child_code = '''
import time
while True:
    time.sleep(1)
'''
        parent_code = '''
from pathlib import Path
from palette_store import PaletteStore
import os
import subprocess
import sys
store = PaletteStore(Path.home() / ".cache/matugen")
with store.operation(lambda: None) as fd:
    with store.workspace("render") as work:
        (Path.home() / "child-work").write_text(str(work))
        child = subprocess.Popen([sys.executable, "-B", "-c", os.environ["RENDER_CHILD_CODE"]],
                                 pass_fds=(fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (Path.home() / "render-child").write_text(str(child.pid))
        os._exit(0)
'''
        result = subprocess.run([sys.executable, "-B", "-c", parent_code],
                                env=self.env | {"RENDER_CHILD_CODE": child_code},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        recovery = None
        child_pid = None
        try:
            child_pid = int((self.home / "render-child").read_text())
            workspace = Path((self.home / "child-work").read_text())
            recovery = subprocess.Popen(
                [sys.executable, "-B", str(SCRIPTS / "palette.py"), "recover"],
                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            with self.assertRaises(subprocess.TimeoutExpired):
                recovery.wait(timeout=0.2)
            self.assertTrue(workspace.is_dir())
            os.kill(child_pid, signal.SIGKILL)
            child_pid = None
            stdout, stderr = recovery.communicate(timeout=5)
            self.assertEqual(recovery.returncode, 0, stdout + stderr)
            self.assertFalse(workspace.exists())
        finally:
            if child_pid is not None:
                os.kill(child_pid, signal.SIGKILL)
            if recovery is not None:
                if recovery.poll() is None:
                    recovery.kill()
                recovery.communicate(timeout=5)

    def test_login_wrapper_recovers_before_starting_either_consumer(self):
        self.kill_publisher("first")
        scripts = self.home / ".config/hypr/scripts"
        scripts.mkdir(parents=True)
        for name in ("palette.py", "palette_store.py"):
            shutil.copyfile(SCRIPTS / name, scripts / name)
        log = self.home / "startup.log"
        for relative, name in (("waybar/scripts/start-waybar.sh", "bar"),
                               ("swaync/scripts/start-swaync.sh", "notifications"),
                               ("hypr/scripts/set-wall.sh", "wallpaper")):
            script = self.home / ".config" / relative
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text(
                '#!/bin/bash\n'
                f'[[ "$(cat "{self.outputs[0]}")" == "last good" ]] || exit 90\n'
                f'printf "%s\\n" "{name}" >>"{log}"\n'
            )
            script.chmod(0o755)
        result = subprocess.run(["bash", str(SCRIPTS / "start-themed-desktop.sh")],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(log.read_text().splitlines()), {"bar", "notifications", "wallpaper"})
        self.assert_old()
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
