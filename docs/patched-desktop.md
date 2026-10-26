# Patched desktop binaries

Waybar and SwayNC use small local source patches. Their normal Arch packages
remain installed and untouched.

Git stores the patches, helpers and configuration, not the built executables or
build caches. On a fresh machine the launchers use the distro binaries until
the build/install commands below are run; `install.sh` does not compile them.

## What is installed

| Program | Local version               | Why it is patched                                                                                                                                   |
| ------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Waybar  | `0.15.0-yoru1`              | Workspace buttons use Hyprland's Lua dispatchers, including named workspaces, scratchpads and move-to-monitor behavior.                             |
| SwayNC  | `0.12.6 (Yoru backports 1)` | Live brightness synchronization without feedback writes; bounded popup previews; full messages in the center; sensitive authentication-code copies. |

### What the patches change

- **Waybar:** the packaged `0.15.0` workspace buttons send legacy Hyprland
  dispatch strings, which this Lua-based Hyprland rejects. The local patch sends
  Lua dispatchers for numbered and named workspaces and scratchpads, preserving
  `move-to-monitor` behavior. Workspace names are escaped as Lua strings.
  Source: `waybar/backports/hyprland-lua-0.15.0.patch:26`.
- **SwayNC:** the packaged `0.12.6` backlight widget cancels and reuses its file
  monitor, so it cannot reliably follow brightness-key changes after reopening.
  The patch recreates the monitor, serializes drag writes and prevents readback
  from writing a value back. It flattens paragraph breaks _only in floating
  previews_, limits them to five lines, and caps/scrolls stacked popups to the
  configured height or available screen space. Full body text remains in the
  notification center. Its own “copy code” action also advertises a sensitive
  clipboard offer. Sources: `swaync/backports/yoru-0.12.6.patch:58`,
  `swaync/backports/yoru-0.12.6.patch:183`,
  `swaync/backports/yoru-0.12.6.patch:269`.

The three-island bar design, hotspot indicator, Tools shortcuts, native radio
drawers and the 300px popup-height setting are **dotfile configuration, CSS and
script changes**. They are not extra compiled packages. The SwayNC patch makes
the preview-line limit and screen-aware bound work; the configured height alone
cannot fix the paragraph issue. Hotspot-password copies are marked sensitive by
the drawer's code, independently of SwayNC's “copy code” change.

### Pacman package or local binary?

The unmodified `/usr/bin/waybar` and `/usr/bin/swaync` are pacman-owned Arch
packages. The binaries in `~/.local/share/yoru/` are manually built
**user-local files**: neither pacman packages nor AUR packages, and not
registered in pacman's database. They do not replace or conflict with the
pacman-owned files. Installing build prerequisites through pacman does not turn
the finished local binaries into pacman packages.

```bash
pacman -Q waybar swaync
pacman -Qo /usr/bin/waybar /usr/bin/swaync
yoru-desktop status
```

The first two commands describe the _packaged copies_; the last shows which
binary each running process actually uses. Running `pacman -Qo` on a user-local
binary instead reports “No package owns” (and exits nonzero). `pacman -Qm`
will not list these files either. Pacman updates `/usr/bin` and system
libraries, **not** your user-local executables or their pinned patches.

### The terms

| Term                | Meaning here                                                                                                                |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Source              | The human-readable upstream C++ or Vala program.                                                                            |
| Patch               | A small `.patch` file describing our changes to that source.                                                                |
| Build / compilation | Turning the patched source into a runnable program.                                                                         |
| Binary              | That finished executable: `waybar` or `swaync`. It does not compile itself when launched.                                   |
| Build cache         | Downloaded source, generated files and compiler output used to speed up a later rebuild. It is not the running application. |
| Manifest            | A `manifest.json` receipt recording the upstream version and source, patch and binary checksums.                            |
| Launcher            | A short script that selects the local binary, or the distro fallback if the local executable is absent.                     |

`cc1plus` is GCC's C++ compiler. It was busy building Waybar, not running the
bar in the background. Multiple build jobs can each use a CPU core. Finishing
or interrupting the build ends those compiler processes.

