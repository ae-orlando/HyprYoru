#!/usr/bin/env bash
# Wallpaper entry point; palette.py owns generation, state and reloads.
# Usage: set-wall.sh [/path/to/wallpaper] [--pick]
set -euo pipefail

exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/palette.py" wallpaper "$@"
