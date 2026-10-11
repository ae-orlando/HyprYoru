#     ____          __             __ ___      __   ___      __   __
#    / __/_ _____  / /____ ___ __ / // (_)__ _/ /  / (_)__ _/ /  / /____ ____
#   _\ \/ // / _ \/ __/ _ `/\ \ // _  / / _ `/ _ \/ / / _ `/ _ \/ __/ -_) __/
#  /___/\_, /_//_/\__/\_,_//_\_\/_//_/_/\_, /_//_/_/_/\_, /_//_/\__/\__/_/
#      /___/                           /___/         /___/

# by ae. Orlando
# _______________________________________________________________________

#=========================================
# Highlighters + perf (must be set before sourcing)
# main: tokens, brackets: ()[]{} nesting, pattern: dangerous
# regexps, cursor: standout, root: sudo warning, line: whole buffer
#=========================================
ZSH_HIGHLIGHT_HIGHLIGHTERS=(main brackets pattern cursor regexp root line)
ZSH_HIGHLIGHT_MAXLENGTH=512

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
typeset -A ZSH_HIGHLIGHT_STYLES
typeset -A ZSH_HIGHLIGHT_PATTERNS
typeset -A ZSH_HIGHLIGHT_REGEXP

# ==========================================
# Token colors (8-color ANSI only: values resolve through the terminal
# palette, so highlighting follows the wallpaper via matugen/Kitty)
# ========================================

# Executables (Magenta/bold via ANSI tertiary slot: follows wallpaper
# through matugen/Kitty, keeps classic distinct command color, no hardcode)
ZSH_HIGHLIGHT_STYLES[command]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[function]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[hashed-command]='fg=magenta,bold'
ZSH_HIGHLIGHT_STYLES[arg0]='fg=magenta,bold'

# User shortcuts (Cyan, distinct from real commands)
ZSH_HIGHLIGHT_STYLES[alias]='fg=cyan,bold'
ZSH_HIGHLIGHT_STYLES[suffix-alias]='fg=cyan,bold'
ZSH_HIGHLIGHT_STYLES[global-alias]='fg=cyan,bold'

# Elevated first words (Yellow bold underline: own visual, warning not error.
# Red is reserved for errors only, so sudo no longer collides with failures)
ZSH_HIGHLIGHT_STYLES[precommand]='fg=yellow,bold,underline'

# Options and flags like -h or --help (Blue)
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=blue,bold'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=blue,bold'

# Valid paths and strings (Green; partial paths light up while typing)
ZSH_HIGHLIGHT_STYLES[path]='fg=green,underline'
ZSH_HIGHLIGHT_STYLES[path_prefix]='fg=green'
ZSH_HIGHLIGHT_STYLES[path_pathseparator]='fg=green,bold'
ZSH_HIGHLIGHT_STYLES[path_prefix_pathseparator]='fg=green,bold'
ZSH_HIGHLIGHT_STYLES[autodirectory]='fg=green,underline'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[dollar-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[dollar-double-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[back-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[back-quoted-argument-delimiter]='fg=green,bold'
ZSH_HIGHLIGHT_STYLES[back-double-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[back-dollar-quoted-argument]='fg=green'
ZSH_HIGHLIGHT_STYLES[rc-quote]='fg=green,bold'

# Unclosed quotes: subtle error while typing (red underline, no bg block)
ZSH_HIGHLIGHT_STYLES[single-quoted-argument-unclosed]='fg=red,underline'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument-unclosed]='fg=red,underline'
ZSH_HIGHLIGHT_STYLES[dollar-quoted-argument-unclosed]='fg=red,underline'
ZSH_HIGHLIGHT_STYLES[back-quoted-argument-unclosed]='fg=red,underline'

# Shell chrome: keywords, separators, redirections (Yellow)
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[commandseparator]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[redirection]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[assign]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[named-fd]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[numeric-fd]='fg=yellow'
ZSH_HIGHLIGHT_STYLES[history-expansion]='fg=yellow,bold'

# Subshells and expansions (Cyan: pops from yellow chrome)
ZSH_HIGHLIGHT_STYLES[command-substitution]='fg=cyan'
ZSH_HIGHLIGHT_STYLES[command-substitution-delimiter]='fg=cyan,bold'
ZSH_HIGHLIGHT_STYLES[process-substitution]='fg=cyan'
ZSH_HIGHLIGHT_STYLES[process-substitution-delimiter]='fg=cyan,bold'

# Patterns (Cyan, same family as shortcuts)
ZSH_HIGHLIGHT_STYLES[globbing]='fg=cyan'

# Comments and plain text (color8 outline gray: muted but readable on
# surface; color0 was invisible)
ZSH_HIGHLIGHT_STYLES[comment]='fg=8'
ZSH_HIGHLIGHT_STYLES[default]='none'

# Unknown commands / Errors (Red bold: highest severity, no bg)
ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=red,bold'

# ==========================================
# Brackets highlighter: rainbow nesting + error
# ========================================
ZSH_HIGHLIGHT_STYLES[bracket-error]='fg=red,bold'
ZSH_HIGHLIGHT_STYLES[bracket-level-1]='fg=blue,bold'
ZSH_HIGHLIGHT_STYLES[bracket-level-2]='fg=cyan'
ZSH_HIGHLIGHT_STYLES[bracket-level-3]='fg=green'
ZSH_HIGHLIGHT_STYLES[bracket-level-4]='fg=magenta'
ZSH_HIGHLIGHT_STYLES[bracket-level-5]='fg=yellow'

# ==========================================
# Cursor / line / root highlighters
# ========================================
ZSH_HIGHLIGHT_STYLES[cursor]='standout'
ZSH_HIGHLIGHT_STYLES[cursor-matchingbracket]='fg=white,bold,bg=blue'
ZSH_HIGHLIGHT_STYLES[line]='none'
ZSH_HIGHLIGHT_STYLES[root]='fg=white,bold,bg=red'

# ==========================================
# Pattern highlighter: kept loaded but empty (rm -rf shout removed per
# feedback; precommand underline already flags elevation)
# ========================================

# ==========================================
# Regexp highlighter: subtle, ANSI-only, no red (red is errors only)
# URLs get the sole blue-underline; TODO pops from gray comments
# ========================================
ZSH_HIGHLIGHT_REGEXP+=('https?://[^ ]+' 'fg=blue,underline')
ZSH_HIGHLIGHT_REGEXP+=('\b(TODO|FIXME|NOTE):?' 'fg=yellow,bold')
