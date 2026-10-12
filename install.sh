#!/usr/bin/env bash
# Dotfiles reproducer — Arch Linux + GDM + Hyprland (Lua) fresh-system install.
#
# Reapplies this repo exactly as it runs on the source machine:
#   Hyprland Lua (hyprland.lua + 9 modules), matugen palette hub, waybar,
#   swaync, rofi type-6/style-9, kitty, btop, gtk3/4, qt6ct, waypaper (backend=none),
#   zsh (OMZ + p10k), fastfetch, fonts, services, mime, gsettings.
#
# Usage:
#   ./install.sh [--profile core|full] [--only-dotfiles] [--no-aur] [--dry-run]
#                [--yes] [--verbose|--quiet] [--log-file PATH] [--no-color] [--help]
#
# Profiles:
#   full (default) — every explicit package from the source machine (exact repro).
#   core           — minimum to boot Hyprland with a working config (no user apps).
#
# Safety: idempotent, backs up ~/.config + ~/.zshenv, supports --dry-run.
# Arch-only. Run as a normal user with sudo access (not as root).
# UI: guided pure-bash prompts (no dependencies) when run on a terminal
# without --yes; colors auto-off when piped, NO_COLOR=1, CLICOLOR=0, or
# TERM=dumb; icons auto-degrade to ASCII with NO_EMOJI=1 or non-UTF-8 locale.
set -euo pipefail

DOTFILES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR_DEFAULT="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-install/logs"
LOG_FILE="$LOG_DIR_DEFAULT/install-$(date +%Y%m%d-%H%M%S).log"
LOG_FILE_EXPLICIT=0
LOG_KEEP=10
BACKUP_DIR="$HOME/.local/state/dotfiles-backup-$(date +%Y%m%d-%H%M%S)"
YAY_BUILD_DIR="/tmp/yay-bin"

PROFILE="full"
PROFILE_EXPLICIT=0
ONLY_DOTFILES=0
NO_AUR=0
DRY_RUN=0
ASSUME_YES=0
VERBOSE=0
QUIET=0

# --------------------------------------------------------------------------
# TUI (pure bash, zero dependencies). Colors auto-off when piped, NO_COLOR=1,
# --no-color, CLICOLOR=0, or TERM=dumb. Icons fall back to ASCII when the
# locale is not UTF-8, TERM=dumb, or NO_EMOJI=1.
# Plain timestamped mirror of every line goes to $LOG_FILE.
# --------------------------------------------------------------------------
setup_colors() {
  if [[ -n "${NO_COLOR:-}" || "${CLICOLOR:-1}" == "0" || "${TERM:-}" == "dumb" ]] || [[ ! -t 1 ]]; then
    C_BOLD=''; C_DIM=''; C_RESET=''
    C_RED=''; C_GREEN=''; C_YELLOW=''
    C_BLUE=''; C_MAGENTA=''; C_CYAN=''
  else
    C_BOLD=$'\e[1m'; C_DIM=$'\e[2m'; C_RESET=$'\e[0m'
    C_RED=$'\e[31m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'
    C_BLUE=$'\e[34m'; C_MAGENTA=$'\e[35m'; C_CYAN=$'\e[36m'
  fi
}

setup_icons() {
  USE_ASCII=0
  local loc="${LC_ALL:-}${LC_CTYPE:-}${LANG:-}"
  local charmap=""
  charmap=$(locale charmap 2>/dev/null || true)
  if [[ -n "${NO_EMOJI:-}" || "${TERM:-}" == "dumb" ]]; then
    USE_ASCII=1
  elif [[ "$charmap" == [Uu][Tt][Ff]-8 || "$charmap" == [Uu][Tt][Ff]8 ]]; then
    USE_ASCII=0
  elif [[ -z "$loc" ]]; then
    USE_ASCII=1
  elif [[ "$loc" != *UTF-8* && "$loc" != *utf8* && "$loc" != *UTF8* ]]; then
    USE_ASCII=1
  fi
  if [[ "$USE_ASCII" -eq 1 ]]; then
    I_OK="ok"; I_WARN="!"; I_FAIL="x"; I_DRY="DRY"
    I_STEP=">"; I_SPIN="*"; I_SKIP="o"; I_ARROW="=>"
  else
    I_OK="✔"; I_WARN="⚠"; I_FAIL="✖"; I_DRY="DRY"
    I_STEP="▸"; I_SPIN="◌"; I_SKIP="○"; I_ARROW="==>"
  fi
}

setup_colors
setup_icons

TOTAL_PHASES=8
PHASE_NUM=0
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
SCRIPT_START=0
LAST_STEP_TS=0
SUDO_KEEPALIVE_PID=""

_log_plain() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*" >>"$LOG_FILE"; }
hr() {
  local w
  w=$(tput cols 2>/dev/null || echo 60)
  [[ "$w" =~ ^[0-9]+$ ]] || w=60
  (( w > 68 )) && w=68
  (( w < 40 )) && w=40
  local ch line i
  if [[ "${USE_ASCII:-0}" -eq 1 ]]; then ch='-'; else ch='─'; fi
  line=""
  for (( i=0; i<w; i++ )); do line+="$ch"; done
  printf '%b\n' "${C_DIM}${line}${C_RESET}"
}

progress_bar() {
  local cur="$1" total="$2" width=14
  local filled=$(( cur * width / total ))
  (( filled > width )) && filled=$width
  local empty=$(( width - filled ))
  local bar fill_ch empty_ch
  if [[ "${USE_ASCII:-0}" -eq 1 ]]; then fill_ch="#"; empty_ch="-";
  else fill_ch="█"; empty_ch="░"; fi
  bar=""
  local i
  for (( i=0; i<filled; i++ )); do bar+="$fill_ch"; done
  for (( i=0; i<empty; i++ )); do bar+="$empty_ch"; done
  printf '%s %s/%s' "$bar" "$cur" "$total"
}

_term() {
  # _term STREAM PRINTTF-ARGS... — print to terminal unless QUIET mutes it.
  # STREAM: out|err. QUIET mutes stdout info but never warnings/errors.
  local stream="$1"; shift
  if [[ "$stream" == "out" && "$QUIET" -eq 1 ]]; then return 0; fi
  if [[ "$stream" == "err" ]]; then printf '%b\n' "$@" >&2; else printf '%b\n' "$@"; fi
}