Other development tools have similar build-only roles: Meson configures the
build, Ninja schedules it, `valac` compiles SwayNC's Vala, `gdbus-codegen`
(from `glib2-devel`) generates Waybar's D-Bus code, and `blueprint-compiler` /
`sassc` generate SwayNC UI and styling resources. Keep runtime libraries such as
GLib and GTK; removing them is not a way to control compiler CPU use.

## Where the files live

These are the default XDG paths on this machine:

| Path                                        | Purpose                                                           |
| ------------------------------------------- | ----------------------------------------------------------------- |
| `~/.local/share/yoru/waybar/waybar`         | Installed local Waybar executable                                 |
| `~/.local/share/yoru/swaync/swaync`         | Installed local SwayNC executable                                 |
| `~/.local/share/yoru/<app>/manifest.json`   | Installed build receipt                                           |
| `~/.cache/yoru/waybar-build/`               | Persistent Waybar build cache                                     |
| `~/.cache/yoru/swaync-build/`               | Persistent SwayNC build cache                                     |
| `~/.local/state/yoru/waybar.log`            | Log for a Waybar process started by the maintenance helper        |
| `~/.local/state/yoru/swaync.log`            | Log for a SwayNC process started by the maintenance helper        |
| `waybar/backports/` and `swaync/backports/` | Version-controlled patches, build helpers and regression fixtures |
| `/usr/bin/waybar` and `/usr/bin/swaync`     | Pacman-managed fallback executables                               |

The launchers follow `XDG_DATA_HOME` when it is set. Builders also respect
`XDG_CONFIG_HOME` and `XDG_CACHE_HOME`; the maintenance helper follows
`XDG_STATE_HOME` for its logs.

Hyprland starts the launcher scripts directly, so its inherited `PATH` does not
need `~/.local/bin`. The terminal commands `waybar` and `swaync` also point to
those launchers through user-local links. SwayNC's user D-Bus activation files
and both programs' systemd user overrides select the same launchers.

The `yoru-desktop` command is linked into `~/.local/bin` by Waybar's
`--install` step; on a fresh checkout before that step, invoke
`python3 -B waybar/scripts/desktop-binaries.py status` from the repo instead.

**Do not enable a second startup mechanism unnecessarily.** Hyprland already
starts both applications. The systemd overrides only keep binary selection
consistent if a user service is used; they do not enable those services.

Sources: `hyprland/modules/autostart.lua:13`,
`waybar/scripts/start-waybar.sh:7`, `swaync/scripts/start-swaync.sh:7`,
`waybar/backports/build-waybar.py:60`, `swaync/backports/build-swaync.py:45`.

## Everyday use: no compilation

Check the selected versions **and the actual running executables**:

```bash
yoru-desktop status
```

Both programs should say `current selected binary`, with matching checksums and
repository patches. A version printed by `waybar --version` alone identifies
the selected file, not necessarily the already-running process.

For ordinary layout/theme edits, press **Super+R**, or run:

```bash
~/.config/waybar/scripts/launch.sh
```

This reloads Waybar in place and reloads SwayNC CSS. It does not kill SwayNC or
compile anything. For SwayNC widget/configuration edits, use:

```bash
swaync-client -R
swaync-client -rs
```

Do not hand-edit generated Matugen color files. Change their templates or
regenerate the palette through the existing wallpaper/theme workflow.

## Rebuild only when necessary

Rebuild when a source patch changes, when moving to a reviewed upstream release,
or when an updated system library makes the existing binary fail. You do not
need to rebuild at login, after a CSS edit, or after every small package update.

From this checkout, use one compiler job and a lower scheduling priority to keep
the desktop responsive:

```bash
cd ~/Dev/dotfiles
nice -n 10 python3 -B waybar/backports/build-waybar.py --install --jobs 1
nice -n 10 python3 -B swaync/backports/build-swaync.py --install --jobs 1
```

Run the commands separately; do not launch both builds in parallel. `--jobs 1`
limits build parallelism, but a single compiler may still show 100% of one CPU
core. `nice` lowers its scheduling priority, not its maximum percentage.
Both helpers default to two jobs if the option is omitted.

For the extra compiled GTK/backlight regression suite:

