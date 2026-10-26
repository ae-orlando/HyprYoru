#!/usr/bin/env python3
"""Isolated palette rendering and coordination tests (never reload live apps)."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path("/tmp/opencode")


def luminance(color):
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(a, b):
    a, b = sorted((luminance(a), luminance(b)))
    return (b + 0.05) / (a + 0.05)


@unittest.skipUnless(shutil.which("matugen"), "matugen required for rendering")
class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="hypryoru-palette-", dir=TEMP_ROOT)
        cls.addClassCleanup(temp.cleanup)
        root = Path(temp.name)
        config = root / "config.toml"
        templates = sorted((REPO / "matugen/templates").iterdir())
        config.write_text(
            "[config]\nversion_check = false\ncontrast = 0.0\n"
            '[config.wallpaper]\nset = false\ncommand = "true"\n\n'
            + "".join(
                f'[templates.render{i}]\ninput_path = "{template}"\n'
                f'output_path = "{root / ("render" + str(i) + template.suffix)}"\n\n'
                for i, template in enumerate(templates)
            )
        )
        cls.samples = {}
        env = os.environ.copy()
        env.update(HOME=str(root), XDG_CONFIG_HOME=str(root / ".config"),
                   XDG_CACHE_HOME=str(root / ".cache"))
        for mode in ("dark", "light"):
            for source in ("#c65f2e", "#4050d0"):
                result = subprocess.run(
                    ["matugen", "--config", str(config), "color", "hex", source,
                     "--mode", mode, "--type", "scheme-tonal-spot"],
                    capture_output=True, text=True, env=env, timeout=30,
                )
                if result.returncode:
                    raise AssertionError(result.stdout + result.stderr)
                output = {}
                for i, template in enumerate(templates):
                    content = (root / f"render{i}{template.suffix}").read_text()
                    if "{{" in content or "<*" in content:
                        raise AssertionError(f"Unresolved expressions in {template.name}")
                    if template.suffix == ".json":
                        json.loads(content)
                    output[template.name] = content
                cls.samples[mode, source] = output

    def test_qt_palette_has_three_complete_distinct_states(self):
        for key, output in self.samples.items():
            with self.subTest(key=key):
                qt = output["qtct-colors.conf"]
                rows = {
                    state: re.search(rf"^{state}_colors=(.+)$", qt, re.M).group(1).split(", ")
                    for state in ("active", "inactive", "disabled")
                }
                for state, colors in rows.items():
                    self.assertEqual(len(colors), 21, state)
                    self.assertTrue(all(re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in colors))
                    self.assertGreaterEqual(contrast(colors[6], colors[9]), 4.5)
                self.assertNotEqual(rows["active"], rows["inactive"])
                self.assertNotEqual(rows["active"], rows["disabled"])
                self.assertGreaterEqual(contrast(rows["active"][12], rows["active"][13]), 4.5)

    def test_kitty_ansi_is_visible_on_its_background(self):
        for key, output in self.samples.items():
            with self.subTest(key=key):
                kitty = dict(re.findall(r"^(background|color\d+)\s+(#[0-9a-fA-F]{6})$",
                                        output["kitty-colors.conf"], re.M))
                self.assertEqual(len(kitty), 17)
                for index in list(range(1, 8)) + list(range(8, 16)):
                    self.assertGreaterEqual(
                        contrast(kitty["background"], kitty[f"color{index}"]), 3.0,
                        (key, index),
                    )
                for index in range(8, 16):
                    self.assertNotEqual(kitty[f"color{index}"], kitty[f"color{index - 8}"])

    def test_css_json_and_lua_roles_are_generated(self):
        for output in self.samples.values():
            self.assertIn("@define-color fg #", output["waybar-matugen.css"])
            self.assertIn("@define-color accent_bg_color #", output["gtk-colors.css"])
            self.assertIn("active_border", output["hypr-colors.lua"])

    def test_autosuggestion_ink_is_readable_but_distinct_from_normal_text(self):
        for key, output in self.samples.items():
            with self.subTest(key=key):
                ghost = re.search(r'MATUGEN_AUTOSUGGEST="(#[0-9a-fA-F]{6})"',
                                  output["shell-colors.sh"]).group(1)
                kitty = dict(re.findall(r"^(background|foreground)\s+(#[0-9a-fA-F]{6})$",
                                        output["kitty-colors.conf"], re.M))
                self.assertGreaterEqual(contrast(ghost, kitty["background"]), 4.5)
                self.assertNotEqual(ghost, kitty["foreground"])

    def test_zsh_warning_and_matching_bracket_foregrounds_are_readable(self):
        for key, output in self.samples.items():
            with self.subTest(key=key):
                kitty = dict(re.findall(r"^(background|color[14])\s+(#[0-9a-fA-F]{6})$",
                                        output["kitty-colors.conf"], re.M))
                for slot in ("color1", "color4"):
                    self.assertGreaterEqual(contrast(kitty[slot], kitty["background"]), 4.5)

    def test_waybar_status_tokens_remain_legible(self):
        for key, output in self.samples.items():
            with self.subTest(key=key):
                colors = dict(re.findall(r"@define-color\s+([\w-]+)\s+(#[\da-fA-F]{6});",
                                         output["waybar-matugen.css"]))
                for token in ("accent", "success", "warning", "danger"):
                    self.assertGreaterEqual(contrast(colors[token], colors["bg1"]), 3.0,
                                            (key, token))
                self.assertEqual(len({colors["success"], colors["warning"], colors["danger"]}), 3)


@unittest.skipUnless(shutil.which("zsh"), "zsh required for shell reload test")
class ShellReloadTests(unittest.TestCase):
    def test_same_second_palette_changes_reload_at_the_next_prompt(self):
        with tempfile.TemporaryDirectory(prefix="hypryoru-zsh-", dir=TEMP_ROOT) as directory:
            root = Path(directory)
            colors = root / "generated/colors.sh"
            colors.parent.mkdir()
            colors.write_text("export MATUGEN_AUTOSUGGEST=first\n")
            stamp = 1_600_000_000_000_000_100
            os.utime(colors, ns=(stamp, stamp))
            script = (
                f'source "{REPO / "zsh/conf.d/post/15-matugen.zsh"}"\n'
                '[[ "$MATUGEN_AUTOSUGGEST" == first ]] || exit 1\n'
                'print -r -- "export MATUGEN_AUTOSUGGEST=second" > "$ZDOTDIR/generated/colors.sh"\n'
                'touch -d "@1600000000.000000200" "$ZDOTDIR/generated/colors.sh"\n'
                '_matugen_colors_reload\n'
                '[[ "$MATUGEN_AUTOSUGGEST" == second ]]\n'
            )
            result = subprocess.run(["zsh", "-fc", script], env=os.environ | {"ZDOTDIR": str(root)},
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
