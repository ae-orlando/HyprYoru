#!/usr/bin/env bash
#       __            __
#      / /  ___ ____ / /  ________
#   _ / _ \/ _ `(_-</ _ \/ __/ __/
#  (_)_.__/\_,_/___/_//_/_/  \__/

# Author: ae. Orlando
# github: https://github.com/ae-orlando
# .................................................

# If not running interactively, don't do anything
[[ $- == *i* ]] || return

# ble.sh must load with --attach=none at the top and attach at the bottom.
# Two locations: the user install (install.sh phase_shell) and the Arch
# blesh-git package.
for _yoru_ble in "$HOME/.local/share/blesh/ble.sh" /usr/share/blesh/ble.sh; do
  if [[ -f $_yoru_ble ]]; then
    source "$_yoru_ble" --attach=none
    break
  fi
done
unset _yoru_ble

# Pre-shell: env, completion
for f in "$HOME/.config/bash"/conf.d/pre/*.bash; do
  [[ -f "$f" ]] && source "$f"
done

# Post-shell: aliases, palette, functions, tools, prompt
for f in "$HOME/.config/bash"/conf.d/post/*.bash; do
  [[ -f "$f" ]] && source "$f"
done

# Attach ble.sh last (its documented pattern)
if [[ ${BLE_VERSION-} ]]; then
  ble-attach
fi

# Leave $? / PIPESTATUS clean for the first prompt: the failing [[ ]]
# test above would otherwise linger as a stale "✔ 1" status segment.
:
