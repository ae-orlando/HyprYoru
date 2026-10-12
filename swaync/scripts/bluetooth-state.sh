#!/usr/bin/env bash
# Echo true when bluetooth controller is powered.
set -uo pipefail
if ! command -v bluetoothctl >/dev/null 2>&1; then
    echo false
    exit 0
fi
if bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; then
    echo true
else
    echo false
fi
