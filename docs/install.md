# Install

Install the desktop on an existing Arch system. Preview changes first, preserve conflicting configs, and verify the result. This is not an Arch/base-system installer or a version-pinned machine image.

## Scope

The selected components determine config links from `LINK_MAP` (`install.sh:76`). `build_plan` in `lib/install-plan.sh:51` assembles package targets, links, services, verification requirements, and phases once for both interfaces and execution. Preflight and verification use those same lists rather than assuming every component was selected.

Developer-tool configs (tmux, VSCodium, OpenCode) are managed by the separate `tools` repository and its `install.sh`. They are not required inside this repository.

## Start here

```bash
./install.sh --dry-run
./install.sh
```

On a terminal, choose Recommended, Customize, Preview, or Check. Recommended goes straight to review; Customize offers component checkboxes and separate system/preference choices. Review defaults to **Cancel** and offers expandable package/config/service details and a return to customization. Closed input cancels instead of approving changes. Without a terminal, installation requires `--yes`.

Explicit scope flags such as `--profile full` or `--only-dotfiles` skip Welcome and populate Review with the requested choices. `--yes` bypasses all menus; explicit `--dry-run` and `--check` run their read-only CLI paths without calling Gum.

## Profiles and package manifests

| Profile | Official manifest                           | AUR manifest                                        |
| ------- | ------------------------------------------- | --------------------------------------------------- |
| `core`  | [`core.txt`](../packages/core.txt)          | [`core-aur.txt`](../packages/core-aur.txt)          |
| `full`  | Core + [`extra.txt`](../packages/extra.txt) | Core + [`extra-aur.txt`](../packages/extra-aur.txt) |

Both profiles also include [`shell.txt`](../packages/shell.txt) unless Zsh is deselected or `--no-shell` is passed. `core` is the default: the desktop, configured shell, referenced fonts, and direct script dependencies. `full` adds personal apps, developer tools, utilities, and extra fonts. Counts come from these five manifests at runtime, not a separately maintained number in this document.

The desktop and its base palette are required for a normal installation. Optional groups are Zsh setup, AUR wallpaper/theme assets, and extra apps/development tools. GDM, Fibocom WWAN, account-shell changes, and application preferences are separate opt-ins. Unchecked groups are **left unmanaged, never uninstalled or disabled**. The full Arch upgrade may still update already-installed packages from an unselected group.

Manifest rules:

- One package per line; blank lines and `#` comments are allowed.
- Package names are validated. Duplicate entries, including across manifests, are rejected.
- Files are parsed as data, never sourced as shell code.
- Keep direct requirements here; let pacman/PKGBUILDs resolve their dependencies.

Neither profile adds kernels, bootloaders, GPU drivers, TLP, or Redshift. Handle hardware provisioning separately. The package phase runs `pacman -Syu`, so existing system packages can still be upgraded normally. Package names are not version locks; the README's source versions are compatibility reference points, not a fresh-system test guarantee.

`--no-aur` skips both AUR packages and helper bootstrap. Otherwise, the installer uses an existing `yay`/`paru`, or builds `yay-bin` in a temporary directory after installing official dependencies. It does not install both helpers. Review third-party PKGBUILDs before allowing AUR builds; `--yes` skips those interactive reviews. Some extra apps, such as Packet Tracer, may require upstream licensed downloads.

Installed packages are skipped. Failed batches are retried individually; recovered attempts do not leave a false failure count. An unresolved required official package stops installation **before config replacement**. Optional package failures are reported and cause a nonzero final exit even if desktop setup continues.

## Flags

| Flag              | Effect                                                                      |
| ----------------- | --------------------------------------------------------------------------- |
| `--profile core`  | Desktop + configured shell; default                                         |
| `--profile full`  | Also add optional apps, development tools, and fonts                        |
| `--only-dotfiles` | Skip system packages/services; prepare configs, shell frameworks, palette   |
| `--link-only`     | Config links + managed ZDOTDIR block only                                   |
| `--no-aur`        | No AUR packages or AUR helper bootstrap                                     |
| `--no-shell`      | Skip Zsh packages/config/frameworks and its generated shell palette         |
| `--with-gdm`      | Install/enable GDM without replacing another display manager                |
| `--with-wwan`     | Install ModemManager tools and the Fibocom WWAN unit                        |
| `--change-shell`  | Opt in to changing the account shell to zsh; needs a terminal               |
| `--set-defaults`  | Opt in to installed-app MIME defaults and GTK preferences                   |
| `--dry-run`       | Print planned actions; no files, logs, locks, downloads, or service changes |
| `--check`         | Read-only diagnostics; no repair or log writes                              |
| `--yes`, `-y`     | Skip wizard/confirmation; use package-manager `--noconfirm`                 |
| `--verbose`       | Expand checks, unchanged items, command output, and preview command details |
| `--quiet`         | Installer warnings/errors only; requires `--yes` for installation           |
| `--ui MODE`       | `auto`, `plain`, or `gum`; unavailable widgets fall back to plain prompts   |
| `--log-file PATH` | Use a new log file; existing files/symlinks are not overwritten             |
| `--no-color`      | Disable colors; also supported through `NO_COLOR=1`                         |
| `--help`, `-h`    | Print usage                                                                 |

