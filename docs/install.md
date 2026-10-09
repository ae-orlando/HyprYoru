# Install

One-shot reproducer for a fresh Arch machine. Idempotent. Backs up replaced paths first.

## Profiles

| Profile | Official pkgs | AUR pkgs | Contents                                                       |
| ------- | ------------- | -------- | -------------------------------------------------------------- |
| `full`  | 151           | 21       | Exact source machine (`PACMAN_CORE` + `PACMAN_EXTRA`, all AUR) |
| `core`  | 111           | 5        | Bootable Hyprland minimum (`PACMAN_CORE` + `AUR_CORE` only)    |

Counts verified in `install.sh`: `PACMAN_CORE` 111, `PACMAN_EXTRA` 40, `AUR_CORE` 5, `AUR_EXTRA` 16.

## Flags

| Flag              | Effect                                                      |
| ----------------- | ----------------------------------------------------------- |
| `--profile`       | `core` or `full` (default `full`)                           |
| `--only-dotfiles` | Skip base/packages/services; link configs + shell + theming |
| `--no-aur`        | Skip AUR packages (cursor/icon themes + `waypaper` missing) |
| `--dry-run`       | Print actions only; needs no `sudo`                         |
| `--yes`           | Non-interactive (`--noconfirm`)                             |
| `--help`          | Print usage                                                 |

## Commands

```bash
./install.sh --dry-run
./install.sh --profile full --yes
./install.sh --profile core --yes
./install.sh --only-dotfiles --yes
```

## Phases

| Phase     | Function in `install.sh` | What it does                                             |
| --------- | ------------------------ | -------------------------------------------------------- |
| Preflight | `phase_preflight`        | Arch/root gates, repo check, backup to `~/.local/state/` |
| Base      | `phase_base`             | `pacman.conf`, reflector, `pacman -Syu`, yay bootstrap   |
| Packages  | `phase_packages`         | Official set, then AUR set via `yay`/`paru`              |
| Services  | `phase_services`         | Custom `wwan-enable.service` + 12 system + 6 user units  |
| Dotfiles  | `phase_dotfiles`         | 13 symlinks, `.zshenv`, perms, dirs, seeds, mime, theme  |
| Shell     | `phase_shell`            | oh-my-zsh, powerlevel10k, `chsh -s zsh`                  |
| Theming   | `phase_theming`          | One `matugen image` run from default wallpaper           |
| Verify    | `phase_verify`           | Binaries, symlinks, configs, fonts, services report      |

## Services

System (12): `gdm.service`, `NetworkManager.service`, `NetworkManager-dispatcher.service`, `NetworkManager-wait-online.service`, `bluetooth.service`, `ModemManager.service`, `power-profiles-daemon.service`, `thermald.service`, `ufw.service`, `postgresql.service`, `reflector.timer`, `wwan-enable.service`.

User (6): `pipewire.socket`, `pipewire-pulse.socket`, `wireplumber.service`, `gnome-keyring-daemon.socket`, `p11-kit-server.socket`, `xdg-user-dirs.service`.

Notes:

- `tlp` stays installed-but-disabled (conflicts with `power-profiles-daemon`).
- `postgresql.service` needs manual `initdb`; `ufw.service` needs manual rules.
- `wwan-enable.service` is a custom unit written to `/etc/systemd/system/`.

## Safety

- Run as user, not root.
- `--dry-run` changes nothing.
- Backups land in `~/.local/state/dotfiles-backup-<timestamp>`.
- Log file: `/tmp/dotfiles-install.log`.
