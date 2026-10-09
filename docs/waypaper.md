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
- `stylesheet = /home/orlando/.config/waypaper/style.css` points to a file that does not exist; Waypaper falls back to its default (harmless).
- `install.sh` seeds `~/Pictures/wallpapers` from `hyprland/wallpapers/` with `cp -n` (no overwrite).
