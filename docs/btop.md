# Btop

System monitor. Config: `btop/btop.conf` (`color_theme = "matugen"`, `theme_background = false`).

## Files

| Path                   | Purpose                     |
| ---------------------- | --------------------------- |
| `btop.conf`            | Main config                 |
| `themes/matugen.theme` | Generated palette (matugen) |

## Notes

- Matugen `post_hook` sends `USR2` to btop on palette change.
- Waybar `cpu`/`memory`/`disk`/`temperature` modules open `kitty -e btop` on right-click.
