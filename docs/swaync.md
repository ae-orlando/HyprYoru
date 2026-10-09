# SwayNC

Notification daemon + control center. Daemon: `swaync`. Bar helper: `swaync-client -swb`.

## Files

| Path                         | Purpose                                   |
| ---------------------------- | ----------------------------------------- |
| `config.json`                | Widgets: mpris, buttons-grid, volume, DND |
| `style.css`                  | Imports generated + static styles         |
| `matugen/colors.css`         | Generated palette                         |
| `Styles/notifications.css`   | Popup styling                             |
| `Styles/central_control.css` | Control-center styling                    |

## Commands

```bash
swaync
swaync-client -swb
swaync-client -rs
swaync-client -t -sw
```

## Notes

- Buttons-grid calls rofi helpers (`wifi.sh`, `rofi-bluetooth`, `screenshot.sh`, `powermenu.sh`), `hyprpicker -a`, and `waypaper`.
- `launch.sh` (Waybar) hard-restarts both `waybar` and `swaync`; prefer `swaync-client -rs` for theme-only reloads.
