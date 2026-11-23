#   ____      __   __ __         ___  _         __
#  /_  / ___ / /  / //_/__ __ __/ _ )(_)__  ___/ /__
#   / /_(_-</ _ \/ ,< / -_) // / _  / / _ \/ _  (_-<
#  /___/___/_//_/_/|_|\__/\_, /____/_/_//_/\_,_/___/
#                        /___/
#: Author: ae. Orlando
#: Github: https://github.com/ae-orlando
# This contains keybnds that you can use to navigate the terminal.
# Whether you're editing a command or scrolling. these are useful.
# _________________________________________________________________

# --- Vi mode as primary (Neovim-style prompt editing) ---
bindkey -v
export KEYTIMEOUT=1

# --- Terminal navigation (vi insert mode) ---
bindkey -M viins "^[[1;5C" forward-word
bindkey -M viins "^[[1;5D" backward-word
bindkey -M viins "\e[1~" beginning-of-line
bindkey -M viins "\e[4~" end-of-line
bindkey -M viins "\e[5~" beginning-of-history
bindkey -M viins "\e[6~" end-of-history
bindkey -M viins "\e[7~" beginning-of-line
bindkey -M viins "\e[3~" delete-char
bindkey -M viins "\e[2~" quoted-insert
bindkey -M viins "\e[5C" forward-word
bindkey -M viins "\e[5D" backward-word
bindkey -M viins "\e\e[C" forward-word
bindkey -M viins "\e\e[D" backward-word
bindkey -M viins "\e[1;5C" forward-word
bindkey -M viins "\e[1;5D" backward-word
bindkey -M viins "\e[8~" end-of-line
bindkey -M viins "\eOH" beginning-of-line
bindkey -M viins "\eOF" end-of-line
bindkey -M viins "\e[H" beginning-of-line
bindkey -M viins "\e[F" end-of-line

# --- Emacs-style shortcuts kept in Vi insert mode ---
bindkey -M viins "^A" beginning-of-line
bindkey -M viins "^E" end-of-line
bindkey -M viins "^W" backward-kill-word
bindkey -M viins "^U" backward-kill-line
bindkey -M viins "^K" kill-line
bindkey -M viins "^Y" yank

# --- Edit command line in Neovim ---
autoload -Uz edit-command-line
zle -N edit-command-line
bindkey -M viins "^X^E" edit-command-line
bindkey -M vicmd "vv" edit-command-line

# --- Optional quality-of-life: vi normal-mode history navigation ---
bindkey -M vicmd "k" up-line-or-history
bindkey -M vicmd "j" down-line-or-history
