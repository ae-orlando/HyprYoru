# ============
# Paths, editor
# ============
export ZSH="$HOME/.oh-my-zsh"
export EDITOR="nvim"
export VISUAL="nvim"
export MANPAGE="nvim +Man!"
export PATH="$HOME/.local/bin:$PATH"

# ============
# Theme
# ============
ZSH_THEME="powerlevel10k/powerlevel10k"

# ============
# fnm (guarded: silent when absent)
# ============
if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd --shell zsh)"
fi
