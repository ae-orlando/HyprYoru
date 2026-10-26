# Zsh

`ZDOTDIR=$HOME/.config/zsh` (written to `~/.zshenv` by `install.sh`). Entry: `zsh/.zshrc`.

## Load Order

1. p10k instant prompt.
2. `conf.d/pre/*.zsh`:
   - `01-env.zsh` (`ZSH`, `EDITOR`, `PATH`, `ZSH_THEME`, `fnm` guard, `PAGER`/`MANPAGER` via `bat --theme=ansi`, `BAT_THEME`/`BAT_STYLE`).
   - `02-plugins.zsh` (`git`, `archlinux`, `extract`, `sudo`, `gh`, `tmux`, `python`).
3. `oh-my-zsh.sh`.
4. `conf.d/post/*.zsh`:
   - `10-aliases.zsh` (`eza`, `nvim`, `git`, `pacman`, `python`/`uv`, `bat`/`cat`, `diff --color`, `grep --color`).
   - `15-matugen.zsh` (sources `generated/colors.sh`, `precmd` reload).
   - `20-functions.zsh` (`ascii` banner, `fonts` list, `shot` screenshots, `bak` backups).
   - `40-zoxide.zsh` (guarded zoxide initialization; `z`/`zi` directory jumping).
   - `50-autosuggestions.zsh` (system plugin + `MATUGEN_AUTOSUGGEST` style).
   - `99-syntaxh.zsh` (system plugin + `main/brackets/regexp/cursor/root` highlighters, ANSI tokens, foreground-only emphasis).
5. `.p10k.zsh` (`$ZDOTDIR` first, `~/.p10k.zsh` fallback).

## Files

| Path                                 | Purpose                                                        |
| ------------------------------------ | -------------------------------------------------------------- |
| `.zshrc`                             | Entry point above                                              |
| `.p10k.zsh`                          | Powerlevel10k lean config                                      |
| `conf.d/pre/01-env.zsh`              | Paths, editor, theme, `fnm`                                    |
| `conf.d/pre/02-plugins.zsh`          | OMZ plugin list                                                |
| `conf.d/post/10-aliases.zsh`         | Aliases                                                        |
| `conf.d/post/15-matugen.zsh`         | Palette reload hook                                            |
| `conf.d/post/20-functions.zsh`       | `ascii`, `fonts`, `shot`, `bak`                                |
| `conf.d/post/25-fzf.zsh`             | fzf keybindings (CTRL-R/T, ALT-C)                              |
| `conf.d/post/30-history.zsh`         | History dedup/sharing tuning                                   |
| `conf.d/post/40-zoxide.zsh`          | `z`/`zi` directory jumping via zoxide                          |
| `conf.d/post/50-autosuggestions.zsh` | Ghost-text styling                                             |
| `conf.d/post/99-syntaxh.zsh`         | Token colors, brackets, URL/annotation overlays, root warning    |
| `generated/colors.sh`                | Generated `MATUGEN_AUTOSUGGEST` + `FZF_DEFAULT_OPTS` + preview |

## Syntax highlighting

`zsh/conf.d/post/99-syntaxh.zsh` loads `zsh-syntax-highlighting` after the
other shell plugins. Commands stay bold magenta, aliases cyan, flags blue,
strings/paths green, and shell operators yellow. These are terminal ANSI
slots, not literal hues: Kitty's Matugen palette supplies their actual colors.

- Errors remain red. The root highlighter warns on an actual `EUID == 0`
  shell; it does not detect `sudo`. Precommands such as `sudo`, `env`, and
  `command` have a separate yellow underline.
- The editing cursor uses an underline; its matching bracket uses a bold,
  underlined accent. Root warnings are red/bold/underlined. None relies on
  low-contrast white-on-pastel background fills.
- URL overlays stop at whitespace and quotes. Annotation overlays match whole
  `TODO`, `FIXME`, or `NOTE` words, not `NOTED` or `TODO_LIST`. These are cosmetic
  regex matches, not safety checks or shell parsing.
- Empty `pattern` and no-op `line` passes are disabled. No special `rm -rf`
  highlighting is installed.
- Highlighting is capped at **1,024 characters**, up from 512. The plugin still
  defers painting while input is queued and skips larger pasted buffers.
  Token-heavy long lines cost more than one long argument, so the cap stays
  conservative instead of disabling the performance guard.

Autosuggestions use regular-weight Matugen `on_surface_variant` text instead
of the too-faint `outline_variant` border color. ANSI gray (`fg=8`) is the
fallback without a generated palette. Existing shells refresh suggestion
styles before each prompt, after the palette reload hook.

Open a new terminal to use configuration changes. Template changes reach
`generated/colors.sh` on the next palette regeneration (normally a wallpaper
change); never hand-edit that generated file.

Run isolated highlighting/contrast tests without changing the live shell:

```bash
python3 -B tests/test_zsh_highlighting.py
python3 -B tests/test_matugen_palette.py
```

## Zoxide

The guarded initialization in `zsh/conf.d/post/40-zoxide.zsh:13` enables directory jumping when zoxide is installed. It learns directories as you visit them; regular `cd` remains unchanged.

```zsh
cd ~/Dev/dotfiles  # Visit a directory to record it.
cd ~
z dotfiles        # Jump back using part of its path.
zi                # Select a remembered directory with fzf.
```

## Provisioning

`install.sh` installs oh-my-zsh unattended and clones `powerlevel10k` to `${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/themes/powerlevel10k`, then runs `chsh -s /usr/bin/zsh` and `zsh -n` syntax check.

## Notes

- No `~/.zshrc` at home; everything resolves through `$ZDOTDIR`.
- `*.bak-*` files under `conf.d/post/` are local debris.
- `.zsh_history` and `.zcompdump*` are gitignored runtime state.
