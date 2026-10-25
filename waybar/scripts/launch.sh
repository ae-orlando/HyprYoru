#!/bin/bash
# by ae. Orlando
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
# _______________________________________________________________________

# SUPER+R reloads in place. Never kill the notification daemon or its inbox.
set -euo pipefail
if pgrep -u "$(id -u)" -x waybar >/dev/null; then
    pkill -u "$(id -u)" -SIGUSR2 -x waybar
else
    "$(dirname -- "${BASH_SOURCE[0]}")/start-waybar.sh" >/dev/null 2>&1 &
fi

if pgrep -u "$(id -u)" -x swaync >/dev/null; then
    swaync-client -rs >/dev/null
fi
