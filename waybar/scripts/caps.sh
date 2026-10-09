#!/usr/bin/env bash
# Caps Lock indicator for waybar custom/caps.
# Polls sysfs LEDs, so no input-group membership is needed.
# No colors here; styling is via classes in colors/style.css.
# CAPS_LED_GLOB overrides the sysfs glob (used for testing).
glob="${CAPS_LED_GLOB:-/sys/class/leds/*capslock/brightness}"

on=false
for f in $glob; do
    [ -r "$f" ] || continue
    [ "$(cat "$f" 2>/dev/null)" = "1" ] && on=true && break
done

# Nerd Fonts lock glyphs, emitted as UTF-8 bytes so no locale is required.
# U+F023 locked, U+F09C unlocked.
if $on; then
    printf '{"text": "\357\200\243", "class": "locked", "tooltip": "Caps Lock on"}'
else
    printf '{"text": "\357\202\234", "class": "unlocked", "tooltip": "Caps Lock off"}'
fi
