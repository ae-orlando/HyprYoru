# Rofi

Launcher + applets. Base config: `rofi/config.rasi` (`modi: drun,run,filebrowser,window`, `icon-theme: "Tela"`).

## Launchers

| Path                               | Purpose                                                                                                      |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `launchers/yoru-main.sh`           | App launcher, default (`yoru-main.rasi`)                                                                     |
| `launchers/yoru-run.sh`            | Run prompt, default (`yoru-main.rasi`)                                                                       |
| `launchers/gen-wallpaper-rasi.sh`  | Single-pass `magick -resize 50% -blur` → rasi; bg'd by `set-wall.sh:78`, lazy-read by `yoru-main.rasi:36,61` |
| `launchers/type-6/launcher.sh`     | App launcher, fallback (`style-9.rasi`)                                                                      |
| `launchers/type-6/launcher_run.sh` | Run prompt, fallback (`style-9.rasi`)                                                                        |
| `launchers/type-6/style-*.rasi`    | 10 type-6 themes (`style-9` active)                                                                          |
| `launchers/launcher.sh`            | Alt launcher (`styles/launcher`)                                                                             |
| `launchers/powermenu.sh`           | Lock/logout/suspend/hibernate/reboot                                                                         |
| `launchers/screenshot.sh`          | Desktop/area/window via `hyprshot`                                                                           |
| `launchers/wifi.sh`                | `nmcli` network picker                                                                                       |
| `launchers/rofi-bluetooth`         | `bluetoothctl` device menu                                                                                   |
| `launchers/wall-changer.sh`        | Thumbnail picker + `set-wall.sh`                                                                             |
| `launchers/quicklinks.sh`          | Browser quick links                                                                                          |

## Shared and Styles

| Path                      | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `shared/colors.rasi`      | Generated palette (matugen)                |
| `shared/fonts.rasi`       | Shared font                                |
| `shared/theme.bash`       | `applets.rasi` selector for applet scripts |
| `styles/yoru-main.rasi`   | Main theme (ML4W-inspired, `ae. Orlando`; matugen colors) |
| `styles/launcher.rasi`    | Full launcher theme                        |
| `styles/applets.rasi`     | Applet theme                               |
| `styles/wifi-blue.rasi`   | Wi-Fi/Bluetooth menu theme                 |
| `styles/wall-picker.rasi` | Wallpaper grid theme                       |

## Commands

```bash
~/.config/rofi/launchers/yoru-main.sh
~/.config/rofi/launchers/yoru-run.sh
~/.config/rofi/launchers/powermenu.sh
~/.config/rofi/launchers/wifi.sh
rofi -dump-config
```

## Notes

- Default bindings: SUPER+Space app launcher, SHIFT+SUPER+Space run prompt (`hyprland/modules/binds.lua`); Waybar `custom/apps` also opens `yoru-main.sh`. Type-6 stays as fallback.
- `install.sh` forces `+x` on `launchers/*.sh`, `type-6/*.sh`, `rofi-bluetooth` (repo has two `644` files).
- `type-6/style-9.rasi` references `~/.config/rofi/images/i.jpg`, which does not exist (blank imagebox, harmless).
