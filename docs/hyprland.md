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

`modules.colors-fallback` is not in that list: `modules.general` requires it
only while the generated `modules.colors` is absent (first boot).

## Files

| Path                          | Purpose                                                                                                |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| `hyprland.lua`                | Entry point, 9 `require` calls                                                                         |
| `modules/colors.lua`          | Generated palette (see `docs/matugen.md`)                                                              |
| `modules/colors-fallback.lua` | Static first-boot palette, used while `colors.lua` is absent                                           |
| `modules/env.lua`             | Env vars incl. `QT_QPA_PLATFORMTHEME=qt6ct`, cursor theme/size                                         |
| `modules/monitors.lua`        | `eDP-1` + empty-output fallback                                                                        |
| `modules/general.lua`         | Look, animations, misc                                                                                 |
| `modules/layouts.lua`         | Dwindle (active) / master + scrolling (dormant)                                                        |
| `modules/input.lua`           | Keyboard, touchpad, gestures                                                                           |
| `modules/rules.lua`           | Window/workspace/layer rules                                                                           |
| `modules/binds.lua`           | All keybindings: app launchers, compositor controls, media/hardware keys and screenshots               |
| `modules/autostart.lua`       | User-local Waybar/SwayNC launchers (distro fallback), clipboard watcher, `hypridle`, `awww-daemon`     |
| `hypridle.conf`               | Idle daemon (`lock_cmd = pidof hyprlock`)                                                              |
| `hyprlock.conf`               | Lock screen, sources `hyprlock-colors.conf`                                                            |
| `hyprlock-colors.conf`        | Generated palette                                                                                      |
| `scripts/set-wall.sh`         | Wallpaper (`awww` immediate) + deferred rofi/hyprlock + `matugen` palette + `hyprctl` (bars via hooks) |
| `scripts/nightlight.sh`       | `hyprsunset` 6500K/4000K toggle                                                                        |
| `whatsong.sh`                 | Now-playing for hyprlock (`playerctl`)                                                                 |
| `wallpapers/`                 | 10 seed wallpapers                                                                                     |
| `.luarc.json`                 | Lua LSP stubs at `/usr/share/hypr/stubs`                                                               |

## Commands

```bash
hyprctl reload
hyprctl monitors
~/.config/hypr/scripts/set-wall.sh ~/Pictures/wallpapers/mystical-night-in-town.jpg
~/.config/hypr/scripts/nightlight.sh
```

## Notes

- `monitors.lua` hardcodes one `eDP-1` mode (this machine's laptop panel); other/hot-plugged outputs use the empty-output fallback.
- All keybindings and the `mainMod`/`shiftMod` modifiers live in `hyprland/modules/binds.lua`.
- `general.lua` pins `layout = "dwindle"`; the `master` and `scrolling` blocks in `layouts.lua` are dormant until that changes.
- `autostart.lua` expects `polkit-gnome-authentication-agent-1`, `nm-applet --indicator`, `hyprsunset`, `awww-daemon`. Cursor theme/size come from `env.lua`, not a `hyprctl setcursor` call.