log()  { _term out "${C_BLUE}${I_ARROW}${C_RESET} $*"; _log_plain "[install] $*"; }
say()  { _term out "    $*"; _log_plain "[info] $*"; }
ok()   { PASS_COUNT=$((PASS_COUNT+1)); _term out "  ${C_GREEN}${I_OK}${C_RESET} $*"; _log_plain "[ok] $*"; }
skip() { SKIP_COUNT=$((SKIP_COUNT+1)); PASS_COUNT=$((PASS_COUNT+1)); _term out "  ${C_DIM}${I_SKIP} SKIP${C_RESET} $*"; _log_plain "[skip] $*"; }
dry()  { _term out "  ${C_MAGENTA}${I_DRY}${C_RESET} $*"; _log_plain "[dry-run] $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); _term err "  ${C_YELLOW}${I_WARN} WARN${C_RESET} $*"; _log_plain "[warn] $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); _term err "  ${C_RED}${I_FAIL} FAIL${C_RESET} $*"; _log_plain "[fail] $*"; }
step() {
  local now
  now=$(date +%s)
  if [[ "$PHASE_NUM" -gt 0 && "$LAST_STEP_TS" -gt 0 && "$QUIET" -eq 0 ]]; then
    local prev_elapsed=$(( now - LAST_STEP_TS ))
    printf '%b\n' "${C_DIM}  (previous phase took ${prev_elapsed}s)${C_RESET}"
    _log_plain "[phase-time] phase $PHASE_NUM took ${prev_elapsed}s"
  fi
  PHASE_NUM=$((PHASE_NUM+1))
  LAST_STEP_TS=$now
  local bar
  bar=$(progress_bar "$PHASE_NUM" "$TOTAL_PHASES")
  printf '\n%b\n' "${C_BOLD}${I_STEP} [${PHASE_NUM}/${TOTAL_PHASES}] $*${C_RESET}"
  _term out "${C_DIM}  ${bar}${C_RESET}"
  _log_plain "== phase ${PHASE_NUM}/${TOTAL_PHASES}: $* =="
}
_log_cmd() { printf -- '----- %s $ %s\n' "$(date '+%F %T')" "$*" >>"$LOG_FILE"; }
_log_exit() { printf -- '----- exit code: %s\n' "$1" >>"$LOG_FILE"; }
run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "$*"
  else
    _log_cmd "$*"
    local rc=0
    if [[ "$VERBOSE" -eq 1 ]]; then
      _term out "${C_DIM}  \$ $*${C_RESET}"
      eval "$@" </dev/null 2>&1 | tee -a "$LOG_FILE"
      rc=${PIPESTATUS[0]}
    else
      eval "$@" </dev/null
      rc=$?
    fi
    _log_exit "$rc"
    return "$rc"
  fi
}
# spin MESSAGE CMD... — long ops get a spinner with elapsed time.
# Output goes to the log unless --verbose (then streams via tee).
spin() {
  local message="$1"; shift
  local cmd="$*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "$cmd"
    return 0
  fi
  _log_cmd "$cmd"
  local start_ts end_ts elapsed
  start_ts=$(date +%s)
  if [[ "$VERBOSE" -eq 1 ]]; then
    _term out "  ${C_CYAN}${I_SPIN}${C_RESET} ${message} ${C_DIM}(live output below)${C_RESET}"
    eval "$cmd" </dev/null 2>&1 | tee -a "$LOG_FILE"
    local vst=${PIPESTATUS[0]}
    end_ts=$(date +%s); elapsed=$(( end_ts - start_ts ))
    if [[ "$vst" -eq 0 ]]; then _term out "  ${C_GREEN}${I_OK} done${C_RESET} ${C_DIM}(${elapsed}s)${C_RESET}"; PASS_COUNT=$((PASS_COUNT+1));
    else _term err "  ${C_RED}${I_FAIL} failed${C_RESET} ${C_DIM}(${elapsed}s)${C_RESET}"; FAIL_COUNT=$((FAIL_COUNT+1)); fi
    _log_exit "$vst"
    return "$vst"
  fi
  if [[ ! -t 1 ]]; then
    local plain_st=0
    eval "$cmd" </dev/null >>"$LOG_FILE" 2>&1 || plain_st=$?
    end_ts=$(date +%s); elapsed=$(( end_ts - start_ts ))
    if [[ "$plain_st" -eq 0 ]]; then printf '%b\n' "  ${C_GREEN}${I_OK} done${C_RESET} ${C_DIM}(${elapsed}s) — ${message}${C_RESET}"; PASS_COUNT=$((PASS_COUNT+1)); else printf '%b\n' "  ${C_RED}${I_FAIL} failed${C_RESET} ${C_DIM}(${elapsed}s) — ${message}${C_RESET}"; FAIL_COUNT=$((FAIL_COUNT+1)); fi
    _log_exit "$plain_st"
    return "$plain_st"
  fi
  printf '%b' "  ${C_CYAN}${I_SPIN}${C_RESET} ${message} "
  eval "$cmd" </dev/null >>"$LOG_FILE" 2>&1 &
  local pid=$!
  local frames
  if [[ "${USE_ASCII:-0}" -eq 1 ]]; then frames='|/-\'; else frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'; fi
  local nframes=${#frames} i=0
  local hide_cursor=0
  if [[ -t 1 ]] && tput civis 2>/dev/null; then hide_cursor=1; fi
  while kill -0 "$pid" 2>/dev/null; do
    if [[ "${USE_ASCII:-0}" -eq 1 ]]; then
      printf '\b%c' "${frames:$((i % nframes)):1}"
    else
      printf '\b%s' "${frames:$((i % nframes)):1}"
    fi
    i=$((i+1))
    sleep 0.12
  done
  local st=0
  wait "$pid" || st=$?
  if [[ "$hide_cursor" -eq 1 ]]; then [[ -t 1 ]] && tput cnorm 2>/dev/null || true; fi
  end_ts=$(date +%s); elapsed=$(( end_ts - start_ts ))
  if [[ "$st" -eq 0 ]]; then printf '\b%b\n' "${C_GREEN}${I_OK} done${C_RESET} ${C_DIM}(${elapsed}s)${C_RESET}"; PASS_COUNT=$((PASS_COUNT+1)); else printf '\b%b\n' "${C_RED}${I_FAIL} failed${C_RESET} ${C_DIM}(${elapsed}s)${C_RESET}"; FAIL_COUNT=$((FAIL_COUNT+1)); fi
  _log_exit "$st"
  return "$st"
}

_restore_cursor() { [[ -t 1 ]] && tput cnorm 2>/dev/null || true; }

cleanup_exit() {
  _restore_cursor
  if [[ -n "${SUDO_KEEPALIVE_PID:-}" ]]; then
    kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
  fi
  if [[ -d "${YAY_BUILD_DIR:-}" ]]; then
    rm -rf "$YAY_BUILD_DIR" 2>/dev/null || true
  fi
}

# Ask for sudo once, before any hidden-output step, and keep it alive.
# The keepalive watches the parent script PID so it cannot outlive us.
ensure_sudo() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] && return 0
  if [[ -n "${SUDO_KEEPALIVE_PID:-}" ]]; then return 0; fi
  say "Administrator privileges are required to install packages."
  if ! sudo -v; then
    fail "sudo access required."
    return 1
  fi
  ok "sudo access confirmed"
  ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null || break; sleep 50; done ) &
  SUDO_KEEPALIVE_PID=$!
}

on_err() {
  local line="$1"
  trap - ERR
  _restore_cursor
  printf '%b\n' "${C_RED}${I_FAIL} FAILED at line ${line}${C_RESET}" >&2
  _log_plain "[fatal] line $line"
  say "Last log lines (full log: $LOG_FILE):" >&2
  tail -n 15 "$LOG_FILE" 2>/dev/null | sed 's/^/  | /' >&2 || true
  printf '%b\n' "Fix the issue above, then re-run. Re-running is safe (idempotent)." >&2
  printf '%b\n' "Tip: re-run with ${C_BOLD}--verbose${C_RESET} to see live command output." >&2
  kill "${SUDO_KEEPALIVE_PID:-}" 2>/dev/null || true
  SUDO_KEEPALIVE_PID=""
  exit 1
}
trap 'on_err $LINENO' ERR
trap cleanup_exit EXIT
trap '_restore_cursor; printf "\nInterrupted.\n" >&2; exit 130' INT TERM

