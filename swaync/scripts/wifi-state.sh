#!/usr/bin/env bash
#   _      ___ ____ ______       __
#  | | /| / (_) _(_) __/ /____ _/ /____
#  | |/ |/ / / _/ /\ \/ __/ _ `/ __/ -_)
#  |__/|__/_/_//_/___/\__/\_,_/\__/\__/

# By ae. Orlando
# ================================================

# Echo true when wifi radio is enabled.
set -uo pipefail
if ! command -v nmcli >/dev/null 2>&1; then
    echo false
    exit 0
fi
if [ "$(nmcli radio wifi 2>/dev/null)" = "enabled" ]; then
    echo true
else
    echo false
fi
