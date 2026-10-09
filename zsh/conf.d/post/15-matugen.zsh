# =======================================
# MATUGEN SHELL COLORS (eza + fzf)
# =======================================
# Generated palette from ~/.config/matugen (see templates/shell-colors.sh).
# Re-sourced automatically before each prompt when matugen rewrites it
# (e.g. after ~/.config/hypr/scripts/set-wall.sh runs).

if [[ -f "$ZDOTDIR/generated/colors.sh" ]]; then
  source "$ZDOTDIR/generated/colors.sh"
  _matugen_colors_mtime=$(stat -c %Y "$ZDOTDIR/generated/colors.sh" 2>/dev/null)

  _matugen_colors_reload() {
    local mtime
    mtime=$(stat -c %Y "$ZDOTDIR/generated/colors.sh" 2>/dev/null)
    if [[ -n "$mtime" && "$mtime" != "$_matugen_colors_mtime" ]]; then
      source "$ZDOTDIR/generated/colors.sh"
      _matugen_colors_mtime=$mtime
    fi
  }
  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _matugen_colors_reload
fi
