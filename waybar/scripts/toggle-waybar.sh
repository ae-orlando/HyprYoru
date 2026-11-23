#!/usr/bin/env bash
#: Author: ae. Orlando
#: Github: https://github.com/ae-orlando
# This scritp toggles waybar on adn off. Use it as you wish
#___________________________________________________

set -euo pipefail
if pgrep -u "$(id -u)" -x waybar >/dev/null; then
    pkill -u "$(id -u)" -x waybar
else
    "$(dirname -- "${BASH_SOURCE[0]}")/start-waybar.sh" >/dev/null 2>&1 &
fi