```bash
python3 -B swaync/backports/build-swaync.py --test --install --jobs 1
```

That test suite builds an additional test executable. It uses a fake backlight,
private D-Bus session and private runtime directory; it can briefly display
synthetic popups, but does not change real brightness, radios or inbox contents.

Use the default persistent cache. `--source` on the Waybar helper is an advanced
option for verifying and reusing an existing build tree, not a normal requirement.
Do not rely on a source checkout in `/tmp` surviving a reboot.

**Do not use `sudo` for either builder.** Root is only needed for normal pacman
package operations. Download checksums are pinned, patch application is strict,
and a failed build/test does not proceed to installation. Build output stays in
the cache; installation copies the finished binary into the user-local data path.

Neither `--install` command restarts a running daemon. Load the new executable
as a separate step:

```bash
yoru-desktop restart waybar
yoru-desktop restart swaync
yoru-desktop status
```

The restart helper refuses multiple instances rather than guessing, checks the
selected executable, uses graceful termination, and verifies the new process's
binary. It does not force-kill an unresponsive process.

### Important: SwayNC's inbox

SwayNC keeps its inbox in memory. A daemon restart is not the same as a CSS or
configuration reload and does not preserve that history. The helper refuses to
restart SwayNC while saved notifications remain; it never clears them for you.
Review and dismiss them yourself before retrying, preferably at a quiet moment.

```bash
swaync-client -c
```

Do not use `killall swaync` or a direct service restart as a shortcut around this
guard. A new notification can arrive near any restart; the guard is a safety
check, not persistent history storage. Restarting Waybar does not restart SwayNC.

Sources: `waybar/scripts/desktop-binaries.py:94` (status),
`waybar/scripts/desktop-binaries.py:148` (inbox guard),
`waybar/scripts/desktop-binaries.py:189` (restart).

## Arch updates and future releases

1. Update Arch normally with `sudo pacman -Syu`; avoid partial upgrades.
2. Run `yoru-desktop status` and check the applications after updates.
3. If a shared-library update causes a loader error or a crash, rebuild against
   the current libraries, then use the controlled restart commands above.
4. Periodically review upstream releases to see whether the local fixes are now
   included. Test the distro binary before retiring a patch.

**Pacman does not update these private binaries.** It continues maintaining the
separate `/usr/bin` copies and system libraries. The build helpers also do not
fetch "latest": they reproduce their pinned versions. A new upstream version
requires reviewing/porting the patch and updating its source checksum and pin,
not just changing a version string or disabling checksum checks.

Keep source edits in the repository's `.patch` files, not in cached source trees.
The installed manifest and `yoru-desktop status` help identify an old install or
changed patch set; checksums do not replace reviewing code changes.

## Recovery and logs

If a newly built executable fails, the distro copy is still available. For a
temporary Waybar fallback, move only the local executable aside:

```bash
mv -i ~/.local/share/yoru/waybar/waybar ~/.local/share/yoru/waybar/waybar.disabled
yoru-desktop restart waybar
```

The launchers and terminal links then select `/usr/bin/waybar`. Re-enable it by
moving `waybar.disabled` back to `waybar` and restarting again. `mv -i` asks
before overwriting an existing backup.

For SwayNC, the same approach uses the `swaync` executable in its own directory,
but **review and empty the inbox before restarting it**. A fallback loses the
local brightness, bounded-preview and sensitive-copy fixes; it is a recovery
route, not proof that the distro version contains those fixes. Waybar's
workspace-button fix belongs to its own binary, not SwayNC. Moving a file
aside alone does not replace a process already running from it.

Read user logs when the maintenance helper started the application:

```bash
tail -n 80 ~/.local/state/yoru/waybar.log
tail -n 80 ~/.local/state/yoru/swaync.log
```

For an application managed by a user service, inspect its journal instead:

```bash
journalctl --user -u waybar.service -n 80 --no-pager
journalctl --user -u swaync.service -n 80 --no-pager
```

Keep the build tools and caches if convenient. They do not consume compiler CPU
while idle. Removing only a build cache would not remove an installed binary,
but would make the next rebuild start from scratch. No cleanup is required.
