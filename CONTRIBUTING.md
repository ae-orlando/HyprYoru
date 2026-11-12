# Contributing to HyprYoru

HyprYoru is an Arch Linux + Hyprland desktop configuration with a guided installer and a Matugen-driven palette. Contributions are welcome, especially reproducible bug reports, documentation fixes, and focused desktop improvements.

## Before you start

- Open an issue before starting large changes or refactors so the approach can be discussed first.
- Report security issues privately as described in [SECURITY.md](SECURITY.md), never in a public issue.
- Redact usernames, hostnames, SSIDs, tokens, and other personal data from logs and screenshots.

## Repository layout

| Path                 | Contents                                                        |
| -------------------- | --------------------------------------------------------------- |
| `install.sh`, `lib/` | Installer entry point, UI, plan, and verified Gum runtime       |
| `packages/`          | Official and AUR package manifests                              |
| `hyprland/`          | Hyprland Lua config, modules, scripts, wallpapers               |
| `waybar/`, `rofi/`   | Bar and launcher configuration, styles, and scripts             |
| `swaync/`            | Notification daemon config plus local backports                 |
| `matugen/`           | Palette config and templates (the source of generated themes)   |
| `kitty/`, `zsh/`, `btop/`, `fastfetch/`, `gtk-setting/`, `qt6ct/` | Application configs |
| `tests/`             | Sandboxed regression tests; never touch the live desktop        |
| `docs/`              | Installer and per-module guides                                 |

Start with [README.md](README.md), then [docs/install.md](docs/install.md).

## Local checks

Run these before opening a pull request:

```bash
bash -n install.sh lib/*.sh
shellcheck --severity=error install.sh lib/*.sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Palette tests need `matugen` (and `imagemagick` for the pipeline test); Zsh tests need `zsh`. Missing tools cause those cases to skip. CI runs the same checks plus ShellCheck over every tracked shell script.

## Making changes

- **Generated palette files are ignored on purpose.** Edit `matugen/templates/*` or `matugen/config.toml`; never commit the outputs listed in `.gitignore` (`waybar/colors/matugen.css`, `kitty/themes/Matugen.conf`, `zsh/generated/colors.sh`, and the rest).
- **Keep installer modes safe.** `--dry-run` and `--check` must remain zero-write. Tests use temporary homes and mocked package, service, desktop, and transport commands; do not add tests that install packages or modify a live session.
- **Update docs with behaviour.** User-visible flags, defaults, keybinds, and module changes belong in the matching guide under `docs/`.
- **Reload instead of restarting.** Use `hyprctl reload` for Hyprland modules and the existing launch scripts for Waybar and SwayNC when validating changes.
- **Include visual evidence.** Bar, launcher, notification, lock-screen, and palette changes should include before/after screenshots.
- **Respect third-party work.** Bundled wallpapers and character images are not covered by the project license; do not add artwork you cannot redistribute.

## Commit messages

Use an imperative, scoped summary:

```text
Feat(waybar): Add idle inhibitor module
Fix(palette): Use on-surface-variant for autosuggestion ink
Docs(install): Align local validation with CI checks
```

Common types are `Feat`, `Fix`, `Docs`, `Chore`, `Refactor`, `Test`, and `CI`. Keep one logical change per commit and avoid mixing generated files with source edits.

## Pull requests

- Branch from `main` and keep the change focused.
- Make sure CI passes; the workflow runs shell syntax checks, ShellCheck, and the full Python test suite.
- Reference related issues and describe any live-system testing in the PR.
- By contributing, you agree that your changes are licensed under GPL-3.0-or-later, as described in [LICENSE](LICENSE).
