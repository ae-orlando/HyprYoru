# Install

One-shot reproducer for a fresh Arch machine. Idempotent. Backs up replaced paths first.

## Profiles

| Profile | Official pkgs | AUR pkgs | Contents                                                       |
| ------- | ------------- | -------- | -------------------------------------------------------------- |
| `full`  | 151           | 21       | Exact source machine (`PACMAN_CORE` + `PACMAN_EXTRA`, all AUR) |
| `core`  | 111           | 5        | Bootable Hyprland minimum (`PACMAN_CORE` + `AUR_CORE` only)    |

Counts verified in `install.sh`: `PACMAN_CORE` 111, `PACMAN_EXTRA` 40, `AUR_CORE` 5, `AUR_EXTRA` 16.

## Flags

| Flag              | Effect                                                                 |
| ----------------- | ---------------------------------------------------------------------- |
| `--profile`       | `core` or `full` (default `full`)                                      |
| `--only-dotfiles` | Skip base/packages/services; link configs + shell + theming (5 phases) |
| `--no-aur`        | Skip AUR packages (cursor/icon themes + `waypaper` missing)            |
| `--dry-run`       | Print actions only; needs no `sudo`                                    |
| `--yes`           | Non-interactive (`--noconfirm`)                                        |
| `--verbose`       | Stream long-operation output live (default: spinner + log file)        |
| `--quiet`         | Minimal terminal output (warnings/errors still shown)                 |
| `--log-file PATH` | Plain log location (default `~/.local/state/dotfiles-install/logs/install-<timestamp>.log`, last 10 kept) |
| `--no-color`      | Disable colors (same as `NO_COLOR=1`)                                 |
| `--help`          | Print usage                                                            |

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
- Backups land in `~/.local/state/dotfiles-backup-<timestamp>/home/` (paths
  mirrored relative to `$HOME`; restore with `cp -a <backup>/home/. ~/`).
- Log file: `~/.local/state/dotfiles-install/logs/install-<timestamp>.log`
  (last 10 kept; override with `--log-file`).

## UI

- Guided prompts on a terminal without `--yes`/`--dry-run`: `1/3` profile menu
  (`1` full / `2` core, validation loop), `2/3` AUR confirm with consequences,
  `3/3` summary screen (profile, counts, disk free, backup/restore hint) + `Y/n`.
  Irrelevant prompts are skipped under `--only-dotfiles`.
- Honest progress: `[n/N]` counts the active phases (`8`, or `5` with
  `--only-dotfiles`), plus a `████░░` bar, per-phase elapsed times, and a total
  in the final summary. Spinners show elapsed seconds; already-ok steps print
  `SKIP` instead of redoing work.
- Packages: already-installed official/AUR packages are detected up front and
  skipped; a failed batch is retried per package so one bad package neither
  hides behind the batch nor aborts the install (failures are listed, install
  continues).
- Colors auto-off when piped, `NO_COLOR=1`, `CLICOLOR=0`, or `TERM=dumb`;
  `NO_EMOJI=1` (or non-UTF-8 locale) falls back to ASCII icons.
  `--verbose` streams long operations live; the log file is always plain
  with timestamps.