is_interactive() { [[ "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 && -t 0 ]]; }

banner() {
  hr
  printf '%b\n' "${C_BOLD}HyprYoru — Arch Hyprland reproducer${C_RESET}"
  printf '%b\n' "${C_DIM}https://github.com/ae-orlando/HyprYoru · single-file, zero-dependency${C_RESET}"
  if [[ "$QUIET" -eq 0 ]]; then
    printf '%b\n' "${C_DIM}Profile: $PROFILE · Phases: $TOTAL_PHASES · Log: $LOG_FILE${C_RESET}"
  fi
  hr
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '%b\n' "${C_MAGENTA}${I_DRY} DRY RUN — no changes will be made${C_RESET}"
  fi
  if [[ "$VERBOSE" -eq 1 ]]; then
    say "Verbose mode: long operations stream live output."
  fi
}

prompt_profile() {
  if [[ "$PROFILE_EXPLICIT" -eq 1 ]]; then return 0; fi
  if ! is_interactive; then return 0; fi
  if [[ "$ONLY_DOTFILES" -eq 1 ]]; then return 0; fi
  hr
  printf '%b\n' "${C_BOLD}1/3 — Installation profile${C_RESET}"
  say "full  = exact source machine  (151 official + 21 AUR, slower, everything)"
  say "core  = bootable Hyprland only (111 official + 5 AUR, faster, no user apps)"
  local ans=""
  while true; do
    read -rp "  Select profile [1] full / [2] core (default: 1): " ans || true
    case "${ans,,}" in
      ""|"1"|"full") PROFILE="full"; break ;;
      "2"|"core") PROFILE="core"; break ;;
      *) printf '%b\n' "  ${C_YELLOW}${I_WARN} WARN${C_RESET} Please enter 1, 2, full, or core." ;;
    esac
  done
  say "Selected profile: $PROFILE"
}

prompt_aur() {
  if [[ "$NO_AUR" -eq 1 ]]; then return 0; fi
  if ! is_interactive; then return 0; fi
  if [[ "$ONLY_DOTFILES" -eq 1 ]]; then return 0; fi
  hr
  printf '%b\n' "${C_BOLD}2/3 — AUR packages${C_RESET}"
  say "Includes cursor/icon themes (Bibata, Kora, Whitesur, Tela),"
  say "waypaper, and user apps (brave, spotify, vscodium, ...)."
  say "Skipping means those themes + waypaper will be missing."
  local ans=""
  while true; do
    read -rp "  Include AUR packages? [Y/n]: " ans || true
    case "$ans" in
      ""|[Yy]|[Yy][Ee][Ss]) break ;;
      [Nn]|[Nn][Oo]) NO_AUR=1; break ;;
      *) printf '%b\n' "  ${C_YELLOW}${I_WARN} WARN${C_RESET} Please answer y or n." ;;
    esac
  done
  if [[ "$NO_AUR" -eq 1 ]]; then say "AUR packages will be skipped."; else say "AUR packages included."; fi
}

confirm_run() {
  if ! is_interactive; then return 0; fi
  hr
  printf '%b\n' "${C_BOLD}3/3 — Confirm install${C_RESET}"
  selected_packages
  local disk_free
  disk_free=$(df -h "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")
  say "Profile:        $PROFILE (${#SEL_OFFICIAL[@]} official + ${#SEL_AUR[@]} AUR)"
  say "Dotfiles:       $DOTFILES_ROOT"
  say "Backup target:  $BACKUP_DIR"
  say "Log file:       $LOG_FILE"
  say "Disk free ($HOME): $disk_free"
  if [[ "$ONLY_DOTFILES" -eq 1 ]]; then
    say "Scope:          dotfiles only (base/packages/services skipped)"
  elif [[ "$NO_AUR" -eq 1 ]]; then
    say "Scope:          system + official packages (AUR skipped)"
  else
    say "Scope:          full system install"
  fi
  say "Phases:         $TOTAL_PHASES (preflight → verify)"
  say "Restore:        cp -a \"$BACKUP_DIR/home/.\" ~/  (if you need to undo)"
  local ans=""
  while true; do
    read -rp "  Proceed with install? [Y/n]: " ans || true
    case "$ans" in
      ""|[Yy]|[Yy][Ee][Ss]) break ;;
      [Nn]|[Nn][Oo]) say "Aborted by user. No changes made."; exit 0 ;;
      *) printf '%b\n' "  ${C_YELLOW}${I_WARN} WARN${C_RESET} Please answer y or n." ;;
    esac
  done
}

format_elapsed() {
  local s="$1"
  if (( s < 60 )); then printf '%ss' "$s";
  else printf '%sm %ss' $(( s / 60 )) $(( s % 60 )); fi
}

final_summary() {
  local end_ts total_elapsed
  end_ts=$(date +%s)
  total_elapsed=$(( end_ts - SCRIPT_START ))
  hr
  printf '%b\n' "${C_BOLD}Done — summary (${TOTAL_PHASES}/${TOTAL_PHASES} phases, $(format_elapsed "$total_elapsed"))${C_RESET}"
  say "Profile:  $PROFILE"
  say "Backup:   $BACKUP_DIR"
  say "Log:      $LOG_FILE"
  if (( SKIP_COUNT > 0 )); then
    printf '%b\n' "  ${C_GREEN}${I_OK} pass: $PASS_COUNT${C_RESET}  ${C_YELLOW}${I_WARN} warnings: $WARN_COUNT${C_RESET}  ${C_RED}${I_FAIL} failures: $FAIL_COUNT${C_RESET}  ${C_DIM}(${SKIP_COUNT} already-ok)${C_RESET}"
  else
    printf '%b\n' "  ${C_GREEN}${I_OK} pass: $PASS_COUNT${C_RESET}  ${C_YELLOW}${I_WARN} warnings: $WARN_COUNT${C_RESET}  ${C_RED}${I_FAIL} failures: $FAIL_COUNT${C_RESET}"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '%b\n' "${C_MAGENTA}${I_DRY} DRY RUN — 0 changes made${C_RESET}"
  else
    say "Next steps:"
    say "  1. Reboot, pick Hyprland in GDM"
    say "  2. SUPER+W wallpaper · SUPER+R bar restart"
    if (( FAIL_COUNT > 0 )); then
      say "Some checks failed — see log: $LOG_FILE"
    fi
  fi
}

