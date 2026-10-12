# Matugen

Palette hub. One wallpaper run regenerates every app theme. Config: `matugen/config.toml` (88 lines).

## Wallpaper Flow

```toml
[config.wallpaper]
set = false
command = "awww img --transition-type center --transition-duration 2 {{ image }}"
```

`set = false` (`matugen/config.toml:19`): matugen is palette-only. Run the wrapper, not `matugen` directly (direct runs change no wallpaper):

```bash
~/.config/hypr/scripts/set-wall.sh <wallpaper>
```

Order in `hyprland/scripts/set-wall.sh:60-95`: cache write → `awww img` immediate (`:71`) → backgrounded hyprlock `cp` + rofi rasi (`:77-78`) → palette-phase `flock` (`:82-83`) → `sleep 2` (`:88`) → `matugen image` (`:90`) → `hyprctl reload` (`:95`). Bars reload once via `post_hook`s below.

## Generated-File Map

| Template (`templates/`) | Output                                      | Consumer              |
| ----------------------- | ------------------------------------------- | --------------------- |
| `hypr-colors.lua`       | `~/.config/hypr/modules/colors.lua`         | `general.lua` borders |
| `hyprlock-colors.conf`  | `~/.config/hypr/hyprlock-colors.conf`       | `hyprlock.conf`       |
| `waybar-matugen.css`    | `~/.config/waybar/colors/matugen.css`       | `style.css` import    |
| `swaync-colors.css`     | `~/.config/swaync/matugen/colors.css`       | `style.css` import    |
| `kitty-colors.conf`     | `~/.config/kitty/themes/Matugen.conf`       | `kitty.conf` include  |
| `rofi-colors.rasi`      | `~/.config/rofi/shared/colors.rasi`         | Launcher styles       |
| `gtk-colors.css`        | `~/.config/gtk-3.0/colors.css`              | `gtk.css` import      |
| `gtk-colors.css`        | `~/.config/gtk-4.0/colors.css`              | GTK4 theme            |
| `qtct-colors.conf`      | `~/.config/qt6ct/colors/matugen.conf`       | `qt6ct.conf`          |
| `btop.theme`            | `~/.config/btop/themes/matugen.theme`       | `btop.conf` theme     |
| `nvim-colors.json`      | `~/.config/matugen/themes/nvim-colors.json` | Opt-in neovim palette |
| `opencode-colors.json`  | `~/.config/opencode/themes/matugen.json`    | OpenCode theme        |
| `shell-colors.sh`       | `~/.config/zsh/generated/colors.sh`         | `15-matugen.zsh`      |

Post-hooks (`matugen/config.toml:36,42,48,73`): `pkill -SIGUSR2 waybar`, `swaync-client -rs`, `pkill -SIGUSR1 kitty`, `pkill -USR2 btop`. Single owner — do not duplicate in scripts.

## Regeneration (gitignored artifacts)

Outputs above are **not committed** (see root `.gitignore`). They are
reproducible artifacts rebuilt in two places:

- `install.sh:phase_theming` — runs `matugen image $wall` on every install.
- Hyprland autostart (`modules/autostart.lua`) — `set-wall.sh` restores the
  last wallpaper (`~/.cache/matugen/current-wallpaper`) or `anime3.png` on
  every login and regenerates all outputs.

So changing wallpaper never dirties `git`, and a fresh clone gets colors by
running `./install.sh` (which also seeds `~/Pictures/wallpapers` from
`hyprland/wallpapers/` and `waypaper/config.ini` from
`waypaper/config.ini.example`).

## Notes

- `*.bak-*` files under `templates/` are local debris.
- `version_check = false`, `prefer = "closest-to-fallback"`, `contrast = 0.0`.
- Never hand-edit outputs; re-run `set-wall.sh`.
- Transition duration (`set-wall.sh:71`) must equal `sleep` (`:88`), or colors land ahead of/behind the wallpaper.
- Rofi/hyprlock backdrops render in the background during the transition; rofi reads them lazily.
