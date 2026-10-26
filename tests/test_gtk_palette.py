#!/usr/bin/env python3
"""Render GTK palettes in a sandbox; never reload apps or write live colors."""

import json
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "matugen/templates/gtk-colors.css"
TEMP_ROOT = Path("/tmp/opencode")
SURFACES = (
    "accent",
    "window",
    "headerbar",
    "popover",
    "view",
    "card",
    "sidebar",
    "secondary_sidebar",
    "dialog",
    "thumbnail",
    "overview",
    "active_toggle",
)


def resolve(colors, name):
    """Resolve aliases while rejecting missing colors and reference cycles."""
    seen = set()
    while name not in seen:
        seen.add(name)
        value = colors[name]
        if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            return value.lower()
        if not re.fullmatch(r"@\w+", value):
            raise AssertionError(f"Expected a solid color for {name}: {value}")
        name = value[1:]
    raise AssertionError(f"Color reference cycle: {name}")


def luminance(color):
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        for v in channels
    ]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


class GtkImportsTests(unittest.TestCase):
    def test_both_gtk_versions_import_the_generated_palette(self):
        for version in ("3.0", "4.0"):
            with self.subTest(version=version):
                css = (REPO / f"gtk-setting/gtk-{version}/gtk.css").read_text()
                self.assertIn("@import 'colors.css';", css)

    def test_gtk4_css_only_roles_map_to_generated_named_colors(self):
        defined = set(re.findall(r"@define-color\s+(\w+)", TEMPLATE.read_text()))
        for name_css in ("gtk.css", "gtk-dark.css"):
            css = (REPO / "gtk-setting/gtk-4.0" / name_css).read_text()
            self.assertIn("@import 'colors.css';", css)
            mappings = dict(re.findall(r"(--[\w-]+):\s*@(\w+);", css))
            for role in ("overview", "active_toggle"):
                for kind in ("bg", "fg"):
                    name = f"{role}_{kind}_color"
                    with self.subTest(css=name_css, name=name):
                        variable = "--" + name.replace("_", "-")
                        self.assertEqual(mappings[variable], name)
                        self.assertIn(name, defined)

    @unittest.skipUnless(importlib.util.find_spec("gi"), "GTK4 bindings unavailable")
    def test_gtk4_stylesheets_parse_with_vendor_theme(self):
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        for name in ("gtk.css", "gtk-dark.css"):
            with self.subTest(name=name):
                provider = Gtk.CssProvider()
                errors = []
                provider.connect("parsing-error", lambda _provider, _section, error: errors.append(error.message))
                provider.load_from_path(str(REPO / "gtk-setting/gtk-4.0" / name))
                self.assertEqual(errors, [])


@unittest.skipUnless(shutil.which("matugen"), "matugen is required for rendering")
class GtkPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(
            prefix="hypryoru-gtk-tests-",
            dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None,
        )
        cls.addClassCleanup(temp.cleanup)
        root = Path(temp.name)
        output = root / "colors.css"
        config = root / "config.toml"
        config.write_text(
            "[config]\nversion_check = false\ncontrast = 0.0\n"
            '[config.wallpaper]\nset = false\ncommand = "true"\n'
            "[templates.gtk]\n"
            f"input_path = {json.dumps(str(TEMPLATE))}\n"
            f"output_path = {json.dumps(str(output))}\n"
        )
        env = os.environ.copy()
        env.update(
            HOME=str(root),
            XDG_CONFIG_HOME=str(root / ".config"),
            XDG_CACHE_HOME=str(root / ".cache"),
        )
        cls.palettes = {}
        for mode in ("dark", "light"):
            for source in ("#c65f2e", "#4050d0"):
                result = subprocess.run(
                    [
                        "matugen", "--config", str(config), "color", "hex", source,
                        "--mode", mode, "--type", "scheme-tonal-spot", "--json", "hex",
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=20,
                )
                if result.returncode:
                    raise AssertionError(result.stdout + result.stderr)
                css = output.read_text()
                if "{{" in css:
                    raise AssertionError("Unresolved Matugen template expression")
                matches = re.findall(r"@define-color\s+(\w+)\s+([^;]+);", css)
                colors = dict(matches)
                if len(colors) != len(matches):
                    raise AssertionError("Duplicate named color definitions")
                cls.palettes[mode, source] = colors, json.loads(result.stdout)["colors"]

    def test_every_surface_has_readable_foreground_contrast(self):
        for key, (colors, _) in self.palettes.items():
            for surface in SURFACES:
                with self.subTest(palette=key, surface=surface):
                    bg = luminance(resolve(colors, f"{surface}_bg_color"))
                    fg = luminance(resolve(colors, f"{surface}_fg_color"))
                    contrast = (max(bg, fg) + 0.05) / (min(bg, fg) + 0.05)
                    self.assertGreaterEqual(contrast, 4.5)

    def test_accent_and_dialog_use_mode_appropriate_material_roles(self):
        roles = {
            "accent_color": "primary",
            "accent_bg_color": "primary",
            "accent_fg_color": "on_primary",
            "dialog_bg_color": "surface_container_high",
            "dialog_fg_color": "on_surface",
        }
        for key, (colors, material) in self.palettes.items():
            for name, role in roles.items():
                with self.subTest(palette=key, name=name):
                    self.assertEqual(resolve(colors, name), material[role]["default"]["color"])

    def test_surface_depth_is_preserved_in_dark_and_light_modes(self):
        for (mode, source), (colors, _) in self.palettes.items():
            with self.subTest(mode=mode, source=source):
                view, window, dialog = (
                    luminance(resolve(colors, f"{role}_bg_color"))
                    for role in ("view", "window", "dialog")
                )
                if mode == "dark":
                    self.assertLess(view, window)
                    self.assertLess(window, dialog)
                else:
                    self.assertGreater(view, window)
                    self.assertGreater(window, dialog)

    def test_new_surfaces_follow_changes_to_the_source_palette(self):
        for mode in ("dark", "light"):
            first, _ = self.palettes[mode, "#c65f2e"]
            second, _ = self.palettes[mode, "#4050d0"]
            for surface in ("dialog", "secondary_sidebar", "thumbnail", "overview", "active_toggle"):
                with self.subTest(mode=mode, surface=surface):
                    name = f"{surface}_bg_color"
                    self.assertNotEqual(resolve(first, name), resolve(second, name))


if __name__ == "__main__":
    unittest.main()