`--link-only` cannot be combined with account-shell/default-application changes. `--no-shell` cannot be combined with `--change-shell`. GDM/WWAN require system installation, not `--only-dotfiles`. `--check` and `--dry-run` are mutually exclusive. Preview/check modes do not write even an explicitly requested log file.

## Commands

```bash
./install.sh --dry-run
./install.sh --profile core --with-gdm
./install.sh --profile full --yes
./install.sh --only-dotfiles --yes
./install.sh --link-only --yes
./install.sh --check --verbose
./install.sh --no-shell --no-aur --dry-run
./install.sh --ui plain
```

## Phases

| Phase     | Function in `install.sh` | Actions                                                     |
| --------- | ------------------------ | ----------------------------------------------------------- |
| Preflight | `phase_preflight`        | Read-only environment, repository, and prerequisite checks  |
| Base      | `phase_base`             | Authenticate sudo, then full `pacman -Syu`                  |
| Packages  | `phase_packages`         | Official packages, then optional helper/AUR packages        |
| Services  | `phase_services`         | Enable selected desktop units; no forced restarts           |
| Dotfiles  | `phase_dotfiles`         | Preserve conflicts, link configs, seed runtime files        |
| Shell     | `phase_shell`            | Clone missing oh-my-zsh/p10k; optional account-shell change |
| Theming   | `phase_theming`          | Generate matugen outputs from cached/default wallpaper      |
| Verify    | `phase_verify`           | Report missing requirements; final failures return exit 1   |

Default phase counts: normal **8**, dotfiles-only **5**, link-only **3**, check **2**. Deselecting Zsh removes its preparation phase (normal **7**, dotfiles-only **4**). The plan determines the actual phase count. Dry-run shows projected actions and a planned verification step rather than failing checks against files it intentionally did not create.

`--only-dotfiles` expects dependencies to be installed already. It can still download missing shell frameworks and generate themes; use `--link-only` for links without those actions. Shell setup clones repositories directly instead of executing a remotely downloaded installer or overwriting `.zshrc`.

### Leaving the shell unmanaged

`--no-shell` skips `shell.txt`, the Zsh directory link, the ZDOTDIR block, framework downloads, account-shell changes, and shell-specific verification. It also excludes the shell palette output, including during later wallpaper changes.

To keep that choice persistent without editing the canonical repository config, the installer preserves the old Matugen path and creates a private `~/.config/matugen/` directory: a filtered `config.toml`, a `templates` symlink, and a `.hypryoru-managed` ownership marker. Other palette templates remain enabled. The private config is a snapshot refreshed on installer reruns, not a live link to canonical config edits; template files remain linked. Selecting Zsh again restores the normal directory-link layout with the previous private directory preserved. `--link-only --no-shell` prepares this filtered configuration but does not generate any palette outputs.

Use the same scope/component flags with `--check` as with installation. For example: `./install.sh --check --no-shell --no-aur`.

## Services

Default system units: `NetworkManager.service`, `bluetooth.service`, `power-profiles-daemon.service`.

User units: `pipewire.socket`, `pipewire-pulse.socket`, `wireplumber.service`, `gnome-keyring-daemon.socket`.

Notes:

- Existing enabled/static units are left alone; masked services are not unmasked.
- NetworkManager is not enabled automatically if `systemd-networkd` or `dhcpcd` is in use. The power-profile service is not enabled over an active/enabled TLP service.
- `--with-gdm` checks the existing `display-manager.service` owner and refuses to replace another manager.
- `--with-wwan` adds `ModemManager.service` and `wwan-enable.service`. The latter comes from [`services/wwan-enable.service`](../services/wwan-enable.service), is specific to the original Fibocom modem setup, and never overwrites a different custom unit.
- PostgreSQL, Docker, Valkey, firewall, and reflector services/timers are not enabled by the installer. Existing pacman settings and mirrors are unchanged.
- These enable actions do not start/restart services or log out the session. Package upgrade hooks and matugen template hooks can still perform their normal refreshes.

## Safety

