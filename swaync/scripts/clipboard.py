#!/usr/bin/env python3
"""Private Cliphist capture and a searchable Yoru picker.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import unicodedata


MAX_ITEMS = 250
MAX_BYTES = 5_000_000  # Cliphist 0.7's own per-item limit.
SCRIPT = Path(__file__).resolve()


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def state_dir():
    folder = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "yoru"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def runtime_dir():
    # Do not put history locks or IPC files in a shared /tmp fallback.
    root = os.environ.get("XDG_RUNTIME_DIR")
    if not root:
        raise RuntimeError("A private XDG_RUNTIME_DIR is required")
    info = Path(root).lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("A private XDG_RUNTIME_DIR is required")
    folder = Path(root) / "yoru-clipboard"
    folder.mkdir(mode=0o700, exist_ok=True)
    info = folder.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("Unsafe clipboard runtime directory")
    return folder


@contextmanager
def locked(name, blocking=True):
    descriptor = os.open(runtime_dir() / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        fcntl.flock(handle, flags)
        yield


def paused():
    return (state_dir() / "clipboard-paused").exists()


def set_paused(value):
    with locked("store.lock"):
        flag = state_dir() / "clipboard-paused"
        if value:
            flag.touch(mode=0o600)
        else:
            flag.unlink(missing_ok=True)


def cliphist(command, data=None):
    # Keep the user's DB path/configuration; never create a second history DB.
    return subprocess.run(
        ["cliphist", "-max-items", str(MAX_ITEMS), "-max-dedupe-search", str(MAX_ITEMS), command],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=8,
    ).stdout


def store(stream):
    # Clear/nil events must not delete another application's previous entry.
    # wl-clipboard identifies x-kde-passwordManagerHint offers as sensitive.
    if os.environ.get("CLIPBOARD_STATE") != "data" or paused():
        return
    data = stream.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        return
    # Serialize capture with pause/delete/clear so a write cannot race a wipe.
    with locked("store.lock"):
        if not paused():
            cliphist("store", data)


def foreign_watchers(proc=Path("/proc")):
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if not args or Path(os.fsdecode(args[0])).name != "wl-paste" or b"--watch" not in args:
                continue
            if any(b"cliphist" in arg or b"clipboard.py" in arg for arg in args[1:]):
                return True
        except (OSError, ValueError):
            continue
    return False


def watch():
    try:
        with locked("watch.lock", blocking=False):
            if foreign_watchers():
                raise RuntimeError("An existing clipboard-history watcher is already running; not duplicating it")
            children = []

            def stop(*_args):
                for child in children:
                    if child.poll() is None:
                        child.terminate()

            old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
            try:
                for kind in ("text", "image"):
                    children.append(subprocess.Popen(
                        ["wl-paste", "--type", kind, "--watch", sys.executable, str(SCRIPT), "store"],
                        stdin=subprocess.DEVNULL,
                    ))
                # If either watcher exits, clean up the pair; never leave an
                # undetected half-running capture session behind.
                _pid, status = os.wait()
                if os.waitstatus_to_exitcode(status) not in (0, -signal.SIGTERM, -signal.SIGINT):
                    raise RuntimeError("Clipboard capture exited unexpectedly")
            finally:
                stop()
                for child in children:
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                for sig, handler in old_handlers.items():
                    signal.signal(sig, handler)
    except BlockingIOError:
        return  # Login/config reloads may safely invoke this more than once.


def history():
    try:
        data = cliphist("list")
    except subprocess.CalledProcessError as error:
        # Cliphist's read-only list does not create a DB on the first run.
        if b"please store something first" in error.stderr:
            return []
        raise
    records = []
    for line in data.splitlines():
        ident, separator, preview = line.partition(b"\t")
        if separator and ident.isdigit():
            # A clipboard offer is untrusted input, not Rofi row metadata.
            text = "".join(
                char if not unicodedata.category(char).startswith("C") else " "
                for char in preview.decode("utf-8", errors="replace")
            )
            records.append((ident, text))
    return records


def choose(rows, title="Clipboard"):
    result = subprocess.run(
        ["rofi", "-dmenu", "-i", "-no-custom", "-no-markup-rows", "-format", "i",
         "-p", title, "-theme", str(config_home() / "rofi/styles/clipboard.rasi")],
        input="\n".join(rows).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    try:
        index = int(result.stdout.strip())
    except ValueError:
        return None
    return index if 0 <= index < len(rows) else None


def restore(ident):
    data = cliphist("decode", ident)
    # Never convert the payload to a string: image bytes and exact whitespace
    # must survive. wl-copy infers the MIME type from the original payload.
    subprocess.run(["wl-copy"], input=data, stderr=subprocess.DEVNULL, check=True, timeout=8)


def picker():
    try:
        with locked("picker.lock", blocking=False):
            while True:
                records = history()
                is_paused = paused()
                controls = ["󰐊  Resume recording" if is_paused else "󰏤  Pause recording",
                            "󰆴  Delete an entry…", "󰆴  Clear history…"]
                rows = controls + ([preview for _ident, preview in records] or ["History is empty"])
                index = choose(rows)
                if index is None:
                    return
                if index == 0:
                    set_paused(not is_paused)
                elif index == 1:
                    selected = choose([preview for _ident, preview in records], "Delete entry") if records else None
                    if selected is not None:
                        with locked("store.lock"):
                            cliphist("delete", records[selected][0])
                elif index == 2:
                    if choose(["Cancel", "Clear history"], "Clear clipboard history?") == 1:
                        with locked("store.lock"):
                            cliphist("wipe")
                elif records:
                    restore(records[index - len(controls)][0])
                    return
    except BlockingIOError:
        return


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("watch", "store", "picker", "pause", "resume", "status"))
    action = parser.parse_args().action
    try:
        if action == "store":
            store(sys.stdin.buffer)
        elif action == "watch":
            watch()
        elif action == "picker":
            picker()
        elif action == "status":
            print("paused" if paused() else "recording")
        else:
            set_paused(action == "pause")
    except (OSError, RuntimeError, subprocess.SubprocessError):
        # Do not put copied text or backend stderr (which may include a
        # preview) in notifications, logs, or crash reports.
        print("Yoru Clipboard: operation failed; check dependencies and clipboard watcher conflicts.", file=sys.stderr)
        if action == "picker":
            subprocess.run(["notify-send", "Yoru Clipboard", "Clipboard history could not be opened."], check=False)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
