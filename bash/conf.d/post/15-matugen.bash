# By ae. Orlando
# This whatches the shell colors.s in bash and reloads it whenver
# matuge changes it.
# ______________________________________________________

_matugen_colors_reload() {
    local file="$HOME/.config/bash/generated/colors.sh" mtime
    if [[ ! -f "$file" ]]; then
        unset _matugen_colors_mtime
        return 0
    fi
    # Sub-second precision: stat %y, same as the zsh hook.
    mtime=$(command stat -c %y -- "$file" 2>/dev/null) || return 0
    if [[ -n "$mtime" && "$mtime" != "${_matugen_colors_mtime-}" ]]; then
        # shellcheck source=/dev/null
        source "$file"
        _matugen_colors_mtime=$mtime
    fi
}

# PROMPT_COMMAND runs before each prompt (bash's precmd equivalent).
# Idempotent registration so re-sourcing never duplicates it.
if [[ ${PROMPT_COMMAND-} != *"_matugen_colors_reload"* ]]; then
    PROMPT_COMMAND="_matugen_colors_reload${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi
_matugen_colors_reload
