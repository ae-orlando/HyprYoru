# ==========================================================
# P10 Quick Prompt
# ===========================================================
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
# ===========================================================
# Modules loaded before Oh My Zsh (environment, plugins)
# ===========================================================
for f in "$ZDOTDIR"/conf.d/pre/*.zsh(N); do
  source "$f"
done

# ===================================
# Oh My Zsh
# ====================================
source "$ZSH/oh-my-zsh.sh"

# ============================================================
# Modules loaded after Oh My Zsh (override its defaults)
# ============================================================
for f in "$ZDOTDIR"/conf.d/post/*.zsh(N); do
  source "$f"
done

# ==============================================================
# Powerlevel10k configuration (lives in $ZDOTDIR so only the zsh
# symlink is needed on fresh installs; ~/.p10k.zsh kept as fallback)
if [[ -f "$ZDOTDIR/.p10k.zsh" ]]; then
  source "$ZDOTDIR/.p10k.zsh"
elif [[ -f ~/.p10k.zsh ]]; then
  source ~/.p10k.zsh
fi
