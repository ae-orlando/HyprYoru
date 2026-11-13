# Changelog

All notable changes to HyprYoru are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- README screenshots for the orange and twilight palettes.
- Contributor Covenant 2.1 code of conduct.

### Changed

- SwayNC backport now tracks upstream `main` at `b8017a4d1a53`, labelled `0.12.6 (main.b8017a4, Yoru backports 2)`; the build helper pins the commit and checksum.

### Fixed

- Notification clicks focus the sender again on Hyprland 0.57.2+. Hyprland treats tokens without a pointer serial as urgent-only and GTK does not expose that serial, so SwayNC now focuses the urgent sender window shortly after the action signal. Chromium/WhatsApp Web comes to the front instead of only marking its workspace urgent.
- SwayNC backlight changes keep the file monitor alive during drag writes, so brightness keys continue to update the slider.

## [0.1.0] - 2026-11-12

First tagged release. HyprYoru is usable on an existing Arch Linux installation but remains pre-1.0: flags, defaults, and file layout may change between minor versions.

### Added

- Guided installer for an existing Arch installation with Gum and numbered-prompt interfaces, an explicit review step, and read-only preview/check modes.
- `core` and `full` profiles, component opt-ins, preserved backups, install logs, and a checksum-verified private Gum runtime.
- Optional GDM and Fibocom WWAN setup, with existing display managers and services left unmanaged unless selected.
- Hyprland configuration written in Lua, including modules for binds, monitors, rules, layouts, input, autostart, idle, and lock.
- Matugen-driven palette pipeline that regenerates Hyprland, Waybar, Kitty, Rofi, SwayNC, GTK, Qt, btop, Zsh, Neovim, and Spicetify themes from a wallpaper.
- Waybar, Rofi launchers, SwayNC (including the local 0.12.6 backport), Kitty, Waypaper, btop, Fastfetch, GTK, and Qt configuration.
- Zsh setup with Oh My Zsh, Powerlevel10k, syntax highlighting, and autosuggestions.
- Sandboxed regression tests using temporary homes, pseudo-terminals, and mocked package/service/desktop commands.
- Per-module documentation under `docs/`, plus contribution and security policies.
- CI running shell syntax checks, ShellCheck, and the full Python test suite.
- GPL-3.0-or-later licensing with a separate notice for bundled third-party artwork.

### Notes

- This is not an Arch base-system installer: kernels, bootloaders, and GPU drivers are intentionally out of scope.
- CI validates the installer and palette logic in isolation; fresh-system installation still requires manual testing on Arch.

[Unreleased]: https://github.com/ae-orlando/HyprYoru/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ae-orlando/HyprYoru/releases/tag/v0.1.0
