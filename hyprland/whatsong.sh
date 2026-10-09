#!/bin/bash
# Now-playing for hyprlock (avoids {} parsing issues in hyprlock.conf)
playerctl metadata --format '{{artist}} - {{title}}' 2>/dev/null || echo ""
