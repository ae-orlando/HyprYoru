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

# Ghost text color derives from matugen (see templates/shell-colors.sh):
# the plugin default `fg=8` is invisible because Kitty maps color8 to the
# surface/background color. Re-applied before each prompt so wallpaper
# changes take effect in long-lived shells (after 15-matugen.zsh reloads
# generated/colors.sh; hooks run in registration order).
_autosuggest_apply_matugen() {
  ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=${MATUGEN_AUTOSUGGEST:-242},bold"
}
_autosuggest_apply_matugen
autoload -Uz add-zsh-hook
add-zsh-hook precmd _autosuggest_apply_matugen
