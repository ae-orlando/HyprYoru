# Waypaper

Wallpaper picker GUI. Config: `waypaper/config.ini`.

## Key Settings

```ini
backend = none
folder = ~/Pictures/wallpapers
post_command = ~/.config/hypr/scripts/set-wall.sh $wallpaper
wallpaper = ~/Pictures/wallpapers/mystical-night-in-town.jpg
```

## Notes

- `backend = none` means Waypaper never sets the wallpaper itself; `post_command` hands off to `set-wall.sh`, which runs `matugen` (`awww img ...`).
- `stylesheet = ~/.config/waypaper/style.css` points to a file that does not exist; Waypaper falls back to its default (harmless).
- `install.sh` seeds `~/Pictures/wallpapers` from `hyprland/wallpapers/` with `cp -n` (no overwrite).
- `config.ini` is gitignored runtime state (`wallpaper = ...` changes on every pick). The committed `config.ini.example` is the seed; `install.sh` copies it to `config.ini` on fresh clones (no overwrite).
