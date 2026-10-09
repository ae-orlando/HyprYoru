# Matugen

Palette hub. One wallpaper run regenerates every app theme. Config: `matugen/config.toml` (75 lines).

## Wallpaper Command

```toml
[config.wallpaper]
set = true
command = "awww img --transition-type center --transition-duration 2 {{ image }}"
```

Run it via:

```bash
matugen image ~/Pictures/wallpapers/mystical-night-in-town.jpg --mode dark --type scheme-tonal-spot --prefer closest-to-fallback
```

Or via the wrapper (adds wallpaper cache + bar reloads):

```bash
~/.config/hypr/scripts/set-wall.sh <wallpaper>
```

## Generated-File Map

| Template (`templates/`) | Output                                      | Consumer              |
| ----------------------- | ------------------------------------------- | --------------------- |
| `hypr-colors.lua`       | `~/.config/hypr/modules/colors.lua`         | `general.lua` borders |
| `hyprlock-colors.conf`  | `~/.config/hypr/hyprlock-colors.conf`       | `hyprlock.conf`       |
| `waybar-matugen.css`    | `~/.config/waybar/colors/matugen.css`       | `style.css` import    |
| `swaync-colors.css`     | `~/.config/swaync/matugen/colors.css`       | `style.css` import    |
| `kitty-colors.conf`     | `~/.config/kitty/themes/Matugen.conf`       | `kitty.conf` include  |
| `rofi-colors.rasi`      | `~/.config/rofi/shared/colors.rasi`         | Launcher styles       |
| `gtk-colors.css`        | `~/.config/gtk-3.0/colors.css`              | `gtk.css` import      |
| `gtk-colors.css`        | `~/.config/gtk-4.0/colors.css`              | GTK4 theme            |
| `qtct-colors.conf`      | `~/.config/qt6ct/colors/matugen.conf`       | `qt6ct.conf`          |
| `btop.theme`            | `~/.config/btop/themes/matugen.theme`       | `btop.conf` theme     |
| `nvim-colors.json`      | `~/.config/matugen/themes/nvim-colors.json` | Opt-in neovim palette |
| `opencode-colors.json`  | `~/.config/opencode/themes/matugen.json`    | OpenCode theme        |
| `shell-colors.sh`       | `~/.config/zsh/generated/colors.sh`         | `15-matugen.zsh`      |

Post-hooks: `pkill -SIGUSR1 kitty`, `pkill -USR2 btop`.

## Notes

- `*.bak-*` files under `templates/` are local debris.
- `version_check = false`, `prefer = "closest-to-fallback"`, `contrast = 0.0`.
- Never hand-edit outputs; re-run `set-wall.sh`.
