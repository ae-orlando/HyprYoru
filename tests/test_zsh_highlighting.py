#!/usr/bin/env python3
"""Exercise installed Zsh highlighters without running any sample commands."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path("/tmp/opencode")
PLUGIN = Path("/usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh")
SYNTAX = REPO / "zsh/conf.d/post/99-syntaxh.zsh"
AUTOSUGGEST = REPO / "zsh/conf.d/post/50-autosuggestions.zsh"

SETUP = r'''
source "$YORU_SYNTAX_CONFIG"
# OMZ normally enables this before the highlighting configuration is sourced.
setopt interactivecomments
typeset -a region_highlight
paint() {
  BUFFER=$1
  CURSOR=${2:-${#BUFFER}}
  WIDGET=self-insert
  _ZSH_HIGHLIGHT_PRIOR_BUFFER=__not_the_current_buffer__
  _ZSH_HIGHLIGHT_PRIOR_CURSOR=-1
  region_highlight=()
  _zsh_highlight
}
'''


@unittest.skipUnless(shutil.which("zsh") and PLUGIN.is_file(), "Zsh highlighter required")
class HighlightingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hypryoru-highlighting-", dir=TEMP_ROOT)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "sample.txt").write_text("test path\n")
        self.env = os.environ | {
            "HOME": str(self.root), "ZDOTDIR": str(self.root),
            "XDG_CONFIG_HOME": str(self.root / ".config"),
            "XDG_CACHE_HOME": str(self.root / ".cache"),
            "ZSH_CUSTOM": str(self.root / ".oh-my-zsh/custom"),
            "YORU_SYNTAX_CONFIG": str(SYNTAX),
        }

    def run_zsh(self, body, env=None):
        result = subprocess.run(
            ["zsh", "-fc", SETUP + body], env=self.env | (env or {}), cwd=self.root,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def highlight(self, buffer, cursor=None, setup=""):
        output = self.run_zsh(
            # Token tests represent a normal user even if CI itself is root.
            'ZSH_HIGHLIGHT_HIGHLIGHTERS=(${ZSH_HIGHLIGHT_HIGHLIGHTERS:#root})\n'
            + setup + '\npaint "$TEST_BUFFER" "$TEST_CURSOR"\n'
            'print -rl -- "${region_highlight[@]}"\n',
            env={"TEST_BUFFER": buffer, "TEST_CURSOR": str(len(buffer) if cursor is None else cursor)},
        )
        return [
            (int(start), int(end), style.split(", memo=", 1)[0])
            for start, end, style in (line.split(" ", 2) for line in output.splitlines() if line)
        ]

    def assert_highlighted(self, regions, buffer, token, style):
        start = buffer.index(token)
        end = start + len(token)
        self.assertTrue(any(a <= start and b >= end and paint == style for a, b, paint in regions),
                        (token, style, regions))

    def test_only_meaningful_highlighters_are_enabled(self):
        output = self.run_zsh('print -r -- "${(j: :)ZSH_HIGHLIGHT_HIGHLIGHTERS}"\n')
        self.assertEqual(output.strip(), "main brackets regexp cursor root")

    def test_commands_aliases_options_and_paths_keep_their_roles(self):
        for buffer, token, style, setup in (
            ("print --help", "print", "fg=magenta,bold", ""),
            ("print --help", "--help", "fg=blue,bold", ""),
            ("yoru_alias value", "yoru_alias", "fg=cyan,bold", "alias yoru_alias='print --'"),
            ("yoru_function", "yoru_function", "fg=magenta,bold", "yoru_function() { :; }"),
            ("print ./sample.txt", "./sample.txt", "fg=green,underline", ""),
            ("command print value", "command", "fg=yellow,bold,underline", ""),
        ):
            with self.subTest(buffer=buffer):
                self.assert_highlighted(self.highlight(buffer, setup=setup), buffer, token, style)

    def test_unknown_commands_stay_red_without_background_blocks(self):
        buffer = "yoru_missing_command_6f0a --flag"
        regions = self.highlight(buffer)
        self.assert_highlighted(regions, buffer, "yoru_missing_command_6f0a", "fg=red,bold")
        self.assertTrue(all("bg=" not in style and "standout" not in style for _, _, style in regions))

    def test_closed_and_unclosed_quotes_have_distinct_readable_styles(self):
        for quoted in ("'hello world'", '"hello world"', "$'hello world'"):
            buffer = "print -- " + quoted
            with self.subTest(quoted=quoted):
                self.assert_highlighted(self.highlight(buffer), buffer, quoted, "fg=green")
        for quoted in ("'unfinished", '"unfinished', "$'unfinished", "`unfinished"):
            buffer = "print -- " + quoted
            with self.subTest(quoted=quoted):
                self.assert_highlighted(self.highlight(buffer), buffer, quoted, "fg=red,underline")

    def test_matching_brackets_use_an_underlined_accent_not_a_pastel_background(self):
        buffer = "print -- $((1 + (2)))"
        regions = self.highlight(buffer, cursor=buffer.index("("))
        self.assertIn((len(buffer) - 1, len(buffer), "fg=blue,bold,underline"), regions)
        self.assertTrue(all("bg=" not in style and "standout" not in style for _, _, style in regions))
        self.assertFalse(any(style == "fg=red,bold" for _, _, style in regions))

    def test_mismatched_brackets_remain_errors(self):
        regions = self.highlight("print -- $((1 + [2)))")
        self.assertTrue(any(style == "fg=red,bold" for _, _, style in regions))

    def test_root_warning_is_foreground_only_and_for_a_real_root_shell(self):
        output = self.run_zsh(r'''
print -r -- "$ZSH_HIGHLIGHT_STYLES[root]"
BUFFER='print -- value'
region_highlight=()
_zsh_highlight_highlighter_root_paint
if (( EUID == 0 )); then
  (( $#region_highlight == 1 )) || exit 1
else
  (( $#region_highlight == 0 )) || exit 1
fi
# Verify the configured root style without attempting to change privileges.
region_highlight=()
_zsh_highlight_add_highlight 0 $#BUFFER root
print -rl -- "${region_highlight[@]}"
''')
        self.assertIn("fg=red,bold,underline", output)
        self.assertNotIn("bg=", output)
        self.assertNotIn("standout", output)

    def test_annotations_match_whole_words_without_false_positives(self):
        for marker in ("TODO", "FIXME", "NOTE"):
            buffer = f"print value # {marker}: check this"
            self.assert_highlighted(self.highlight(buffer), buffer, marker + ":", "fg=yellow,bold")
        for word in ("NOTED", "TODOS", "TODO_LIST", "FIXME123", "FOO_NOTE"):
            with self.subTest(word=word):
                regions = self.highlight(f"print value # {word}")
                self.assertFalse(any(style == "fg=yellow,bold" for _, _, style in regions))

    def test_url_overlay_stops_at_whitespace_and_quotes(self):
        url = "https://example.test/path"
        for quote in ('"', "'", ""):
            with self.subTest(quote=quote):
                buffer = f"print -- {quote}{url}{quote}\t--flag"
                self.assert_highlighted(self.highlight(buffer), buffer, url, "fg=blue,underline")
                end = buffer.index(url) + len(url)
                for _, b, style in self.highlight(buffer):
                    if style == "fg=blue,underline":
                        self.assertEqual(b, end)

    def test_long_commands_highlight_up_to_the_guard_and_clear_above_it(self):
        for length in (513, 768, 1024):
            buffer = "print -- " + "x" * (length - len("print -- "))
            with self.subTest(length=length):
                self.assert_highlighted(self.highlight(buffer), buffer, "print", "fg=magenta,bold")
        self.assertEqual(self.highlight("print -- " + "x" * 1016), [])

    def test_pending_input_still_defers_expensive_highlighting(self):
        for variable in ("KEYS_QUEUED_COUNT", "PENDING"):
            with self.subTest(variable=variable):
                self.assertEqual(self.highlight("print -- value", setup=f"{variable}=1"), [])

    def test_repeated_sourcing_does_not_accumulate_regexp_rules(self):
        output = self.run_zsh(r'''
source "$YORU_SYNTAX_CONFIG"
print -r -- "${#ZSH_HIGHLIGHT_REGEXP}"
''')
        self.assertEqual(output.strip(), "2")


@unittest.skipUnless(shutil.which("zsh"), "Zsh required for autosuggestion tests")
class AutosuggestionTests(unittest.TestCase):
    def test_regular_weight_generated_style_reloads_and_has_an_ansi_fallback(self):
        with tempfile.TemporaryDirectory(prefix="hypryoru-ghost-", dir=TEMP_ROOT) as directory:
            script = r'''
unset MATUGEN_AUTOSUGGEST
source "$YORU_AUTOSUGGEST_CONFIG"
[[ $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == fg=8 ]] || exit 1
MATUGEN_AUTOSUGGEST='#aabbcc'
_autosuggest_apply_matugen
[[ $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == 'fg=#aabbcc' ]] || exit 2
MATUGEN_AUTOSUGGEST='#223344'
_autosuggest_apply_matugen
[[ $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == 'fg=#223344' ]] || exit 3
source "$YORU_AUTOSUGGEST_CONFIG"
integer matches=0
for hook in "${precmd_functions[@]}"; do
  [[ $hook == _autosuggest_apply_matugen ]] && (( ++matches ))
done
(( matches == 1 )) || exit 4
'''
            env = os.environ | {"HOME": directory, "ZDOTDIR": directory,
                                "YORU_AUTOSUGGEST_CONFIG": str(AUTOSUGGEST)}
            result = subprocess.run(["zsh", "-fc", script], env=env, cwd=directory,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")

    def test_prompt_hooks_apply_the_new_palette_to_a_long_lived_shell(self):
        with tempfile.TemporaryDirectory(prefix="hypryoru-ghost-reload-", dir=TEMP_ROOT) as directory:
            root = Path(directory)
            colors = root / "generated/colors.sh"
            colors.parent.mkdir()
            colors.write_text("export MATUGEN_AUTOSUGGEST='#aabbcc'\n")
            stamp = 1_600_000_000_000_000_100
            os.utime(colors, ns=(stamp, stamp))
            script = r'''
source "$YORU_MATUGEN_CONFIG"
source "$YORU_AUTOSUGGEST_CONFIG"
[[ $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == 'fg=#aabbcc' ]] || exit 1
print -r -- "export MATUGEN_AUTOSUGGEST='#223344'" > "$ZDOTDIR/generated/colors.sh"
touch -d '@1600000000.000000200' "$ZDOTDIR/generated/colors.sh"
for hook in "${precmd_functions[@]}"; do
  if [[ $hook == _matugen_colors_reload || $hook == _autosuggest_apply_matugen ]]; then
    "$hook"
  fi
done
[[ $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == 'fg=#223344' ]] || exit 2
'''
            env = os.environ | {
                "HOME": directory, "ZDOTDIR": directory,
                "YORU_AUTOSUGGEST_CONFIG": str(AUTOSUGGEST),
                "YORU_MATUGEN_CONFIG": str(REPO / "zsh/conf.d/post/15-matugen.zsh"),
            }
            result = subprocess.run(["zsh", "-fc", script], env=env, cwd=directory,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
