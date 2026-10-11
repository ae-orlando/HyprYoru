# ========
# Aliases
# ========

# eza
alias ls="eza -a --color=always --group-directories-first --icons=always"
alias l="eza -al --color=always --group-directories-first --icons=always"
alias ll="eza -al --color=always --group-directories-first --icons=always --git"
alias lt="eza -a --tree --level=2 --color=always --group-directories-first --icons=always"
alias ltt="eza -a --tree --level=3 --color=always --group-directories-first --icons=always"

# Editing
alias v="nvim"
alias vi="nvim"
alias vim="nvim"

alias c="clear"
alias x="exit"
alias q="exit"

alias cp="cp -iv"
alias mv="mv -iv"
alias rm="rm -vI"
alias mkd="mkdir -pv"

alias grep="grep --color=auto"
alias diff="diff --color=auto"
alias less="less -R"
alias cat="bat --style=plain --paging=never --theme=ansi"
alias bat="bat --theme=ansi"
alias df="df -h"
alias free="free -m"

alias gs="git status -sb"
alias ga="git add ."
alias gc="git commit -m"
alias gp="git push"
alias gl="git pull"
alias gd="git diff"

alias update="sudo pacman -Syu"
alias install="sudo pacman -S"
alias remove="sudo pacman -Rns"

alias py="python"
alias venv="uv venv .venv && source .venv/bin/activate"

alias ports="sudo netstat -tulanp"
alias renet="sudo systemctl restart NetworkManager"
