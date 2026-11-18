#!/usr/bin/env bash
#     __ __         _____         __  _____          __           __
#    / //_/__ __ __/ ___/__ ____ / /_/ ___/__  ___  / /________  / /
#   / ,< / -_) // / /__/ _ `(_-</ __/ /__/ _ \/ _ \/ __/ __/ _ \/ /
#  /_/|_|\__/\_, /\___/\_,_/___/\__/\___/\___/_//_/\__/_/  \___/_/
#           /___/
# Author: ae. Orlando
# Github: https://github.com/ae-orlando
#________________________________________________________________

#: This toggles the showthekey kystromke overlay (keycast).
#: While running, EVERY keystroke is displayed on the screen
#: I ussually use it when recording tutorials which in which
#: The user needs to see my keystrokes.

if pgrep -f showmethekey >/dev/null; then
    pkill -f showmethekey #Kills gtk frontend + pkexec backend
    exit 0
fi

#: Initial configurations for the desired behaviour.
#: Feel free to tweak these to your liking.
# -A: no settings, -k: show keys window, -C: click-through
showmethekey-gtk -A -K -C >/dev/null 2>&1 & disown
