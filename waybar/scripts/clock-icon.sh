#!/usr/bin/env bash
# Time-of-day icon for waybar custom/clock-icon (companion to the clock module).
# Nerd Fonts weather glyphs, emitted as UTF-8 bytes so no locale is required.
# U+F0596 morning, U+F0599 day, U+F0597 evening, U+F0594 night.
# No colors here; styling is via classes in colors/style.css.
h=$((10#$(date +%H)))
if [ "$h" -ge 5 ] && [ "$h" -lt 11 ]; then
    printf '{"text": "\363\260\226\226", "class": "morning", "tooltip": "Morning"}'
elif [ "$h" -ge 11 ] && [ "$h" -lt 17 ]; then
    printf '{"text": "\363\260\226\231", "class": "day", "tooltip": "Daytime"}'
elif [ "$h" -ge 17 ] && [ "$h" -lt 22 ]; then
    printf '{"text": "\363\260\226\227", "class": "evening", "tooltip": "Evening"}'
else
    printf '{"text": "\363\260\226\224", "class": "night", "tooltip": "Night"}'
fi
