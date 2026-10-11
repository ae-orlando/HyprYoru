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
   - `50-autosuggestions.zsh` (system plugin + `MATUGEN_AUTOSUGGEST` style).
   - `99-syntaxh.zsh` (system plugin + `main/brackets/pattern/cursor/regexp/root/line` highlighters, 8-color ANSI tokens, `rm -rf` pattern).
5. `.p10k.zsh` (`$ZDOTDIR` first, `~/.p10k.zsh` fallback).

## Files

| Path                                 | Purpose                                              |
| ------------------------------------ | ---------------------------------------------------- |
| `.zshrc`                             | Entry point above                                    |
| `.p10k.zsh`                          | Powerlevel10k lean config                            |
| `conf.d/pre/01-env.zsh`              | Paths, editor, theme, `fnm`                          |
| `conf.d/pre/02-plugins.zsh`          | OMZ plugin list                                      |
| `conf.d/post/10-aliases.zsh`         | Aliases                                              |
| `conf.d/post/15-matugen.zsh`         | Palette reload hook                                  |
| `conf.d/post/20-functions.zsh`       | `ascii`, `fonts`, `shot`, `bak`                      |
| `conf.d/post/50-autosuggestions.zsh` | Ghost-text styling                                   |
| `conf.d/post/99-syntaxh.zsh`         | Highlight token colors + brackets/root/pattern     |
| `generated/colors.sh`                | Generated `MATUGEN_AUTOSUGGEST` + `FZF_DEFAULT_OPTS` + preview |

## Provisioning

`install.sh` installs oh-my-zsh unattended and clones `powerlevel10k` to `${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/themes/powerlevel10k`, then runs `chsh -s /usr/bin/zsh` and `zsh -n` syntax check.

## Notes

- No `~/.zshrc` at home; everything resolves through `$ZDOTDIR`.
- `*.bak-*` files under `conf.d/post/` are local debris.
- `.zsh_history` and `.zcompdump*` are gitignored runtime state.
