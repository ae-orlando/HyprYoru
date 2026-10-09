# =======================================
# SYNTAX HIGHLIGHTER
# =======================================

#=========================================
#Source
#=========================================
if [[ -f /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
elif [[ -f "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
  source "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi


# ==========================================
# Initialize Styling arrays
# ========================================
##typeset -A ZSH_HIGHLIGHT_STYLES

# Commands and built-in functions (Magenta, follows terminal palette)
ZSH_HIGHLIGHT_STYLES[command]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[alias]='fg=magenta,bold'

# Options and flags like -h or --help (Blue)
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=blue'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=blue'

# Valid paths and strings (Green)
ZSH_HIGHLIGHT_STYLES[path]='fg=green,underline'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=green'

# Unknown commands / Errors (Red)
ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=red,bold'

# Variables (Yellow)
ZSH_HIGHLIGHT_STYLES[assign]='fg=yellow'
