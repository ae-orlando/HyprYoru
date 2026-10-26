#     __  ___     __                     ______       _________     __
#    /  |/  /__ _/ /___ _____ ____ ___  / __/ /  ___ / / / ___/__  / /__  _______
#   / /|_/ / _ `/ __/ // / _ `/ -_) _ \_\ \/ _ \/ -_) / / /__/ _ \/ / _ \/ __(_-<
#  /_/  /_/\_,_/\__/\_,_/\_, /\__/_//_/___/_//_/\__/_/_/\___/\___/_/\___/_/ /___/
#                       /___/

# Generated palette from ~/.config/matugen (see templates/shell-colors.sh).
# by ae. Orlando
# _______________________________________________________________________

# Re-sourced automatically before each prompt when matugen rewrites it
# (e.g. after ~/.config/hypr/scripts/set-wall.sh runs).

_matugen_colors_reload() {
  local file="$ZDOTDIR/generated/colors.sh" mtime
  if [[ ! -f "$file" ]]; then
    unset _matugen_colors_mtime
    return 0
  fi

  # Sub-second changes matter when a wallpaper and mode change land within
  # one second. zstat +mtime (and stat %Y) only report whole seconds.
  mtime=$(command stat -c %y -- "$file" 2>/dev/null) || return 0

  if [[ -n "$mtime" && "$mtime" != "${_matugen_colors_mtime-}" ]]; then
    unset EZA_COLORS
    source "$file" && _matugen_colors_mtime=$mtime
  fi
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _matugen_colors_reload
_matugen_colors_reload
