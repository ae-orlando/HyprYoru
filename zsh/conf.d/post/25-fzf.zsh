# fzf keybindings: CTRL-R history, CTRL-T files, ALT-C directories.
# Guarded: silent when absent. Previews/colors come from FZF_DEFAULT_OPTS
# (matugen-generated, see 15-matugen.zsh); file search uses fd when present.
# by ae. Orlando
# _______________________________________________________________________

if command -v fzf >/dev/null 2>&1; then
  source <(fzf --zsh)
fi
