#!/usr/bin/env bash
# Pending Arch update count for waybar custom/updates.
# Repo checked every poll; AUR cached for 2h (yay -Qu is slow).
# Emits error state instead of a false "up to date" when checks fail.

AUR_CACHE="/tmp/waybar-aur-count"
AUR_TTL=7200 # seconds

repo_out=$(checkupdates 2>/tmp/waybar-repo-err)
repo_status=$?
repo_err=$(cat /tmp/waybar-repo-err 2>/dev/null)

if [ "$repo_status" -ne 0 ] && [ "$repo_status" -ne 2 ]; then
    printf '{"text": "", "class": "error", "tooltip": "Update check failed: %s"}' "$(echo "$repo_err" | head -1)"
    exit 0
fi
repo=$(echo "$repo_out" | grep -c .)

aur_note=""
if [ -f "$AUR_CACHE" ] && [ $(( $(date +%s) - $(stat -c %Y "$AUR_CACHE") )) -lt "$AUR_TTL" ]; then
    aur=$(cat "$AUR_CACHE")
    aur_note=" (AUR cached)"
else
    aur_out=$(yay -Qu --aur 2>/tmp/waybar-aur-err)
    aur_status=$?
    aur_err=$(cat /tmp/waybar-aur-err 2>/dev/null)
    if [ "$aur_status" -eq 0 ] || { [ "$aur_status" -eq 1 ] && [ -z "$aur_err" ]; }; then
        aur=$(echo "$aur_out" | grep -c .)
        echo "$aur" > "$AUR_CACHE"
    elif [ -f "$AUR_CACHE" ]; then
        aur=$(cat "$AUR_CACHE")
        aur_note=" (AUR stale: check failed)"
    else
        printf '{"text": "", "class": "error", "tooltip": "AUR check failed: %s"}' "$(echo "$aur_err" | head -1)"
        exit 0
    fi
fi

total=$((repo + aur))
if [ "$total" -gt 0 ]; then
    printf '{"text": "󰚰 %s", "class": "pending", "tooltip": "%s repo + %s AUR updates%s (click to update)"}' "$total" "$repo" "$aur" "$aur_note"
else
    printf '{"text": "", "class": "hidden", "tooltip": "System up to date"}'
fi
