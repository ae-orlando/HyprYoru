# Waybar

Top bar. Config: `waybar/config.jsonc`. Style entry: `waybar/style.css` imports `colors/matugen.css` then `colors/style.css`.

## Layout

- Left: `custom/apps` (opens `yoru-main.sh`), `hyprland/workspaces`.
- Center: `bluetooth`, `clock`, `custom/notification`.
- Right: `group/system` (`cpu` + `memory` + `temperature` drawer), `network`, `group/audio` (`pulseaudio` + `custom/mic` drawer), `battery`, `power-profiles-daemon`, `tray`.

## Files

| Path                  | Purpose                                           |
| --------------------- | ------------------------------------------------- |
| `config.jsonc`        | Bar definition (Waybar `v0.15.0` reads `jsonc`)   |
| `style.css`           | Two `@import` lines for generated + static colors |
| `colors/matugen.css`  | Generated palette                                 |
| `colors/style.css`    | Static pill/workspaces styling                    |
| `network_menu.xml`    | `network` click menu                              |

## Scripts

| Script              | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `scripts/mic.sh`    | `custom/mic` source mute/active state                |
| `scripts/updates.sh`  | Dormant: pending-count JSON, hidden unless >100 updates and unwired (no `custom/updates` module) |
| `scripts/update-now.sh` | Dormant: paired `yay -Syu` runner for `updates.sh` |
| `scripts/launch.sh` | Hard restart `waybar` + `swaync`                     |

## Commands

```bash
waybar
~/.config/waybar/scripts/launch.sh
pkill -SIGUSR2 waybar
swaync-client -rs
```

## Notes

- System drawer: `group/system` (`waybar/config.jsonc:151`) expands on hover; `cpu`/`memory`/`temperature` open `kitty -e btop` on click. `temperature` reads `thermal-zone: 0`, critical at 80°C. Styling: `#system` drawer + `#cpu`/`#memory`/`#temperature` accents in `waybar/colors/style.css:251`.
- Theme reloads: matugen `post_hook` (`matugen/config.toml:36`) owns `SIGUSR2`; scripts must not duplicate it or the bar reloads twice. `launch.sh` hard restart is manual-only (drops tray state).
