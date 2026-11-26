#     ____        _   __
#    / __/__ _  _| | / /__ ________
#   / _// _ \ |/ / |/ / _ `/ __(_-<
#  /___/_//_/___/|___/\_,_/_/ /___/

# Contains environment variables and preferences.
# Author: ae. Orlando
# Github: https://github.com/ae-orlando

export EDITOR="nvim"
export VISUAL="nvim"
export MANPAGE="nvim +Man!"
export PATH="$HOME/.local/bin:$PATH"

# ============
# Pagers + syntax highlighting (terminal-following, no hardcoded theme)
# ============
# bat --theme=ansi resolves through Kitty/matugen ANSI slots, so man pages,
# --help output, and fzf previews follow the wallpaper instantly.
export PAGER="less"
export LESS="-R"
export MANROFFOPT="-c"
export MANPAGER="sh -c 'col -bx | bat -l man -p --theme=ansi'"
export BAT_THEME="ansi"
export BAT_STYLE="numbers,changes"

# ============
# fnm (guarded: silent when absent)
# ============
if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd --shell bash)"
fi

# ============
# direnv (guarded: silent when absent)
# ============
if command -v direnv >/dev/null 2>&1; then
  eval "$(direnv hook bash)"
fi
