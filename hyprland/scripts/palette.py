#!/usr/bin/env python3
"""Apply Matugen palettes without publishing partial or superseded renders.

The live Matugen config remains the source of truth, including --no-shell
installations. Each invocation renders to an isolated temporary config; only
the latest successful render is installed and its consumers reloaded.
"""

import argparse
import json
import subprocess
import sys
import time
import tomllib
import uuid
from contextlib import contextmanager
from pathlib import Path

from palette_store import PaletteStore, StoreError, atomic_text, sync_dir

HOME = Path.home()
CACHE = HOME / ".cache/matugen"
INTENT = CACHE / "intent.json"
WALL_FILE = CACHE / "current-wallpaper"
MODE_FILE = CACHE / "current-mode"
APPLIED = CACHE / "current-request"
COMMITTED = CACHE / "committed.json"
CONFIG = HOME / ".config/matugen/config.toml"
WALL_DIR = HOME / "Pictures/wallpapers"
SEED_DIR = HOME / ".config/hypr/wallpapers"
TRANSITION = 2
STORE = PaletteStore(CACHE)
ACTIVE_FD = None


class PaletteError(Exception):
    pass


@contextmanager
def locked(name):
    with STORE.lock(name):
        yield


def reconcile():
    """Called only with no live operations, after journal recovery is complete."""
    if COMMITTED.exists():
        try:
            state = json.loads(COMMITTED.read_text())
            if (
                not isinstance(state, dict)
                or state.get("mode") not in ("dark", "light")
                or not isinstance(state.get("wall"), str)
                or not isinstance(state.get("id"), str)
            ):
                raise ValueError("invalid committed palette state")
        except (OSError, ValueError) as exc:
            raise PaletteError(f"Cannot read last committed palette: {exc}") from exc
        for path, value in (
            (WALL_FILE, state["wall"]),
            (MODE_FILE, state["mode"]),
            (APPLIED, state["id"]),
        ):
            if not path.is_file() or path.read_text().strip() != value:
                atomic_text(path, value + "\n")
        atomic_text(INTENT, json.dumps(state) + "\n")
    elif WALL_FILE.exists() or MODE_FILE.exists():
        # Upgrade path for a palette saved before transactional state existed.
        state = {
            "id": (
                APPLIED.read_text().strip() if APPLIED.is_file() else uuid.uuid4().hex
            ),
            "wall": WALL_FILE.read_text().strip() if WALL_FILE.is_file() else "",
            "mode": current_mode(),
            "gtk_update": False,
        }
        atomic_text(INTENT, json.dumps(state) + "\n")
    elif INTENT.exists():
        # An interrupted first render has no successful request to restore.
        INTENT.unlink()
        sync_dir(CACHE)


@contextmanager
def operation(exclusive=False):
    global ACTIVE_FD
    with STORE.operation(reconcile, exclusive=exclusive) as descriptor:
        ACTIVE_FD = descriptor
        try:
            yield
        finally:
            ACTIVE_FD = None


def child_fds():
    return (ACTIVE_FD,) if ACTIVE_FD is not None else ()


def intent():
    try:
        state = json.loads(INTENT.read_text())
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def current_mode():
    try:
        mode = MODE_FILE.read_text().strip()
    except OSError:
        mode = "dark"
    return mode if mode in ("light", "dark") else "dark"


def current_wall():
    try:
        wall = Path(WALL_FILE.read_text().strip()).expanduser()
        if wall.is_file():
            return wall
    except OSError:
        pass
    for wall in (WALL_DIR / "anime3.png", SEED_DIR / "anime3.png"):
        if wall.is_file():
            return wall
    raise PaletteError("No saved or seed wallpaper is available")


