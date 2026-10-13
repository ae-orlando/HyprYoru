#!/usr/bin/env bash
#   ________                 ______       __
#  /_  __/ /  ___ __ _  ___ / __/ /____ _/ /____
#   / / / _ \/ -_)  ' \/ -_)\ \/ __/ _ `/ __/ -_)
#  /_/ /_//_/\__/_/_/_/\__/___/\__/\_,_/\__/\__/

# By ae. Orlando
# =============================================================================

# Echo true when dark mode is active (button shown as on).
# Source of truth: ~/.cache/matugen/current-mode, fallback to GTK ini.
set -uo pipefail
MODE_FILE="$HOME/.cache/matugen/current-mode"
GTK3="$HOME/.config/gtk-3.0/settings.ini"
if [ -f "$MODE_FILE" ]; then
    case "$(cat "$MODE_FILE" 2>/dev/null)" in
    light)
        echo false
        exit 0
        ;;
    dark)
        echo true
        exit 0
        ;;
    esac
fi
if [ -f "$GTK3" ] && grep -Eq '^gtk-application-prefer-dark-theme=(0|false)' "$GTK3" 2>/dev/null; then
    echo false
else
    echo true
fi
