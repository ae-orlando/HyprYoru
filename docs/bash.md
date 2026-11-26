# Bash Configuration (HyprYoru parity with Zsh)

This document describes the bash configuration in `bash/` — a full-feature port of the HyprYoru zsh config with p10k-lean-8colors prompt parity, ble.sh line editor, matugen palette sync, and installer integration.

## Overview

| Component | Zsh equivalent | Status |
|-----------|----------------|--------|
| Prompt | powerlevel10k lean (8-color) | ✅ Parity |
| Line editor | zsh built-in + zsh-syntax-highlighting + zsh-autosuggestions | ✅ ble.sh |
| Palette | matugen → zsh/generated/colors.sh | ✅ matugen → bash/generated/colors.sh |
| Framework | oh-my-zsh + powerlevel10k | ❌ Not needed (ble.sh built-in) |
| Keybinds | `01-binds.zsh` (emacs/vi) | ❌ Divergence — ble.sh provides emacs |
| Completion | `02-completion.zsh` | ✅ `02-completion.bash` |
| Aliases | `10-aliases.zsh` | ✅ `10-aliases.bash` |
| Functions | `20-functions.zsh` | ✅ `20-functions.bash` |
| History | `30-history.zsh` | ✅ `30-history.bash` |
| zoxide | `40-zoxide.zsh` | ✅ `40-zoxide.bash` |
| fzf | `25-fzf.zsh` | ✅ `25-fzf.bash` (ble-import under ble.sh) |
| Autosuggestions | `50-autosuggestions.zsh` | ✅ `50-blesh.bash` + `_blesh_apply_matugen` |

## File Structure

```
bash/
├── .bashrc                     # Entry point (loads ble.sh, sources conf.d)
├── conf.d/
│   ├── pre/
│   │   ├── 01-env.bash         # Environment variables (EDITOR, PATH, etc.)
│   │   └── 02-completion.bash  # Bash completion setup
│   └── post/
│       ├── 10-aliases.bash     # Common aliases (ls, grep, git, etc.)
│       ├── 15-matugen.bash     # Palette reload hook (PROMPT_COMMAND)
│       ├── 20-functions.bash   # Helper functions (mkcd, extract, etc.)
│       ├── 25-fzf.bash         # fzf keybindings (ble-import or fzf --bash)
│       ├── 30-history.bash     # History settings (HISTSIZE, HISTCONTROL)
│       ├── 40-zoxide.bash      # zoxide init (smart cd)
│       ├── 50-blesh.bash       # ble.sh layer (faces, autosuggest, transient, PREEXEC)
│       └── 90-prompt.bash      # Prompt (p10k-lean-8colors replica)
└── generated/
    └── colors.sh               # matugen output (sourced by 15-matugen)
```

## Divergences from Zsh Config

### 1. No `01-binds.zsh` port (Keybindings)

**Zsh:** `zsh/conf.d/pre/01-binds.zsh` configures emacs/vi keybindings, history search, etc.

**Bash:** **Not ported.** ble.sh provides a full emacs-compatible line editor with history search (`Ctrl-R`), word movement, kill-ring, etc. by default. The zsh-specific bind commands (e.g., `bindkey`) have no direct bash equivalent; ble.sh's keymap system replaces them.

**Rationale:** ble.sh's default emacs keymap covers all common interactive needs. Custom binds can be added in `50-blesh.bash` via `ble-bind` if needed.

---

### 2. PS2 Continuation Prompt

**Zsh (p10k):** Context-aware continuation prompts:
- `dquote> ` inside double quotes
- `then> ` after `if/then`
- `> ` for backslash continuation
- Uses `MULTILINE_NEWLINE_PROMPT_PREFIX='├─'` only for multi-line prompt rendering

**Bash:** Single static `PS2='\[\e[37m\]├─\[\e[0m\] '` (gray `├─ `) for all continuation states.

**Reason:** Bash's `PS2` is a static string; it cannot dynamically change based on parse state like zsh's `PS2` with `%_` or p10k's context-aware prefixes. ble.sh does not expose a PS2 override hook.

**Impact:** Visual only. Functionality identical.

---

### 3. Syntax Highlighting Faces (ble.sh vs zsh-syntax-highlighting)

