# GTK and Qt

Shared dark theme: `adw-gtk3-dark`, icons `kora-pgrey`, cursor `Bibata-Modern-Classic 24`, font `Adwaita Sans Medium 11`.

## Files

| Path                               | Purpose                                  |
| ---------------------------------- | ---------------------------------------- |
| `gtk-setting/gtk-3.0/settings.ini` | GTK3 theme/icon/cursor/font              |
| `gtk-setting/gtk-3.0/gtk.css`      | Imports `colors.css`, medium font weight |
| `gtk-setting/gtk-3.0/colors.css`   | Generated palette (matugen)              |
| `gtk-setting/gtk-3.0/bookmarks`    | Gitignored file-manager bookmarks        |
| `gtk-setting/gtk-4.0/settings.ini` | GTK4 theme/icon/cursor/font              |
| `gtk-setting/gtk-4.0/colors.css`   | Generated palette (matugen)              |
| `gtk-setting/gtk-4.0/gtk.css`      | Imports `colors.css` (matugen)            |
| `qt6ct/qt6ct.conf`                 | Fusion style + `colors/matugen.conf`     |
| `qt6ct/colors/matugen.conf`        | Generated palette (matugen)              |
| `qt6ct/qss/`                       | Empty stylesheet dir                     |

## Live Settings

`install.sh` applies via `gsettings`:

```bash
gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark'
gsettings set org.gnome.desktop.interface icon-theme 'kora-pgrey'
gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Classic'
gsettings set org.gnome.desktop.interface font-name 'Adwaita Sans Medium 11'
```

Hyprland also sets `QT_QPA_PLATFORMTHEME=qt6ct`, `XCURSOR_THEME`, `XCURSOR_SIZE=24` in `hyprland/modules/env.lua`.
