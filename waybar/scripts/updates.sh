#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Pending Arch update count for waybar custom/updates.
# Repo via checkupdates each poll; AUR via one batched RPC call (fast,
# no yay spawn, no cache). Emits error state instead of a false
# "up to date" when checks fail.

LOCK="${XDG_CACHE_HOME:-$HOME/.cache}/waybar-updates/check.lock"
RPC_URL="https://aur.archlinux.org/rpc/v5/info"
BATCH=200 # arg[] packages per RPC request
MAX_TIP=12

mkdir -p "$(dirname "$LOCK")"

json_escape() { # make a string safe inside a JSON "..." value
    sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' -e ':a;N;$!ba;s/\n/\\n/g' |
        tr -d '\000-\010\013-\037' |
        head -c 1200
}

fail() {
    printf '{"text": "", "class": "error", "tooltip": "%s"}' "$(printf '%s' "$1" | json_escape)"
    exit 0
}

# Never overlap: interval poll vs SIGRTMIN+8 refresh.
exec 9>"$LOCK"
flock -n 9 || exit 0

# Offline: hide quietly; the network module already shows the state.
if ! nm-online -q --timeout=2; then
    printf '{"text": "", "class": "hidden", "tooltip": "Offline — update check skipped"}'
    exit 0
fi

# --- Official repo ---
repo_out=$(checkupdates 2>&1)
case $? in
0) ;;
2) repo_out="" ;;
*) fail "Repo check failed: $(printf '%s' "$repo_out" | head -1)" ;;
esac
repo=$(printf '%s\n' "$repo_out" | grep -c .)
repo_tip=$(printf '%s\n' "$repo_out" | awk '{print $1}')

# --- AUR: foreign packages vs one batched RPC info call ---
aur=0
aur_tip=""
foreign=$(pacman -Qm 2>&1) || fail "pacman -Qm failed: $foreign"
if [ -n "$foreign" ]; then
    declare -A installed=()
    names=()
    while read -r n v; do
        installed[$n]=$v
        names+=("$n")
    done <<<"$foreign"

    aur_new=""
    for ((i = 0; i < ${#names[@]}; i += BATCH)); do
        args=()
        for n in "${names[@]:i:BATCH}"; do args+=(--data-urlencode "arg[]=$n"); done
        rpc=$(curl -sf --max-time 20 --get "${args[@]}" "$RPC_URL") ||
            fail "AUR check failed: RPC request error"
        aur_new+=$(jq -r '.results[] | "\(.Name)\t\(.Version)"' <<<"$rpc")$'\n'
    done

    while IFS=$'\t' read -r n newver; do
        [ -z "$n" ] && continue
        oldver=${installed[$n]:-}
        if [ -n "$oldver" ] && [ "$(vercmp "$newver" "$oldver")" -gt 0 ]; then
            aur=$((aur + 1))
            aur_tip+="$n"$'\n'
        fi
    done <<<"$aur_new"
fi

# --- Emit ---
total=$((repo + aur))
if [ "$total" -eq 0 ]; then
    printf '{"text": "", "class": "hidden", "tooltip": "System up to date"}'
    exit 0
fi

tip="󰚰 $repo repo + $aur AUR updates"
tip="$tip
$(printf '%s\n%s\n' "$repo_tip" "$aur_tip" | grep . | head -n "$MAX_TIP")"
left=$((total - MAX_TIP))
[ "$left" -gt 0 ] && tip="$tip
… and $left more"

printf '{"text": "󰚰 %s", "class": "pending", "tooltip": "%s"}' "$total" "$(printf '%s' "$tip" | json_escape)"