| Zsh face (zsh-syntax-highlighting) | ble.sh face | Status |
|------------------------------------|-------------|--------|
| `command` (executables) | `syntax_command` | ✅ Mapped |
| `builtin` | `command_builtin` | ✅ Mapped |
| `function` | `command_function` | ✅ Mapped |
| `alias` | `command_alias` | ✅ Mapped |
| `hashed-command` | `command_jobs` | ✅ Mapped |
| `reserved-word` / `keyword` | `command_keyword` | ✅ Mapped |
| `path` / `path_pathseparator` | `command_directory` / `command_file` / `syntax_tilde` | ⚠️ Partial — ble.sh colors paths only after parsing, not while typing |
| `globbing` | `syntax_glob` | ✅ Mapped |
| `history-expansion` | `syntax_history_expansion` | ✅ Mapped |
| `single-quoted-argument` / `double-quoted-argument` | `syntax_quoted` | ✅ Mapped |
| `back-quoted-argument-delimiter` | `syntax_quotation` | ✅ Mapped |
| `dollar-quoted-argument` / `rc-quote` | `syntax_quotation` | ✅ Mapped |
| `dollar-double-quoted-argument` | `syntax_expr` | ✅ Mapped |
| `back-double-quoted-argument` | `syntax_escape` | ✅ Mapped |
| `assign` / `variable` | — | ❌ **No ble.sh face** — keeps ble.sh default |
| `redirection` | `syntax_delimiter` | ✅ Mapped |
| `comment` | `syntax_comment` | ✅ Mapped (fg=8 outline gray) |
| `unknown-token` / `command-not-found` | `syntax_error` | ✅ Mapped (red bold, no bg) |
| `bracket-level-1`…`bracket-level-5` | `syntax_brace` | ⚠️ **Single face** — no rainbow nesting; uses level-1 blue bold |

**Missing in ble.sh (keep defaults):**
- `precommand` (sudo, env, nohup)
- `option` / `option-flag` (-h, --help)
- `variable` ($VAR)
- `path` highlighter (real-time path coloring while typing)
- `regexp` highlighter
- `cursor` face
- Rainbow bracket nesting (5 levels → 1)

**Documented in:** `bash/conf.d/post/50-blesh.bash` header comment.

---

### 4. Transient Prompt Implementation

