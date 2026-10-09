# Dotfiles

Arch Linux + GDM + Hyprland (Lua) desktop configuration with a matugen-driven system palette and a one-shot reproducer script.

## Overview

This repo holds the full desktop config (Hyprland, Waybar, Rofi, SwayNC, Kitty, btop, GTK/Qt, Waypaper, Zsh, Fastfetch) plus `install.sh`, which reapplies it on a fresh Arch machine. Matugen is the palette hub: one wallpaper run regenerates all app themes.

## Prerequisites

- Arch Linux (`/etc/arch-release` required by `install.sh`).
- Normal user with `sudo` access. Do not run as root.
- Network access (pacman, AUR, oh-my-zsh, powerlevel10k).
- Verified versions on source: Hyprland `0.56.2`, matugen `4.2.0`, Waybar `v0.15.0`.

## Installation

Run `install.sh` from the repo root:

```bash
./install.sh --dry-run
./install.sh --profile full --yes
```

Common variants:

```bash
./install.sh --profile core --yes
./install.sh --only-dotfiles --yes
./install.sh --no-aur --dry-run
./install.sh --help
```

Phases in order: `phase_preflight`, `phase_base`, `phase_packages`, `phase_services`, `phase_dotfiles`, `phase_shell`, `phase_theming`, `phase_verify`. See `docs/install.md` for the profile/package matrix.

## Usage

- Reload Hyprland after editing a module: `hyprctl reload`.
- Set wallpaper + regenerate palette: `~/.config/hypr/scripts/set-wall.sh <wallpaper>`.
- Toggle night light: `~/.config/hypr/scripts/nightlight.sh`.
- Hard-restart bar + notifications: `~/.config/waybar/scripts/launch.sh`.
- Re-check system state: `./install.sh --only-dotfiles --yes`.

## Project Structure

```text
.
├── install.sh
├── hyprland/      # hyprland.lua + modules/, scripts/, hypridle/lock
├── matugen/       # config.toml + templates/ (palette hub)
├── waybar/        # config.jsonc + style + scripts/
├── rofi/          # config.rasi + launchers/ + styles/ + shared/
├── swaync/        # config.json + Styles/ + matugen/
├── kitty/         # kitty.conf + themes/Matugen.conf
├── zsh/           # .zshrc + conf.d/pre + conf.d/post + generated/
├── waypaper/      # config.ini (backend=none)
├── btop/          # btop.conf + themes/
├── fastfetch/     # config.jsonc + png/ + snaps/
├── gtk-setting/   # gtk-3.0/ + gtk-4.0/
├── qt6ct/         # qt6ct.conf + colors/
└── docs/          # per-module guides
```

Per-module docs live in `docs/`. Start with `docs/install.md`, then `docs/hyprland.md` and `docs/matugen.md`.
