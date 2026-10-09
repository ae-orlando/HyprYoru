# ===========================================
# Default paths
# ===========================================
export ZSH="$HOME/.oh-my-zsh"
export EDITOR="nvim"
export VISUAL="nvim"
export MANPAGE="nvim +Man!"
export PATH="$HOME/.local/bin:$PATH"

# ============================================
# Zsh Theme Initalizton
# ============================================
ZSH_THEME="powerlevel10k/powerlevel10k"

#=============================================
# Fast Node Manager Initalizton
# ============================================
if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd --shell zsh)"
fi
