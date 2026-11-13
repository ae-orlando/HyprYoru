# Patched desktop binaries

SwayNC uses a small local source patch. Waybar follows the normal Arch package,
which now handles Hyprland's Lua dispatch protocol natively. The normal Arch
packages remain installed and untouched.

Git stores the SwayNC patch, helper and configuration, not the built executable
or build cache. On a fresh machine the launcher uses the distro binary until the
build/install command below is run; `install.sh` does not compile it.

## What is installed

| Program | Version                     | Notes                                                                                                                                               |
| ------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Waybar  | `0.16.0` (Arch package)     | No local patch. Upstream handles Hyprland's Lua dispatch protocol, including named workspaces, scratchpads and move-to-monitor behavior.             |
| SwayNC  | `0.12.6 (main.b8017a4, Yoru backports 2)` | Latest upstream main; live brightness synchronization without feedback writes; bounded popup previews; full messages in the center; sensitive authentication-code copies; notification-click activation. |

### What the SwayNC patch changes

- **SwayNC:** the backport is pinned to upstream main commit
  `b8017a4d1a53` after the `0.12.6` tag. The patch serializes backlight drag
  writes and prevents slider readback from writing a value back, while keeping
  the file monitor alive. It flattens paragraph breaks _only in floating
  previews_, limits them to five lines, and caps/scrolls stacked popups to the
  configured height or available screen space. Full body text remains in the
  notification center. Its own “copy code” action also advertises a sensitive
  clipboard offer. It attaches the last pointer serial to the XDG activation
  token, so Hyprland 0.57.2+ focuses the sender instead of only marking it
  urgent. Sources: `swaync/backports/yoru-main.patch:101`,
  `swaync/backports/yoru-main.patch:207`,
  `swaync/backports/yoru-main.patch:317`,
  `swaync/backports/yoru-main.patch:387`.

The three-island bar design, hotspot indicator, Tools shortcuts, native radio
drawers and the 300px popup-height setting are **dotfile configuration, CSS and
script changes**. They are not extra compiled packages. The SwayNC patch makes
the preview-line limit and screen-aware bound work; the configured height alone
cannot fix the paragraph issue. Hotspot-password copies are marked sensitive by
the drawer's code, independently of SwayNC's “copy code” change.

### Pacman package or local binary?

The unmodified `/usr/bin/waybar` and `/usr/bin/swaync` are pacman-owned Arch
packages. The SwayNC binary in `~/.local/share/yoru/swaync/` is a manually built
**user-local file**: neither a pacman package nor an AUR package, and not
registered in pacman's database. It does not replace or conflict with the
pacman-owned file. Installing build prerequisites through pacman does not turn
the finished local binary into a pacman package.

```bash
pacman -Q waybar swaync
pacman -Qo /usr/bin/waybar /usr/bin/swaync
yoru-desktop status
```

The first two commands describe the _packaged copies_; the last shows which
binary each running process actually uses. Running `pacman -Qo` on the local
SwayNC binary instead reports “No package owns” (and exits nonzero). `pacman -Qm`
will not list it either. Pacman updates `/usr/bin` and system libraries,
**not** the user-local SwayNC executable or its pinned patch.

### The terms

| Term                | Meaning here                                                                                                                |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Source              | The human-readable upstream C++ or Vala program.                                                                            |
| Patch               | A small `.patch` file describing our changes to that source.                                                                |
| Build / compilation | Turning the patched source into a runnable program.                                                                         |
| Binary              | That finished executable: `swaync`. It does not compile itself when launched.                                              |
| Build cache         | Downloaded source, generated files and compiler output used to speed up a later rebuild. It is not the running application. |
| Manifest            | A `manifest.json` receipt recording the upstream version and source, patch and binary checksums.                            |
| Launcher            | A short script that selects the local binary, or the distro fallback if the local executable is absent.                     |

`cc1plus` is GCC's C++ compiler. It builds SwayNC. You may notice high CPU
usage; that is normal and stops once the build finishes. Multiple build jobs can
each use a CPU core. Finishing or interrupting the build ends those compiler
processes.

Other development tools have similar build-only roles: Meson configures the
build, Ninja schedules it, `valac` compiles SwayNC's Vala, and
`blueprint-compiler` / `sassc` generate SwayNC UI and styling resources. Keep
runtime libraries such as GLib and GTK; removing them is not a way to control
compiler CPU use.

## Where the files live

These are the default XDG paths in this setup:

