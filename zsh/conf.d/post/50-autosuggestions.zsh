#     ___       __       ____                       __  _
#    / _ |__ __/ /____  / __/_ _____ ____ ____ ___ / /_(_)__  ___  ___
#   / __ / // / __/ _ \_\ \/ // / _ `/ _ `/ -_|_-</ __/ / _ \/ _ \(_-<
#  /_/ |_\_,_/\__/\___/___/\_,_/\_, /\_, /\__/___/\__/_/\___/_//_/___/
#                              /___//___/

# by ae. Orlando
# _______________________________________________________________________

if [[ -f /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# Regular-weight muted ink stays distinct from bold commands without hiding
# on light backgrounds. With no generated palette, use terminal gray (ANSI 8).
# Re-applied before each prompt after 15-matugen.zsh reloads the palette;
# hooks run in registration order, including in long-lived shells.
_autosuggest_apply_matugen() {
  ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=${MATUGEN_AUTOSUGGEST:-8}"
}
_autosuggest_apply_matugen
autoload -Uz add-zsh-hook
add-zsh-hook precmd _autosuggest_apply_matugen
