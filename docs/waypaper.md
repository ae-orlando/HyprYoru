# Waypaper

Wallpaper picker GUI. Config: `waypaper/config.ini`.

## Key Settings

```ini
backend = none
folder = ~/Pictures/wallpapers
post_command = ~/.config/hypr/scripts/set-wall.sh "$wallpaper"
wallpaper = ~/Pictures/wallpapers/mystical-night-in-town.jpg
```

## Notes

- `backend = none` means Waypaper never sets the wallpaper itself; `post_command` hands off to `set-wall.sh`, which runs `awww img ...` (center 2s) first, then `matugen` palette-only (`[config.wallpaper] set=false`). `swww_*` keys are ignored.
- `stylesheet = ~/.config/waypaper/style.css` points to a file that does not exist; Waypaper falls back to its default (harmless).
- `install.sh` seeds `~/Pictures/wallpapers` from `hyprland/wallpapers/` with `cp -n` (no overwrite).
- `config.ini` is gitignored runtime state (`wallpaper = ...` changes on every pick). The committed `config.ini.example` is the seed; `install.sh` copies it to `config.ini` on fresh clones (no overwrite).
- Binds default to the Rofi picker: `SUPER+W` runs `~/.config/rofi/launchers/wall-changer.sh`, `SUPER+SHIFT+W` runs it with `--random` (`hyprland/modules/binds.lua:190-197`). Waypaper stays installed but unbound; see below to switch.

## Prefer Waypaper? Switching the picker

The default binds use the custom Rofi thumbnail launcher
(`rofi/launchers/wall-changer.sh`). Waypaper stays installed for its exclusive
features: slideshow, Wallpaper Engine (`linux_wallpaperengine_*`), mpvpaper
video wallpapers, GIF filtering, per-monitor fills, and its own stylesheet and
keybindings. Both pickers share the same pipeline — with `backend = none` +
`post_command`, either one lands in `set-wall.sh` (awww transition → matugen
palette), so the theme behaves identically.

1. Confirm Waypaper is installed (it's in `packages/core-aur.txt`; skipped by
   `install.sh --no-aur`):

   ```bash
   command -v waypaper
   ```

2. Verify `~/.config/waypaper/config.ini` has the hand-off (seeded from
   `config.ini.example`). Without it, `backend = none` means picks do nothing:

   ```ini
   backend = none
   post_command = ~/.config/hypr/scripts/set-wall.sh "$wallpaper"
   ```

3. Repoint the binds — one variable drives both
   (`hyprland/modules/binds.lua:25`):

   ```lua
   -- Rofi (default):
   local wallpaperPicker = "~/.config/rofi/launchers/wall-changer.sh"
   -- Waypaper:
   local wallpaperPicker = "waypaper"
   ```

   `SUPER+W` opens the GUI, `SUPER+SHIFT+W` runs `waypaper --random`.

4. Optional: point the SwayNC control-center wallpaper button at Waypaper too —
   in `swaync/config.json`, change the wallpaper tool command
   `~/.config/swaync/scripts/open-rofi.sh wallpaper` to `waypaper`.
   (As-is, the Rofi picker stays reachable from the control center.)

5. `hyprctl reload`, then test both binds.

To go back, restore the `wall-changer.sh` value in step 3.
