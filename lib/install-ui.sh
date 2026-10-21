#!/usr/bin/env bash
# Presentation and command logging for install.sh. Sourcing this file is read-only.

WARN_MESSAGES=()
FAIL_MESSAGES=()

setup_ui() {
  C_BOLD=''; C_DIM=''; C_RESET=''
  C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_MAGENTA=''; C_CYAN=''
  if [[ -t 1 && -z "${NO_COLOR:-}" && "${CLICOLOR:-1}" != 0 && "${TERM:-}" != dumb ]]; then
    C_BOLD=$'\e[1m'; C_DIM=$'\e[2m'; C_RESET=$'\e[0m'
    C_RED=$'\e[31m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'
    C_BLUE=$'\e[34m'; C_MAGENTA=$'\e[35m'; C_CYAN=$'\e[36m'
  fi
  USE_ASCII=1
  if [[ -z "${NO_EMOJI:-}" && "${TERM:-}" != dumb ]]; then
    case "$(locale charmap 2>/dev/null || true)" in
      UTF-8|UTF8|utf8|utf-8) USE_ASCII=0 ;;
    esac
  fi
  I_OK='+'; I_WARN='!'; I_FAIL='x'; I_STEP='>'; I_SKIP='-'
  if [[ "$USE_ASCII" -eq 0 ]]; then
    I_OK='✓'; I_FAIL='✕'; I_STEP='▸'; I_SKIP='·'
  fi
}

_term() {
  local stream="$1"; shift
  [[ "$stream" != out || "$QUIET" -eq 0 ]] || return 0
  if [[ "$stream" == err ]]; then printf '%s\n' "$@" >&2; else printf '%s\n' "$@"; fi
}

_log_plain() {
  [[ "$LOG_ENABLED" -eq 1 ]] || return 0
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*" >>"$LOG_FILE"
}

say()  { _term out "    $*"; _log_plain "[info] $*"; }
log()  { [[ "$VERBOSE" -eq 0 ]] || _term out "    ${C_DIM}$*${C_RESET}"; _log_plain "[detail] $*"; }
ok()   { PASS_COUNT=$((PASS_COUNT + 1)); _term out "  ${C_GREEN}${I_OK}${C_RESET} $*"; _log_plain "[ok] $*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); WARN_MESSAGES+=("$*"); _term err "  ${C_YELLOW}${I_WARN}${C_RESET} $*"; _log_plain "[warn] $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); FAIL_MESSAGES+=("$*"); _term err "  ${C_RED}${I_FAIL}${C_RESET} $*"; _log_plain "[fail] $*"; }
dry()  { _term out "  ${C_MAGENTA}PLAN${C_RESET} $*"; }
skip() {
  SKIP_COUNT=$((SKIP_COUNT + 1))
  [[ "$VERBOSE" -eq 0 ]] || _term out "  ${C_DIM}${I_SKIP} $*${C_RESET}"
  _log_plain "[skip] $*"
}

hr() {
  [[ "$QUIET" -eq 0 ]] || return 0
  local width line char='─'
  width=$(tput cols 2>/dev/null || printf '72')
  [[ "$width" =~ ^[0-9]+$ ]] || width=72
  (( width <= 76 )) || width=76
  (( width >= 20 )) || width=20
  [[ "$USE_ASCII" -eq 0 ]] || char='-'
  printf -v line '%*s' "$width" ''
  _term out "${C_DIM}${line// /$char}${C_RESET}"
}

format_elapsed() {
  local seconds="$1"
  if (( seconds < 60 )); then printf '%ss' "$seconds"
  else printf '%sm %ss' "$((seconds / 60))" "$((seconds % 60))"; fi
}

progress_bar() {
  local done="$1" total="$2" width=16 fill='█' empty='░' bar='' i filled
  filled=$((done * width / total))
  if [[ "$USE_ASCII" -eq 1 ]]; then fill='#'; empty='-'; fi
  for ((i=0; i<width; i++)); do
    if (( i < filled )); then bar+="$fill"; else bar+="$empty"; fi
  done
  printf '%s' "$bar"
}

finish_phase() {
  [[ "$LAST_STEP_TS" -gt 0 ]] || return 0
  local elapsed=$(( $(date +%s) - LAST_STEP_TS ))
  log "Phase $PHASE_NUM finished in $(format_elapsed "$elapsed")"
}

