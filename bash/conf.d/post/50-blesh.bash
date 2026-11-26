# _     _            _
# | |__ | | ___   ___| |__
# | '_ \| |/ _ \ / __| '_ \
# | |_) | |  __/_\__ \ | | |
# |_.__/|_|\___(_)___/_| |_|
#

# by ae. Orlando
# _______________________________________________________________________
# ble.sh layer: syntax-highlighting faces (port of zsh/conf.d/post/99-syntaxh.zsh
# 8-colour ANSI slots), autosuggestion ghost (50-autosuggestions.zsh parity),
# transient prompt (p10k TRANSIENT_PROMPT=always) and the PREEXEC hook that
# feeds the prompt's "took" segment. No-op when ble.sh is not loaded.
#
# Divergences from zsh-syntax-highlighting (documented in docs/bash.md):
#   * ble.sh has no path/regexp/cursor highlighters in its syntax layer
#   * one syntax_brace face instead of the 5-colour bracket nesting
#   * precommand (sudo/env), option (-h/--help) and $variable styles have
#     no ble.sh face and keep ble.sh's own defaults

[[ -n ${BLE_VERSION-} ]] || return 0

# =====================================================================
# Faces — 1:1 with the zsh file's ANSI slots (magenta = executable,
# cyan = shortcut, yellow = chrome, green = text, red = error).
# =====================================================================
# Executables, builtins, functions (magenta bold).
ble-face syntax_command='fg=magenta,bold'
ble-face command_builtin='fg=magenta,bold'
ble-face command_builtin_dot='fg=magenta,bold'
ble-face command_function='fg=magenta,bold'
ble-face command_jobs='fg=magenta,bold'

# User shortcuts (cyan bold, distinct from real commands).
ble-face command_alias='fg=cyan,bold'

# Reserved words (yellow; red stays reserved for errors).
ble-face command_keyword='fg=yellow'

# Shell chrome: separators, redirections, history expansion (yellow).
ble-face syntax_delimiter='fg=yellow'
ble-face syntax_history_expansion='fg=yellow,bold'

# Valid paths and directory commands (green — zsh's path/autodirectory
# slot; ble.sh colours them once parsed, not while typing).
ble-face syntax_tilde='fg=green,underline'
ble-face command_directory='fg=green,underline'
ble-face command_file='fg=green,underline'

# Strings and quotes (green; quote delimiters green bold like zsh's
# back-quoted-argument-delimiter).
ble-face syntax_quoted='fg=green'
ble-face syntax_quotation='fg=green,bold'
ble-face syntax_escape='fg=green'

# Substitutions and globs (cyan — same family as shortcuts in zsh).
ble-face syntax_expr='fg=cyan'
ble-face syntax_glob='fg=cyan'

# Comments: colour-8 outline gray (colour 0 was invisible).
ble-face syntax_comment='fg=8'

# Unknown commands / errors (red bold, highest severity, no background —
# ble.sh defaults to a red background block here).
ble-face syntax_error='fg=red,bold'

# Matching brackets: zsh paints nesting level 1 blue bold; ble.sh has a
# single face, so the innermost colour is used (no rainbow nesting).
ble-face syntax_brace='fg=blue,bold'

# =====================================================================
# Autosuggestion ghost text — re-applied whenever the palette changes.
# 90-prompt replays this entry after _matugen_colors_reload in the
# PROMPT_COMMAND chain, so a wallpaper swap updates the ghost in the
# same prompt (zsh does the same through its precmd hook order).
# =====================================================================
_blesh_apply_matugen() {
    local spec="fg=${MATUGEN_AUTOSUGGEST:-8}"
    [[ ${_blesh_autosuggest_spec-} == "$spec" ]] && return 0
    _blesh_autosuggest_spec=$spec
    ble-face auto_complete="$spec"
}
if [[ $(declare -p PROMPT_COMMAND 2>/dev/null) == 'declare -a'* ]]; then
    PROMPT_COMMAND=("${PROMPT_COMMAND[@]}" _blesh_apply_matugen)
else
    PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND;}_blesh_apply_matugen"
fi
_blesh_apply_matugen

# =====================================================================
# Transient prompt (p10k POWERLEVEL9K_TRANSIENT_PROMPT=always).
# On accept, ble.sh erases the old prompt and redraws prompt_ps1_final
# followed by the typed line — a single "❯ cmd" line. 90-prompt
# refreshes this on every build so the glyph keeps the status colour of
# the command just run (verified against the zsh/p10k transcript).
# =====================================================================
bleopt prompt_ps1_final=$'\n''\[\e[32m\]❯\[\e[0m\] '

# =====================================================================
# Silence ble.sh's own markers — zsh prints nothing after commands.
# =====================================================================
bleopt exec_errexit_mark=    # no "[ble: exit 1]" after failures
bleopt exec_elapsed_enabled= # the prompt has its own "took" segment
bleopt exec_exit_mark=       # no marker when the shell exits
bleopt prompt_eol_mark=      # no "[ble: EOF]" after short output

# PIPESTATUS fidelity in PROMPT_COMMAND: ble.sh only composes the
# pipestatus reproducer for the prompt dispatcher when this is set
# (ble-edit/exec/compose-PIPESTATUS-reproducer), so without it a pipe
# like "true|false" reaches 90-prompt with a stale single-element
# PIPESTATUS and its ✘/✔ pipe segment never appears.
bleopt exec_restore_pipestatus=1

# No "-- MULTILINE -- (RET or C-m...)" info hint while editing an
# incomplete command: zsh shows nothing there (its continuation prompt
# is just PS2). Created here with := because lib/keymap.emacs.sh loads
# at attach (after this file) — its bleopt/declare -v keeps a value
# that already exists, so our empty sticks. The arg/REC indicators are
# appended outside the unit text and stay.
bleopt prompt_emacs_mode_indicator:=

# =====================================================================
# Exec time: PREEXEC stamps _yoru_cmd_start once per command line.
# This replaces the DEBUG-trap fallback in 90-prompt (which skips
# installing itself while BLE_VERSION is set). Unlike the DEBUG trap,
# PREEXEC fires once for the whole line, so "sleep 4; echo hi" measures
# the line — exactly p10k's prompt_command_execution_time semantics.
# =====================================================================
_yoru_preexec_blesh() {
    ((${_yoru_prompting:-0})) && return 0
    [[ -n ${EPOCHREALTIME-} ]] || return 0
    _yoru_cmd_start=$EPOCHREALTIME
}
blehook PREEXEC!=_yoru_preexec_blesh
