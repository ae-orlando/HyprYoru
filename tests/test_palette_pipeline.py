#!/usr/bin/env python3
"""Exercise real Matugen with fake desktop commands and a disposable HOME."""

import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "hyprland/scripts/palette.py"
TEMP_ROOT = Path("/tmp/opencode")
sys.path.insert(0, str(SCRIPT.parent))

def tiny_png(rgb):
    """Construct a valid 2x2 RGB PNG without depending on host images."""
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(
            ">I", zlib.crc32(name + data))

    pixels = (b"\x00" + bytes(rgb) * 2) * 2
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


@unittest.skipUnless(shutil.which("matugen") and shutil.which("magick"),
                     "matugen and magick required for pipeline tests")
class PalettePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hypryoru-pipeline-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        config = self.home / ".config/matugen"
        config.mkdir(parents=True)
        (config / "config.toml").write_bytes((REPO / "matugen/config.toml").read_bytes())
        (config / "templates").symlink_to(REPO / "matugen/templates", target_is_directory=True)
        self.walls = self.home / "Pictures/wallpapers"
        self.walls.mkdir(parents=True)
        self.first = self.walls / "warm wall.png"
        self.first.write_bytes(tiny_png((200, 96, 72)))
        self.second = self.walls / "cool wall.png"
        self.second.write_bytes(tiny_png((48, 88, 212)))
        bins = self.root / "bin"
        bins.mkdir()
        for program in ("awww", "hyprctl", "pkill", "swaync-client", "gsettings"):
            stub = bins / program
            stub.write_text(
                "#!/bin/bash\n"
                '[[ "${1:-}" == query ]] && exit 0\n'
                'printf "%s %s\\n" "${0##*/}" "$*" >>"$PALETTE_TEST_LOG"\n'
            )
            stub.chmod(0o755)
        (bins / "matugen").write_text(
            "#!/bin/bash\n"
            'if [[ -n "${PALETTE_SLOW_WALL:-}" && "$*" == *"$PALETTE_SLOW_WALL"* ]]; then\n'
            '  touch "$PALETTE_SLOW_MARKER"\n'
            '  sleep 1\n'
            'fi\n'
            'exec /usr/bin/matugen "$@"\n'
        )
        (bins / "matugen").chmod(0o755)
        (bins / "rofi").write_text("#!/bin/sh\nexit 1\n")
        (bins / "rofi").chmod(0o755)
        self.log = self.root / "commands.log"
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
            XDG_CACHE_HOME=str(self.home / ".cache"),
            PATH=f"{bins}:{os.environ['PATH']}", PALETTE_TEST_LOG=str(self.log),
        )
        # Backdrops intentionally outlive the foreground wallpaper command.
        # Wait before TemporaryDirectory.cleanup, not for a guessed sleep.
        self.addCleanup(self.wait_for_palette_workers)

    def wait_for_palette_workers(self):
        deadline = time.monotonic() + 10
        expected_home = f"HOME={self.home}".encode()
        while time.monotonic() < deadline:
            active = False
            for process in Path("/proc").iterdir():
                if not process.name.isdecimal():
                    continue
                try:
                    if str(SCRIPT).encode() not in (process / "cmdline").read_bytes():
                        continue
                    environment = (process / "environ").read_bytes().split(b"\0")
                    if expected_home in environment:
                        active = True
                        break
                except (OSError, PermissionError):
                    continue  # A process exited or belongs to another user.
            if not active:
                return
            time.sleep(0.02)
        self.fail("Sandboxed palette workers did not finish before cleanup")

    def run_palette(self, *args, env=None):
        return subprocess.run(["python3", str(SCRIPT), *map(str, args)],
                              env=env or self.env, capture_output=True, text=True,
                              timeout=30)

    def test_wallpaper_toggle_and_reload_once(self):
        applied = self.run_palette("wallpaper", self.first)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual((self.home / ".cache/matugen/current-mode").read_text().strip(), "dark")
        self.assertTrue((self.home / ".config/waybar/colors/matugen.css").is_file())
        self.assertFalse((self.home / ".config/opencode").exists())
        self.assertNotIn("gsettings", self.log.read_text())
        toggled = self.run_palette("toggle")
        self.assertEqual(toggled.returncode, 0, toggled.stderr)
        self.assertEqual((self.home / ".cache/matugen/current-mode").read_text().strip(), "light")
        lock_image = self.home / ".cache/hyprlock/wallpaper.png"
        rofi_image = self.home / ".cache/rofi/current-wallpaper.rasi"
        for _ in range(100):
            if lock_image.is_file() and rofi_image.is_file():
                break
            time.sleep(0.05)
        self.assertTrue(lock_image.is_file(), "The lock screen did not receive a PNG")
        self.assertEqual(lock_image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn("blurred_wallpaper.png", rofi_image.read_text())
        log = self.log.read_text()
        self.assertEqual(log.count("pkill -SIGUSR2 waybar"), 2)
        self.assertEqual(log.count("pkill -SIGUSR1 kitty"), 2)
        self.assertEqual(log.count("swaync-client -rs"), 2)
        self.assertIn("gsettings set org.gnome.desktop.interface gtk-theme adw-gtk3\n", log)

    def test_bad_wallpaper_and_cancel_do_not_change_state(self):
        self.assertEqual(self.run_palette("wallpaper", "--pick").returncode, 0)
        self.assertFalse((self.home / ".cache/matugen/intent.json").exists())
        result = self.run_palette("wallpaper", self.walls / "missing.png")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".cache/matugen/current-wallpaper").exists())

    def test_private_config_never_writes_to_an_unselected_shell(self):
        config = self.home / ".config/matugen/config.toml"
        config.write_text(config.read_text().split("[templates.shell]")[0])
        personal = self.home / ".config/zsh/generated/colors.sh"
        personal.parent.mkdir(parents=True)
        personal.write_text("# personal colors\n")
        applied = self.run_palette("wallpaper", self.first)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(personal.read_text(), "# personal colors\n")

    def test_failed_render_restores_last_good_wallpaper_and_palette(self):
        applied = self.run_palette("wallpaper", self.first)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        output = self.home / ".config/waybar/colors/matugen.css"
        original = output.read_bytes()
        bad = self.walls / "broken.png"
        bad.write_text("not a PNG")
        failed = self.run_palette("wallpaper", bad)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual((self.home / ".cache/matugen/current-wallpaper").read_text().strip(), str(self.first))
        self.assertTrue(self.log.read_text().strip().endswith(str(self.first)))

    def test_newer_request_wins_even_during_an_older_render(self):
        marker = self.root / "old-render-started"
        env = self.env | {"PALETTE_SLOW_WALL": str(self.first),
                          "PALETTE_SLOW_MARKER": str(marker)}
        old = subprocess.Popen(["python3", str(SCRIPT), "wallpaper", str(self.first)],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if marker.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(marker.exists(), "Old render did not start")
            newer = self.run_palette("wallpaper", self.second)
            self.assertEqual(newer.returncode, 0, newer.stderr)
            stdout, stderr = old.communicate(timeout=30)
            self.assertEqual(old.returncode, 0, stdout + stderr)
            self.assertEqual((self.home / ".cache/matugen/current-wallpaper").read_text().strip(), str(self.second))
            self.assertIn(str(self.second), (self.home / ".config/waybar/colors/matugen.css").read_text())
            self.assertEqual(self.log.read_text().count("pkill -SIGUSR2 waybar"), 1)
        finally:
            if old.poll() is None:
                old.terminate()
                old.communicate(timeout=5)

    def test_toggle_supersedes_a_wallpaper_render_without_reanimating(self):
        marker = self.root / "wall-render-started"
        env = self.env | {"PALETTE_SLOW_WALL": str(self.first),
                          "PALETTE_SLOW_MARKER": str(marker)}
        old = subprocess.Popen(["python3", str(SCRIPT), "wallpaper", str(self.first)],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if marker.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(marker.exists())
            toggled = self.run_palette("toggle")
            self.assertEqual(toggled.returncode, 0, toggled.stderr)
            old.communicate(timeout=30)
            self.assertEqual(old.returncode, 0)
            self.assertEqual((self.home / ".cache/matugen/current-mode").read_text().strip(), "light")
            log = self.log.read_text()
            self.assertEqual(log.count("awww img"), 1)
            self.assertEqual(log.count("pkill -SIGUSR2 waybar"), 1)
            self.assertIn("gtk-theme adw-gtk3\n", log)
        finally:
            if old.poll() is None:
                old.terminate()
                old.communicate(timeout=5)


class PublishTests(unittest.TestCase):
    def test_failed_publication_restores_previous_outputs(self):
        spec = importlib.util.spec_from_file_location("hypryoru_palette", SCRIPT)
        palette = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(palette)
        with tempfile.TemporaryDirectory(prefix="hypryoru-rollback-", dir=TEMP_ROOT) as directory:
            root = Path(directory)
            old = [root / "first.css", root / "second.css"]
            new = [root / "first.new", root / "second.new"]
            for path in old:
                path.write_text("last good\n")
            for path in new:
                path.write_text("new palette\n")
            palette.STORE = palette.PaletteStore(root / "cache")
            replace = os.replace
            failed = False

            def fail_second(source, target):
                nonlocal failed
                if Path(target) == old[1] and not failed:
                    failed = True
                    raise OSError("simulated publication failure")
                return replace(source, target)

            with patch("palette_store.os.replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "simulated publication failure"):
                    palette.publish(list(zip(new, old)))
            self.assertTrue(failed)
            for path in old:
                self.assertEqual(path.read_text(), "last good\n")


if __name__ == "__main__":
    unittest.main()
