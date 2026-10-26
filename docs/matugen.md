# Matugen

Matugen supplies the wallpaper-derived roles. `hyprland/scripts/palette.py`
coordinates wallpaper, palette, and dark/light state; `matugen/config.toml` is
the template source of truth. Generated output files are gitignored—edit their
templates, never the outputs.

## Apply a wallpaper or change mode

```bash
~/.config/hypr/scripts/set-wall.sh <wallpaper>
~/.config/hypr/scripts/set-wall.sh --pick
~/.config/swaync/scripts/toggle-theme.sh
```

The two shell entry points call the same coordinator. `set-wall.sh` starts the
`awww` center transition immediately, then waits two seconds before rendering
the palette. The coordinator reads the **active** Matugen config, makes an
isolated config with temporary output paths and no hooks, checks every output,
and publishes them with rollback on publication failure. Only the latest
request can publish. It saves `~/.cache/matugen/current-wallpaper` and
`current-mode` with the palette, then reloads Hyprland, Waybar, SwayNC, Kitty,
and btop once. An explicit theme toggle changes GTK preferences with
`gsettings`; wallpaper changes do not override GTK preferences if application
defaults were not selected at install time. The tracked `settings.ini` files
are never edited. Lock-screen and Rofi backdrops are prepared during the
transition but published only after that request's palette succeeds.

The wallpaper will be restored to the last successful one if palette
generation fails. A missing explicit path or cancelled picker makes no
changes. If there is no previous successful wallpaper on first boot, the
failed wallpaper cannot be rolled back; the error is printed to stderr.

`[config.wallpaper] set = false`: Matugen never calls `awww` itself. The
`command` in `config.toml` is required by Matugen even though `set` is false.
Running `matugen image` directly remains useful for manual template work, but
bypasses concurrency/rollback protections.

## Generated-file map

| Template (`matugen/templates/`) | Output | Consumer |
| --- | --- | --- |
| `hypr-colors.lua` | `~/.config/hypr/modules/colors.lua` | Hyprland borders |
| `hyprlock-colors.conf` | `~/.config/hypr/hyprlock-colors.conf` | Hyprlock |
| `waybar-matugen.css` | `~/.config/waybar/colors/matugen.css` | Waybar |
| `swaync-colors.css` | `~/.config/swaync/matugen/colors.css` | SwayNC |
| `kitty-colors.conf` | `~/.config/kitty/themes/Matugen.conf` | Kitty and terminal colors |
| `rofi-colors.rasi` | `~/.config/rofi/shared/colors.rasi` | Rofi |
| `gtk-colors.css` | `~/.config/gtk-3.0/colors.css`, `~/.config/gtk-4.0/colors.css` | GTK 3/4 |
| `qtct-colors.conf` | `~/.config/qt6ct/colors/matugen.conf` | Qt6CT |
| `btop.theme` | `~/.config/btop/themes/matugen.theme` | btop |
| `nvim-colors.json` | `~/.config/matugen/themes/nvim-colors.json` | Opt-in Neovim palette |
| `shell-colors.sh` | `~/.config/zsh/generated/colors.sh` | Zsh/fzf |

OpenCode V2 uses its `system` theme to derive colors from Kitty's foreground,
background, and ANSI slots. This repo no longer generates the old-format
OpenCode theme in the separately managed tools directory. An existing custom
file there is **not** deleted. If it was selected, choose `system` in OpenCode
to follow Matugen. No OpenCode settings are changed by this repo.

The original Matugen `post_hook`s remain available for **direct** Matugen
invocations. Coordinated wallpaper/theme runs render without those hooks and
send the same graceful signals once after publication. Never kill the bar or
notification daemon for a palette refresh.

## Fresh installs and shell opt-out

`install.sh` seeds wallpapers and runs Matugen palette-only (no wallpaper
daemon required), honoring `~/.cache/matugen/current-mode` when present.
Hyprland autostart restores the last successful wallpaper and regenerates the
palette on login. With `--no-shell`, the installer supplies a private Matugen
config without the shell template; the coordinator reads that active config
and never writes the unselected shell's files.

The default is a tonal-spot palette with a restrained contrast. Waybar status
colors, Qt widget states, GTK surfaces, and Kitty ANSI slots use Material roles
rather than fixed white/gray values; hues remain wallpaper-derived. For a
different look, change `matugen/config.toml` or a template, then regenerate.

## Tests (sandboxed; no desktop reload)

```bash
python3 -B tests/test_gtk_palette.py
python3 -B tests/test_matugen_palette.py
python3 -B tests/test_palette_pipeline.py
python3 -B tests/test_install.py
```
