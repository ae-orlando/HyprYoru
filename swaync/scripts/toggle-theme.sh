#!/usr/bin/env bash
# Keep the SwayNC command stable while sharing the wallpaper palette pipeline.
set -euo pipefail

exec python3 "$HOME/.config/hypr/scripts/palette.py" toggle
