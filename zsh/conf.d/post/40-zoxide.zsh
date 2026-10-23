#   ____            _    __
#  /_  / ___ __ __ (_)__/ /__
#   / /_/ _ \\ \ // / _  / -_)
#  /___/\___/_\_\/_/\_,_/\__/

# by ae. Orlando.
# github: https://github.com/ae-orlando
# __________________________________________________
#
# This initializes the zoxode, integrating it to the shell.
# :z(n): jumps you to the directory named 'n' :zi: opens an iteractive mode tru fzf

if command -v zoxide > /dev/null 2>&1; then
    eval "$(zoxide init zsh)"
fi
