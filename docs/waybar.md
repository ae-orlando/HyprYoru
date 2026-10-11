# Waybar

Top bar. Config: `waybar/config.jsonc`. Style entry: `waybar/style.css` imports `colors/matugen.css` then `colors/style.css`.

## Layout

- Left: `custom/apps` (opens `yoru-main.sh`), `hyprland/workspaces`.
- Center: `bluetooth`, `clock`, `custom/notification`.
- Right: `network`, `group/audio` (`pulseaudio` + `custom/mic` drawer), `battery`, `power-profiles-daemon`, `tray`.

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
