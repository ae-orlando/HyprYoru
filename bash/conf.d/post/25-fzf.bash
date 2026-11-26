#     ____              _____         __
#    / __/_ _____ __ __/ __(_)__  ___/ /__ ____
#   / _// // /_ // // / _// / _ \/ _  / -_) __/
#  /_/  \_,_//__/\_, /_/ /_/_//_/\_,_/\__/_/
#               /___/

# by ae. Orlando
# _______________________________________________________________________
# fzf keybindings: CTRL-R history, CTRL-T files, ALT-C directories.
# Guarded: silent when absent. Previews/colors come from FZF_DEFAULT_OPTS
# (matugen-generated, see 15-matugen.bash); file search uses fd when present.
# Under ble.sh we load blesh-contrib's integrations instead of stock
# fzf --bash, which conflicts with ble.sh's line editor (same split as
# zsh's fzf --zsh vs. the plain-bash path).

if ! command -v fzf >/dev/null 2>&1; then
    return 0
fi

if [[ -n ${BLE_VERSION-} ]]; then
    # contrib/ sits next to ble.sh (user install or the Arch package);
    # -f keeps a contrib-less install silent. Imports are immediate so
    # the bindings exist before the first keypress — same as fzf --zsh.
    ble-import -f contrib/integration/fzf-completion
    ble-import -f contrib/integration/fzf-key-bindings
else
    eval "$(fzf --bash)"
fi