step() {
  finish_phase
  PHASE_NUM=$((PHASE_NUM + 1))
  LAST_STEP_TS=$(date +%s)
  _term out '' "${C_CYAN}${I_STEP}${C_RESET} ${C_BOLD}$*${C_RESET}  ${C_DIM}[$PHASE_NUM/$TOTAL_PHASES] $(progress_bar "$((PHASE_NUM - 1))" "$TOTAL_PHASES")${C_RESET}"
  _log_plain "[phase $PHASE_NUM/$TOTAL_PHASES] $*"
}

banner() {
  hr
  _term out "  ${C_BOLD}${C_MAGENTA}HyprYoru${C_RESET}  ${C_DIM}/  Your desktop, configured.${C_RESET}"
  _term out "  ${C_CYAN}Choose intentionally. Review everything. Keep your originals.${C_RESET}"
  hr
  if [[ "$DRY_RUN" -eq 1 ]]; then
    _term out "  ${C_MAGENTA}PLAN ONLY${C_RESET}  No files, logs, packages, or services will change."
  elif [[ "$CHECK_ONLY" -eq 1 ]]; then
    _term out "  ${C_CYAN}CHECK ONLY${C_RESET}  Read-only diagnostics; no repair actions."
  fi
}

section() { _term out '' "  ${C_BOLD}$*${C_RESET}"; }
field() { local text; printf -v text '    %-15s %s' "$1" "$2"; _term out "$text"; }

is_interactive() {
  [[ "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 && "$CHECK_ONLY" -eq 0 && -t 0 && -t 1 ]]
}

ask_yes_no() {
  local question="$1" default="$2" answer suffix='[y/N]'
  if [[ "$UI_BACKEND" == gum && "$UI_SESSION" -eq 1 ]]; then
    local -a options=(No Yes)
    [[ "$default" != yes ]] || options=(Yes No)
    if ! ui_choose "$question" "${options[@]}"; then
      _term err 'Approval cancelled; existing backups are retained.'
      exit 130
    fi
    [[ "$UI_REPLY" == Yes ]]
    return
  fi
  [[ "$default" != yes ]] || suffix='[Y/n]'
  while true; do
    if ! IFS= read -r -p "    $question $suffix: " answer; then
      printf '\nInput closed; installation cancelled.\n' >&2
      exit 1
    fi
    case "${answer,,}" in
      '') [[ "$default" == yes ]]; return ;;
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) _term err "    Please answer yes or no." ;;
    esac
  done
}

command_text() { local text; printf -v text '%q ' "$@"; printf '%s' "${text% }"; }

# Argument arrays, never eval. Foreground execution preserves terminal input.
run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then dry "$(command_text "$@")"; return 0; fi
  _log_plain "[command] $(command_text "$@")"
  local rc=0
  local -a status=()
  if [[ "$QUIET" -eq 1 && "$LOG_ENABLED" -eq 1 ]]; then
    "$@" >>"$LOG_FILE" 2>&1 || rc=$?
  elif [[ "$LOG_ENABLED" -eq 1 ]]; then
    if "$@" 2>&1 | tee -a "$LOG_FILE"; then
      rc=0
    else
      status=("${PIPESTATUS[@]}")
      rc=${status[0]}
      [[ "$rc" -ne 0 ]] || rc=${status[1]}
    fi
  else
    "$@" || rc=$?
  fi
  _log_plain "[exit] $rc"
  return "$rc"
}