usage() {
  printf '%b\n' "${C_BOLD}Usage:${C_RESET} ./install.sh [options]"
  printf '\n%b\n' "${C_BOLD}Options:${C_RESET}"
  printf '  %-22s %s\n' "--profile core|full" "core = bootable minimum (111+5), full = exact machine (151+21) [default: full]"
  printf '  %-22s %s\n' "--only-dotfiles" "skip base/packages/services; link configs + shell + theming"
  printf '  %-22s %s\n' "--no-aur" "skip AUR packages (themes + waypaper missing)"
  printf '  %-22s %s\n' "--dry-run" "print actions without changing anything"
  printf '  %-22s %s\n' "--yes, -y" "non-interactive (passes --noconfirm to pacman/AUR)"
  printf '  %-22s %s\n' "--verbose" "stream long-operation output live (default: spinner + log)"
  printf '  %-22s %s\n' "--quiet" "minimal terminal output (warnings/errors still shown)"
  printf '  %-22s %s\n' "--log-file PATH" "write plain log here [default: ~/.local/state/dotfiles-install/logs/<timestamp>.log]"
  printf '  %-22s %s\n' "--no-color" "disable colors (same as NO_COLOR=1)"
  printf '  %-22s %s\n' "--help, -h" "this help"
  printf '\n%b\n' "${C_BOLD}Profiles:${C_RESET}"
  printf '  %-8s %s\n' "full" "exact source machine — every explicit package (default)"
  printf '  %-8s %s\n' "core" "minimum to boot Hyprland with a working config (no user apps)"
  printf '\n%b\n' "${C_BOLD}Examples:${C_RESET}"
  printf '  %s\n' "./install.sh --dry-run"
  printf '  %s\n' "./install.sh --profile full --yes"
  printf '  %s\n' "./install.sh --profile core --yes"
  printf '  %s\n' "./install.sh --only-dotfiles --yes"
  printf '  %s\n' "./install.sh --no-aur --verbose"
  printf '\n%b\n' "${C_DIM}Interactive (no --yes, no --dry-run): guided menus for profile, AUR set,${C_RESET}"
  printf '%b\n' "${C_DIM}then a confirmation screen. NO_COLOR=1 / NO_EMOJI=1 force plain output.${C_RESET}"
  printf '%b\n' "${C_DIM}Plain log always kept at: $LOG_FILE${C_RESET}"
}

compute_phases() {
  if [[ "$ONLY_DOTFILES" -eq 1 ]]; then TOTAL_PHASES=5; else TOTAL_PHASES=8; fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      [[ -n "${2:-}" ]] || { echo "Missing value for --profile (core|full)" >&2; exit 1; }
      PROFILE="$2"; PROFILE_EXPLICIT=1; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; PROFILE_EXPLICIT=1; shift ;;
    --only-dotfiles) ONLY_DOTFILES=1; shift ;;
    --no-aur) NO_AUR=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    --quiet) QUIET=1; shift ;;
    --log-file)
      [[ -n "${2:-}" ]] || { echo "Missing value for --log-file" >&2; exit 1; }
      LOG_FILE="$2"; LOG_FILE_EXPLICIT=1; shift 2 ;;
    --log-file=*) LOG_FILE="${1#*=}"; LOG_FILE_EXPLICIT=1; shift ;;
    --no-color) NO_COLOR=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 1 ;;
  esac
done
[[ "$PROFILE" == "core" || "$PROFILE" == "full" ]] || { echo "Invalid --profile: $PROFILE (use core|full)" >&2; exit 1; }
if [[ "$VERBOSE" -eq 1 && "$QUIET" -eq 1 ]]; then echo "Cannot combine --verbose and --quiet." >&2; exit 1; fi
setup_colors
setup_icons
compute_phases

PACMAN_FLAGS="--needed"
AUR_FLAGS="--needed"
if [[ "$ASSUME_YES" -eq 1 ]]; then
  PACMAN_FLAGS="$PACMAN_FLAGS --noconfirm"
  AUR_FLAGS="$AUR_FLAGS --noconfirm"
fi

# --------------------------------------------------------------------------
# Package sets (from `pacman -Qqen` / `-Qqm` on source machine, 2026-10-09).
# *-debug packages excluded (debug symbols, never install explicitly).
# tela-icon-theme added: rofi/config.rasi requests icon-theme "Tela" but it
# was missing on source (fallback worked); installing makes it exact.
# Deliberate additions vs source explicit list:
#   base (meta, assumed present), curl (oh-my-zsh bootstrap needs it),
#   playerctl (was dep-of-waybar; binds/whatsong need it directly).
# --------------------------------------------------------------------------

# Official repo — always needed for the config to function.
PACMAN_CORE=(
  base
  hyprland hypridle hyprlock hyprsunset hyprpicker hyprshot hyprshutdown
  xdg-desktop-portal-hyprland xdg-user-dirs
  polkit-gnome qt5-wayland qt6-wayland qt6ct
  waybar swaync rofi awww matugen nwg-look
  adw-gtk-theme gnome-themes-extra gnome-keyring seahorse
  grim slurp wl-clipboard swappy
  pipewire pipewire-alsa pipewire-jack pipewire-pulse wireplumber pavucontrol
  bluez bluez-utils bluetui networkmanager network-manager-applet modemmanager modem-manager-gui
  power-profiles-daemon brightnessctl playerctl
  kitty zsh zsh-autosuggestions zsh-syntax-highlighting zsh-completions
  fastfetch btop eza fzf fd bat yazi neovim tmux figlet
  noto-fonts noto-fonts-emoji ttf-nerd-fonts-symbols
  ttf-jetbrains-mono ttf-jetbrains-mono-nerd ttf-go-nerd ttf-0xproto-nerd
  ttf-adwaitamono-nerd ttf-cascadia-code-nerd ttf-cousine-nerd ttf-d2coding-nerd
  ttf-firacode-nerd ttf-iawriter-nerd ttf-ibmplex-mono-nerd ttf-iosevka-nerd
  ttf-lilex-nerd ttf-martian-mono-nerd ttf-victor-mono-nerd
  otf-commit-mono-nerd otf-geist-mono-nerd
  gdm gvfs gvfs-mtp gvfs-smb
  pacman-contrib reflector man-db sudo git curl base-devel
  imagemagick imv
  mpc mpv
  nautilus
  chromium
  direnv github-cli
  fnm bun pnpm uv rust cmake ninja
  7zip zip unrar cabextract atool
  bc tree
)

# Official repo — user apps / hardware / extras (source machine had them).
PACMAN_EXTRA=(
  firefox nemo evince okular ristretto vlc obs-studio
  obsidian easyeffects calf lsp-plugins-lv2 mda.lv2 x42-plugins-lv2 zam-plugins-lv2
  docker docker-buildx docker-compose valkey postgresql
  linux linux-firmware btrfs-progs grub efibootmgr os-prober mtools fuse2
  intel-media-driver libva-utils vulkan-intel
  thermald tlp ufw dnsmasq
  redshift
  netstat-nat usb_modeswitch
  archlinux-wallpaper
  vim
  opencode
)

# AUR — needed for config (cursors/icons/wallpaper helper).
AUR_CORE=(
  bibata-cursor-theme-bin
  kora-icon-theme
  whitesur-icon-theme
  tela-icon-theme
  waypaper
)

# AUR — user apps from source machine.
AUR_EXTRA=(
  brave-bin spotify vscodium-bin
  packettracer
  pgadmin4-desktop-bin pgadmin4-server-bin
  ani-cli keep nmrs lazysql pspg
  python-imageio-ffmpeg python-screeninfo python-terminaltables3
  paru yay
)

SYSTEM_SERVICES=(
  gdm.service
  NetworkManager.service NetworkManager-dispatcher.service NetworkManager-wait-online.service
  bluetooth.service
  ModemManager.service
  power-profiles-daemon.service
  thermald.service
  ufw.service
  postgresql.service
  reflector.timer
  wwan-enable.service
)
USER_SERVICES=(
  pipewire.socket pipewire-pulse.socket wireplumber.service
  gnome-keyring-daemon.socket p11-kit-server.socket
  xdg-user-dirs.service
)

