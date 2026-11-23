# Changelog

All notable changes to HyprYoru are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-24

### Added

- Zsh: vi-mode terminal navigation binds (`zsh/conf.d/post/01-binds.zsh`). Vi mode is primary (`bindkey -v`, `KEYTIMEOUT=1`) with word/line/history navigation in insert mode, Emacs-style shortcuts kept (`Ctrl+A/E/W/U/K/Y`), and `edit-command-line` via `Ctrl+X Ctrl+E` / `vv`.
- Hyprland: floating mini terminal binding (`shiftMod + return`, 700×450 centered).
- Hyprland: keycast keystroke overlay — `keycast-toggle.sh` script, `shiftMod + K` bind, and a dedicated window rule (floating, pinned, no focus, borderless, no shadow, 75% opacity, 600×100 bottom-right).
- Hyprland: Waybar toggle binding (`altMod + R`) and `waybar/scripts/toggle-waybar.sh` script.
- Matugen: Obsidian CSS snippet template (`obsidian-colors.css`), `[templates.obsidian]` in `config.toml`, and `hyprland/scripts/obsidian-theme.sh` post_hook that symlinks the generated CSS into every registered Obsidian vault's `.obsidian/snippets/` and enables the `matugen` snippet.
- Zsh: vault helpers (`note`, `vault`, `vcheck`) and the `gcom` commit function (`zsh/conf.d/post/20-functions.zsh`).
- CI: GitHub Actions checkout/setup-python bumped to v7; zsh-syntax-highlighting installed in CI.
- README: CI and license badges; desktop screenshots for the orange and twilight palettes.
- Git: narrowed the token ignore guard so ordinary names like `swaync/Styles/tokens.css` are no longer caught.

### Changed

- Hyprland: animations and blur re-tuned — blur passes 3→1 (size 6), brightness 0.9→0.5, new `easeInCubic` curve, `popin 82%`/`slidefade 20%` animation styles, Rofi animation `popin 82%`.
- SwayNC: backport now tracks upstream `main` at `b8017a4d1a53`, labelled `0.12.6 (main.b8017a4, Yoru backports 2)`; patch file renamed `yoru-0.12.6.patch` → `yoru-main.patch`; `SOURCE_REF`/`SOURCE_SHA256` pin the commit.
- Kitty: bold font reverted from `ExtraBold` to `bold`; cursor trail decay tuned (0.2/0.8 → 0.15/0.6).
- Zsh: `gcm` helper renamed to `gcom`.
- Powerlevel10k: prompt made fluent on git status; VCS/command execution time/context/toolbox prefixes uncommented.
- Installer link map: added `.config/git:git` (15 entries total).
- SwayNC/Waybar: transitions 160ms ease → 180ms ease-out; SwayNC `transition-time` 200→180; reduced-motion media query added to `base.css`.
- Docs: README now links the Code of Conduct; screenshots and badges added.

### Fixed

- Matugen: shadow color value quoted in `hypr-colors.lua` and `colors-fallback.lua`.
- Matugen: autosuggestions ghost text uses `outline` color instead of too-faint `outline_variant`.
- SwayNC: notification clicks focus the sender again on Hyprland 0.57.2+ (urgent-window fallback).
- SwayNC: backlight changes keep the file monitor alive during drag writes, so brightness keys continue to update the slider.
- Tests: resolve `matugen` from PATH instead of hardcoding `/usr/bin/matugen`.

### Notes

- This is not an Arch base-system installer: kernels, bootloaders, and GPU drivers are intentionally out of scope.
- CI validates the installer and palette logic in isolation; fresh-system installation still requires manual testing on Arch.

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

[Unreleased]: https://github.com/ae-orlando/HyprYoru/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ae-orlando/HyprYoru/releases/tag/v0.2.0
[0.1.0]: https://github.com/ae-orlando/HyprYoru/releases/tag/v0.1.0
