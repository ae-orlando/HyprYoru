# Waybar

Top bar. Config: `waybar/config.jsonc`. Style entry: `waybar/style.css` imports `colors/matugen.css` then `colors/style.css`.

## Layout

- Left: `custom/apps`, `tray`, `bluetooth`, `pulseaudio`, `custom/mic`, `custom/active-app`.
- Center: `clock`, `hyprland/workspaces`, `custom/notification`, `custom/caps`.
- Right: `network`, `group/system`, `power-profiles-daemon`, `battery`, `custom/power`.

## Files

| Path                  | Purpose                                           |
| --------------------- | ------------------------------------------------- |
| `config.jsonc`        | Bar definition (Waybar `v0.15.0` reads `jsonc`)   |
| `style.css`           | Two `@import` lines for generated + static colors |
| `colors/matugen.css`  | Generated palette                                 |
| `colors/style.css`    | Static pill/workspaces styling                    |
| `colors/one-dark.css` | Alternate static palette                          |
| `network_menu.xml`    | `network` click menu                              |
| `power_menu.xml`      | `custom/power` click menu                         |
| `config.back`         | Inactive backup config                            |

## Scripts

| Script                        | Purpose                                   |
| ----------------------------- | ----------------------------------------- |
| `scripts/mic.sh`              | `custom/mic` source mute/active state     |
| `scripts/caps.sh`             | `custom/caps` Caps Lock indicator         |
| `scripts/updates.sh`          | `checkupdates` + `yay` pending-count JSON |
| `scripts/update-now.sh`       | Full `yay -Syu` in kitty + module refresh |
| `scripts/animation.sh`        | `custom/animation` frames                 |
| `scripts/animation-toggle.sh` | Cycle animation mode                      |
| `scripts/launch.sh`           | Hard restart `waybar` + `swaync`          |

## Commands

```bash
waybar
~/.config/waybar/scripts/launch.sh
pkill -SIGUSR2 waybar
swaync-client -rs
```
