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

# ==========================================
# Token colors (8-color ANSI only: values resolve through the terminal
# palette, so highlighting follows the wallpaper via matugen/Kitty)
# ========================================

# Executables (Catppuccin mauve, hardcoded: intentionally exempt from the
# wallpaper-following ANSI palette so commands keep their classic color)
ZSH_HIGHLIGHT_STYLES[command]='fg=#cba6f7,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=#cba6f7,bold'
ZSH_HIGHLIGHT_STYLES[function]='fg=#cba6f7,bold'
ZSH_HIGHLIGHT_STYLES[hashed-command]='fg=#cba6f7,bold'

# User shortcuts (Cyan, distinct from real commands)
ZSH_HIGHLIGHT_STYLES[alias]='fg=cyan,bold'
ZSH_HIGHLIGHT_STYLES[suffix-alias]='fg=cyan,bold'
ZSH_HIGHLIGHT_STYLES[global-alias]='fg=cyan,bold'

# Elevated/destructive first words (Red, plain: bold is reserved for errors)
ZSH_HIGHLIGHT_STYLES[precommand]='fg=red'

# Options and flags like -h or --help (Blue)
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=blue,bold'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=blue,bold'

# Valid paths and strings (Green; partial paths light up while typing)
ZSH_HIGHLIGHT_STYLES[path]='fg=green,underline'
ZSH_HIGHLIGHT_STYLES[path_prefix]='fg=green'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=green'

# Shell chrome: keywords, separators, redirections (Yellow)
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[commandseparator]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[redirection]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[assign]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[history-expansion]='fg=yellow,bold'

# Patterns (Cyan, same family as shortcuts)
ZSH_HIGHLIGHT_STYLES[globbing]='fg=cyan'

# Unknown commands / Errors (Red, bold: highest severity)
ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=red,bold'
