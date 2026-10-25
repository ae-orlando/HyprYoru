#!/usr/bin/env python3
"""Report patched desktop versions and restart one daemon safely.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import fcntl
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

APPS = ("waybar", "swaync")
REPO = Path(__file__).resolve().parents[2]


def home_dir(variable, fallback):
    return Path(os.environ.get(variable) or Path.home() / fallback)


def local_binary(app):
    return home_dir("XDG_DATA_HOME", ".local/share") / "yoru" / app / app


def launcher(app):
    return home_dir("XDG_CONFIG_HOME", ".config") / app / "scripts" / f"start-{app}.sh"


def selected_binary(app):
    binary = local_binary(app)
    return (
        binary
        if binary.is_file() and os.access(binary, os.X_OK)
        else Path("/usr/bin") / app
    )


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def process_ids(app, proc=Path("/proc")):
    result = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (
                entry.stat().st_uid != os.getuid()
                or (entry / "comm").read_text().strip() != app
            ):
                continue
            # A terminated child waiting to be reaped is not a live daemon.
            if (entry / "stat").read_text().rsplit(")", 1)[1].split()[0] != "Z":
                result.append(int(entry.name))
        except (OSError, IndexError):
            continue
    return sorted(result)


def manifest(app):
    return json.loads(local_binary(app).with_name("manifest.json").read_text())


def verify_local(app):
    binary = selected_binary(app)
    if binary != local_binary(app):
        return
    record = manifest(app)
    if digest(binary) != record.get("binary_sha256"):
        raise RuntimeError(
            f"{app}: installed binary does not match its manifest; reinstall a verified build first"
        )


def version(binary):
    result = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, timeout=5
    )
    if result.returncode:
        raise RuntimeError(f"Cannot run {binary}: {result.stderr.strip()}")
    return result.stdout.strip()


def status():
    for app in APPS:
        binary = selected_binary(app)
        print(f"{app}: {version(binary)}")
        print(f"  selected: {binary}")
        if binary == local_binary(app):
            record = manifest(app)
            print(
                "  installed checksum: "
                + (
                    "OK"
                    if digest(binary) == record.get("binary_sha256")
                    else "MISMATCH"
                )
            )
            patches = sorted((REPO / app / "backports").glob("*.patch"))
            patch_hash = hashlib.sha256(
                b"".join(path.read_bytes() for path in patches)
            ).hexdigest()
            print(
                "  repository patches: "
                + (
                    "match installation"
                    if patch_hash == record.get("patch_sha256")
                    else "changed; rebuild before activating"
                )
            )
        ids = process_ids(app)
        if not ids:
            print("  running: not running")
        for pid in ids:
            executable = Path(f"/proc/{pid}/exe")
            try:
                state = (
                    "current selected binary"
                    if digest(executable) == digest(binary)
                    else "different/older binary; restart needed"
                )
                print(f"  running: PID {pid}, {os.readlink(executable)} ({state})")
            except OSError:
                print(f"  running: PID {pid} exited during inspection")


def notification_count():
    result = subprocess.run(
        ["swaync-client", "--skip-wait", "--count"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return int(result.stdout.strip())


def require_safe_inbox(app, ids):
    if app == "swaync" and ids and notification_count() != 0:
        raise RuntimeError(
            "SwayNC still has saved notifications. Review and dismiss them in the center before restarting. Nothing was cleared or restarted."
        )


@contextmanager
def restart_lock():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise RuntimeError("XDG_RUNTIME_DIR is required")
    root = Path(runtime)
    info = root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise RuntimeError("Unsafe user runtime directory")
    fd = os.open(
        root / "yoru-desktop-restart.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    with os.fdopen(fd, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def unit_active(app):
    return (
        subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", app + ".service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def restart(app):
    with restart_lock():
        ids = process_ids(app)
        if len(ids) > 1:
            raise RuntimeError(
                f"Multiple {app} instances are running; refusing to guess which profile to stop"
            )
        verify_local(app)
        expected = selected_binary(app)
        # Check dependencies/loader errors before touching the running program.
        version(expected)
        require_safe_inbox(app, ids)
        child = None
        if unit_active(app):
            unit = subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    app + ".service",
                    "-p",
                    "ExecStart",
                    "--value",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if str(launcher(app)) not in unit:
                raise RuntimeError(
                    f"{app}.service does not use the configured launcher; rerun the build helper with --install first"
                )
            subprocess.run(
                ["systemctl", "--user", "restart", app + ".service"], check=True
            )
        else:
            for pid in ids:
                os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 8
            while process_ids(app):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"{app} did not stop gracefully; no forced kill was attempted"
                    )
                time.sleep(0.05)
            logs = home_dir("XDG_STATE_HOME", ".local/state") / "yoru"
            logs.mkdir(mode=0o700, parents=True, exist_ok=True)
            with (logs / (app + ".log")).open("a") as output:
                child = subprocess.Popen(
                    [str(launcher(app))],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=output,
                    start_new_session=True,
                )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if child is not None and child.poll() is not None:
                raise RuntimeError(f"{app} exited during startup; inspect its user log")
            live = process_ids(app)
            if len(live) == 1 and live[0] not in ids:
                try:
                    if digest(Path(f"/proc/{live[0]}/exe")) == digest(expected):
                        print(f"{app}: restarted as PID {live[0]} using {expected}")
                        return
                except OSError:
                    pass
            time.sleep(0.1)
        raise RuntimeError(
            f"{app} did not start with the selected executable within 10 seconds"
        )


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "status",
        help="show selected versions, checksums and the actual running executables",
    )
    reload = commands.add_parser(
        "restart", help="load a selected binary; refuses to lose a SwayNC inbox"
    )
    reload.add_argument("app", choices=APPS)
    args = parser.parse_args()
    try:
        if args.command == "status":
            status()
        else:
            restart(args.app)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
