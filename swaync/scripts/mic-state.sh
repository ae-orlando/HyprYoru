#!/usr/bin/env bash
# Echo true when the default source (mic) is unmuted (active).
set -uo pipefail
if ! command -v wpctl >/dev/null 2>&1; then
    echo true
    exit 0
fi
if wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | grep -q '\[MUTED\]'; then
    echo false
else
    echo true
fi
