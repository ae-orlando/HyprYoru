#              __
#  ____  _____/ /_
# /_  / / ___/ __ \
#  / /_(__  ) / / /
# /___/____/_/ /_/
# By ae. Orlando
# _______________________________________________________________________

# =====================
# Instant prompt (p10k)
# =====================
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# =====================
# Pre OMZ: env, plugins
# =====================
for f in "$ZDOTDIR"/conf.d/pre/*.zsh(N); do
  source "$f"
done

# ========
# OMZ
# ========
source "$ZSH/oh-my-zsh.sh"

# ==========================
# Post OMZ: overrides, theme
# ==========================
for f in "$ZDOTDIR"/conf.d/post/*.zsh(N); do
  source "$f"
done

# ==========================
# p10k config ($ZDOTDIR first)
# ==========================
if [[ -f "$ZDOTDIR/.p10k.zsh" ]]; then
  source "$ZDOTDIR/.p10k.zsh"
elif [[ -f ~/.p10k.zsh ]]; then
  source ~/.p10k.zsh
fi
