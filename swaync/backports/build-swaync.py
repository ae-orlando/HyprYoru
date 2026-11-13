#!/usr/bin/env python3
"""Build the pinned SwayNC backports without replacing any pacman-owned files.

Usage: build-swaync.py [--test] [--install] [--jobs N]
Prerequisites: meson ninja vala blueprint-compiler sassc plus SwayNC's runtime
development dependencies (GTK4, libadwaita, gtk4-layer-shell, libgee, json-glib,
granite-7, libpulse, Wayland). Installation never restarts the daemon.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "0.12.6"
# Upstream main after the 0.12.6 tag. Bump SOURCE_REF and SOURCE_SHA256 together.
SOURCE_REF = "b8017a4d1a53debdf0e8766628fb80357eae31e7"
SOURCE_NAME = f"SwayNotificationCenter-{SOURCE_REF}"
SOURCE_SHA256 = "ceb2cd3e5904a12d56e5636cb1e7210e646c0d5f2fe93be0b58df27776f6ee37"
MARKER = "# Managed by Yoru SwayNC backports"
CREDIT = "# Author: ae Orland\n# GitHub: https://github.com/ae-orlando\n"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_managed(path, contents):
    if path.exists() and MARKER not in path.read_text():
        raise RuntimeError(f"Refusing to overwrite an unmanaged file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".yoru-new")
    staging.write_text(MARKER + "\n" + CREDIT + contents)
    staging.replace(path)


def install(binary, patch_hash):
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    target = data / "yoru/swaync/swaync"
    manifest = target.with_name("manifest.json")
    if target.exists() and not manifest.exists():
        raise RuntimeError(f"Refusing to overwrite an unmanaged binary: {target}")
    launcher = config / "swaync/scripts/start-swaync.sh"
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise RuntimeError(f"Missing executable launcher: {launcher}")
    link = Path.home() / ".local/bin/swaync"
    if (link.exists() or link.is_symlink()) and (
        not link.is_symlink() or link.resolve() not in (target.resolve(), launcher.resolve())
    ):
        raise RuntimeError(f"Refusing to overwrite an unmanaged command: {link}")
    manager = config / "waybar/scripts/desktop-binaries.py"
    if not manager.is_file() or not os.access(manager, os.X_OK):
        raise RuntimeError(f"Missing executable maintenance helper: {manager}")
    manager_link = Path.home() / ".local/bin/yoru-desktop"
    if (manager_link.exists() or manager_link.is_symlink()) and (
        not manager_link.is_symlink() or manager_link.resolve() != manager.resolve()
    ):
        raise RuntimeError(f"Refusing to overwrite an unmanaged command: {manager_link}")
    # Preflight all user-level activation overrides before changing anything.
    activation = {
        data
        / "dbus-1/services/org.erikreider.swaync.service": f'[D-BUS Service]\nName=org.freedesktop.Notifications\nExec="{launcher}"\n',
        data
        / "dbus-1/services/org.erikreider.swaync.cc.service": f'[D-BUS Service]\nName=org.erikreider.swaync.cc\nExec="{launcher}"\n',
        config
        / "systemd/user/swaync.service.d/yoru-backports.conf": f'[Service]\nExecStart=\nExecStart="{launcher}"\n',
    }
    for path in activation:
        if path.exists() and MARKER not in path.read_text():
            raise RuntimeError(
                f"Refusing to overwrite an unmanaged activation file: {path}"
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the live process's inode when the installed bits are unchanged.
    if not target.is_file() or digest(binary) != digest(target):
        with tempfile.NamedTemporaryFile(prefix=".swaync-", dir=target.parent, delete=False) as handle:
            staging = Path(handle.name)
        try:
            shutil.copy2(binary, staging)
            staging.chmod(0o755)
            staging.replace(target)
        finally:
            staging.unlink(missing_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "upstream": VERSION,
                "source_ref": SOURCE_REF,
                "source_sha256": SOURCE_SHA256,
                "patch_sha256": patch_hash,
                "binary_sha256": digest(target),
            },
            indent=2,
        )
        + "\n"
    )
    for path, contents in activation.items():
        install_managed(path, contents)
    link.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".yoru-link-", dir=link.parent) as directory:
        staging = Path(directory) / "command"
        staging.symlink_to(launcher)
        staging.replace(link)
    manager_link.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".yoru-link-", dir=manager_link.parent) as directory:
        staging = Path(directory) / "command"
        staging.symlink_to(manager)
        staging.replace(manager_link)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(
        f"Installed: {target}\nDistro /usr/bin/swaync is unchanged. The running daemon has not been restarted."
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="test actual widgets on private D-Bus with a fake backlight",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="install for this user, without restarting",
    )
    parser.add_argument("--jobs", type=int, default=2, help="parallel compiler jobs (default: 2)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    required = ("meson", "ninja", "valac", "blueprint-compiler", "sassc", "patch")
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise RuntimeError("Missing build programs: " + ", ".join(missing))
    patches = sorted(HERE.glob("*.patch"))
    if not patches:
        raise RuntimeError("No backport patches found")
    patch_hash = hashlib.sha256(
        b"".join(path.read_bytes() for path in patches)
    ).hexdigest()
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "yoru/swaync-build"
    )
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"main-{SOURCE_REF[:12]}.tar.gz"
    if not archive.exists():
        with urllib.request.urlopen(
            f"https://codeload.github.com/ErikReider/SwayNotificationCenter/tar.gz/{SOURCE_REF}",
            timeout=60,
        ) as response:
            downloaded = response.read(20_000_001)
        if (
            len(downloaded) > 20_000_000
            or hashlib.sha256(downloaded).hexdigest() != SOURCE_SHA256
        ):
            raise RuntimeError("Downloaded source checksum mismatch")
        archive.write_bytes(downloaded)
    if digest(archive) != SOURCE_SHA256:
        raise RuntimeError(f"Cached source checksum mismatch; inspect {archive}")
    work = cache / f"{VERSION}-main-{SOURCE_REF[:12]}-{patch_hash[:12]}"
    source = work / SOURCE_NAME
    stamp = work / "patches-applied"
    if not stamp.exists():
        if source.exists():
            raise RuntimeError(
                f"Incomplete build source exists; inspect it before retrying: {source}"
            )
        work.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as package:
            package.extractall(work, filter="data")
        for path in patches:
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(path)],
                cwd=source,
                check=True,
            )
        stamp.write_text(patch_hash + "\n")
    options = [
        "--prefix=/usr",
        "--sysconfdir=/etc",
        "--buildtype=release",
        "-Dman-pages=false",
        "-Dsystemd-service=false",
        "-Dzsh-completions=false",
        "-Dbash-completions=false",
        "-Dfish-completions=false",
    ]
    if not (source / "build/meson-private/coredata.dat").exists():
        subprocess.run(["meson", "setup", "build", *options], cwd=source, check=True)
    subprocess.run(
        ["meson", "compile", "-C", "build", "-j", str(args.jobs)], cwd=source, check=True
    )
    subprocess.run(
        ["meson", "test", "-C", "build", "--print-errorlogs"], cwd=source, check=True
    )
    if args.test:
        subprocess.run(
            [sys.executable, "-B", str(HERE / "test-backports.py"), str(source), "--jobs", str(args.jobs)],
            check=True,
        )
    binary = source / "build/src/swaync"
    subprocess.run([str(binary), "--version"], check=True)
    print(f"Built: {binary}")
    if args.install:
        install(binary, patch_hash)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Build interrupted. The running notification daemon was not restarted.")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
