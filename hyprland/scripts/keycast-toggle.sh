#!/usr/bin/env bash
#     __ __         _____         __  _____          __           __
#    / //_/__ __ __/ ___/__ ____ / /_/ ___/__  ___  / /________  / /
#   / ,< / -_) // / /__/ _ `(_-</ __/ /__/ _ \/ _ \/ __/ __/ _ \/ /
#  /_/|_|\__/\_, /\___/\_,_/___/\__/\___/\___/_//_/\__/_/  \___/_/
#           /___/
# Author: ae. Orlando
# Github: https://github.com/ae-orlando
#________________________________________________________________

#: This toggles the showmethekey keystroke overlay (keycast).
#: While running, EVERY keystroke is displayed on the screen
#: I ussually use it when recording tutorials which in which
#: The user needs to see my keystrokes.

WINDOW_CLASS="one.alynx.showmethekey"

#: State = does the overlay window exist?
#: NEVER use pgrep/pkill here:
#:  - showmethekey-cli runs as root via pkexec, so pkill can't kill
#:    it (leaks a backend, and pgrep then lies "running" forever)
#:  - pkill -f matches ANY process whose cmdline mentions the name,
#:    including unrelated terminals/editors/greps
if hyprctl clients -j | grep -q "$WINDOW_CLASS"; then
    #: Graceful close: the frontend exits cleanly and takes its root
    #: backend with it. The {window=...} table is REQUIRED: a plain
    #: string arg makes Hyprland close the *active* window instead.
    hyprctl dispatch "hl.dsp.window.close({window='class:$WINDOW_CLASS'})" >/dev/null 2>&1
    exit 0
fi

#: Initial configurations for the desired behaviour.
#: Feel free to tweak these to your liking.
#: -A: no settings window, -k: show keys window
#: (NO -C: the strip must be clickable, otherwise pointer events
#:  pass through it and SUPER + LMB can't drag it anywhere)
showmethekey-gtk -A -k >/dev/null 2>&1 & disown
