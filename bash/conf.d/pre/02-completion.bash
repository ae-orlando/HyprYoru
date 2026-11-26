#     ___       __       _____                __    __
#    / _ |__ __/ /____  / ___/__  __ _  ___  / /__ / /____
#   / __ / // / __/ _ \/ /__/ _ \/  ' \/ _ \/ / -_) __/ -_)
#  /_/ |_\_,_/\__/\___/\___/\___/_/_/_/ .__/_/\__/\__/\__/
#                                    /_/

# Author: ae. Orlando
# Github: https://github.com/ae-orlando

# bash-completions
if [[ -f /usr/share/bash-completion/bash_completion ]]; then
    source /usr/share/bash-completion/bash_completion
fi

# git conpletions
if [[ -f /usr/share/git/completion/git-completion.bash ]]; then
    source /usr/share/git/completion/git-completion.bash
fi
