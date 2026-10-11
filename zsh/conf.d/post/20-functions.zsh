#     ____              __  _
#    / __/_ _____  ____/ /_(_)__  ___  ___
#   / _// // / _ \/ __/ __/ / _ \/ _ \(_-<
#  /_/  \_,_/_//_/\__/\__/_/\___/_//_/___/
# by ae. Orlando
# _______________________________________________________________________

# ================ ASCII =====================
# Render an ASCII banner with figlet and copy it to the Wayland clipboard.
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

# List installed fonts, optionally filtered: fonts [pattern]
# No args -> unique family names; with args -> full fc-list lines incl. file + style.
fonts() {
    if [[ $# -eq 0 ]]; then
        fc-list : family | sort -u
    else
        fc-list | grep -i "$*"
    fi
}

# Timestamped screenshots: shot [area|full|window] (default: area)
shot() {
    local dir=~/Pictures/screenshots mode=${1:-area} file geom
    mkdir -p "$dir"
    file="$dir/shot-$(date +%Y%m%d-%H%M%S).png"
    case $mode in
        full) grim "$file" || return 1 ;;
        area) geom=$(slurp) || return 1; grim -g "$geom" "$file" || return 1 ;;
        window)
            command -v jq >/dev/null || { print -u2 "shot: window mode needs jq"; return 1 }
            geom=$(hyprctl activewindow -j | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')
            grim -g "$geom" "$file" || return 1 ;;
        *) print -u2 "shot: usage: shot [area|full|window]"; return 1 ;;
    esac
    notify-send "Screenshot" "$file"
}

# Timestamped backup: bak <file>... (matches repo .bak-<epoch> convention)
bak() {
    local f
    [[ $# -eq 0 ]] && { print -u2 "bak: usage: bak <file>..."; return 1 }
    for f; do
        [[ -f $f ]] || { print -u2 "bak: not found: $f"; continue }
        cp -v -- "$f" "$f.bak-$(date +%s)"
    done
}
