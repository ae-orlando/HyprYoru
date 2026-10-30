# Waybar

Top bar. Config: `waybar/config.jsonc`. Style entry: `waybar/style.css` imports `colors/matugen.css` then `colors/style.css`.

## Layout

- Left: `custom/apps` (opens `yoru-main.sh`), `hyprland/workspaces`, `hyprland/window` (active window indicator).
- Center: the date/time clock, independently centered.
- Right: `group/system` (`cpu` + `memory` + `temperature` drawer), `custom/updates` (pending Arch/AUR count + on-click upgrade), `group/connections` (`custom/network` + `bluetooth`), `group/audio` (`pulseaudio` + `custom/mic`), `group/power` (`battery` + `power-profiles-daemon`), `tray`, `custom/notification`.

These form three floating islands. An active/muted microphone stays visible;
only the system statistics use a hover drawer. Radio clicks open the native
connection drawers rather than toggling power.

## Files

| Path                  | Purpose                                           |
| --------------------- | ------------------------------------------------- |
| `config.jsonc`        | Bar definition (Waybar `v0.15.0` reads `jsonc`)   |
| `style.css`           | Two `@import` lines for generated + static colors |
| `colors/matugen.css`  | Generated palette                                 |
| `colors/style.css`    | Static pill/workspaces styling                    |
| `network_menu.xml`    | Legacy menu, not wired into the current bar       |

## Scripts

| Script                        | Purpose                                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------------ |
| `scripts/mic.sh`              | `custom/mic` source mute/active state                                                            |
| `scripts/updates.sh`          | Pending-count JSON for `custom/updates`: repos via `checkupdates`, AUR via one batched RPC; hidden when up to date |
| `scripts/update-now.sh`       | On-click `yay -Syu` runner for `custom/updates`; refreshes the count on exit                           |
| `scripts/network.py`          | Read-only NetworkManager status, including hotspot mode                                          |
| `scripts/start-waybar.sh`     | Local compatibility binary, or distro fallback                                                   |
| `scripts/desktop-binaries.py` | Status and controlled daemon restarts (`yoru-desktop`)                                           |
| `scripts/launch.sh`           | In-place Waybar reload + SwayNC CSS reload; no daemon kill                                       |

## Commands

```bash
yoru-desktop status
~/.config/waybar/scripts/launch.sh
yoru-desktop restart waybar
```

## Notes

- System drawer: `group/system` (`waybar/config.jsonc:188`) expands on hover; `cpu`/`memory`/`temperature` open `kitty -e btop` on click. `temperature` reads `thermal-zone: 0`, critical at 80°C.
- Theme reloads: the palette coordinator sends `SIGUSR2` once after all outputs are published; direct Matugen runs use their configured `post_hook`. Super+R manually reloads configuration/style without replacing the executable.
- Pacman owns `/usr/bin/waybar`. The user-local `0.15.0-yoru1` executable is not a pacman/AUR package; it fixes workspace buttons for Hyprland Lua. Build, activation, updates and rollback are covered in [patched desktop maintenance](patched-desktop.md).
