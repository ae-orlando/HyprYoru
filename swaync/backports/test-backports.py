#!/usr/bin/env python3
"""Build real widget regressions against a fake backlight and private D-Bus.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent


def run_inside(binary, config, style, root):
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    wayland = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
    if not wayland.startswith("/"):
        wayland = str(Path(os.environ["XDG_RUNTIME_DIR"]) / wayland)
    env = os.environ | {"YORU_TEST_SYSROOT": str(root), "GSETTINGS_BACKEND": "memory", "GTK_A11Y": "none",
                        "GIO_USE_VFS": "local", "GTK_USE_PORTAL": "0", "GDK_DEBUG": "no-portals",
                        "XDG_RUNTIME_DIR": str(runtime), "WAYLAND_DISPLAY": wayland}
    # Never connect to the real system bus, even if the test-source seam breaks.
    env["DBUS_SYSTEM_BUS_ADDRESS"] = "unix:path=/nonexistent-yoru-test-bus"
    fake = subprocess.Popen([str(binary), "--fake-login"], env=env)
    try:
        deadline = time.monotonic() + 5
        while not (root / "ready").exists():
            if fake.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Fake login service did not start")
            time.sleep(0.02)
        subprocess.run([str(binary), str(config), str(style)], env=env, check=True, timeout=30)
    finally:
        fake.terminate()
        fake.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--style", type=Path)
    parser.add_argument("--sysroot", type=Path)
    args = parser.parse_args()
    if args.inside:
        run_inside(args.source, args.config, args.style, args.sysroot)
        return
    with tempfile.TemporaryDirectory(prefix="swaync-regression-", dir="/tmp/opencode") as temporary:
        root = Path(temporary)
        source = root / "source"
        shutil.copytree(args.source, source, ignore=shutil.ignore_patterns("build", ".git"))
        # Only the test copy receives these two seams. Production source and
        # binaries continue to use /sys and the actual system bus.
        util = source / "src/controlCenter/widgets/backlight/backlightUtil.vala"
        text = util.read_text()
        assert text.count('"/sys"') == 2 and text.count("BusType.SYSTEM") == 1
        util.write_text(text.replace('"/sys"', 'Environment.get_variable ("YORU_TEST_SYSROOT")').replace("BusType.SYSTEM", "BusType.SESSION"))
        shutil.copy2(HERE / "regression.vala", source / "src/yoru-regression.vala")
        meson = source / "src/meson.build"
        meson.write_text(meson.read_text() + "\nexecutable('yoru-regression', [app_sources, app_resources, 'yoru-regression.vala'], vala_args: args + ['--main=SwayNotificationCenter.YoruRegression.main'], dependencies: app_deps, install: false)\n")
        options = ["--prefix=/usr", "--sysconfdir=/etc", "--buildtype=release", "-Dman-pages=false",
                   "-Dsystemd-service=false", "-Dzsh-completions=false", "-Dbash-completions=false", "-Dfish-completions=false"]
        subprocess.run(["meson", "setup", "build", *options], cwd=source, check=True)
        subprocess.run(["meson", "compile", "-C", "build", "-j", "4", "yoru-regression"], cwd=source, check=True)
        device = root / "fake-sys/class/backlight/test"
        device.mkdir(parents=True)
        (device / "brightness").write_text("370")
        (device / "max_brightness").write_text("1000")
        (root / "fake-sys/writes").write_text("0")
        config = json.loads((HERE.parent / "config.json").read_text())
        config["widget-config"]["backlight"]["device"] = "test"
        fixture = root / "config.json"
        fixture.write_text(json.dumps(config))
        # No service directories: GTK cannot accidentally activate a second
        # portal/accessibility stack against the live session's runtime sockets.
        bus_config = root / "dbus.conf"
        bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(root) + '</listen>'
                              '<auth>EXTERNAL</auth><policy context="default"><allow own="*"/>'
                              '<allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        subprocess.run(["dbus-run-session", "--config-file", str(bus_config), "--", sys.executable, "-B", str(Path(__file__).resolve()),
                        str(source / "build/src/yoru-regression"), "--inside", "--config", str(fixture),
                        "--style", str(HERE.parent / "style.css"), "--sysroot", str(root / "fake-sys")], check=True)


if __name__ == "__main__":
    main()
