#       __            __
#      / /  ___ ____ / /  ________
#   _ / _ \/ _ `(_-</ _ \/ __/ __/
#  (_)_.__/\_,_/___/_//_/_/  \__/

# Athor: ae. Orlando
# github: https://github.com/ae-orlando
# .................................................

# If not running interactively, don't do anything
[[ $- == *i* ]] || return

# ble.sh must load with --attach=none at the top and attach at the bottom
if [[ -f "$HOME/.local/share/blesh/ble.sh" ]]; then
  source "$HOME/.local/share/blesh/ble.sh" --attach=none
fi

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
