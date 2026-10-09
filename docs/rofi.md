# Rofi

Launcher + applets. Base config: `rofi/config.rasi` (`modi: drun,run,filebrowser,window`, `icon-theme: "Tela"`).

## Launchers

| Path                               | Purpose                              |
| ---------------------------------- | ------------------------------------ |
| `launchers/type-6/launcher.sh`     | App launcher (`style-9.rasi`)        |
| `launchers/type-6/launcher_run.sh` | Run prompt (`style-9.rasi`)          |
| `launchers/type-6/style-*.rasi`    | 10 type-6 themes (`style-9` active)  |
| `launchers/launcher.sh`            | Alt launcher (`styles/launcher`)     |
| `launchers/powermenu.sh`           | Lock/logout/suspend/hibernate/reboot |
| `launchers/screenshot.sh`          | Desktop/area/window via `hyprshot`   |
| `launchers/wifi.sh`                | `nmcli` network picker               |
| `launchers/rofi-bluetooth`         | `bluetoothctl` device menu           |
| `launchers/wall-changer.sh`        | Thumbnail picker + `set-wall.sh`     |
| `launchers/quicklinks.sh`          | Browser quick links                  |

## Shared and Styles

| Path                      | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `shared/colors.rasi`      | Generated palette (matugen)                |
| `shared/fonts.rasi`       | Shared font                                |
| `shared/theme.bash`       | `applets.rasi` selector for applet scripts |
| `styles/launcher.rasi`    | Full launcher theme                        |
| `styles/applets.rasi`     | Applet theme                               |
| `styles/wifi-blue.rasi`   | Wi-Fi/Bluetooth menu theme                 |
| `styles/wall-picker.rasi` | Wallpaper grid theme                       |

## Commands

```bash
~/.config/rofi/launchers/type-6/launcher.sh
~/.config/rofi/launchers/powermenu.sh
~/.config/rofi/launchers/wifi.sh
rofi -dump-config
```

## Notes

- `install.sh` forces `+x` on `launchers/*.sh`, `type-6/*.sh`, `rofi-bluetooth` (repo has two `644` files).
- `type-6/style-9.rasi` references `~/.config/rofi/images/i.jpg`, which does not exist (blank imagebox, harmless).
- `*.bak-*` files under `shared/` and `styles/` are local debris.
