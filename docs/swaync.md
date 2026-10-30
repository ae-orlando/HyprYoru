# SwayNC

Notification daemon + control center. Daemon: `swaync`. Bar helper: `swaync-client -swb`.

## Files

| Path                         | Purpose                                   |
| ---------------------------- | ----------------------------------------- |
| `config.json`                | Widgets: menubar, toggles/connections grids, volume, backlight, mpris, DND, inhibitors, notifications |
| `style.css`                  | Imports generated + static styles (tokens, base, notifications, control center) |
| `matugen/colors.css`         | Generated palette                         |
| `Styles/tokens.css`          | Semantic token mapping from matugen roles  |
| `Styles/base.css`            | Shared base styling                       |
| `Styles/notifications.css`   | Popup styling                             |
| `Styles/central_control.css` | Control-center styling                    |

## Commands

```bash
swaync --version
swaync-client -swb
swaync-client -rs
swaync-client -t -sw
yoru-desktop status
```

## Notes

- One navigation tile each opens the native Wi-Fi/Bluetooth drawers. Sound, microphone and dark mode remain direct toggles.
- Tools provides capture, color picker, the canonical wallpaper chooser, audio devices, image annotation and Cliphist history. Clipboard capture skips sensitive offers; the picker provides pause/resume, delete and confirmed clear controls.
- `scripts/toggle-theme.sh` delegates to `hyprland/scripts/palette.py` and flips dark/light without re-animating the wallpaper. The coordinator publishes all themes and then gracefully reloads each consumer once; direct Matugen runs still use their configured post-hooks.
- `launch.sh` (Waybar) reloads the bar and SwayNC CSS without killing the notification daemon. Use `swaync-client -R` for widget/configuration changes.
- Pacman owns `/usr/bin/swaync`. The user-local `0.12.6` backport is not a pacman/AUR package; it fixes live brightness and bounded floating previews, retains full body text in the notification center, and marks its own copied authentication codes as sensitive.
- For executable changes use `yoru-desktop restart swaync`, which refuses to restart with saved notifications. The inbox is not persistent across daemon restarts. See [patched desktop maintenance](patched-desktop.md) for builds, updates and rollback.
