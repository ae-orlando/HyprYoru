"""Durable, recoverable publication for the wallpaper palette coordinator.

Output replacements are individually atomic, not one filesystem transaction.
A write-ahead journal and retained backups make an interrupted batch reversible.
Only a durably committed batch keeps its new files during recovery.
"""

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path


class StoreError(Exception):
    pass


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def make_dir(path):
    if not path.exists():
        make_dir(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
        sync_dir(path.parent)


def atomic_text(path, text):
    """Replace one small state file, flushing both its contents and its rename."""
    make_dir(path.parent)
    temporary = path.parent / f".yoru-palette-write-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x") as output:
            os.chmod(temporary, 0o600)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise StoreError(f"Not a regular palette file: {path}")
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def copy_sync(source, destination):
    """Create a new sibling file without following/replacing an existing file."""
    with source.open("rb") as incoming, destination.open("xb") as output:
        shutil.copyfileobj(incoming, output)
        os.fchmod(output.fileno(), stat.S_IMODE(source.stat().st_mode))
        output.flush()
        os.fsync(output.fileno())


class PaletteStore:
    def __init__(self, root):
        self.root = root
        self.transactions = root / "transactions"
        self.work = root / "work"

    @staticmethod
    def _private_directory(path):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise StoreError(f"Invalid palette storage directory: {path}")
        make_dir(path)

    @contextmanager
    def lock(self, name):
        make_dir(self.root)
        with (self.root / name).open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def operation(self, reconcile, exclusive=False):
        """Recover only when idle; do not delete another request's live work.

        The admission lock prevents new shared holders from starving explicit
        recovery. Normal requests can overlap. Pass the yielded fd to render
        children so they remain protected if their parent is killed.
        """
        make_dir(self.root)
        with (self.root / "active.lock").open("a+") as active:
            with self.lock("admission.lock"):
                if exclusive:
                    fcntl.flock(active, fcntl.LOCK_EX)
                    idle = True
                else:
                    try:
                        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        idle = True
                    except BlockingIOError:
                        fcntl.flock(active, fcntl.LOCK_SH)
                        idle = False
                if idle:
                    with self.lock("publish.lock"):
                        self._recover()
                        self._clean_work()
                        reconcile()
                    if not exclusive:
                        fcntl.flock(active, fcntl.LOCK_SH)
            yield active.fileno()

    @contextmanager
    def workspace(self, kind):
        if kind not in ("render", "backdrop"):
            raise StoreError(f"Unknown palette workspace: {kind}")
        self._private_directory(self.work)
        directory = self.work / f"{kind}-{uuid.uuid4().hex}"
        directory.mkdir(mode=0o700)
        try:
            yield directory
        finally:
            # This exact private directory is ours, not a general cache sweep.
            shutil.rmtree(directory)

    def _clean_work(self):
        if self.work.exists():
            self._private_directory(self.work)
            for path in self.work.iterdir():
                if (
                    re.fullmatch(r"(?:render|backdrop)-[0-9a-f]{32}", path.name)
                    and path.is_dir() and not path.is_symlink()
                ):
                    shutil.rmtree(path)
            sync_dir(self.work)
        self._clean_atomic_writes(self.root)

    @staticmethod
    def _clean_atomic_writes(directory):
        for path in directory.iterdir():
            if (
                re.fullmatch(r"\.yoru-palette-write-[0-9a-f]{32}\.tmp", path.name)
                and path.is_file() and not path.is_symlink()
            ):
                path.unlink()
        sync_dir(directory)

    @staticmethod
    def _sibling(entry, transaction_id, suffix):
        target = Path(entry["target"])
        return target.parent / f".yoru-palette-{transaction_id}-{entry['index']}.{suffix}"

    @staticmethod
    def _write_journal(directory, journal):
        atomic_text(directory / "journal.json", json.dumps(journal) + "\n")

    def _read_journal(self, directory):
        def require(condition, message):
            if not condition:
                raise ValueError(message)

        try:
            path = directory / "journal.json"
            if path.is_symlink():
                raise ValueError("journal is a symlink")
            journal = json.loads(path.read_text())
            require(
                journal["version"] == 1 and journal["id"] == directory.name,
                "invalid journal version/ID",
            )
            require(
                journal["phase"] in ("preparing", "ready", "committed", "rolled-back"),
                "invalid journal phase",
            )
            entries = journal["entries"]
            require(isinstance(entries, list) and entries, "missing journal entries")
            targets = set()
            for index, entry in enumerate(entries):
                target = Path(entry["target"])
                require(
                    target.is_absolute() and ".." not in target.parts,
                    "invalid output path",
                )
                require(
                    type(entry["index"]) is int and entry["index"] == index
                    and type(entry["existed"]) is bool,
                    "invalid output entry",
                )
                require(entry["target"] not in targets, "duplicate output paths")
                targets.add(entry["target"])
                for key in ("before", "after"):
                    require(
                        (key == "before" and not entry["existed"] and entry[key] is None)
                        or (isinstance(entry[key], str)
                            and re.fullmatch(r"[0-9a-f]{64}", entry[key])),
                        "invalid output checksum",
                    )
            return journal
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StoreError(
                f"Cannot safely recover palette journal {directory}: {exc}"
            ) from exc

    def _cleanup(self, directory, journal):
        # Both success and rollback retain their journal until sibling files
        # are durably removed. A second crash can repeat this cleanup safely.
        for entry in journal["entries"]:
            for suffix in ("new", "old", "restore"):
                self._sibling(entry, journal["id"], suffix).unlink(missing_ok=True)
            sync_dir(Path(entry["target"]).parent)
        self._clean_atomic_writes(directory)
        (directory / "journal.json").unlink()
        sync_dir(directory)
        directory.rmdir()
        sync_dir(self.transactions)

    def _recover_transaction(self, directory):
        journal = self._read_journal(directory)
        if journal["phase"] == "ready":
            # Validate the whole batch before touching anything. Unexpected
            # edits or missing backups need inspection, not destructive guesses.
            for entry in journal["entries"]:
                target = Path(entry["target"])
                if target.is_symlink():
                    raise StoreError(f"Palette recovery refuses a symlink: {target}")
                if target.exists() and digest(target) not in (
                    entry["before"], entry["after"]
                ):
                    raise StoreError(
                        f"Palette output changed outside the transaction: {target}"
                    )
                if entry["existed"]:
                    backup = self._sibling(entry, journal["id"], "old")
                    if digest(backup) != entry["before"]:
                        raise StoreError(f"Palette backup is damaged: {backup}")
            for entry in journal["entries"]:
                target = Path(entry["target"])
                if entry["existed"]:
                    restore = self._sibling(entry, journal["id"], "restore")
                    restore.unlink(missing_ok=True)
                    copy_sync(self._sibling(entry, journal["id"], "old"), restore)
                    os.replace(restore, target)
                else:
                    target.unlink(missing_ok=True)
                sync_dir(target.parent)
            journal["phase"] = "rolled-back"
            self._write_journal(directory, journal)
        self._cleanup(directory, journal)

    def _recover(self):
        if not self.transactions.exists():
            return
        self._private_directory(self.transactions)
        for directory in sorted(self.transactions.iterdir()):
            if not re.fullmatch(r"[0-9a-f]{32}", directory.name):
                continue
            if directory.is_symlink() or not directory.is_dir():
                raise StoreError(f"Invalid palette transaction directory: {directory}")
            if (directory / "journal.json").exists():
                self._recover_transaction(directory)
            else:
                # No output sidecars are created before the first journal has
                # been flushed. Only an interrupted journal write can be here.
                self._clean_atomic_writes(directory)
                directory.rmdir()
                sync_dir(self.transactions)

    def publish(self, targets):
        with self.lock("publish.lock"):
            self._recover()
            self._publish(targets)

    def _publish(self, targets):
        transaction_id = uuid.uuid4().hex
        entries = []
        normalized = []
        for index, (source, target) in enumerate(targets):
            if target.is_symlink():
                raise StoreError(f"Refusing to replace a theme symlink: {target}")
            make_dir(target.parent)
            target = target.parent.resolve() / target.name
            entries.append(
                {
                    "index": index,
                    "target": str(target),
                    "existed": target.exists(),
                    "before": digest(target) if target.exists() else None,
                    "after": digest(source),
                }
            )
            normalized.append((source, target))
        if not entries or len({entry["target"] for entry in entries}) != len(entries):
            raise StoreError("Empty or duplicate palette output paths")
        self._private_directory(self.transactions)
        directory = self.transactions / transaction_id
        directory.mkdir(mode=0o700)
        sync_dir(self.transactions)
        journal = {
            "version": 1,
            "id": transaction_id,
            "phase": "preparing",
            "entries": entries,
        }
        # The full list of sidecars is durable *before* any are created.
        self._write_journal(directory, journal)
        try:
            for entry, (source, target) in zip(entries, normalized):
                copy_sync(source, self._sibling(entry, transaction_id, "new"))
                if entry["existed"]:
                    copy_sync(target, self._sibling(entry, transaction_id, "old"))
                sync_dir(target.parent)
            journal["phase"] = "ready"
            self._write_journal(directory, journal)
            for entry, (_, target) in zip(entries, normalized):
                os.replace(self._sibling(entry, transaction_id, "new"), target)
                sync_dir(target.parent)
            journal["phase"] = "committed"
            self._write_journal(directory, journal)
        except BaseException:
            self._recover_transaction(directory)
            raise
        try:
            self._cleanup(directory, journal)
        except OSError as exc:
            # Outputs are already committed. Retain the journal for the next
            # invocation instead of reporting a failed palette/rolling it back.
            print(f"Palette: committed; cleanup deferred: {exc}", file=sys.stderr)