def select_wallpaper(args):
    if args == ["--pick"]:
        if not WALL_DIR.is_dir():
            raise PaletteError(f"Wallpaper directory not found: {WALL_DIR}")
        choices = sorted(
            wall.name
            for wall in WALL_DIR.iterdir()
            if wall.is_file()
            and wall.suffix.lower()
            in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")
        )
        if not choices:
            raise PaletteError(f"No wallpapers in {WALL_DIR}")
        menu = subprocess.run(
            [
                "rofi",
                "-dmenu",
                "-i",
                "-p",
                "Wallpaper",
                "-theme",
                str(HOME / ".config/rofi/launchers/type-6/style-9.rasi"),
            ],
            input="\n".join(choices) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if menu.returncode or not menu.stdout.strip():
            return None  # Cancelling a picker must not change the wallpaper.
        wall = WALL_DIR / menu.stdout.strip()
    elif not args:
        wall = current_wall()
    elif len(args) == 1 and not args[0].startswith("--"):
        wall = Path(args[0]).expanduser()
    else:
        raise PaletteError("Usage: set-wall.sh [/path/to/wallpaper] [--pick]")
    if not wall.is_file():
        raise PaletteError(f"Wallpaper not found: {wall}")
    return wall.resolve()


def run_awww(wall, wait=False):
    if wait:
        for _ in range(30):
            if (
                subprocess.run(
                    ["awww", "query"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.1)
        else:
            raise PaletteError("awww-daemon is not ready; wallpaper unchanged")
    subprocess.run(
        [
            "awww",
            "img",
            "--transition-type",
            "center",
            "--transition-duration",
            str(TRANSITION),
            str(wall),
        ],
        check=True,
    )


def request(wall=None, toggle=False):
    with locked("request.lock"):
        previous = intent()
        mode = (
            previous.get("mode")
            if previous.get("mode") in ("light", "dark")
            else current_mode()
        )
        if toggle:
            mode = "light" if mode == "dark" else "dark"
            wall = (
                Path(previous.get("wall", ""))
                if previous.get("wall")
                else current_wall()
            )
            if not wall.is_file():
                wall = current_wall()
        else:
            run_awww(wall, wait=True)
        desired = {
            "id": uuid.uuid4().hex,
            "wall": str(wall),
            "mode": mode,
            "gtk_update": toggle,
        }
        atomic_text(INTENT, json.dumps(desired) + "\n")
    return desired


def toml_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return json.dumps(value)
    raise PaletteError(f"Unsupported Matugen config value: {value!r}")


def stage_config(root):
    if not CONFIG.is_file():
        raise PaletteError(f"Matugen config missing: {CONFIG}")
    config = tomllib.loads(CONFIG.read_text())
    templates = config.get("templates", {})
    if not templates:
        raise PaletteError("Matugen has no configured templates")
    lines = ["[config]"]
    for key, value in config.get("config", {}).items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {toml_value(value)}")
    lines.extend(["", "[config.wallpaper]", "set = false", 'command = "true"', ""])
    targets = []
    for name, template in templates.items():
        source = Path(template["input_path"]).expanduser()
        destination = Path(template["output_path"]).expanduser()
        if not source.is_file() or not destination.is_absolute():
            raise PaletteError(f"Invalid template paths for {name}")
        staged = root / f"{name}{destination.suffix}"
        lines.extend(
            [
                f"[templates.{name}]",
                f"input_path = {toml_value(str(source))}",
                f"output_path = {toml_value(str(staged))}",
                "",
            ]
        )
        targets.append((staged, destination))
    config_path = root / "config.toml"
    config_path.write_text("\n".join(lines))
    return config_path, targets


def publish(targets):
    STORE.publish(targets)


def reload_consumers():
    # Isolated renders cannot run Matugen's per-template post_hooks. Fire the
    # same graceful signals once, after *all* generated files have landed.
    for cmd in (
        ["hyprctl", "reload"],
        ["pkill", "-SIGUSR2", "waybar"],
        ["swaync-client", "-rs"],
        ["pkill", "-SIGUSR1", "kitty"],
        ["pkill", "-USR2", "btop"],
    ):
        try:
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        except OSError:
            pass  # Installing themes is valid without a running desktop.


def gtk_mode(mode):
    theme = "adw-gtk3-dark" if mode == "dark" else "adw-gtk3"
    preference = "prefer-dark" if mode == "dark" else "prefer-light"
    failed = []
    for key, value in (("gtk-theme", theme), ("color-scheme", preference)):
        try:
            result = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", key, value],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode:
                failed.append(key)
        except OSError:
            failed.append(key)
    if failed:
        print(
            f"Palette: could not update GTK preferences: {', '.join(failed)}",
            file=sys.stderr,
        )


def prepare_backdrop(desired):
    # Conversion overlaps the wallpaper transition, but the worker cannot
    # publish until this exact request has committed its palette.
    try:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "backdrop",
                desired["wall"],
                desired["id"],
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        print(f"Palette: backdrop deferred: {exc}", file=sys.stderr)


def render(desired):
    # Wallpaper already transitioned; generation need not block other requests.
    if desired["id"] != intent().get("id"):
        return False
    with locked("render.lock"):
        if desired["id"] != intent().get("id"):
            return False
        with STORE.workspace("render") as directory:
            config, targets = stage_config(directory)
            result = subprocess.run(
                [
                    "matugen",
                    "--config",
                    str(config),
                    "image",
                    desired["wall"],
                    "--mode",
                    desired["mode"],
                    "--type",
                    "scheme-tonal-spot",
                ],
                text=True,
                capture_output=True,
                check=False,
                pass_fds=child_fds(),
            )
            if result.returncode:
                raise PaletteError(f"Matugen failed: {result.stderr or result.stdout}")
            for source, _ in targets:
                if not source.is_file() or not source.stat().st_size:
                    raise PaletteError(f"Matugen did not produce {source.name}")
                content = source.read_text()
                if "{{" in content or "<*" in content:
                    raise PaletteError(f"Unresolved expressions in {source.name}")
                if source.suffix == ".json":
                    json.loads(content)
            wall_state = directory / "current-wallpaper"
            mode_state = directory / "current-mode"
            request_state = directory / "current-request"
            committed_state = directory / "committed.json"
            wall_state.write_text(desired["wall"] + "\n")
            mode_state.write_text(desired["mode"] + "\n")
            request_state.write_text(desired["id"] + "\n")
            committed_state.write_text(json.dumps(desired) + "\n")
            with locked("request.lock"):
                if desired["id"] != intent().get("id"):
                    return False
                publish(
                    targets
                    + [
                        (wall_state, WALL_FILE),
                        (mode_state, MODE_FILE),
                        (request_state, APPLIED),
                        (committed_state, COMMITTED),
                    ]
                )
            # A wallpaper change must not override GTK preferences when the
            # installer was run without application defaults. Only an explicit
            # theme toggle changes the user's GTK theme and color scheme.
            if desired["gtk_update"]:
                gtk_mode(desired["mode"])
            # Even if a newer request arrives during publication, this one
            # may become the rollback target if that newer render fails.
            reload_consumers()
            return True


def rollback_request(desired):
    with locked("request.lock"):
        if intent().get("id") != desired["id"]:
            return
        previous_wall = WALL_FILE.read_text().strip() if WALL_FILE.is_file() else ""
        if (
            previous_wall
            and Path(previous_wall).is_file()
            and previous_wall != desired["wall"]
        ):
            try:
                run_awww(Path(previous_wall))
            except (OSError, subprocess.CalledProcessError):
                pass
        previous = {
            "id": uuid.uuid4().hex,
            "wall": previous_wall,
            "mode": current_mode(),
        }
        atomic_text(INTENT, json.dumps(previous) + "\n")


def backdrop(wall, request_id):
    """Build real PNGs during transition; publish only after palette commit."""
    with STORE.workspace("backdrop") as root:
        if intent().get("id") != request_id:
            return
        lock_image = root / "lock.png"
        blur_image = root / "blur.png"
        subprocess.run(
            ["magick", f"{wall}[0]", "-auto-orient", lock_image],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=child_fds(),
        )
        if intent().get("id") != request_id:
            return
        subprocess.run(
            [
                "magick",
                f"{wall}[0]",
                "-auto-orient",
                "-resize",
                "50%",
                "-blur",
                "0x8",
                blur_image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=child_fds(),
        )
        rofi = HOME / ".cache/rofi"
        hyprlock = HOME / ".cache/hyprlock"
        rasi = root / "wallpaper.rasi"
        # JSON quoting is compatible with Rasi string escapes.
        rasi.write_text(
            f"* {{\n    current-image: url({json.dumps(str(rofi / 'blurred_wallpaper.png'))}, height);\n}}\n"
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with locked("request.lock"):
                if intent().get("id") != request_id:
                    return
                if APPLIED.is_file() and APPLIED.read_text().strip() == request_id:
                    publish(
                        [
                            (lock_image, hyprlock / "wallpaper.png"),
                            (blur_image, rofi / "blurred_wallpaper.png"),
                            (rasi, rofi / "current-wallpaper.rasi"),
                        ]
                    )
                    (CACHE / "backdrop-error").unlink(missing_ok=True)
                    return
            time.sleep(0.1)
        raise PaletteError("Timed out waiting for the wallpaper palette")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pick", action="store_true", help="Pick a wallpaper with Rofi"
    )
    parser.add_argument(
        "action", choices=("wallpaper", "toggle", "backdrop", "recover")
    )
    parser.add_argument("args", nargs="*")
    options = parser.parse_args()
    if options.action == "recover":
        if options.args or options.pick:
            parser.error("recover takes no arguments")
        with operation(exclusive=True):
            print("Palette recovery complete.")
        return
    with operation():
        apply(options, parser)


def apply(options, parser):
    if options.action == "backdrop":
        if len(options.args) != 2:
            parser.error("backdrop expects a wallpaper and request ID")
        backdrop(*options.args)
        return
    if options.action == "toggle":
        if options.args or options.pick:
            parser.error("toggle takes no arguments")
        desired = request(toggle=True)
        prepare_backdrop(desired)
    else:
        wall = select_wallpaper(
            ["--pick"] if options.pick and not options.args else options.args
        )
        if options.pick and options.args:
            parser.error("--pick cannot be combined with a wallpaper path")
        if wall is None:
            return
        desired = request(wall)
        prepare_backdrop(desired)
        time.sleep(TRANSITION)
    try:
        applied = render(desired)
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
        PaletteError,
        StoreError,
    ) as exc:
        rollback_request(desired)
        raise PaletteError(str(exc)) from exc
    if applied:
        print(f"Wallpaper + {desired['mode']} palette applied: {desired['wall']}")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
        PaletteError,
        StoreError,
    ) as exc:
        if len(sys.argv) > 1 and sys.argv[1] == "backdrop":
            # Error reporting happens after the operation lock is released.
            # Serialize with recovery's state-file cleanup as well.
            with locked("publish.lock"):
                if intent().get("id") == sys.argv[-1]:
                    atomic_text(CACHE / "backdrop-error", str(exc) + "\n")
        print(f"Palette: {exc}", file=sys.stderr)
        sys.exit(1)
