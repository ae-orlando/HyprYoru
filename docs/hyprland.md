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
| `modules/autostart.lua`       | Recovery-gated themed desktop startup, clipboard watcher, `hypridle`, `awww-daemon`                     |
| `hypridle.conf`               | Idle daemon (`lock_cmd = pidof hyprlock`)                                                              |
| `hyprlock.conf`               | Lock screen, sources `hyprlock-colors.conf`                                                            |
| `hyprlock-colors.conf`        | Generated palette                                                                                      |
| `scripts/set-wall.sh`         | Stable wrapper for `scripts/palette.py`: immediate `awww`, staged Matugen palette and deferred backdrops |
| `scripts/palette.py`          | Coordinates wallpaper/theme requests and graceful consumer reloads                                     |
| `scripts/palette_store.py`    | Durable publication journals, crash recovery and owned workspace cleanup                               |
| `scripts/start-themed-desktop.sh` | Recovers before starting Waybar/SwayNC, then restores the wallpaper                                 |
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

## Keybindings

All keybindings live in `hyprland/modules/binds.lua` using `mainMod` (SUPER) and
`shiftMod` (SUPER + SHIFT). Notable bindings:

- `shiftMod + return` — open a floating, centered mini terminal (700×450).
- `shiftMod + K` — toggle the showmethekey keystroke overlay (keycast).
- `altMod + R` (SUPER + ALT + R) — toggle Waybar on/off.
- `altMod + F` (SUPER + ALT + F) — true fullscreen (hides the waybar).
- `mainMod + R` — reload Waybar (`launch.sh`).
- `mainMod + T` — toggle floating.
- `shiftMod + F` — maximize window.
- `mainMod + P` — toggle pseudotile.

The keycast overlay (`one.alynx.showmethekey`) has a matching window rule
(`hyprland/modules/rules.lua`): floating, pinned, no focus, borderless, no
shadow, 75% opacity, sized 600×100 and placed bottom-right. See
`hyprland/scripts/keycast-toggle.sh` for the toggle script.

Animations and blur were re-tuned: blur passes reduced to 1 (size 6), window
animations use `popin 82%`/`slidefade 20%` styles, and Rofi animations use
`popin 82%`.

## Notes

- `monitors.lua` hardcodes one `eDP-1` mode (this machine's laptop panel); other/hot-plugged outputs use the empty-output fallback.
- All keybindings and the `mainMod`/`shiftMod` modifiers live in `hyprland/modules/binds.lua`.
- `general.lua` pins `layout = "dwindle"`; the `master` and `scrolling` blocks in `layouts.lua` are dormant until that changes.
- `autostart.lua` expects `polkit-gnome-authentication-agent-1`, `nm-applet --indicator`, `hyprsunset`, `awww-daemon`. Cursor theme/size come from `env.lua`, not a `hyprctl setcursor` call.
