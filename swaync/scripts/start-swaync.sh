#!/usr/bin/env bash
# Start the tested local backport, falling back to the distro daemon.
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
set -euo pipefail

local_daemon="${XDG_DATA_HOME:-$HOME/.local/share}/yoru/swaync/swaync"
if [[ -x "$local_daemon" ]]; then
    exec "$local_daemon" "$@"
fi
exec /usr/bin/swaync "$@"