# Only unattended commands run behind a spinner. Interactive pacman/makepkg
# must stay in the foreground so their questions remain visible and usable.
# An attempt is not a final failure: callers decide whether to retry or abort.
spin() {
  local message="$1"; shift
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "$message"
    [[ "$VERBOSE" -eq 0 ]] || say "$(command_text "$@")"
    return 0
  fi
  local started elapsed rc=0 frames='|/-\' i=0
  started=$(date +%s)
  _log_plain "[task] $message"
  if [[ "$ASSUME_YES" -eq 0 || "$VERBOSE" -eq 1 ]]; then
    say "$message"
    run "$@" || rc=$?
  else
    _log_plain "[command] $(command_text "$@")"
    if [[ "$LOG_ENABLED" -eq 1 ]]; then
      (trap - ERR; "$@") </dev/null >>"$LOG_FILE" 2>&1 &
    else
      (trap - ERR; "$@") </dev/null >/dev/null 2>&1 &
    fi
    ACTIVE_PID=$!
    if [[ -t 1 && "$QUIET" -eq 0 && "${TERM:-}" != dumb ]]; then
      [[ "$USE_ASCII" -eq 1 ]] || frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
      tput civis 2>/dev/null || true
      while kill -0 "$ACTIVE_PID" 2>/dev/null; do
        printf '\r  %s%s%s %s  %s' "$C_CYAN" "${frames:$((i % ${#frames})):1}" "$C_RESET" "$message" "$(format_elapsed "$(( $(date +%s) - started ))")"
        i=$((i + 1))
        sleep 0.12
      done
      printf '\r\033[2K'
      _restore_cursor
    fi
    wait "$ACTIVE_PID" || rc=$?
    ACTIVE_PID=''
    _log_plain "[exit] $rc"
  fi
  elapsed=$(( $(date +%s) - started ))
  if [[ "$rc" -eq 0 ]]; then
    ok "$message ($(format_elapsed "$elapsed"))"
  else
    _term err "  ${C_YELLOW}${I_WARN}${C_RESET} $message returned $rc ($(format_elapsed "$elapsed"))"
    _log_plain "[attempt-failed] $message ($rc)"
  fi
  return "$rc"
}

_restore_cursor() { [[ ! -t 1 ]] || tput cnorm 2>/dev/null || true; }

vpass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  [[ "$VERBOSE" -eq 0 ]] || _term out "  ${C_GREEN}${I_OK}${C_RESET} $*"
  _log_plain "[verify-pass] $*"
}
vfail() { fail "$*"; }
vwarn() { warn "$*"; }

final_summary() {
  finish_phase
  local title='Installation complete' color="$C_GREEN"
  if (( FAIL_COUNT > 0 )); then
    title='Needs attention'; color="$C_RED"
    [[ "$DRY_RUN" -eq 0 ]] || title='Plan blocked — nothing changed'
  elif [[ "$DRY_RUN" -eq 1 ]]; then title='Plan complete — nothing changed'; color="$C_MAGENTA"
  elif [[ "$CHECK_ONLY" -eq 1 ]]; then title='Checks complete'
  elif (( WARN_COUNT > 0 )); then title='Installed with notes'; color="$C_YELLOW"; fi
  if [[ "$DRY_RUN" -eq 1 && "${GUM_CACHE_CHANGED:-0}" -eq 1 ]]; then
    if (( FAIL_COUNT > 0 )); then title='Plan blocked — no desktop changes'
    else title='Plan complete — no desktop changes'; fi
  fi
  _term out ''
  hr
  _term out "  ${C_BOLD}${color}${title}${C_RESET}  ${C_DIM}$(format_elapsed "$(( $(date +%s) - SCRIPT_START ))")${C_RESET}"
  field 'Results' "$PASS_COUNT passed / $SKIP_COUNT unchanged / $WARN_COUNT warnings / $FAIL_COUNT failures"
  field 'Phases' "${COMPLETED_PHASES:-0}/$TOTAL_PHASES completed"
  [[ "$BACKUP_READY" -eq 0 ]] || field 'Backups' "$BACKUP_DIR"
  [[ "$LOG_ENABLED" -eq 0 ]] || field 'Log' "$LOG_FILE"
  [[ "${GUM_DOWNLOADED:-0}" -eq 0 ]] || field 'UI runtime' "$GUM_BIN (approved cache; retained)"
  if [[ "$DRY_RUN" -eq 0 && "$CHECK_ONLY" -eq 0 && "$LINK_ONLY" -eq 0 && "$FAIL_COUNT" -eq 0 ]]; then
    if [[ "$WITH_GDM" -eq 1 ]]; then say 'Next: log out or reboot, then select Hyprland in GDM.'
    else say 'Next: start Hyprland through your existing session manager or from a TTY.'; fi
    say 'SUPER+W wallpaper  /  SUPER+R reload bar  /  ./install.sh --check'
  fi
  if (( FAIL_COUNT > 0 )); then
    _term err '  Resolve the failures above before relying on this installation.'
  fi
  hr
}
