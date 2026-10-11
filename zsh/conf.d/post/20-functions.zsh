# Reserved for user shell functions.

# Render an ASCII banner with figlet and copy it to the Wayland clipboard.
# (Adapted from ML4W's ml4w-ascii-header: args instead of prompts,
# wl-copy only, no $HOME droppings.)
# Usage: ascii [-f font] <text...>   (prompts when no text given)
ascii() {
    local font=smslant text
    if [[ $1 == "-f" ]]; then font=$2; shift 2; fi
    text="$*"
    if [[ -z $text ]]; then
        read -r "text?Enter the text for ascii encoding: "
    fi
    [[ -z $text ]] && return 1
    if ! command -v figlet >/dev/null 2>&1; then
        print -u2 "ascii: figlet not installed (sudo pacman -S figlet)"
        return 1
    fi
    local art
    art=$(figlet -f "$font" "$text") || return 1
    print -r -- "$art"
    if print -r -- "$art" | wl-copy 2>/dev/null; then
        print "Text copied to clipboard!"
    fi
}