| Path                                        | Purpose                                                           |
| ------------------------------------------- | ----------------------------------------------------------------- |
| `~/.local/share/yoru/swaync/swaync`         | Installed local SwayNC executable                                 |
| `~/.local/share/yoru/swaync/manifest.json`  | Installed build receipt                                           |
| `~/.cache/yoru/swaync-build/`               | Persistent SwayNC build cache                                     |
| `~/.local/state/yoru/waybar.log`            | Log for a Waybar process started by the maintenance helper        |
| `~/.local/state/yoru/swaync.log`            | Log for a SwayNC process started by the maintenance helper        |
| `swaync/backports/`                         | Version-controlled patches, build helper and regression fixtures  |
| `/usr/bin/waybar` and `/usr/bin/swaync`     | Pacman-managed primary and fallback executables                   |

The launchers follow `XDG_DATA_HOME` when it is set. The SwayNC builder also
respects `XDG_CONFIG_HOME` and `XDG_CACHE_HOME`; the maintenance helper follows
`XDG_STATE_HOME` for its logs.

Hyprland starts the launcher scripts directly, so its inherited `PATH` does not
need `~/.local/bin`. The optional terminal links `waybar` and `swaync` point to
those launchers. SwayNC's user D-Bus activation files and systemd user override
select the same launcher.

The `yoru-desktop` command is linked into `~/.local/bin` by the SwayNC
`--install` step; on a fresh checkout before that step, invoke
`python3 -B waybar/scripts/desktop-binaries.py status` from the repo instead.

**Do not enable a second startup mechanism unnecessarily.** Hyprland already
starts both applications. The SwayNC systemd override only keeps binary
selection consistent if a user service is used; it does not enable that service.

Sources: `hyprland/modules/autostart.lua:13`,
`waybar/scripts/start-waybar.sh:7`, `swaync/scripts/start-swaync.sh:7`,
`swaync/backports/build-swaync.py:45`.

## Everyday use: no compilation

Check the selected versions **and the actual running executables**:

```bash
yoru-desktop status
```

Both programs should say `current selected binary`. SwayNC should also show
matching checksums and repository patches. A version printed by
`waybar --version` alone identifies the selected file, not necessarily the
already-running process.

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
nice -n 10 python3 -B swaync/backports/build-swaync.py --install --jobs 1
```

`--jobs 1` limits build parallelism, but a single compiler may still show 100%
of one CPU core. `nice` lowers its scheduling priority, not its maximum
percentage. The helper defaults to two jobs if the option is omitted.

For the extra compiled GTK/backlight regression suite:

```bash
python3 -B swaync/backports/build-swaync.py --test --install --jobs 1
```

That test suite builds an additional test executable. It uses a fake backlight,
private D-Bus session and private runtime directory; it can briefly display
synthetic popups, but does not change real brightness, radios or inbox contents.

The SwayNC helper uses the default persistent cache. Do not rely on a source
checkout in `/tmp` surviving a reboot.

**Do not use `sudo` for the builder.** Root is only needed for normal pacman
package operations. Download checksums are pinned, patch application is strict,
and a failed build/test does not proceed to installation. Build output stays in
the cache; installation copies the finished binary into the user-local data path.

The `--install` command does not restart a running daemon. Load the new
executable as a separate step:

```bash
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

**Pacman does not update the private SwayNC binary.** It continues maintaining
the separate `/usr/bin` copy and system libraries. The build helper also does
not fetch "latest" on every run: it reproduces the reviewed `SOURCE_REF` in
`swaync/backports/build-swaync.py`. To move to a newer upstream commit, review
and rebase `yoru-main.patch`, update `SOURCE_REF` and `SOURCE_SHA256` together,
then rebuild and test before restarting the daemon. Do not change only a version
string or disable checksum checks.

Keep source edits in the repository's `.patch` files, not in cached source trees.
The installed manifest and `yoru-desktop status` help identify an old install or
changed patch set; checksums do not replace reviewing code changes.

## Recovery and logs

If a newly built SwayNC executable fails, the distro copy is still available.
Move only the local executable aside:

```bash
mv -i ~/.local/share/yoru/swaync/swaync ~/.local/share/yoru/swaync/swaync.disabled
yoru-desktop restart swaync
```

The launcher then selects `/usr/bin/swaync`. Re-enable it by moving
`swaync.disabled` back to `swaync` and restarting again. `mv -i` asks before
overwriting an existing backup.

**Review and empty the inbox before restarting SwayNC.** A fallback loses the
local brightness, bounded-preview, sensitive-copy and notification-activation
fixes; it is a recovery route, not proof that the distro version contains those
fixes. Moving a file aside alone does not replace a process already running from
it.

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
