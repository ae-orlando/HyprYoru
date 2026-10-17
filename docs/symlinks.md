# Symlinks

`install.sh` `LINK_MAP` (14 entries). Target is replaced with a symlink to the repo source.

| Target (`$HOME/...`) | Source (`$DOTFILES_ROOT/...`) |
| -------------------- | ----------------------------- |
| `.config/hypr`       | `hyprland`                    |
| `.config/btop`       | `btop`                        |
| `.config/kitty`      | `kitty`                       |
| `.config/matugen`    | `matugen`                     |
| `.config/qt6ct`      | `qt6ct`                       |
| `.config/rofi`       | `rofi`                        |
| `.config/swaync`     | `swaync`                      |
| `.config/waybar`     | `waybar`                      |
| `.config/waypaper`   | `waypaper`                    |
| `.config/zsh`        | `zsh`                         |
| `.config/fastfetch`  | `fastfetch`                   |
| `.config/gtk-3.0`    | `gtk-setting/gtk-3.0`         |
| `.config/gtk-4.0`    | `gtk-setting/gtk-4.0`         |
| `.config/VSCodium/User` | `vscodium/User`            |

## Related Paths

- `~/.zshenv` contains `export ZDOTDIR="$HOME/.config/zsh"`.
- `~/.config/gtk-3.0/bookmarks` is generated, not linked (gitignored).
- `~/.config/VSCodium` is a **real** directory (VSCodium writes caches there); only its `User/` subtree — `settings.json` + `snippets/` — is linked and tracked. Machine state (`globalStorage/`, `workspaceStorage/`, `History/`) is gitignored.
- Out-of-repo symlinks (`nvim`, `opencode`, `tmux`, `pgadmin4`) are left alone with a warning.
