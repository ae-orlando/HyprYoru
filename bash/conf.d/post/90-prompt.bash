#  __  __              ___                      __
#  \ \/ /__  ______ __/ _ \_______  __ _  ___  / /_
#   \  / _ \/ __/ // / ___/ __/ _ \/  ' \/ _ \/ __/
#   /_/\___/_/  \_,_/_/  /_/  \___/_/_/_/ .__/\__/
#                                      /_/

# By ae. Orlando
# This is the bash prompt designed to match the p10k style exactly.
# Transient prompt is made visible by `blesh`
# Implements a p10k-lean-8colors replica using ANSI slot colors only,
# so the prompt repaints with the wallpaper via Kitty/matugen.

# =====================================================================
# Icons (ANSI-C escapes keep this file pure ASCII)
# =====================================================================
_yoru_icon_lock=$''   # U+F023
_yoru_icon_gear=$''   # U+F013
_yoru_icon_direnv=$'▼' # U+25BC
_yoru_icon_venv=$''   # U+E73C
_yoru_icon_task=$''   # U+F4A0

# Directories containing one of these files are never shortened.
# Same 23-entry list as zsh/.p10k.zsh anchor_files.
_yoru_anchor_files=(
    .bzr .citc .git .hg .node-version .python-version .go-version
    .ruby-version .lua-version .java-version .perl-version .php-version
    .tool-versions .mise.toml .shorten_folder_marker .svn .terraform
    CVS Cargo.toml composer.json go.mod package.json stack.yaml
)

# =====================================================================
# Helpers. Every helper answers in $REPLY so building a prompt never
# forks a subshell (only git/taskwarrior run external commands).
# =====================================================================

