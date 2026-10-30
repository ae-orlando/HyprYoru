# Btop

System monitor. Config: `btop/btop.conf` (`color_theme = "matugen"`, `theme_background = false`).

## Files

| Path                   | Purpose                     |
| ---------------------- | --------------------------- |
| `btop.conf`            | Main config                 |
| `themes/matugen.theme` | Generated palette (matugen) |

## Notes

- The coordinator sends `USR2` once after a wallpaper/theme change; Matugen's `post_hook` does the same for direct Matugen runs.
- Waybar `cpu`/`memory`/`temperature` modules open `kitty -e btop` on click (`waybar/config.jsonc:201`, `waybar/config.jsonc:208`, `waybar/config.jsonc:218`).