# Symlink map: target -> source (relative to $HOME / dotfiles root).
# gtk bookmarks are NOT linked (gitignored user state — generated instead).
LINK_MAP=(
  ".config/hypr:hyprland"
  ".config/btop:btop"
  ".config/kitty:kitty"
  ".config/matugen:matugen"
  ".config/qt6ct:qt6ct"
  ".config/rofi:rofi"
  ".config/swaync:swaync"
  ".config/waybar:waybar"
  ".config/waypaper:waypaper"
  ".config/zsh:zsh"
  ".config/fastfetch:fastfetch"
  ".config/gtk-3.0:gtk-setting/gtk-3.0"
  ".config/gtk-4.0:gtk-setting/gtk-4.0"
)

# --------------------------------------------------------------------------
# 0. Preflight
# --------------------------------------------------------------------------
phase_preflight() {
  step "preflight (profile=$PROFILE only-dotfiles=$ONLY_DOTFILES dry-run=$DRY_RUN)"
  if [[ "$(id -u)" -eq 0 ]]; then
    fail "Do not run as root; run as your user (sudo is used internally)."
    exit 1
  fi
  ok "Running as user: $USER (not root)"
  if [[ ! -f /etc/arch-release ]]; then
    fail "Arch Linux only (no /etc/arch-release). Aborting."
    exit 1
  fi
  ok "Arch Linux detected"
  mkdir -p "$(dirname "$LOG_FILE")"
  log "Dotfiles root: $DOTFILES_ROOT"
  local missing=0
  for d in hyprland waybar rofi kitty matugen swaync zsh waypaper btop fastfetch gtk-setting qt6ct; do
    if [[ ! -d "$DOTFILES_ROOT/$d" ]]; then fail "Missing dir in repo: $d"; missing=1; fi
  done
  [[ "$missing" -eq 1 ]] && exit 1
  ok "Repo layout OK (12 config dirs present)"
  # Environment snapshot.
  local disk_free mem_total net_status
  disk_free=$(df -h "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")
  mem_total=$(free -h 2>/dev/null | awk '/^Mem:/ {print $2}' || echo "unknown")
  if command -v curl >/dev/null 2>&1 && curl -Is --max-time 8 https://archlinux.org >/dev/null 2>&1; then net_status="reachable (archlinux.org)";
  elif ping -c1 -W3 archlinux.org >/dev/null 2>&1; then net_status="reachable (ping)";
  else net_status="UNREACHABLE — pacman/AUR/oh-my-zsh will fail"; fi
  say "Disk free ($HOME): $disk_free · Memory: $mem_total · Network: $net_status"
  if [[ "$net_status" == UNREACHABLE* && "$ONLY_DOTFILES" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
    warn "No network detected; package phases are likely to fail."
  fi
  # Backup preview: count real (non-symlink) entries we would move aside.
  local backup_count=0
  for entry in "${LINK_MAP[@]}"; do
    target="$HOME/${entry%%:*}"
    if [[ -e "$target" && ! -L "$target" ]]; then backup_count=$((backup_count+1)); fi
  done
  [[ -f "$HOME/.zshenv" ]] && backup_count=$((backup_count+1))
  # Backup anything we are about to replace, preserving paths relative
  # to $HOME (e.g. $BACKUP_DIR/home/.config/hypr) so names cannot collide.
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "mkdir -p $BACKUP_DIR (would back up $backup_count path(s): .config entries + .zshenv)"
  else
    mkdir -p "$BACKUP_DIR"
    for entry in "${LINK_MAP[@]}"; do
      target="$HOME/${entry%%:*}"
      if [[ -e "$target" && ! -L "$target" ]]; then
        log "Backing up real dir/file $target"
        dest="$BACKUP_DIR/home/${entry%%:*}"
        mkdir -p "$(dirname "$dest")"
        cp -a "$target" "$dest" 2>/dev/null || true
      fi
    done
    if [[ -f "$HOME/.zshenv" ]]; then
      mkdir -p "$BACKUP_DIR/home"
      cp -a "$HOME/.zshenv" "$BACKUP_DIR/home/.zshenv" 2>/dev/null || true
    fi
    ok "Backup dir ready: $BACKUP_DIR ($backup_count path(s) preserved)"
    say "Restore if needed: cp -a \"$BACKUP_DIR/home/.\" ~/ (then re-link)"
  fi
  if [[ "$ONLY_DOTFILES" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
    skip "sudo check (only-dotfiles or dry-run needs no privilege)"
  else
    ensure_sudo || exit 1
  fi
  # Warn on machine-specific settings carried over verbatim.
  warn "monitors.lua hardcodes eDP-1 1920x1080@60.02; empty-output fallback covers other monitors."
  warn "Desktop entries / mime assume chromium, evince, ristretto installed (core profile does)."
}

# --------------------------------------------------------------------------
# 1. Base system (pacman conf, mirrors, full upgrade, AUR helper)
# --------------------------------------------------------------------------
ensure_pacman_conf() {
  log "Ensuring pacman.conf: Color + ParallelDownloads=5 (multilib left disabled, as on source)"
  if grep -q "^#Color" /etc/pacman.conf; then
    run "sudo sed -i 's/^#Color/Color/' /etc/pacman.conf"
  fi
  if grep -q "^#ParallelDownloads" /etc/pacman.conf; then
    run "sudo sed -i 's/^#ParallelDownloads.*/ParallelDownloads = 5/' /etc/pacman.conf"
  elif ! grep -q "^ParallelDownloads" /etc/pacman.conf; then
    run "sudo sh -c 'printf \"ParallelDownloads = 5\\n\" >> /etc/pacman.conf'"
  fi
}

ensure_reflector() {
  # Source used reflector with --save/--protocol https/--latest 5/--sort age.
  if command -v reflector >/dev/null 2>&1; then
    log "Refreshing mirrors with reflector (may take a minute)"
    spin "Refreshing mirrors" "sudo reflector --protocol https --latest 5 --sort age --save /etc/pacman.d/mirrorlist || true"
  else
    warn "reflector not installed yet; mirrors left as-is (reflector installed in step 2)"
  fi
}

ensure_aur_helper() {
  if command -v yay >/dev/null 2>&1; then
    skip "AUR helper yay already present"
    return
  fi
  if command -v paru >/dev/null 2>&1; then
    skip "AUR helper paru already present (yay missing — will use paru)"
    return
  fi
  log "Bootstrapping yay-bin from AUR"
  spin "Installing build tools" "sudo pacman -S --needed --noconfirm base-devel git"
  spin "Cloning yay-bin" "rm -rf \"$YAY_BUILD_DIR\" && git clone https://aur.archlinux.org/yay-bin.git \"$YAY_BUILD_DIR\""
  spin "Building yay-bin" "sh -c 'cd \"$YAY_BUILD_DIR\" && makepkg -si --noconfirm'"
}

aur_cmd() {
  if command -v yay >/dev/null 2>&1; then echo "yay"; else echo "paru"; fi
}

phase_base() {
  step "base system"
  ensure_pacman_conf
  ensure_reflector
  log "Full system upgrade (pacman -Syu)"
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    spin "Full system upgrade (pacman -Syu)" "sudo pacman -Syu --noconfirm"
  else
    spin "Full system upgrade (pacman -Syu)" "sudo pacman -Syu"
  fi
  ensure_aur_helper
}

# --------------------------------------------------------------------------
# 2. Packages
# --------------------------------------------------------------------------
selected_packages() {
  SEL_OFFICIAL=("${PACMAN_CORE[@]}")
  SEL_AUR=("${AUR_CORE[@]}")
  if [[ "$PROFILE" == "full" ]]; then
    SEL_OFFICIAL+=("${PACMAN_EXTRA[@]}")
    SEL_AUR+=("${AUR_EXTRA[@]}")
  fi
}

# Print the subset of "$@" not installed locally (one per line).
# Official packages are queried via pacman -Q; AUR packages via the helper's -Q.
missing_official() {
  local p
  for p in "$@"; do
    pacman -Qq "$p" >/dev/null 2>&1 || printf '%s\n' "$p"
  done
}

missing_aur() {
  local helper="$1"; shift
  local p
  for p in "$@"; do
    "$helper" -Qq "$p" >/dev/null 2>&1 || printf '%s\n' "$p"
  done
}

phase_packages() {
  step "packages (profile=$PROFILE)"
  selected_packages
  local official=("${SEL_OFFICIAL[@]}")
  local aur=("${SEL_AUR[@]}")
  say "Already-installed packages are skipped automatically."
  local official_todo=()
  if (( ${#official[@]} > 0 )); then
    mapfile -t official_todo < <(missing_official "${official[@]}")
  fi
  local official_skipped=$(( ${#official[@]} - ${#official_todo[@]} ))
  if (( official_skipped > 0 )); then
    say "Official: $official_skipped of ${#official[@]} already installed, skipping"
  fi
  if (( ${#official_todo[@]} == 0 )); then
    skip "official packages (all ${#official[@]} present)"
  else
    log "Installing ${#official_todo[@]} official packages (${official_skipped} already present)"
    # shellcheck disable=SC2086
    if ! spin "Installing ${#official_todo[@]} official packages" "sudo pacman -S $PACMAN_FLAGS ${official_todo[*]}"; then
      warn "Batch install failed; retrying per package to isolate failures"
      local failed_official=() p
      for p in "${official_todo[@]}"; do
        # shellcheck disable=SC2086
        if spin "Installing $p" "sudo pacman -S $PACMAN_FLAGS $p"; then :; else failed_official+=("$p"); fi
      done
      if (( ${#failed_official[@]} > 0 )); then
        warn "Official package(s) failed (${#failed_official[@]}): ${failed_official[*]} (continuing)"
      else
        ok "All official packages installed on retry"
      fi
    fi
  fi
  if [[ "$NO_AUR" -eq 1 ]]; then
    warn "Skipping AUR (--no-aur). Cursor/icon themes + waypaper will be missing."
    return
  fi
  local helper
  helper="$(aur_cmd)"
  if ! command -v "$helper" >/dev/null 2>&1; then
    warn "No AUR helper found ($helper missing); skipping ${#aur[@]} AUR packages"
    return
  fi
  local aur_todo=()
  if (( ${#aur[@]} > 0 )); then
    mapfile -t aur_todo < <(missing_aur "$helper" "${aur[@]}")
  fi
  local aur_skipped=$(( ${#aur[@]} - ${#aur_todo[@]} ))
  if (( aur_skipped > 0 )); then
    say "AUR: $aur_skipped of ${#aur[@]} already installed, skipping"
  fi
  if (( ${#aur_todo[@]} == 0 )); then
    skip "AUR packages (all ${#aur[@]} present)"
  else
    log "Installing ${#aur_todo[@]} AUR packages via $helper (${aur_skipped} already present)"
    # shellcheck disable=SC2086
    if ! spin "Installing ${#aur_todo[@]} AUR packages via $helper" "$helper -S $AUR_FLAGS ${aur_todo[*]}"; then
      warn "Batch AUR install failed; retrying per package to isolate failures"
      local failed_aur=() p
      for p in "${aur_todo[@]}"; do
        # shellcheck disable=SC2086
        if spin "Installing $p via $helper" "$helper -S $AUR_FLAGS $p"; then :; else failed_aur+=("$p"); fi
      done
      if (( ${#failed_aur[@]} > 0 )); then
        warn "AUR package(s) failed (${#failed_aur[@]}): ${failed_aur[*]} (continuing)"
      else
        ok "All AUR packages installed on retry"
      fi
    fi
  fi
}

# --------------------------------------------------------------------------
# 3. Services (incl. custom wwan-enable.service found on source machine)
# --------------------------------------------------------------------------
WWAN_UNIT_PATH="/etc/systemd/system/wwan-enable.service"
write_wwan_unit() {
  # Verbatim copy of the source machine's custom unit (Fibocom WWAN modem).
  if [[ -f "$WWAN_UNIT_PATH" ]] && grep -q "Fibocom WWAN Modem" "$WWAN_UNIT_PATH" 2>/dev/null; then
    skip "wwan-enable.service already present"
    return
  fi
  log "Installing wwan-enable.service (custom unit from source machine)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "write $WWAN_UNIT_PATH"
    return
  fi
  sudo tee "$WWAN_UNIT_PATH" >/dev/null <<'EOF'
[Unit]
Description=Auto-enable Fibocom WWAN Modem
After=ModemManager.service NetworkManager.service
Wants=ModemManager.service

[Service]
Type=oneshot
ExecStartPre=/usr/bin/rfkill unblock wwan
ExecStart=/bin/sh -c 'sleep 3; MM_ID=$(mmcli -L | grep -oP "Modem/\K[0-9]+"); if [ -n "$MM_ID" ]; then mmcli -m "$MM_ID" -e; fi'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target sleep.target
EOF
}

phase_services() {
  step "services"
  write_wwan_unit
  run "sudo systemctl daemon-reload"
  for svc in "${SYSTEM_SERVICES[@]}"; do
    # tlp is installed but was DISABLED on source (conflicts with power-profiles-daemon).
    if [[ "$svc" == "tlp.service" ]]; then continue; fi
    if systemctl list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -x "$svc" >/dev/null; then
      run "sudo systemctl enable $svc"
    else
      warn "Unit not found, skipping enable: $svc"
    fi
  done
  # Source had tlp installed-but-disabled; enforce that to avoid power-profile fights.
  if systemctl list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -x "tlp.service" >/dev/null; then
    run "sudo systemctl disable tlp.service || true"
  fi
  for svc in "${USER_SERVICES[@]}"; do
    run "systemctl --user enable $svc || true"
  done
  warn "postgresql.service enabled but not initialized here — run 'sudo -iu postgres initdb -D /var/lib/postgres/data' if needed."
  warn "ufw.service enabled but no rules set here — configure manually (e.g. 'sudo ufw enable')."
}

# --------------------------------------------------------------------------
# 4. Dotfiles: symlinks, zshenv, perms, dirs, wallpapers, gtk/mime/gsettings
# --------------------------------------------------------------------------
link_one() {
  local target="$HOME/$1" src="$DOTFILES_ROOT/$2"
  if [[ -L "$target" && "$(readlink "$target")" == "$src" ]]; then
    skip "Link OK: $target"
    return
  fi
  if [[ -e "$target" && ! -L "$target" ]]; then
    log "Moving real $target aside (already backed up)"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      mv "$target" "$target.pre-dotfiles-$(date +%s)" || true
    fi
  fi
  log "Linking $target -> $src"
  run "ln -sfn \"$src\" \"$target\""
}

phase_dotfiles() {
  step "dotfiles"
  run "mkdir -p \"$HOME/.config\""
  for entry in "${LINK_MAP[@]}"; do
    link_one "${entry%%:*}" "${entry#*:}"
  done
  # ~/.zshenv must exist BEFORE first zsh start so ZDOTDIR resolves.
  log "Writing ~/.zshenv (ZDOTDIR)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry 'write $HOME/.zshenv: export ZDOTDIR="$HOME/.config/zsh"'
  else
    printf 'export ZDOTDIR="$HOME/.config/zsh"\n' >"$HOME/.zshenv"
  fi
  # Executable bits: repo has 644 on two rofi launchers; binds.lua + swaync
  # invoke them directly, so force +x (fresh clones preserve 644 otherwise).
  log "Fixing executable bits on scripts"
  run "chmod +x \"$DOTFILES_ROOT/hyprland/scripts/\"*.sh \"$DOTFILES_ROOT/hyprland/whatsong.sh\""
  run "chmod +x \"$DOTFILES_ROOT/waybar/scripts/\"*.sh"
  run "chmod +x \"$DOTFILES_ROOT/swaync/scripts/\"*.sh"
  run "chmod +x \"$DOTFILES_ROOT/rofi/launchers/\"*.sh \"$DOTFILES_ROOT/rofi/launchers/type-6/\"*.sh \"$DOTFILES_ROOT/rofi/launchers/rofi-bluetooth\""
  # Runtime dirs (matugen/set-wall.sh + waybar + swaync + qt6ct expect them).
  run "mkdir -p \"$HOME/Pictures/wallpapers\" \"$HOME/Pictures/Screenshots\""
  run "mkdir -p \"$HOME/.cache/matugen\" \"$HOME/.cache/hyprlock\" \"\${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-thumbs\""
  run "mkdir -p \"$HOME/.config/qt6ct/colors\" \"$HOME/.local/bin\" \"$HOME/.local/share/fonts\""
  # Seed wallpapers without overwriting the user's 229-file library.
  log "Seeding ~/Pictures/wallpapers from repo (no overwrite)"
  run "cp -n \"$DOTFILES_ROOT/hyprland/wallpapers/\"* \"$HOME/Pictures/wallpapers/\" 2>/dev/null || true"
  # Waypaper runtime state is gitignored; seed it from the example on fresh clones.
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry 'ensure ~/.config/waypaper/config.ini from config.ini.example (no overwrite)'
  elif [[ ! -f "$HOME/.config/waypaper/config.ini" && -f "$DOTFILES_ROOT/waypaper/config.ini.example" ]]; then
    log "Seeding waypaper/config.ini from example (no overwrite)"
    cp -n "$DOTFILES_ROOT/waypaper/config.ini.example" "$HOME/.config/waypaper/config.ini" 2>/dev/null || true
  else
    skip "waypaper/config.ini already present"
  fi
  # Matugen output dirs that would otherwise vanish on fresh clones
  # (their only tracked content was the now-gitignored generated file).
  run "mkdir -p \"$HOME/.config/swaync/matugen\" \"$HOME/.config/matugen/themes\" \"$HOME/.config/zsh/generated\" \"$HOME/.config/btop/themes\" \"$HOME/.config/qt6ct/colors\" \"$HOME/.config/opencode/themes\""
  # XDG dirs + PROJECTS line (source had XDG_PROJECTS_DIR="$HOME/").
  run "xdg-user-dirs-update || true"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if ! grep -q "XDG_PROJECTS_DIR" "$HOME/.config/user-dirs.dirs" 2>/dev/null; then
      echo 'XDG_PROJECTS_DIR="$HOME/"' >>"$HOME/.config/user-dirs.dirs"
    else
      skip "XDG_PROJECTS_DIR already set"
    fi
  else
    dry 'ensure XDG_PROJECTS_DIR in ~/.config/user-dirs.dirs'
  fi
  # GTK bookmarks (gitignored user state — regenerate the 5 defaults).
  log "Writing gtk-3.0/bookmarks"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "write bookmarks (Documents Music Pictures Videos Downloads)"
  else
    cat >"$HOME/.config/gtk-3.0/bookmarks" <<'EOF'
file:///home/ORLANDO_PLACEHOLDER/Documents
file:///home/ORLANDO_PLACEHOLDER/Music
file:///home/ORLANDO_PLACEHOLDER/Pictures
file:///home/ORLANDO_PLACEHOLDER/Videos
file:///home/ORLANDO_PLACEHOLDER/Downloads
EOF
    sed -i "s|ORLANDO_PLACEHOLDER|$USER|g" "$HOME/.config/gtk-3.0/bookmarks"
  fi
  # mimeapps.list — verbatim from source (chromium/evince/ristretto/packettracer).
  log "Writing ~/.config/mimeapps.list"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "write mimeapps.list"
  else
    cat >"$HOME/.config/mimeapps.list" <<'EOF'
[Default Applications]
# Browser / schemes
text/html=chromium.desktop
x-scheme-handler/about=chromium.desktop
x-scheme-handler/http=chromium.desktop
x-scheme-handler/https=chromium.desktop
x-scheme-handler/unknown=chromium.desktop

# Cisco Packet Tracer
application/x-pka=CiscoPacketTracer-9.0.1.desktop
application/x-pkt=CiscoPacketTracer-9.0.1.desktop
application/x-pkz=CiscoPacketTracer-9.0.1.desktop
application/x-pksz=CiscoPacketTracer-9.0.1.desktop
x-scheme-handler/pttp=CiscoPacketTracerPtsa-9.0.1.desktop

# Documents - Evince
application/pdf=org.gnome.Evince.desktop
application/postscript=org.gnome.Evince.desktop
application/x-bzpdf=org.gnome.Evince.desktop
application/x-gzpdf=org.gnome.Evince.desktop
application/x-xzpdf=org.gnome.Evince.desktop

# Images - Ristretto
image/bmp=org.xfce.ristretto.desktop
image/gif=org.xfce.ristretto.desktop
image/jpeg=org.xfce.ristretto.desktop
image/png=org.xfce.ristretto.desktop
image/svg+xml=org.xfce.ristretto.desktop
image/tiff=org.xfce.ristretto.desktop
image/webp=org.xfce.ristretto.desktop
image/x-pixmap=org.xfce.ristretto.desktop
image/x-xpixmap=org.xfce.ristretto.desktop
EOF
  fi
  # gsettings (matches gtk-setting/*/settings.ini + live gsettings).
  if command -v gsettings >/dev/null 2>&1; then
    run "gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark' || true"
    run "gsettings set org.gnome.desktop.interface icon-theme 'kora-pgrey' || true"
    run "gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Classic' || true"
    run "gsettings set org.gnome.desktop.interface font-name 'Adwaita Sans Medium 11' || true"
  else
    warn "gsettings not found; GTK theme live-applied only via settings.ini"
  fi
  spin "Rebuilding font cache" "fc-cache -f >/dev/null 2>&1 || true"
  warn "rofi type-6/style-9 references ~/.config/rofi/images/i.jpg which does not exist (blank imagebox, harmless)."
  warn "waypaper stylesheet ~/.config/waypaper/style.css does not exist upstream-side; Waypaper uses its default (harmless)."
}

# --------------------------------------------------------------------------
# 5. Shell: oh-my-zsh + powerlevel10k + default shell
# --------------------------------------------------------------------------
phase_shell() {
  step "shell"
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    log "Installing oh-my-zsh (unattended)"
    spin "Installing oh-my-zsh" "sh -c \"\$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\" \"\" --unattended"
  else
    skip "oh-my-zsh already present"
  fi
  local p10k_dir="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k"
  if [[ ! -d "$p10k_dir" ]]; then
    log "Installing powerlevel10k"
    spin "Installing powerlevel10k" "git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \"$p10k_dir\""
  else
    skip "powerlevel10k already present"
  fi
  if [[ "$SHELL" != "/usr/bin/zsh" && "$SHELL" != "/bin/zsh" ]]; then
    log "Setting default shell to zsh (needs password)"
    run "chsh -s /usr/bin/zsh || chsh -s /bin/zsh"
  else
    skip "default shell already zsh"
  fi
  run "zsh -n \"\$HOME/.config/zsh/.zshrc\" && echo 'zshrc syntax OK' || echo 'zshrc check skipped/failed'"
}

# --------------------------------------------------------------------------
# 6. Theming: one matugen run regenerates all 12 outputs + wallpaper
# --------------------------------------------------------------------------
phase_theming() {
  step "theming (matugen)"
  # Generated palette files are gitignored artifacts (see .gitignore).
  # They are rebuilt here on every install and on every login via
  # hyprland autostart -> set-wall.sh, so wallpaper changes never dirty git.
  local wall=""
  if [[ -f "$HOME/Pictures/wallpapers/mystical-night-in-town.jpg" ]]; then
    wall="$HOME/Pictures/wallpapers/mystical-night-in-town.jpg"
  elif [[ -f "$HOME/.config/hypr/wallpapers/anime3.png" ]]; then
    wall="$HOME/.config/hypr/wallpapers/anime3.png"
  fi
  if [[ -z "$wall" ]]; then
    warn "No wallpaper found; skipping matugen (run ~/.config/hypr/scripts/set-wall.sh <wall> later)"
    return
  fi
  if ! command -v matugen >/dev/null 2>&1; then
    fail "matugen not installed; palette files (gitignored) cannot be generated. Install matugen, then run: ~/.config/hypr/scripts/set-wall.sh $wall"
    return
  fi
  # Output dirs for gitignored artifacts (empty on fresh clones).
  run "mkdir -p \"$HOME/.config/swaync/matugen\" \"$HOME/.config/matugen/themes\" \"$HOME/.config/zsh/generated\" \"$HOME/.config/btop/themes\" \"$HOME/.config/qt6ct/colors\" \"$HOME/.config/opencode/themes\""
  log "Generating palette from $wall"
  spin "Generating palette (matugen)" "matugen image \"$wall\" --mode dark --type scheme-tonal-spot --prefer closest-to-fallback || true"
}

# --------------------------------------------------------------------------
# 7. Verify (read-only; never fails the install, just reports)
# --------------------------------------------------------------------------
vpass() { PASS_COUNT=$((PASS_COUNT+1)); printf '%b\n' "  ${C_GREEN}${I_OK} PASS${C_RESET}  $*"; _log_plain "[verify-pass] $*"; }
vfail() { FAIL_COUNT=$((FAIL_COUNT+1)); printf '%b\n' "  ${C_RED}${I_FAIL} FAIL${C_RESET}  $*"; _log_plain "[verify-fail] $*"; }
vwarn() { WARN_COUNT=$((WARN_COUNT+1)); printf '%b\n' "  ${C_YELLOW}${I_WARN} WARN${C_RESET}  $*"; _log_plain "[verify-warn] $*"; }

check_bin() {
  if command -v "$1" >/dev/null 2>&1; then
    vpass "binary $1"
  else
    vfail "binary missing: $1"
  fi
}

phase_verify() {
  step "verify"
  say "Binaries referenced by binds/autostart/waybar/swaync:"
  for b in kitty nautilus chromium spotify rofi hyprctl hyprlock hypridle hyprsunset \
    waybar swaync swaync-client nm-applet polkit-gnome-authentication-agent-1 awww-daemon \
    grim slurp wl-copy playerctl wpctl brightnessctl waypaper matugen magick \
    pavucontrol bluetoothctl nmcli checkupdates; do
    if [[ "$b" == "polkit-gnome-authentication-agent-1" ]]; then
      if [[ -x /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 ]]; then vpass "$b"; else vfail "$b"; fi
    elif [[ "$b" == "awww-daemon" ]]; then
      if command -v awww >/dev/null 2>&1; then vpass "awww (+daemon)"; else vfail "awww"; fi
    else
      check_bin "$b"
    fi
  done
  say "Symlinks:"
  for entry in "${LINK_MAP[@]}"; do
    target="$HOME/${entry%%:*}"
    if [[ -L "$target" ]]; then vpass "link $target"; else vfail "not a symlink: $target"; fi
  done
  if [[ -f "$HOME/.zshenv" ]]; then vpass "~/.zshenv"; else vfail "~/.zshenv"; fi
  say "Configs:"
  if [[ -f "$HOME/.config/hypr/hyprland.lua" ]]; then vpass "hyprland.lua"; else vfail "hyprland.lua"; fi
  if [[ -f "$HOME/.config/waybar/config.jsonc" ]]; then vpass "waybar config.jsonc"; else vfail "waybar config"; fi
  if [[ -f "$HOME/.config/matugen/config.toml" ]]; then vpass "matugen config"; else vfail "matugen config"; fi
  if command -v zsh >/dev/null 2>&1 && zsh -n "$HOME/.config/zsh/.zshrc" 2>/dev/null; then vpass "zshrc syntax"; else vwarn "zshrc syntax unchecked"; fi
  if command -v fc-list >/dev/null 2>&1 && fc-list | grep -qi "JetBrainsMono Nerd"; then vpass "JetBrains Nerd font"; else vwarn "JetBrains Nerd font not found"; fi
  if fc-list 2>/dev/null | grep -qi "GoMono Nerd"; then vpass "GoMono Nerd font"; else vwarn "GoMono Nerd font not found (hyprlock labels)"; fi
  if fc-list 2>/dev/null | grep -qi "MartianMono Nerd"; then vpass "MartianMono Nerd font"; else vwarn "MartianMono Nerd font not found (yoru rofi theme)"; fi
  say "Services (enabled?):"
  for svc in gdm.service NetworkManager.service bluetooth.service power-profiles-daemon.service reflector.timer; do
    if systemctl is-enabled "$svc" 2>/dev/null | grep -q "enabled"; then vpass "$svc enabled"; else vwarn "$svc not enabled"; fi
  done
}

prune_logs() {
  [[ -d "$LOG_DIR_DEFAULT" ]] || return 0
  ls -1 "$LOG_DIR_DEFAULT"/install-*.log 2>/dev/null | sort -r | tail -n +$((LOG_KEEP + 1)) | xargs -r rm -f --
}

main() {
  SCRIPT_START=$(date +%s)
  LAST_STEP_TS=0
  mkdir -p "$(dirname "$LOG_FILE")"
  : >"$LOG_FILE" || true
  if [[ "$LOG_FILE_EXPLICIT" -eq 0 ]]; then prune_logs; fi
  _log_plain "[start] profile=$PROFILE only-dotfiles=$ONLY_DOTFILES no-aur=$NO_AUR dry-run=$DRY_RUN verbose=$VERBOSE quiet=$QUIET log=$LOG_FILE"
  banner
  prompt_profile
  prompt_aur
  confirm_run
  log "=== dotfiles install start: profile=$PROFILE ==="
  phase_preflight
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    phase_base
    phase_packages
    phase_services
  else
    log "Skipping base/packages/services (--only-dotfiles)"
  fi
  phase_dotfiles
  phase_shell
  phase_theming
  phase_verify
  final_summary
}

main "$@"
