# Hyprland

Lua config (`~/.config/hypr/hyprland.lua`). One topic per module; reload with `hyprctl reload`.

## Entry Point

`hyprland/hyprland.lua` requires 9 modules:

- `modules.colors` (matugen-generated, do not hand-edit)
- `modules.env`
- `modules.monitors`
- `modules.general`
- `modules.layouts`
- `modules.input`
- `modules.rules`
- `modules.binds`
- `modules.autostart`

## Files

| Path                    | Purpose                                       |
| ----------------------- | --------------------------------------------- |
| `hyprland.lua`          | Entry point, 9 `require` calls                |
| `modules/colors.lua`    | Generated palette (see `docs/matugen.md`)     |
| `modules/env.lua`       | Env vars incl. `QT_QPA_PLATFORMTHEME=qt6ct`   |
| `modules/monitors.lua`  | `eDP-1` + empty-output fallback               |
| `modules/general.lua`   | Look, animations, misc                        |
| `modules/layouts.lua`   | Dwindle/master/scrolling                      |
| `modules/input.lua`     | Keyboard, touchpad, gestures                  |
| `modules/rules.lua`     | Window/workspace/layer rules                  |
| `modules/binds.lua`     | Keybindings                                   |
| `modules/autostart.lua` | `waybar`, `swaync`, `hypridle`, `awww-daemon` |
| `hypridle.conf`         | Idle daemon (`lock_cmd = pidof hyprlock`)     |
| `hyprlock.conf`         | Lock screen, sources `hyprlock-colors.conf`   |
| `hyprlock-colors.conf`  | Generated palette                             |
| `scripts/set-wall.sh`   | Wallpaper + `matugen` + rofi wallpaper rasi + bar reloads |
| `scripts/nightlight.sh` | `hyprsunset` 6500K/4000K toggle               |
| `whatsong.sh`           | Now-playing for hyprlock (`playerctl`)        |
| `wallpapers/`           | 10 seed wallpapers                            |
| `.luarc.json`           | Lua LSP stubs at `/usr/share/hypr/stubs`      |

## Commands

```bash
hyprctl reload
hyprctl monitors
~/.config/hypr/scripts/set-wall.sh ~/Pictures/wallpapers/mystical-night-in-town.jpg
~/.config/hypr/scripts/nightlight.sh
```

## Notes

- `monitors.lua` hardcodes one `eDP-1` mode; untracked monitors use the empty-output fallback.
- `autostart.lua` expects `polkit-gnome-authentication-agent-1`, `nm-applet --indicator`, `hyprsunset`, `awww-daemon`.