# Render a PS1 fragment as visible text: drop readline markers (\[ \]),
# ANSI color sequences (\e[...m) and the backslashes _yoru_esc added
# before $ ` \. Used only for width arithmetic.
_yoru_visible() {
    local s=$1 out='' i=0 c d j
    local n=${#s} # separate statement: `local` expands all words first
    while ((i < n)); do
        c=${s:i:1}
        if [[ $c == $'\e' ]]; then
            # raw ESC from $'\e[…m' fragments: skip the CSI sequence
            ((i += 1))
            if [[ ${s:i:1} == '[' ]]; then
                while ((i < n)) && [[ ${s:i:1} != [A-Za-z] ]]; do
                    ((i += 1))
                done
                ((i += 1))
            fi
            continue
        fi
        if [[ $c == '\' ]]; then
            d=${s:i+1:1}
            case $d in
            '[' | ']')
                ((i += 2))
                continue
                ;;
            'e')
                if [[ ${s:i+2:1} == '[' ]]; then
                    j=$((i + 3))
                    while ((j < n)) && [[ ${s:j:1} != m ]]; do
                        ((j += 1))
                    done
                    i=$((j + 1))
                    continue
                fi
                ;;
            '$' | '`' | '\')
                out+=$d
                ((i += 2))
                continue
                ;;
            esac
        fi
        out+=$c
        ((i += 1))
    done
    REPLY=$out
}

# Escape $ ` \ so promptvars expansion renders them literally. bash
# expands $(...) inside PS1 after backslash decoding, so an unescaped
# $(...) in a branch or directory name would otherwise execute.
_yoru_esc() {
    local s=$1
    s=${s//\\/\\\\}
    s=${s//\$/\\$}
    s=${s//\`/\\\`}
    REPLY=$s
}

# Terse signal name for exit codes > 128 (143 -> TERM); falls back to
# the signal number when kill -l does not know it.
_yoru_signame() {
    local n=$(($1 - 128)) name
    if ((n <= 0)); then
        REPLY=$1
        return 0
    fi
    name=$(command kill -l "$n" 2>/dev/null)
    name=${name%%[[:space:]]*}
    name=${name#SIG}
    if [[ -n $name && $name == [A-Za-z]* ]]; then
        REPLY=$name
    else
        REPLY=$n
    fi
}

# p10k branch/tag truncation: more than 32 chars -> first12…last12.
_yoru_trunc32() {
    local s=$1
    if ((${#s} > 32)); then
        s=${s:0:12}'…'${s: -12}
    fi
    REPLY=$s
}

# Join pipeline stages with |, mapping >128 to a signal name.
_yoru_join_stages() {
    local joined='' sep='' x
    for x in "$@"; do
        if ((x > 128)); then
            _yoru_signame "$x"
            joined+=$sep$REPLY
        else
            joined+=$sep$x
        fi
        sep='|'
    done
    REPLY=$joined
}

# =====================================================================
# Right-prompt segments (spec section 3, in RIGHT_PROMPT_ELEMENTS
# order: status, exec-time, jobs, direnv, virtualenv, taskwarrior).
# Empty $REPLY means the segment stays hidden.
# =====================================================================

_yoru_seg_status() {
    local st=$1
    shift
    local -a ps=("$@")
    REPLY=''

    if ((st == 0)); then
        local any=0 x
        for x in "${ps[@]}"; do
            if ((x != 0)); then any=1; fi
        done
        ((any)) || return 0
        _yoru_join_stages "${ps[@]}"
        REPLY='\[\e[32m\]✔ '"$REPLY"$'\[\e[0m\]'
        return 0
    fi

    if ((${#ps[@]} > 1)); then
        _yoru_join_stages "${ps[@]}"
        REPLY='\[\e[31m\]✘ '"$REPLY"$'\[\e[0m\]'
        return 0
    fi

    if ((st > 128)); then
        _yoru_signame "$st"
        REPLY='\[\e[31m\]✘ '"$REPLY"$'\[\e[0m\]'
    fi
}

# command_execution_time. Start time comes from the DEBUG preexec trap
# below (ble.sh preexec writes the same variable once Step 4 lands).
# Threshold 3 s, precision 0, format 'd h m s' — exactly p10k's
# prompt_command_execution_time, including "every unit once >= 60".
_yoru_seg_exectime() {
    REPLY=''
    local start=${_yoru_cmd_start-}
    _yoru_cmd_start='' # never repeat a stale duration
    [[ -n $start && $start == *.* && -n ${EPOCHREALTIME-} ]] || return 0

    local now=$EPOCHREALTIME
    local sf=${start#*.} nf=${now#*.}
    sf=${sf}000000
    sf=${sf:0:6}
    nf=${nf}000000
    nf=${nf:0:6}
    local us=$(((${now%%.*} - ${start%%.*}) * 1000000 + (10#$nf - 10#$sf)))
    if ((us < 0)); then us=0; fi
    local d=$(((us + 500000) / 1000000))
    ((d >= 3)) || return 0

    local text
    if ((d < 60)); then
        text=${d}s
    else
        text="$((d % 60))s"
        text="$((d / 60 % 60))m $text"
        if ((d >= 3600)); then
            text="$((d / 3600 % 24))h $text"
            if ((d >= 86400)); then
                text="$((d / 86400))d $text"
            fi
        fi
    fi

    # "took " in the default fg, the value in fg 3 (yellow).
    REPLY='\[\e[39m\]took \[\e[33m\]'"$text"$'\[\e[0m\]'
}

# background_jobs — glyph only (BACKGROUND_JOBS_VERBOSE=false).
_yoru_seg_jobs() {
    REPLY=''
    local j
    j=$(jobs -p 2>/dev/null)
    if [[ -n $j ]]; then
        REPLY='\[\e[31m\]'"${_yoru_icon_gear}"$'\[\e[0m\]'
    fi
}

# direnv — just the yellow glyph (DIRENV_FOREGROUND=3).
_yoru_seg_direnv() {
    REPLY=''
    if [[ -n ${DIRENV_DIR-} ]]; then
        REPLY='\[\e[33m\]'"${_yoru_icon_direnv}"$'\[\e[0m\]'
    fi
}

# virtualenv — name resolution mirrors p10k prompt_virtualenv:
# pyvenv.cfg "prompt", then VIRTUAL_ENV_PROMPT "(name) ", then the
# basename with the generic-name -> parent-directory rule. The config
# empties both delimiters, so the text is just icon + space + name.
_yoru_seg_venv() {
    REPLY=''
    [[ -n ${VIRTUAL_ENV-} ]] || return 0

    local base=${VIRTUAL_ENV%/}
    base=${base##*/}
    local v='' line

    if [[ -r ${VIRTUAL_ENV%/}/pyvenv.cfg ]]; then
        while IFS= read -r line; do
            [[ $line == prompt* ]] || continue
            v=${line#prompt}
            v=${v#"${v%%[![:space:]]*}"}
            [[ $v == '='* ]] || {
                v=''
                continue
            }
            v=${v#=}
            v=${v#"${v%%[![:space:]]*}"}
            v=${v%"${v##*[![:space:]]}"}
            if [[ $v == \"*\" ]]; then
                v=${v:1:${#v}-2}
            elif [[ $v == \'*\' ]]; then
                v=${v:1:${#v}-2}
            fi
            if [[ -n $v ]]; then break; fi
            v=''
        done <"${VIRTUAL_ENV%/}/pyvenv.cfg"
    fi

    if [[ -z $v ]]; then
        # Same pattern as zsh: "(name) " with a trailing space, and only
        # when it differs from "(basename) ".
        if [[ ${VIRTUAL_ENV_PROMPT-} == \(*?\)\  && ${VIRTUAL_ENV_PROMPT-} != "($base) " ]]; then
            v=${VIRTUAL_ENV_PROMPT:1:${#VIRTUAL_ENV_PROMPT}-3}
        elif [[ $base == virtualenv || $base == venv || $base == .venv || $base == env ]]; then
            local p=${VIRTUAL_ENV%/}
            v=${p%/*}
            v=${v##*/}
        else
            v=$base
        fi
    fi

    _yoru_esc "$v"
    REPLY='\[\e[36m\]'"${_yoru_icon_venv} ${REPLY}"$'\[\e[0m\]'
}

# taskwarrior — pending/overdue counts, cached by task-data mtime (the
# strategy p10k uses). p10k only records counts >= 1, so a zero pending
# count leaves $REPLY empty and the segment hides. Content is p10k's
# default: "!<overdue>/" then "<pending>".
_yoru_seg_task() {
    REPLY=''
    command -v task >/dev/null 2>&1 || return 0
    local data=${TASKDATA:-$HOME/.local/share/task}
    [[ -d $data ]] || return 0

    local -a files=()
    local f
    for f in "$data/pending.data" "$data/completed.data" "$data/taskchampion.sqlite3"; do
        if [[ -f $f ]]; then files+=("$f"); fi
    done
    ((${#files[@]})) || return 0 # task has never been used here

    local sig
    sig=$(command stat --printf='%Y;' -- "${files[@]}" 2>/dev/null) || return 0
    sig+=${TASKDATA:-}

    if [[ -n $sig && $sig == "${_yoru_task_sig-}" ]]; then
        : # cache hit; an empty count is a valid cached result
    else
        local pend overdue text=''
        pend=$(command task +PENDING count rc.color=0 rc._forcecolor=0 </dev/null 2>/dev/null)
        overdue=$(command task +OVERDUE count rc.color=0 rc._forcecolor=0 </dev/null 2>/dev/null)
        if [[ $overdue =~ ^[1-9][0-9]*$ ]]; then text='!'$overdue'/'; fi
        if [[ $pend =~ ^[1-9][0-9]*$ ]]; then text+=$pend; fi
        _yoru_task_sig=$sig
        _yoru_task_text=$text
    fi

    if [[ -n ${_yoru_task_text-} ]]; then
        REPLY='\[\e[36m\]'"${_yoru_icon_task} ${_yoru_task_text}"$'\[\e[0m\]'
    fi
}

# =====================================================================
# Git segment — git status --porcelain=v2 parser plus my_git_formatter's
# assembly rules (spec section 5). Divergences from zsh (wip marker,
# push ahead/behind, merge action) are documented in docs/bash.md.
# =====================================================================
_yoru_git_part() {
    REPLY=''
    command -v git >/dev/null 2>&1 || return 0
    if [[ $PWD == "$HOME" ]]; then return 0; fi # VCS_DISABLED_WORKDIR_PATTERN='~'

    local out
    out=$(command git status --porcelain=v2 --branch --show-stash 2>/dev/null) || return 0

    local oid='' head='' upstream='' ahead=0 behind=0 stash=0
    local staged=0 unstaged=0 conflicted=0 untracked=0
    local line ab xy x y
    while IFS= read -r line; do
        case $line in
        '# branch.oid '*) oid=${line#'# branch.oid '} ;;
        '# branch.head '*) head=${line#'# branch.head '} ;;
        '# branch.upstream '*) upstream=${line#'# branch.upstream '} ;;
        '# branch.ab ')
            ab=${line#'# branch.ab '}
            ahead=${ab%% *}
            ahead=${ahead#+}
            behind=${ab##* }
            behind=${behind#-}
            ;;
        '# stash ') stash=${line#'# stash '} ;;
        '1 '* | '2 '*)
            xy=${line:2:2}
            x=${xy:0:1}
            y=${xy:1:1}
            if [[ $x != '.' ]]; then staged=$((staged + 1)); fi
            if [[ $y != '.' ]]; then unstaged=$((unstaged + 1)); fi
            ;;
        'u ') conflicted=$((conflicted + 1)) ;;
        '? ') untracked=$((untracked + 1)) ;;
        esac
    done <<<"$out"

    [[ -n $oid ]] || return 0

    local local_branch='' tag=''
    if [[ -n $head && $head != '(detached)' ]]; then
        local_branch=$head
    elif [[ -n $head ]]; then
        # Detached HEAD: porcelain v2 has no tag field, so ask git directly
        # (only in this rare case, to keep the common path to one git call).
        tag=$(command git describe --tags --exact-match HEAD 2>/dev/null)
    fi

    local remote=''
    if [[ -n $upstream ]]; then
        remote=${upstream#*/} # "origin/main" -> "main"
    fi

    # Exact zsh color slots: meta %f, clean %2F, modified %3F,
    # untracked %4F, conflicted %1F.
    local meta='\[\e[39m\]' clean='\[\e[32m\]' modified='\[\e[33m\]'
    local unc='\[\e[34m\]' conflicted_c='\[\e[31m\]'

    local res="${meta}on " b
    if [[ -n $local_branch ]]; then
        _yoru_trunc32 "$local_branch"
        b=$REPLY
        _yoru_esc "$b"
        res+="${clean}${REPLY}"
    elif [[ -n $tag ]]; then
        _yoru_trunc32 "$tag"
        b=$REPLY
        _yoru_esc "$b"
        res+="${meta}#${clean}${REPLY}"
    elif [[ -n $oid ]]; then
        res+="${meta}@${clean}${oid:0:8}"
    fi

    if [[ -n $remote && $remote != "$local_branch" ]]; then
        _yoru_esc "$remote"
        res+="${meta}:${clean}${REPLY}"
    fi

    if ((ahead || behind)); then
        if ((behind)); then res+=" ${clean}⇣${behind}"; fi
        if ((ahead && ! behind)); then res+=" "; fi
        if ((ahead)); then res+="${clean}⇡${ahead}"; fi
    fi

    if ((stash)); then res+=" ${clean}*${stash}"; fi
    if ((conflicted)); then res+=" ${conflicted_c}~${conflicted}"; fi
    if ((staged)); then res+=" ${modified}+${staged}"; fi
    if ((unstaged)); then res+=" ${modified}!${unstaged}"; fi
    if ((untracked)); then res+=" ${unc}?${untracked}"; fi

    REPLY=$res
}

# =====================================================================
# Dir segment (spec section 6): ~ form, lock glyph for non-writable or
# vanished directories, truncate_to_unique beyond 80 columns.
# =====================================================================

# Shorten every eligible segment to its shortest unique prefix, exactly
# like p10k's truncate_to_unique: the first segment, the last segment
# and marker-file directories are anchors; the glob runs against the
# real filesystem path and only counts directories (a sibling like
# "opencode-pty" correctly forces a longer prefix).
_yoru_truncate_dir() {
    local disp=$1
    REPLY=$disp

    local -a segs=()
    IFS=/ read -ra segs <<<"$disp"
    local n=${#segs[@]}
    ((n >= 3)) || return 0

    local first_elig
    if [[ ${segs[0]} == '~' ]]; then first_elig=1; else first_elig=2; fi
    local last_elig=$((n - 2))
    if ((first_elig > last_elig)); then return 0; fi

    local -a out=("${segs[@]}") matches=()
    local cur fsdir m pfx j cand
    if [[ ${segs[0]} == '~' ]]; then cur=$HOME; else cur=''; fi

    for ((k = 1; k <= last_elig; k++)); do
        if [[ -z $cur ]]; then fsdir=/${segs[k]}; else fsdir=$cur/${segs[k]}; fi

        if ((k >= first_elig)); then
            local anchored=0
            for m in "${_yoru_anchor_files[@]}"; do
                if [[ -e $fsdir/$m ]]; then
                    anchored=1
                    break
                fi
            done

            if ((! anchored)); then
                for ((j = 1; j <= ${#segs[k]}; j++)); do
                    pfx=${segs[k]:0:j}
                    matches=()
                    for cand in "$cur/$pfx"*; do
                        if [[ -d $cand ]]; then matches+=("$cand"); fi
                    done
                    if ((${#matches[@]} == 1)) && [[ ${matches[0]} == "$fsdir" ]]; then
                        out[k]=$pfx
                        break
                    fi
                done
            fi
        fi
        cur=$fsdir
    done

    local IFS=/
    REPLY="${out[*]}"
}

_yoru_dir_part() {
    REPLY=''
    local fs=$PWD disp
    if [[ $fs == "$HOME" ]]; then
        disp='~'
    elif [[ $fs == "$HOME/"* ]]; then
        disp='~/'"${fs#"$HOME"/}"
    else
        disp=$fs
    fi

    if ((${#disp} > 80)); then
        _yoru_truncate_dir "$disp"
        disp=$REPLY
    fi

    _yoru_esc "$disp"
    local body=$REPLY lock=''
    if [[ ! -w $PWD || ! -d $PWD ]]; then
        lock="${_yoru_icon_lock} "
    fi
    REPLY='\[\e[34m\]'"${lock}${body}"$'\[\e[0m\]'
}

# =====================================================================
# The single PROMPT_COMMAND dispatcher (spec section 2).
# =====================================================================
_yoru_prompt() {
    # MUST be the very first statement — atomic capture of status + pipeline:
    local last_status=$? last_pipestatus=("${PIPESTATUS[@]}")
    # ^ verified: intact at PROMPT_COMMAND entry, and this one statement
    #   captures both before any builtin clobbers them (holds even with the
    #   DEBUG trap below installed).

    _yoru_prompting=1 # blocks the preexec hook while we build

    # Run entries registered by earlier files (matugen reload etc.)
    local pc
    for pc in "${_yoru_prev_prompt_command[@]}"; do
        if [[ -n $pc ]]; then eval "$pc"; fi
    done

    # ---- line 1, right side ----
    local -a rp=()
    _yoru_seg_status "$last_status" "${last_pipestatus[@]}"
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi
    _yoru_seg_exectime
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi
    _yoru_seg_jobs
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi
    _yoru_seg_direnv
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi
    _yoru_seg_venv
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi
    _yoru_seg_task
    if [[ -n $REPLY ]]; then rp+=("$REPLY"); fi

    # ---- line 1, left side: frame + dir + git ----
    local line1_left='\[\e[37m\]╭─\[\e[0m\] '
    _yoru_dir_part
    line1_left+=$REPLY
    local gitp
    _yoru_git_part
    gitp=$REPLY
    if [[ -n $gitp ]]; then line1_left+=" $gitp"; fi

    # ---- pad line 1 to exactly $COLUMNS ----
    local cols=${COLUMNS:-80}
    if ((cols <= 1)); then cols=80; fi

    local right_block='' i
    for ((i = 0; i < ${#rp[@]}; i++)); do
        if ((i)); then right_block+=' '; fi
        right_block+=${rp[i]}
    done

    _yoru_visible "$line1_left"
    local left_vis=$REPLY
    _yoru_visible "$right_block"
    local right_vis=$REPLY

    local pad=$((cols - ${#left_vis} - ${#right_vis}))
    if ((pad < 1)); then
        right_block='' # overlap: drop the right block (p10k behaviour)
        pad=$((cols - ${#left_vis}))
    fi
    if ((pad < 0)); then pad=0; fi
    local padstr=''
    printf -v padstr '%*s' "$pad" ''

    # ---- assemble PS1 (spec section 7) ----
    PS1=$'\n'"$line1_left$padstr$right_block"$'\n''\[\e[37m\]╰─\[\e[0m\]'
    if ((last_status == 0)); then
        PS1+='\[\e[32m\]'
    else
        PS1+='\[\e[31m\]'
    fi
    PS1+='❯\[\e[0m\] '
    PS2='\[\e[37m\]├─\[\e[0m\] '

    # ble.sh transient prompt (p10k TRANSIENT_PROMPT=always): on accept,
    # ble.sh erases the old prompt and redraws prompt_ps1_final plus the
    # typed line — one "❯ cmd" line in the status colour of the command
    # just run (matches the zsh/p10k transcript byte-for-byte).
    if [[ -n ${BLE_VERSION-} ]]; then
        if ((last_status == 0)); then
            bleopt prompt_ps1_final=$'\n''\[\e[32m\]❯\[\e[0m\] '
        else
            bleopt prompt_ps1_final=$'\n''\[\e[31m\]❯\[\e[0m\] '
        fi
    fi

    _yoru_prompting=''
}

# =====================================================================
# Exec-time source: stamp _yoru_cmd_start before every command line.
# With ble.sh, 50-blesh.bash registers the PREEXEC hook (once per line —
# p10k parity); this DEBUG trap is the plain-bash fallback, where it
# fires per simple command. Skipped while ble.sh is active (its hook
# owns the stamping) and when another DEBUG trap already exists (its
# owner keeps it).
# =====================================================================
_yoru_preexec_debug() {
    # Inside our own prompt build: BASH_COMMAND matches the dispatcher or
    # its first statement (the latter only matters with functrace on).
    if ((${_yoru_prompting:-0})); then return 0; fi
    case ${BASH_COMMAND-} in
    *_yoru_prompt* | 'local last_status='*) return 0 ;;
    esac
    [[ -n ${EPOCHREALTIME-} ]] || return 0
    _yoru_cmd_start=$EPOCHREALTIME
}

if [[ -z ${BLE_VERSION-} && -z $(trap -p DEBUG 2>/dev/null) ]]; then
    trap '_yoru_preexec_debug' DEBUG
fi

# =====================================================================
# Registration: save whatever PROMPT_COMMAND holds now (string or the
# bash-5.1+ array form), then become the single dispatcher.
# Idempotent — re-sourcing never duplicates anything.
# =====================================================================
# Re-source normalization: re-running .bashrc makes 15-matugen,
# 40-zoxide and 50-blesh re-register around the dispatcher (their own
# guards look for their name in PROMPT_COMMAND, which no longer
# contains it). Fold those entries back into the child list —
# deduplicated — and reset PROMPT_COMMAND to the sole dispatcher.
# Without this, "reload" would execute BEFORE _yoru_prompt and clobber
# the very $?/PIPESTATUS the dispatcher captures atomically.
_yoru_pc_refold() {
    local pc e seg joined=';' prev
    if [[ $(declare -p PROMPT_COMMAND 2>/dev/null) == 'declare -a'* ]]; then
        for e in "${PROMPT_COMMAND[@]}"; do
            [[ -n $pc ]] && pc+=';'
            pc+=$e
        done
        unset PROMPT_COMMAND # scalar-assign on an array keeps old [1..]
    else
        pc=${PROMPT_COMMAND-}
    fi
    pc=${pc//$'\n'/;}
    local -a segs=()
    while [[ $pc == *';'* ]]; do
        segs+=("${pc%%;*}")
        pc=${pc#*;}
    done
    segs+=("$pc")
    for prev in "${_yoru_prev_prompt_command[@]}"; do
        prev=${prev//$'\n'/;}
        joined+=$prev';'
    done
    for seg in "${segs[@]}"; do
        seg=${seg#"${seg%%[![:space:]]*}"}
        seg=${seg%"${seg##*[![:space:]]}"}
        [[ -n $seg ]] || continue
        [[ $seg == *_yoru_prompt* ]] && continue
        if [[ $joined != *";$seg;"* ]]; then
            _yoru_prev_prompt_command+=("$seg")
            joined+=$seg';'
        fi
    done
    PROMPT_COMMAND=_yoru_prompt
}

if [[ ${PROMPT_COMMAND[*]-} != *_yoru_prompt* ]]; then
    _yoru_prev_prompt_command=()
    if [[ -n ${PROMPT_COMMAND-} ]]; then
        if [[ $(declare -p PROMPT_COMMAND 2>/dev/null) == 'declare -a'* ]]; then
            _yoru_prev_prompt_command=("${PROMPT_COMMAND[@]}")
            unset PROMPT_COMMAND # scalar-assign on an array keeps old [1..]
        else
            _yoru_prev_prompt_command=("$PROMPT_COMMAND")
        fi
    fi
    PROMPT_COMMAND=_yoru_prompt
else
    _yoru_pc_refold
fi