- Installation runs as your normal user. Only package/service phases use sudo; dotfiles-only and link-only modes do not.
- Config paths use `~/.config`; installation rejects a different `XDG_CONFIG_HOME` rather than silently mixing locations.
- Conflicting directories and symlinks, including broken symlinks, are **moved**, not deleted. A failed preservation step aborts replacement; a failed link attempts to move the original back.
- Individual edits are copied to backup first, then replaced through a temporary file. Backup failure leaves the original untouched.
- When Zsh is selected, custom `.zshenv` statements stay intact and the installer maintains a final ZDOTDIR block. Existing GTK bookmarks and wallpapers are not overwritten. New bookmark URIs use the actual home/XDG directories, including spaces and non-ASCII paths.
- MIME defaults and live GTK preferences stay unchanged unless `--set-defaults` is selected. Only installed desktop entries are assigned; custom Packet Tracer associations are not replaced with hardcoded version names.
- The Qt palette path is adapted to the current home; because configs are symlinked, this can update the repository's `qt6ct/qt6ct.conf`. Its previous content is preserved first.
- `--dry-run` and `--check` never initialize storage or prune logs. They can also run on a non-Arch host for inspection; actual installation remains Arch-only.

### Backups and restoration

Backups are created lazily under `${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-install/backups/<timestamp>-<pid>/`:

```text
<run>/
├── manifest.tsv          # actions, original paths, preserved paths
├── home/                 # moved directories and original symlinks
├── edited/               # copies of individual files before edits
├── restore-gsettings.sh  # present only if GTK preferences were changed
└── restore-shell.sh      # present only if the account shell was changed
```

Inspect `manifest.tsv` before restoring. For a moved config directory, remove only its current installer symlink, then move that specific preserved path back. For edited files, inspect the corresponding copy under `edited/`. Restore a whole directory before applying individual-file copies only if those copies are still relevant to it.

Do **not** blindly copy the whole backup over live `~/.config` symlinks: that can write through them into the repository. The optional restoration snippets can be inspected and run with `bash` to restore the prior gsettings/login-shell values; account-shell changes may require authentication. Package upgrades, package installation, service enablement, and newly seeded runtime files are not automatically rolled back.

Logs use `${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-install/logs/install-<timestamp>-<pid>.log`. Default-log runs retain the newest 10 matching logs in that directory; using `--log-file` does not trigger rotation. Logs contain timestamped status messages, quoted command arguments, exit codes, and command output. Existing explicit log files are never truncated.

## UI

- Welcome → Components → Review → Installation → Results; Recommended skips component editing, not review.
- Gum supplies arrow-key menus and multi-select checkboxes when installed and supported. Use Space/Tab to toggle, Enter to submit, and Escape/Ctrl+C to cancel. A sole optional item uses an explicit Include/Skip pair to avoid Gum automatically selecting it on Enter. Numbered prompts provide the same choices; toggle numbers separated by spaces and use `q` to cancel.
- `--ui auto` detects widgets only for interactive sessions. Missing/incompatible Gum, `TERM=dumb`, or a terminal smaller than 50 columns × 12 rows uses plain prompts. `--ui plain` forces that fallback; `--ui gum` requests widgets but never installs them. To use Gum, install it separately with your package manager.
- Review shows selected/missing/already-present package counts, preservation actions, storage paths, and shell/login/default-app choices. Details are expandable before approval. Package availability and service guards are rechecked while applying; selected targets and component choices still come from the reviewed plan.
- The final approval defaults to Cancel, including when a global Gum preference tries to preselect another item. An empty component selection stays empty; it does not restore recommended defaults.
- Phase progress shows completed phases, not fabricated download percentages. Unattended tasks get elapsed-time spinners; interactive package-manager questions keep foreground input/output. Successful checks and unchanged items are collapsed unless `--verbose` is used.
- Results distinguish failures, warnings, unchanged items, and successful actions. Interactive results offer notes, available logs/backup manifests, and read-only verification with the reviewed scope. Rechecking does not change the original installation exit status. The sudo keepalive stops before these result actions.
- Colors turn off when piped, with `NO_COLOR=1`, `CLICOLOR=0`, `TERM=dumb`, or `--no-color`. `NO_EMOJI=1` or a non-UTF-8 locale selects ASCII status icons.

## Local validation without a VM

```bash
bash -n install.sh
bash -n lib/install-ui.sh
bash -n lib/install-plan.sh
bash -n lib/install-wizard.sh
python3 -B tests/test_install.py
systemd-analyze verify services/wwan-enable.service
```

The Python standard-library suite uses temporary homes, an independent fixture repository, real pseudo-terminals, and mocked package/service/desktop commands. It covers manifest validation, zero-write read-only modes, backup failures, symlinks, shell opt-out and palette isolation, shared-plan execution, widget/fallback navigation, cancellation, result actions, and mocked install/rerun flows. Apply-mode cases skip when the host is not a normal-user Arch environment.

The default widget tests mock Gum's input/output. To additionally test real widgets with an existing binary:

```bash
HYPRYORU_TEST_GUM=/absolute/path/to/gum python3 -B tests/test_install.py
```

Without that optional variable, the real-widget case is skipped. The suite never downloads or installs Gum. No tests install system packages, alter live desktop configs, or require a VM; they do not replace fresh-system integration testing.
