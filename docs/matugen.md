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
and publishes them with a durable journal and rollback on publication failure.
Only the latest request can publish. It saves `~/.cache/matugen/current-wallpaper` and
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

## Automatic recovery after interruption

No manual command is needed after a power cut. At login,
`hyprland/scripts/start-themed-desktop.sh` runs recovery **before** starting
Waybar or SwayNC, then restores the saved wallpaper through `set-wall.sh`.
Wallpaper, toggle, and backdrop invocations also recover when the coordinator
is idle. Normal wallpaper requests can still overlap; recovery never removes
another live job's workspace. Explicit recovery waits for live jobs to finish.

`hyprland/scripts/palette_store.py` writes a journal under
`~/.cache/matugen/transactions/` before creating identifiable sibling staging
files beside each output. New contents and backups are flushed with `fsync`
before any replacement. The batch is marked committed only after all output
renames and their parent directories are flushed:

- **Interrupted preparation:** discard staging; existing themes were untouched.
- **Interrupted publication/rollback:** restore the previous files and saved
  state. Backups remain available until rollback is durably complete, so
  recovery can itself be interrupted and repeated.
- **Committed publication:** keep the new themes; finish removing backups.

Recovery resets stale `intent.json` to `committed.json`, the wallpaper/mode
snapshot published in the same batch as the themes. It removes abandoned
`render-<ID>` / `backdrop-<ID>` directories only inside the dedicated
`~/.cache/matugen/work/` namespace, plus specifically named coordinator state
temporaries. It never sweeps generic `tmp*` files or unidentified legacy debris.
Kernel locks release on process death/reboot; the empty lock files can remain.

For diagnostics or recovery without a new wallpaper transition:

```bash
python3 ~/.config/hypr/scripts/palette.py recover
```

This command repairs files/state only; it does not set a wallpaper or reload
running applications. A missing/damaged backup or an unexpected external edit
causes recovery to stop with an error and retain its journal rather than
overwrite the edit. The login wrapper also stops before launching themed
daemons if recovery fails. Do not delete journals/backups before inspecting
such an error. These protections assume a filesystem/device that honors
`fsync`; they do not repair filesystem corruption or recover journals deleted
by an external cache cleaner. Direct Matugen/installer renders bypass the
transaction journal.

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
python3 -B tests/test_palette_recovery.py
python3 -B tests/test_install.py
```