**Zsh (p10k):** `POWERLEVEL9K_TRANSIENT_PROMPT=always` — on accept, redraws the previous prompt as a single line `❯ cmd` (green/red by *previous* command's status), preserving the blank line above.

**Bash (ble.sh):** Uses `bleopt prompt_ps1_final` dynamically set in `90-prompt.bash`:
```bash
if ((last_status == 0)); then
    bleopt prompt_ps1_final=$'\n''\[\e[32m\]❯\[\e[0m\] '
else
    bleopt prompt_ps1_final=$'\n''\[\e[31m\]❯\[\e[0m\] '
fi
```

**Why not `prompt_ps1_transient=trim`?** That mode keeps the `╰─❯` suffix. We need the p10k behavior: erase `╭─`/`╰─❯` entirely, leave only `❯ cmd` on a fresh line.

**Verified:** Byte-for-byte match with zsh/p10k transcript (see `step3-prompt-spec.md` §9).

---

### 5. PIPESTATUS Fidelity

**Zsh:** `$pipestatus` array always available in precmd.

**Bash + ble.sh:** Requires `bleopt exec_restore_pipestatus=1` (set in `50-blesh.bash`). Without it, ble.sh's `eval-with-setexit` reproducer is disabled and `PIPESTATUS` arrives stale in `PROMPT_COMMAND`.

**Our config:** Enables it explicitly. The dispatcher in `90-prompt.bash` captures `$?` + `${PIPESTATUS[@]}` atomically as its first statement — works correctly because ble.sh restores both before running `PROMPT_COMMAND`.

---

### 6. Exec Time Source

**Zsh (p10k):** `prompt_command_execution_time` — measures wall time of the whole command line (preexec to precmd).

**Bash:** Two implementations:
- **With ble.sh:** `blehook PREEXEC` in `50-blesh.bash` — fires once per command line (p10k parity).
- **Without ble.sh:** `DEBUG` trap in `90-prompt.bash` — fires per simple command (fallback only).

The DEBUG trap is **guarded** to skip when `BLE_VERSION` is set or another DEBUG trap exists.

---

### 7. ble.sh Default Markers (Disabled)

Zsh prints nothing after commands. ble.sh defaults to showing:
- `[ble: exit 1]` after failures
- `[ble: EOF]` after short output
- Elapsed time marker

**Our config disables all** in `50-blesh.bash`:
```bash
bleopt exec_errexit_mark=
bleopt exec_elapsed_enabled=
bleopt exec_exit_mark=
bleopt prompt_eol_mark=
```
The prompt's own status segment (`✘/✔/TERM/took`) replaces them.

---

### 8. Multiline Info Hint (Disabled)

ble.sh shows `-- MULTILINE -- (RET or C-m: insert a newline, C-j: run)` when editing an incomplete command.

**Zsh:** Shows nothing there (continuation is purely `PS2`).

**Our config:** `bleopt prompt_emacs_mode_indicator:=` (empty string). The arg/REC indicators (numeric arg, macro recording) are appended outside the unit text and remain visible.

---

### 9. Autosuggestion Ghost Color

**Zsh:** `ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE` set from `MATUGEN_AUTOSUGGEST` (hex) in generated colors.

**Bash:** `ble-face auto_complete` set by `_blesh_apply_matugen()` in `50-blesh.bash`, registered in `PROMPT_COMMAND` to re-apply on palette reload. ble.sh's color parser accepts `fg=#RRGGBB`.

---

### 10. Installer: ble.sh Source Choice

The installer offers two methods for ble.sh:

| Method | Location | Use case |
|--------|----------|----------|
| **Arch `blesh-git` package** | `/usr/share/blesh/ble.sh` | Default on Arch; managed by pacman |
| **Upstream clone** | `~/.local/share/blesh/ble.sh` (tag `v0.4.0-devel4`) | Non-Arch distros; pinned version |

`.bashrc` tries both locations in order (user clone first, then Arch package). The wizard option `--no-blesh-clone` / `UI_OPTION_BLESH` controls this.

---

### 11. No Git `wip` / `⇠⇢` / Merge Action Segments

**Zsh (p10k):** Shows `wip` for uncommitted changes, `⇠N⇢M` for ahead/behind, merge/rebase/cherry-pick action.

**Bash:** **Omitted** — the git segment in `90-prompt.bash` only shows branch + dirty (`*`) + ahead/behind counts (`+N/-N`). The extra p10k segments add complexity without proportional value for bash usage.

---

### 12. No Git Prompt When `PWD == $HOME`

**Both:** Git segment is suppressed when `PWD == $HOME` to avoid scanning the home directory (often a git repo with many files).

---

### 13. No `SHARE_HISTORY` / `history_share`

**Zsh:** Does not set `SHARE_HISTORY` in this config (uses per-session history with `inc_append_history`).

**Bash:** No equivalent needed; `histappend` + `PROMPT_COMMAND` history sync would be required for sharing, which we don't enable.

---

## Loading Order (`.bashrc`)

```
1. ble.sh (--attach=none)          # Must load first
2. conf.d/pre/01-env.bash
3. conf.d/pre/02-completion.bash
4. conf.d/post/10-aliases.bash
5. conf.d/post/15-matugen.bash     # Registers _matugen_colors_reload in PROMPT_COMMAND
6. conf.d/post/20-functions.bash
7. conf.d/post/25-fzf.bash         # ble-import or fzf --bash
8. conf.d/post/30-history.bash
9. conf.d/post/40-zoxide.bash      # Registers __zoxide_hook in PROMPT_COMMAND
10. conf.d/post/50-blesh.bash      # Faces, autosuggest, transient, PREEXEC
11. conf.d/post/90-prompt.bash     # Becomes sole PROMPT_COMMAND dispatcher
12. ble-attach                     # Must be last
```

The `PROMPT_COMMAND` chain at prompt time:
```
_matugen_colors_reload → __zoxide_hook → _blesh_apply_matugen → _yoru_prompt (dispatcher)
```

`90-prompt.bash` saves previous entries, becomes the sole dispatcher, and runs saved entries first — **idempotent on re-source** via `_yoru_pc_refold()`.

---

## Testing

Run the test suite:

```bash
# All tests (includes zsh/integration tests)
python3 -B -m unittest discover -s tests

# Bash prompt tests only
python3 -B -m pytest tests/test_bash_prompt.py -v
```

**Expected:** 134 pass, 2 fail (pre-existing light-theme autosug contrast), 8 skipped (PTY tests).

**Manual interactive verification (tmux):**
```bash
HOME=/tmp/test bash --rcfile /path/to/dotfiles/bash/.bashrc -i
# Test: true|false → ✘ 0|1, false|true → ✔ 1|0, SIGTERM → ✘ TERM
# Test: sleep 4 → "took 4s"
# Test: transient ❯ green/red by previous status
# Test: width 80/100 exact
# Test: re-source .bashrc → status still works
```