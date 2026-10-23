#!/usr/bin/env bash
#   _      ___ ____ ______       __
#  | | /| / (_) _(_) __/ /____ _/ /____
#  | |/ |/ / / _/ /\ \/ __/ _ `/ __/ -_)
#  |__/|__/_/_//_/___/\__/\_,_/\__/\__/

# Author: ae Orland
# GitHub: https://github.com/ae-orlando
# ================================================

# Read the same authoritative state as the menu and power action.
set -uo pipefail
python -B "$HOME/.config/rofi/launchers/connectivity/menu.py" wifi --state 2>/dev/null || echo false
