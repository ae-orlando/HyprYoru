# Security policy

## Supported versions

HyprYoru is a rolling configuration for Arch Linux. Only the latest `main` commit is supported; there are no maintained release branches.

## Reporting a vulnerability

Do **not** open a public issue for a security problem.

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. If that option is unavailable, open a minimal public issue asking for a private contact channel, without disclosing any details about the problem.

Include as much of the following as you can:

- Affected files, scripts, or components, and the commit you tested
- Steps to reproduce or a proof of concept
- Impact and the conditions required to exploit it
- Any suggested fix or mitigation
- Whether the issue is already public elsewhere

Redact credentials, tokens, personal paths, and other sensitive data from logs and screenshots.

## Scope

In scope:

- `install.sh` and `lib/` (including download verification, backup, and restore paths)
- Shell and Python helpers under the tracked config directories
- CI workflows and repository automation
- Shipped configuration that could cause unsafe execution, data loss, or privilege misuse

Out of scope:

- Vulnerabilities in Arch packages, AUR helpers, Hyprland, or other upstream software; report those upstream
- Third-party wallpapers and character artwork
- Modifications made after installation in a user's local copy

## Handling

Reports are handled on a best-effort basis with no guaranteed response time. Confirmed issues will be fixed on `main`, and reporters will be credited unless they prefer to remain anonymous.
