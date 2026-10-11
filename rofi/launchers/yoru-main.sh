#!/usr/bin/env bash
# Yoru app launcher (theme: rofi/styles/yoru-main.rasi).
# Type-6 launcher stays the default; point waybar custom/apps here once
# this theme has earned it.

rofi \
    -show drun -show-icons \
    -theme "$HOME/.config/rofi/styles/yoru-main.rasi"
