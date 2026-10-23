#!/usr/bin/env bash
#     ___  __  ______       __            __
#    / _ )/ /_/ __/ /____ _/ /____   ___ / /
#   / _  / __/\ \/ __/ _ `/ __/ -_) (_-</ _ \
#  /____/\__/___/\__/\_,_/\__/\__(_)___/_//_/

# Author: ae Orland
# GitHub: https://github.com/ae-orlando
# ==================================================

# Read the same controller as the menu and power action.
set -uo pipefail
python -B "$HOME/.config/rofi/launchers/connectivity/menu.py" bluetooth --state 2>/dev/null || echo false
