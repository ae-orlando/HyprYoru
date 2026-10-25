#!/usr/bin/env python3
"""Build the pinned Hyprland-Lua compatibility patch; optionally install locally.

Usage: build-waybar.py [--install] [--jobs N] [--source /path/to/already-patched/source]
Requires Waybar's development libraries, Meson, Ninja, a C++20 compiler,
gdbus-codegen (Arch: glib2-devel), and wayland-scanner. Never uses sudo or
restarts a running bar. The distro /usr/bin/waybar is left untouched.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "0.15.0"
SOURCE_SHA = "21c2bbef88c40473c355003582f9331d2f9b8a01efdcce0935edfc5f6b023a3e"
MARKER = "# Managed by Yoru Waybar backports"
OPTIONS = [
    "--prefix=/usr",
    "--sysconfdir=/etc",
    "--buildtype=release",
    "-Doptimization=2",
    "-Dman-pages=disabled",
    "-Dtests=disabled",
    "-Dcava=disabled",
    "-Dsystemd=disabled",
    "-Ddbusmenu-gtk=enabled",
    "-Dpulseaudio=enabled",
    "--wrap-mode=nodownload",
]


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_and_patch(archive, directory, patches):
    with tarfile.open(archive) as package:
        package.extractall(directory, filter="data")
    source = directory / f"Waybar-{VERSION}"
    for patch in patches:
        subprocess.run(
            ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)],
            cwd=source,
            check=True,
        )
    return source


def install(binary, patch_hash):
    data = (
        Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        / "yoru/waybar"
    )
    target = data / "waybar"
    manifest = data / "manifest.json"
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    launcher = config / "waybar/scripts/start-waybar.sh"
    manager = config / "waybar/scripts/desktop-binaries.py"
    link = Path.home() / ".local/bin/waybar"
    manager_link = Path.home() / ".local/bin/yoru-desktop"
    override = config / "systemd/user/waybar.service.d/yoru-backports.conf"
    for path in (launcher, manager):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"Missing executable launcher: {path}")
    if (target.exists() or target.is_symlink()) and not manifest.exists():
        raise RuntimeError(f"Refusing to overwrite an unmanaged binary: {target}")
    if (link.exists() or link.is_symlink()) and (
        not link.is_symlink() or link.resolve() not in (target.resolve(), launcher.resolve())
    ):
        raise RuntimeError(f"Refusing to overwrite an unmanaged command: {link}")
    if (manager_link.exists() or manager_link.is_symlink()) and (
        not manager_link.is_symlink() or manager_link.resolve() != manager.resolve()
    ):
        raise RuntimeError(f"Refusing to overwrite an unmanaged command: {manager_link}")
    if override.exists() and MARKER not in override.read_text():
        raise RuntimeError(f"Refusing to overwrite an unmanaged service override: {override}")
    data.mkdir(parents=True, exist_ok=True)
    # Identical reinstallation must not orphan the running executable's inode.
    if not target.is_file() or checksum(binary) != checksum(target):
        with tempfile.NamedTemporaryFile(prefix=".waybar-", dir=data, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copy2(binary, temporary)
            temporary.chmod(0o755)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "upstream": VERSION,
                "source_sha256": SOURCE_SHA,
                "patch_sha256": patch_hash,
                "binary_sha256": checksum(target),
            },
            indent=2,
        )
        + "\n"
    )
    link.parent.mkdir(parents=True, exist_ok=True)
    for command, destination in ((link, launcher), (manager_link, manager)):
        with tempfile.TemporaryDirectory(prefix=".yoru-link-", dir=link.parent) as directory:
            staging = Path(directory) / "command"
            staging.symlink_to(destination)
            staging.replace(command)
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(MARKER + "\n# Author: ae Orland\n# GitHub: https://github.com/ae-orlando\n"
                        + f'[Service]\nExecStart=\nExecStart="{launcher}"\n')
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(
        f"Installed: {target}\nDistro binary unchanged; running Waybar has not been restarted."
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="install for this user without restarting",
    )
    parser.add_argument(
        "--jobs", type=int, default=2, help="parallel compiler jobs (default: 2)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="reuse a build tree after verifying its source against the pinned archive and patches",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    required = (
        "meson",
        "ninja",
        "c++",
        "gdbus-codegen",
        "wayland-scanner",
        "pkg-config",
        "patch",
    )
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise RuntimeError("Missing build programs: " + ", ".join(missing))
    patches = sorted(HERE.glob("*.patch"))
    if not patches:
        raise RuntimeError("No compatibility patches found")
    patch_hash = hashlib.sha256(
        b"".join(path.read_bytes() for path in patches)
    ).hexdigest()
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "yoru/waybar-build"
    )
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"{VERSION}.tar.gz"
    if not archive.exists():
        with urllib.request.urlopen(
            f"https://codeload.github.com/Alexays/Waybar/tar.gz/refs/tags/{VERSION}",
            timeout=60,
        ) as response:
            downloaded = response.read(20_000_001)
        if (
            len(downloaded) > 20_000_000
            or hashlib.sha256(downloaded).hexdigest() != SOURCE_SHA
        ):
            raise RuntimeError("Downloaded source checksum mismatch")
        archive.write_bytes(downloaded)
    if checksum(archive) != SOURCE_SHA:
        raise RuntimeError(f"Cached archive checksum mismatch; inspect {archive}")
    if args.source:
        source = args.source.resolve()
        if not (source / "meson.build").is_file():
            raise RuntimeError(
                f"Source tree is missing: {source}. Retry without --source to build in the persistent user cache."
            )
        with tempfile.TemporaryDirectory(
            prefix="waybar-source-check-", dir="/tmp/opencode"
        ) as directory:
            expected = extract_and_patch(archive, Path(directory), patches)
            for path in expected.rglob("*"):
                if path.is_file():
                    candidate = source / path.relative_to(expected)
                    if (
                        not candidate.is_file()
                        or candidate.read_bytes() != path.read_bytes()
                    ):
                        raise RuntimeError(
                            f"Source differs from the pinned backport: {candidate}"
                        )
    else:
        work = cache / f"{VERSION}-{patch_hash[:12]}"
        source = work / f"Waybar-{VERSION}"
        stamp = work / "patches-applied"
        if not stamp.exists():
            if source.exists():
                raise RuntimeError(
                    f"Incomplete build source exists; inspect before retrying: {source}"
                )
            work.mkdir(parents=True, exist_ok=True)
            source = extract_and_patch(archive, work, patches)
            stamp.write_text(patch_hash + "\n")
    if not (source / "build/meson-private/coredata.dat").exists():
        subprocess.run(["meson", "setup", "build", *OPTIONS], cwd=source, check=True)
    subprocess.run(
        ["meson", "compile", "-C", "build", "-j", str(args.jobs)],
        cwd=source,
        check=True,
    )
    # Exercise the exact header used by the bar, without any GUI or IPC side effects.
    with tempfile.TemporaryDirectory(
        prefix="waybar-command-test-", dir="/tmp/opencode"
    ) as directory:
        test = Path(directory) / "workspace-test"
        subprocess.run(
            [
                "c++",
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-pedantic",
                "-I",
                str(source / "include"),
                str(HERE / "test-workspace-command.cpp"),
                "-o",
                str(test),
            ],
            check=True,
        )
        subprocess.run([str(test)], check=True)
    binary = source / "build/waybar"
    subprocess.run([str(binary), "--version"], check=True)
    print(f"Built: {binary}")
    if args.install:
        install(binary, patch_hash)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Build interrupted. The running bar was not restarted.")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
