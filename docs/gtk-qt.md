# GTK and Qt

GTK switches between `adw-gtk3-dark` and `adw-gtk3` with the Matugen mode.
Icons remain `kora-pgrey`, cursor `Bibata-Modern-Classic 24`, font `Adwaita Sans Medium 11`.

## Files

| Path                               | Purpose                                  |
| ---------------------------------- | ---------------------------------------- |
| `gtk-setting/gtk-3.0/settings.ini` | GTK3 theme/icon/cursor/font              |
| `gtk-setting/gtk-3.0/gtk.css`      | Imports `colors.css`, medium font weight |
| `gtk-setting/gtk-3.0/colors.css`   | Generated palette (matugen)              |
| `gtk-setting/gtk-3.0/bookmarks`    | Gitignored file-manager bookmarks        |
| `gtk-setting/gtk-4.0/settings.ini` | GTK4 theme/icon/cursor/font              |
| `gtk-setting/gtk-4.0/colors.css`   | Generated palette (matugen)              |
| `gtk-setting/gtk-4.0/gtk.css`      | Light adw-gtk3 widgets + Matugen overlay  |
| `gtk-setting/gtk-4.0/gtk-dark.css` | Dark adw-gtk3 widgets + Matugen overlay   |
| `qt6ct/qt6ct.conf`                 | Fusion style + `colors/matugen.conf`     |
| `qt6ct/colors/matugen.conf`        | Generated palette (matugen)              |
| `qt6ct/qss/`                       | Empty stylesheet dir                     |

## Live Settings

`install.sh` sets the chosen GTK preferences when defaults are enabled. An
explicit theme toggle syncs theme and color scheme after a successful palette
render; wallpaper-only changes leave GTK preferences alone. It never rewrites
the tracked `settings.ini` files.
For example, dark mode uses:

```bash
gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark'
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings set org.gnome.desktop.interface icon-theme 'kora-pgrey'
gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Classic'
gsettings set org.gnome.desktop.interface font-name 'Adwaita Sans Medium 11'
```

Hyprland also sets `QT_QPA_PLATFORMTHEME=qt6ct`, `XCURSOR_THEME`, `XCURSOR_SIZE=24` in `hyprland/modules/env.lua`.
Qt6CT maps active, inactive and disabled widget states to different Material
roles; it no longer mixes fixed whites/grays with light-mode surfaces.
