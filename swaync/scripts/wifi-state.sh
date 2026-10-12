#!/usr/bin/env bash
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
