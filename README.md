# HyprYoru

Arch Linux + Hyprland (Lua) desktop configuration with a matugen-driven palette and a guided installer. GDM is optional ([ae-orlando/HyprYoru](https://github.com/ae-orlando/HyprYoru/tree/main)).

## Overview

HyprYoru holds the desktop config (Hyprland, Waybar, Rofi, SwayNC, Kitty, btop, GTK/Qt, Waypaper, Zsh, Fastfetch) plus `install.sh` for an existing Arch installation. Matugen is the palette hub: one wallpaper run regenerates all app themes.

## Prerequisites

- An installed Arch Linux system and a normal user account; do not install as root.
- `sudo` and `pacman` for system installation; `flock` from `util-linux` for the install lock.
- Network access for packages, shell frameworks, or an approved UI download. `--link-only --ui plain` needs no downloads.
- Verified versions on source: Hyprland `0.56.2`, matugen `4.2.0`, Waybar `v0.15.0`.

## Installation

Clone HyprYoru, then run `install.sh` from the repo root:

```bash
git clone https://github.com/ae-orlando/HyprYoru.git ~/Dev/dotfiles
cd ~/Dev/dotfiles
./install.sh --dry-run
./install.sh
```

Common variants:

```bash
./install.sh --profile core --yes    # desktop + configured shell (default)
./install.sh --profile full --yes    # also add optional apps/dev tools
./install.sh --with-gdm              # opt in to graphical login
./install.sh --only-dotfiles --yes
./install.sh --link-only --yes       # links + ZDOTDIR only
./install.sh --no-shell              # keep your current shell configuration
./install.sh --ui plain              # force the numbered-prompt wizard
./install.sh --check                 # read-only diagnostics
./install.sh --help
```

The guided flow is **Welcome → Components → Review → Installation → Results**. Before opening menus, the installer prefers compatible system Gum, then a verified private cache. If neither is available, it offers a one-time download of a pinned, checksum-verified Gum runtime—no sudo or system package installation. Approving this preparation makes the first menu enhanced; declining or a preparation failure uses equivalent numbered prompts.

`--ui plain`, `--yes`, explicit `--dry-run`, and explicit `--check` bypass UI downloads and cache inspection. An approved UI download stays cached even if you later cancel the wizard or select Preview; the desktop installation plan still makes no changes in preview mode.

Review selected/missing package counts, expandable config/service actions, backup paths, and preferences before approving. `core` is the default; Zsh is selected by default but optional. GDM, WWAN, login-shell changes, and application defaults are opt-in. Deselecting a component never uninstalls it. See [installation details](docs/install.md) for flags, service policy, and restoration.

Package lists live in `packages/*.txt`. Neither profile adds kernels, bootloaders, or GPU drivers; the standard package phase still performs a full Arch system upgrade. These manifests select software, not pinned versions or an exact machine snapshot.

The installer links desktop and shell configs only. Developer-tool configs (tmux, VSCodium, OpenCode) belong to the separate `tools` repository and are linked by its own `install.sh`.

## Usage

- Reload Hyprland after editing a module: `hyprctl reload`.
- Set wallpaper + regenerate palette: `~/.config/hypr/scripts/set-wall.sh <wallpaper>`.
- Toggle night light: `~/.config/hypr/scripts/nightlight.sh`.
- Reload the bar and notification CSS without killing either daemon: `~/.config/waybar/scripts/launch.sh`.
- For locally installed patched builds, check the running binaries with `yoru-desktop status`. The binaries are **user-local files, not pacman/AUR packages**; pacman still owns separate `/usr/bin` copies. See [patched desktop maintenance](docs/patched-desktop.md) for setup, package ownership, updates and controlled restarts.
- Re-check system state without changes: `./install.sh --check`.

## Project Structure

```text
.
├── install.sh
├── lib/           # shared plan, verified Gum runtime, wizard, logging
├── packages/      # desktop/shell/extra official and AUR manifests
├── services/      # optional Fibocom WWAN unit
├── tests/         # sandboxed installer regression tests
├── hyprland/      # hyprland.lua + modules/, scripts/, hypridle/lock
├── matugen/       # config.toml + templates/ (palette hub)
├── waybar/        # config.jsonc + style + scripts/
├── rofi/          # config.rasi + launchers/ + styles/ + shared/
├── swaync/        # config.json + Styles/ + matugen/
├── kitty/         # kitty.conf + themes/Matugen.conf
├── zsh/           # .zshrc + conf.d/pre + conf.d/post + generated/
├── waypaper/      # config.ini (backend=none)
├── btop/          # btop.conf + themes/
├── fastfetch/     # config.jsonc + png/
├── gtk-setting/   # gtk-3.0/ + gtk-4.0/
├── qt6ct/         # qt6ct.conf + colors/
└── docs/          # per-module guides
```

Per-module docs live in `docs/`. Start with `docs/install.md`, then `docs/hyprland.md` and `docs/matugen.md`.

## Installer checks

Run local regression tests without installing packages or changing the live desktop:

```bash
bash -n install.sh
bash -n lib/install-ui.sh
bash -n lib/install-plan.sh
bash -n lib/install-wizard.sh
bash -n lib/gum-runtime.sh
python3 -B tests/test_install.py
```
