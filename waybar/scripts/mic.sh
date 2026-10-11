#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Mic indicator for waybar custom/mic.
# Visible only when the source is muted or actively in use; idle otherwise.
muted=false
inuse=false

wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | grep -q '\[MUTED\]' && muted=true
pactl list source-outputs 2>/dev/null | grep -q 'Source Output' && inuse=true

if $muted; then
    printf '{"text": "", "class": "muted", "tooltip": "Microphone muted (click to unmute)"}'
elif $inuse; then
    printf '{"text": "", "class": "active", "tooltip": "Microphone in use (click to mute)"}'
else
    printf '{"text": "", "class": "hidden", "tooltip": "Microphone idle"}'
fi
