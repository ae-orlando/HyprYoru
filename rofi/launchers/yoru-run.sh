#!/usr/bin/env bash
# by ae. Orlando
# (Note: -show drun -show run opens DRUN, not run — rofi honors
# the first -show, which is why type-6 launcher_run.sh behaves the same.)

rofi \
    -show run \
    -theme "$HOME/.config/rofi/styles/yoru-main.rasi"
