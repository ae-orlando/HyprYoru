#!/usr/bin/env bash
# Monochrome minimal pleasure animation for waybar custom/animation.
# Persistent: waybar runs once, each stdout line = one update (JSON).
# Plain text only (no Pango spans) so CSS theme colors drive the look.
# Modes: 0 pacman, 1 wave, 2 bounce. Left-click cycles, right-click pauses.
# All frames within a mode are equal-length to avoid jitter.

MODE_FILE="/tmp/waybar-animation-mode"
PAUSE_FILE="/tmp/waybar-animation-paused"

# Compact pacman: mouth open(ᗧ)/closed(ᗣ) synced to dots eaten.
pacman_frames=(
    "ᗧ···"
    "ᗣ···"
    "ᗧ·· "
    "ᗣ·· "
    "ᗧ·  "
    "ᗣ·  "
)

# Compact wave: 4 cells wide.
wave_frames=(
    "▁▂▃▄"
    "▂▃▄▅"
    "▃▄▅▆"
    "▄▅▆▇"
    "▅▆▇█"
    "▆▇█▇"
)

# Compact bounce: 4 cells wide.
bounce_frames=(
    "●···"
    "·●··"
    "··●·"
    "···●"
    "··●·"
    "·●··"
)

mode_names=("pacman" "wave" "bounce")
i=0
while true; do
    if [ -f "$PAUSE_FILE" ]; then
        printf '{"text": "⏸", "class": "paused", "tooltip": "Animation paused (right-click to resume, left-click to switch mode)"}\n'
        sleep 1
        continue
    fi

    mode=0
    if [ -f "$MODE_FILE" ]; then
        read -r mode < "$MODE_FILE" 2>/dev/null
    fi
    case "$mode" in
        0|1|2) ;;
        *) mode=0 ;;
    esac

    case "$mode" in
        0)
            text="${pacman_frames[$((i % ${#pacman_frames[@]}))]}"
            class="mode-pacman"
            ;;
        1)
            text="${wave_frames[$((i % ${#wave_frames[@]}))]}"
            class="mode-wave"
            ;;
        2)
            text="${bounce_frames[$((i % ${#bounce_frames[@]}))]}"
            class="mode-bounce"
            ;;
    esac

    printf '{"text": "%s", "class": "%s", "tooltip": "Animation: %s (left-click: switch, right-click: pause)"}\n' \
        "$text" "$class" "${mode_names[$mode]}"
    i=$((i + 1))
    sleep 0.18
done
