#!/usr/bin/env bash
# HyprYoru desktop installer for an existing Arch Linux installation.
# Package intent lives in packages/*.txt; presentation lives in lib/install-ui.sh.
# --dry-run and --check never initialize logs, locks, backups, or system changes.
set -Eeuo pipefail

DOTFILES_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-install"
RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
LOG_DIR_DEFAULT="$STATE_ROOT/logs"
LOG_FILE="$LOG_DIR_DEFAULT/install-$RUN_ID.log"
LOG_FILE_EXPLICIT=0
LOG_ENABLED=0
LOG_KEEP=10
BACKUP_DIR="$STATE_ROOT/backups/$RUN_ID"
BACKUP_READY=0
LOCK_FILE="${XDG_RUNTIME_DIR:-$STATE_ROOT}/hypryoru-install.lock"
DISPLAY_MANAGER_LINK='/etc/systemd/system/display-manager.service'
WWAN_UNIT_PATH='/etc/systemd/system/wwan-enable.service'

PROFILE=core
PROFILE_EXPLICIT=0
ONLY_DOTFILES=0
LINK_ONLY=0
CHECK_ONLY=0
NO_AUR=0
DRY_RUN=0
ASSUME_YES=0
VERBOSE=0
QUIET=0
WITH_GDM=0
WITH_WWAN=0
CHANGE_SHELL=0
SET_DEFAULTS=0
WITH_SHELL=1
UI_MODE=auto
UI_BACKEND=plain
UI_SESSION=0
SCOPE_EXPLICIT=0
HELP=0

TOTAL_PHASES=8
PHASE_NUM=0
COMPLETED_PHASES=0
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
SCRIPT_START=0
LAST_STEP_TS=0
SUDO_KEEPALIVE_PID=''
ACTIVE_PID=''
AUR_HELPER=''
NEW_TEMP=''
TEMP_FILES=()
TEMP_DIRS=()
PACMAN_CORE=()
PACMAN_SHELL=()
PACMAN_EXTRA=()
AUR_CORE=()
AUR_EXTRA=()
SEL_OFFICIAL=()
SEL_AUR=()
PACMAN_FLAGS=(--needed)
CONFIRM_FLAGS=()
MISSING_PACKAGES=()
FAILED_PACKAGES=()
SCRIPT_PATHS=()
declare -A PRESERVED_FILES=()

# shellcheck source=lib/install-ui.sh
source "$DOTFILES_ROOT/lib/install-ui.sh"

# target relative to HOME : source relative to the repository.
# Developer-tool configs belong to the separate tools repository.
LINK_MAP=(
  '.config/hypr:hyprland'
  '.config/btop:btop'
  '.config/kitty:kitty'
  '.config/matugen:matugen'
  '.config/qt6ct:qt6ct'
  '.config/rofi:rofi'
  '.config/swaync:swaync'
  '.config/waybar:waybar'
  '.config/waypaper:waypaper'
  '.config/zsh:zsh'
  '.config/fastfetch:fastfetch'
  '.config/gtk-3.0:gtk-setting/gtk-3.0'
  '.config/gtk-4.0:gtk-setting/gtk-4.0'
  '.config/spicetify/Themes/matugen:spicetify/Themes/matugen'
)
SYSTEM_SERVICES=()
USER_SERVICES=(pipewire.socket pipewire-pulse.socket wireplumber.service gnome-keyring-daemon.socket)

# shellcheck source=lib/install-plan.sh
source "$DOTFILES_ROOT/lib/install-plan.sh"
# shellcheck source=lib/gum-runtime.sh
source "$DOTFILES_ROOT/lib/gum-runtime.sh"
# shellcheck source=lib/install-wizard.sh
source "$DOTFILES_ROOT/lib/install-wizard.sh"

usage() {
  cat <<'EOF'
HyprYoru / Arch desktop installer

Usage: ./install.sh [options]

Scope
  --profile core|full   Desktop + configured shell, or extra apps/dev tools [core]
  --only-dotfiles       Skip system packages/services; set up configs, shell, palette
  --link-only           Link configs + set ZDOTDIR; no setup downloads or services
  --no-aur              Skip AUR packages AND helper bootstrap
  --no-shell            Skip the Zsh package bundle, config, frameworks, and shell palette
  --with-gdm            Install/enable GDM only if no other display manager owns login
  --with-wwan           Install ModemManager + the source machine's Fibocom WWAN unit
  --change-shell        Also change your login shell to zsh (requires a terminal)
  --set-defaults        Also set installed-app MIME defaults and GTK preferences

Preview and diagnostics (no writes, including logs)
  --dry-run             Show the selected actions without executing them
  --check               Check the existing installation without repairing it

Output and automation
  --yes, -y             Skip wizard/confirmation; use package-manager --noconfirm
  --verbose             Show unchanged items, every check, and live command output
  --quiet               Warnings/errors only; requires --yes for installation
  --ui auto|plain|gum   Prefer Gum [auto]; offer a verified runtime if missing; no sudo
  --log-file PATH       Use a NEW log file instead of the default state directory
  --no-color            Disable colors (also NO_COLOR=1); NO_EMOJI=1 selects ASCII
  --help, -h            Show this help

Examples
  ./install.sh --dry-run
  ./install.sh
  ./install.sh --profile full --with-gdm --yes
  ./install.sh --only-dotfiles --yes
  ./install.sh --link-only --yes
  ./install.sh --check --verbose

Package lists: packages/{core,shell,core-aur,extra,extra-aur}.txt
Full adds software, not kernels, bootloaders, GPU drivers, or enabled server services.
EOF
}

arg_error() { printf 'Error: %s\nTry ./install.sh --help.\n' "$*" >&2; return 2; }

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --profile)
        [[ -n "${2:-}" && "$2" != --* ]] || { arg_error 'Missing --profile value (core|full)'; return 2; }
        PROFILE="$2"; PROFILE_EXPLICIT=1; SCOPE_EXPLICIT=1; shift 2 ;;
      --profile=*) PROFILE="${1#*=}"; PROFILE_EXPLICIT=1; SCOPE_EXPLICIT=1; shift ;;
      --only-dotfiles) ONLY_DOTFILES=1; SCOPE_EXPLICIT=1; shift ;;
      --link-only) LINK_ONLY=1; ONLY_DOTFILES=1; SCOPE_EXPLICIT=1; shift ;;
      --check) CHECK_ONLY=1; shift ;;
      --no-aur) NO_AUR=1; SCOPE_EXPLICIT=1; shift ;;
      --no-shell) WITH_SHELL=0; SCOPE_EXPLICIT=1; shift ;;
      --with-gdm) WITH_GDM=1; SCOPE_EXPLICIT=1; shift ;;
      --with-wwan) WITH_WWAN=1; SCOPE_EXPLICIT=1; shift ;;
      --change-shell) CHANGE_SHELL=1; SCOPE_EXPLICIT=1; shift ;;
      --set-defaults) SET_DEFAULTS=1; SCOPE_EXPLICIT=1; shift ;;
      --dry-run) DRY_RUN=1; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      --verbose) VERBOSE=1; shift ;;
      --quiet) QUIET=1; shift ;;
      --ui)
        [[ -n "${2:-}" && "$2" != --* ]] || { arg_error 'Missing --ui value (auto|plain|gum)'; return 2; }
        UI_MODE="$2"; shift 2 ;;
      --ui=*) UI_MODE="${1#*=}"; shift ;;
      --log-file)
        [[ -n "${2:-}" && "$2" != --* ]] || { arg_error 'Missing --log-file path'; return 2; }
        LOG_FILE="$2"; LOG_FILE_EXPLICIT=1; shift 2 ;;
      --log-file=*) LOG_FILE="${1#*=}"; LOG_FILE_EXPLICIT=1; shift ;;
      --no-color) NO_COLOR=1; shift ;;
      --help|-h) HELP=1; shift ;;
      *) arg_error "Unknown option: $1"; return 2 ;;
    esac
  done
  [[ "$PROFILE" == core || "$PROFILE" == full ]] || { arg_error 'Profile must be core or full'; return 2; }
  [[ -n "$LOG_FILE" ]] || { arg_error 'Log path cannot be empty'; return 2; }
  [[ "$UI_MODE" == auto || "$UI_MODE" == plain || "$UI_MODE" == gum ]] || { arg_error 'UI must be auto, plain, or gum'; return 2; }
  (( VERBOSE == 0 || QUIET == 0 )) || { arg_error 'Cannot combine --verbose and --quiet'; return 2; }
  (( DRY_RUN == 0 || CHECK_ONLY == 0 )) || { arg_error 'Choose --dry-run or --check, not both'; return 2; }
  validate_selection || return 2
  (( QUIET == 0 || ASSUME_YES == 1 || DRY_RUN == 1 || CHECK_ONLY == 1 )) || { arg_error '--quiet requires --yes for installation'; return 2; }
  PACMAN_FLAGS=(--needed)
  CONFIRM_FLAGS=()
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    PACMAN_FLAGS+=(--noconfirm)
    CONFIRM_FLAGS+=(--noconfirm)
  fi
}

# Read data, never source/evaluate a package manifest. Reject duplicates and flags.
read_manifest() {
  local -n result="$1"
  local file="$2" line number=0
  local -A seen=()
  result=()
  [[ -r "$file" ]] || { fail "Package manifest not readable: $file"; return 1; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    number=$((number + 1))
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -n "$line" ]] || continue
    if [[ ! "$line" =~ ^[a-zA-Z0-9@_+][a-zA-Z0-9@._+-]*$ ]]; then
      fail "Invalid package at $file:$number: $line"; return 1
    fi
    if [[ -n "${seen[$line]+present}" ]]; then
      fail "Duplicate package at $file:$number: $line"; return 1
    fi
    seen["$line"]=1
    result+=("$line")
  done <"$file"
  (( ${#result[@]} > 0 )) || { fail "Empty package manifest: $file"; return 1; }
}

load_packages() {
  read_manifest PACMAN_CORE "$DOTFILES_ROOT/packages/core.txt" || return 1
  read_manifest PACMAN_SHELL "$DOTFILES_ROOT/packages/shell.txt" || return 1
  read_manifest PACMAN_EXTRA "$DOTFILES_ROOT/packages/extra.txt" || return 1
  read_manifest AUR_CORE "$DOTFILES_ROOT/packages/core-aur.txt" || return 1
  read_manifest AUR_EXTRA "$DOTFILES_ROOT/packages/extra-aur.txt" || return 1
  local package
  local -A seen=()
  for package in "${PACMAN_CORE[@]}" "${PACMAN_SHELL[@]}" "${PACMAN_EXTRA[@]}" "${AUR_CORE[@]}" "${AUR_EXTRA[@]}"; do
    [[ -z "${seen[$package]+present}" ]] || { fail "Package appears in multiple manifests: $package"; return 1; }
    seen["$package"]=1
  done
}

check_display_manager() {
  [[ "$WITH_GDM" -eq 1 ]] || return 0
  [[ -e "$DISPLAY_MANAGER_LINK" || -L "$DISPLAY_MANAGER_LINK" ]] || return 0
  local owner
  owner=$(readlink -f -- "$DISPLAY_MANAGER_LINK") || { fail 'Broken display-manager.service; repair it before enabling GDM'; return 1; }
  [[ "${owner##*/}" == gdm.service ]] || { fail "Another display manager owns login ($owner); it will not be replaced"; return 1; }
}

phase_preflight() {
  step 'Preflight'
  local entry src target file line input prefix='~/.config/matugen/' missing=0 binary
  local pattern='^[[:space:]]*input_path[[:space:]]*=[[:space:]]*"([^"]+)"'
  [[ "$HOME" == /* && "$HOME" != / && -d "$HOME" ]] || { fail 'HOME must be an existing absolute user directory'; return 1; }
  [[ "$HOME$DOTFILES_ROOT" != *$'\n'* && "$HOME$DOTFILES_ROOT" != *$'\t'* ]] || { fail 'HOME/repository paths cannot contain tabs or newlines'; return 1; }
  for entry in "${PLAN_LINKS[@]}"; do
    src="$DOTFILES_ROOT/${entry#*:}"
    target="$HOME/${entry%%:*}"
    [[ -d "$src" ]] || { fail "Missing config directory: $src"; missing=1; }
    if [[ "$DOTFILES_ROOT" == "$target" || "$DOTFILES_ROOT" == "$target/"* ]]; then
      fail "Repository is inside a path the installer would replace: $target"; missing=1
    fi
  done
  for entry in "${PLAN_OWNED_DIRS[@]}"; do
    target="$HOME/$entry"
    if [[ "$DOTFILES_ROOT" == "$target" || "$DOTFILES_ROOT" == "$target/"* ]]; then
      fail "Repository is inside a private config directory the installer would replace: $target"; missing=1
    fi
  done
  for file in "${PLAN_SOURCE_FILES[@]}"; do
    [[ -s "$DOTFILES_ROOT/$file" ]] || { fail "Missing/empty source config: $file"; missing=1; }
  done
  if [[ -r "$DOTFILES_ROOT/matugen/config.toml" ]]; then
    while IFS= read -r line; do
      [[ "$line" =~ $pattern ]] || continue
      input="${BASH_REMATCH[1]}"
      if [[ "$input" != "$prefix"* || ! -s "$DOTFILES_ROOT/matugen/${input#"$prefix"}" ]]; then
        fail "Missing or unsupported matugen template: $input"; missing=1
      fi
    done < <(render_palette_config)
  fi
  [[ "$missing" -eq 0 ]] || return 1
  ok "Repository ready (${#PLAN_LINKS[@]} config links; package manifests validated)"
  [[ "$DRY_RUN" -eq 0 ]] || check_display_manager || return 1
  if (( DRY_RUN == 1 || CHECK_ONLY == 1 )); then
    [[ -f /etc/arch-release ]] || warn 'Not an Arch host; read-only planning/checks are still available'
    return 0
  fi
  [[ "$EUID" -ne 0 ]] || { fail 'Run as your normal user, not root; sudo is used only for system changes'; return 1; }
  [[ -f /etc/arch-release ]] || { fail 'Installation requires Arch Linux (/etc/arch-release)'; return 1; }
  [[ "${XDG_CONFIG_HOME:-$HOME/.config}" == "$HOME/.config" ]] || { fail 'This config expects XDG_CONFIG_HOME=$HOME/.config'; return 1; }
  command -v flock >/dev/null 2>&1 || { fail 'Required prerequisite missing: flock (util-linux)'; return 1; }
  if [[ "$CHANGE_SHELL" -eq 1 && ! -t 0 ]]; then fail '--change-shell requires a terminal for chsh authentication'; return 1; fi
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    for binary in sudo pacman; do
      command -v "$binary" >/dev/null 2>&1 || { fail "Required prerequisite missing: $binary"; return 1; }
    done
    check_display_manager || return 1
  elif [[ "$LINK_ONLY" -eq 0 ]]; then
    local -a prerequisites=(matugen xdg-user-dirs-update fc-cache)
    [[ "$WITH_SHELL" -eq 0 ]] || prerequisites+=(git zsh)
    for binary in "${prerequisites[@]}"; do
      command -v "$binary" >/dev/null 2>&1 || { fail "Dotfiles-only needs $binary already installed; use the package profile first"; return 1; }
    done
  fi
  say 'The eDP-1 monitor preset is unchanged; other outputs use the preferred-mode fallback.'
}

prune_logs() {
  local record file count=0
  [[ -d "$LOG_DIR_DEFAULT" ]] || return 0
  while IFS= read -r -d '' record; do
    file="${record#* }"
    count=$((count + 1))
    if (( count > LOG_KEEP )) && [[ "$file" != "$LOG_FILE" ]]; then rm -f -- "$file"; fi
  done < <(find "$LOG_DIR_DEFAULT" -maxdepth 1 -type f -name 'install-*.log' -printf '%T@ %p\0' | sort -z -rn)
}

init_runtime() {
  (( DRY_RUN == 0 && CHECK_ONLY == 0 )) || return 0
  umask 077
  mkdir -p -- "$(dirname -- "$LOCK_FILE")"
  # Do not put 2>/dev/null on exec: that would silence stderr for the whole script.
  if ! { exec 200>"$LOCK_FILE"; }; then fail "Cannot open installer lock: $LOCK_FILE"; return 1; fi
  if ! flock -n 200; then fail 'Another HyprYoru installation is already running'; return 1; fi
  mkdir -p -- "$(dirname -- "$LOG_FILE")"
  if [[ -e "$LOG_FILE" || -L "$LOG_FILE" ]] || ! (set -o noclobber; : >"$LOG_FILE"); then
    fail "Refusing to overwrite an existing/unwritable log: $LOG_FILE"; return 1
  fi
  LOG_ENABLED=1
  [[ "$LOG_FILE_EXPLICIT" -eq 1 ]] || prune_logs
  _log_plain "[start] profile=$PROFILE dotfiles=$ONLY_DOTFILES link-only=$LINK_ONLY no-aur=$NO_AUR zsh=$WITH_SHELL gdm=$WITH_GDM wwan=$WITH_WWAN shell=$CHANGE_SHELL defaults=$SET_DEFAULTS"
  _log_plain "[paths] repository=$DOTFILES_ROOT home=$HOME backups=$BACKUP_DIR"
}

prepare_backup() {
  [[ "$BACKUP_READY" -eq 0 ]] || return 0
  if [[ -e "$BACKUP_DIR" || -L "$BACKUP_DIR" ]]; then fail "Refusing to reuse an existing backup: $BACKUP_DIR"; return 1; fi
  mkdir -p -- "$(dirname -- "$BACKUP_DIR")" || return 1
  if ! mkdir -m 700 -- "$BACKUP_DIR"; then fail "Cannot create backup directory: $BACKUP_DIR"; return 1; fi
  printf '# action\toriginal path\tbackup path\n' >"$BACKUP_DIR/manifest.tsv" || return 1
  BACKUP_READY=1
}

# Copy individual files before editing. Directory/symlink replacements use moves.
# Separate trees avoid collisions between an old config dir and an edited repo file.
preserve_file() {
  local target="$1" dest
  [[ -z "${PRESERVED_FILES[$target]+present}" ]] || return 0
  [[ "$target" == "$HOME/"* ]] || { fail "Backup target is outside HOME: $target"; return 1; }
  prepare_backup || return 1
  dest="$BACKUP_DIR/edited/${target#"$HOME/"}"
  if [[ -e "$target" || -L "$target" ]]; then
    [[ ! -e "$dest" && ! -L "$dest" ]] || { fail "Backup already exists: $dest"; return 1; }
    mkdir -p -- "$(dirname -- "$dest")" || return 1
    if ! cp -a -- "$target" "$dest"; then fail "Backup failed; leaving $target untouched"; return 1; fi
    printf 'copied\t%s\t%s\n' "$target" "$dest" >>"$BACKUP_DIR/manifest.tsv" || return 1
  else
    printf 'created\t%s\t-\n' "$target" >>"$BACKUP_DIR/manifest.tsv" || return 1
  fi
  PRESERVED_FILES["$target"]=1
}

make_temp() {
  NEW_TEMP=$(mktemp "$(dirname -- "$1")/.hypryoru.XXXXXX") || return 1
  TEMP_FILES+=("$NEW_TEMP")
}

replace_file() {
  local target="$1" temp="$2"
  if [[ -f "$target" ]] && cmp -s -- "$target" "$temp"; then
    rm -f -- "$temp"; skip "Unchanged: $target"; return 0
  fi
  preserve_file "$target" || return 1
  [[ ! -f "$target" ]] || chmod --reference="$target" -- "$temp" || return 1
  mv -fT -- "$temp" "$target" || return 1
  log "Updated: $target"
}

link_one() {
  local target="$HOME/$1" src="$DOTFILES_ROOT/$2" dest='' moved=0
  [[ -d "$src" ]] || { fail "Cannot link missing source: $src"; return 1; }
  if [[ -L "$target" && "$target" -ef "$src" ]]; then skip "Link already correct: $target"; return 0; fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    [[ ! -e "$target" && ! -L "$target" ]] || dry "Move $target into the backup (including existing symlinks)"
    dry "Link $target -> $src"; return 0
  fi
  mkdir -p -- "$(dirname -- "$target")" || return 1
  prepare_backup || return 1
  if [[ -e "$target" || -L "$target" ]]; then
    dest="$BACKUP_DIR/home/$1"
    [[ ! -e "$dest" && ! -L "$dest" ]] || { fail "Backup collision: $dest"; return 1; }
    mkdir -p -- "$(dirname -- "$dest")" || return 1
    if ! mv -T -- "$target" "$dest"; then fail "Cannot preserve $target; replacement cancelled"; return 1; fi
    moved=1
    printf 'moved\t%s\t%s\n' "$target" "$dest" >>"$BACKUP_DIR/manifest.tsv" || return 1
  fi
  if ! run ln -sT -- "$src" "$target"; then
    fail "Cannot create link: $target"
    if [[ "$moved" -eq 1 && ! -e "$target" && ! -L "$target" ]]; then
      if mv -T -- "$dest" "$target"; then
        printf 'restored\t%s\t%s\n' "$target" "$dest" >>"$BACKUP_DIR/manifest.tsv" || return 1
      else
        warn "Restore the original manually from $dest"
      fi
    fi
    return 1
  fi
  printf 'linked\t%s\t%s\n' "$target" "$src" >>"$BACKUP_DIR/manifest.tsv" || return 1
}

ensure_zshenv() {
  local target="$HOME/.zshenv" temp
  if [[ "$DRY_RUN" -eq 1 ]]; then dry 'Ensure ~/.zshenv has a managed ZDOTDIR block; preserve custom content'; return 0; fi
  make_temp "$target" || return 1
  temp="$NEW_TEMP"
  if [[ -f "$target" ]]; then
    if ! awk '
      /^# >>> HyprYoru >>>$/ {if (managed) exit 2; managed=1; next}
      /^# <<< HyprYoru <<<$/ {if (!managed) exit 2; managed=0; next}
      !managed {print}
      END {if (managed) exit 2}
    ' "$target" >"$temp"; then
      fail 'Unbalanced HyprYoru markers in ~/.zshenv; repair the block before retrying.'
      return 1
    fi
  fi
  # Do not delete arbitrary user statements mentioning ZDOTDIR. The final block wins.
  printf '# >>> HyprYoru >>>\nexport ZDOTDIR="$HOME/.config/zsh"\n# <<< HyprYoru <<<\n' >>"$temp" || return 1
  replace_file "$target" "$temp"
}

ensure_sudo() {
  [[ "$DRY_RUN" -eq 0 ]] || return 0
  [[ -z "$SUDO_KEEPALIVE_PID" ]] || return 0
  say 'Authenticating sudo before package installation (password input stays visible).'
  run sudo -v || return 1
  (
    trap - ERR
    exec 200>&-
    sleeper=''
    trap '[[ -z "$sleeper" ]] || kill "$sleeper" 2>/dev/null; exit 0' TERM INT
    while kill -0 "$$" 2>/dev/null; do
      sudo -n true || break
      sleep 50 &
      sleeper=$!
      wait "$sleeper" || break
      sleeper=''
    done
  ) </dev/null >/dev/null 2>&1 &
  SUDO_KEEPALIVE_PID=$!
}

in_dir() { local directory="$1"; shift; (cd -- "$directory" && "$@"); }

find_aur_helper() {
  local helper
  for helper in yay paru; do
    if command -v "$helper" >/dev/null 2>&1; then AUR_HELPER="$helper"; return 0; fi
  done
  return 1
}

ensure_aur_helper() {
  [[ "$NO_AUR" -eq 0 ]] || return 0
  if find_aur_helper; then skip "Using existing AUR helper: $AUR_HELPER"; return 0; fi
  AUR_HELPER=yay
  if [[ "$DRY_RUN" -eq 1 ]]; then dry 'Bootstrap yay-bin in a temporary directory (base-devel, git clone, makepkg -si)'; return 0; fi
  local build
  spin 'Install AUR build tools' sudo pacman -S "${PACMAN_FLAGS[@]}" base-devel git || return 1
  build=$(mktemp -d "${TMPDIR:-/tmp}/hypryoru-aur.XXXXXX") || return 1
  TEMP_DIRS+=("$build")
  spin 'Fetch yay-bin PKGBUILD' git clone -- https://aur.archlinux.org/yay-bin.git "$build" || return 1
  say 'AUR build scripts are third-party code; review the PKGBUILD before approving installation.'
  if is_interactive; then
    run cat -- "$build/PKGBUILD" || return 1
    if ! ask_yes_no 'Build this AUR helper?' no; then return 1; fi
  fi
  spin 'Build and install yay-bin' in_dir "$build" makepkg -si --needed "${CONFIRM_FLAGS[@]}" || return 1
  command -v yay >/dev/null 2>&1 || return 1
}

phase_base() {
  step 'Update Arch packages'
  ensure_sudo
  say 'Existing pacman settings and mirror configuration are kept unchanged.'
  spin 'Full system upgrade (pacman -Syu)' sudo pacman -Syu "${CONFIRM_FLAGS[@]}"
}

missing_packages() {
  MISSING_PACKAGES=()
  if [[ "$DRY_RUN" -eq 1 ]]; then MISSING_PACKAGES=("$@"); return 0; fi
  local installed package
  local -A present=()
  if ! installed=$(pacman -Qq); then fail 'Cannot read the local pacman database'; return 1; fi
  while IFS= read -r package; do [[ -z "$package" ]] || present["$package"]=1; done <<<"$installed"
  for package in "$@"; do
    [[ -n "${present[$package]+yes}" ]] || MISSING_PACKAGES+=("$package")
  done
}

install_package_set() {
  local label="$1" manager="$2"; shift 2
  local -a requested=("$@") todo=() failed=() command=()
  local package
  missing_packages "${requested[@]}" || return 1
  todo=("${MISSING_PACKAGES[@]}")
  if (( ${#todo[@]} == 0 )); then skip "$label packages already installed (${#requested[@]})"; return 0; fi
  say "$label: ${#todo[@]} queued, $(( ${#requested[@]} - ${#todo[@]} )) already installed."
  if [[ "$manager" == pacman ]]; then command=(sudo pacman -S "${PACMAN_FLAGS[@]}")
  else command=("$manager" -S "${PACMAN_FLAGS[@]}"); fi
  if spin "Install ${#todo[@]} $label packages" "${command[@]}" "${todo[@]}"; then return 0; fi
  if (( ${#todo[@]} == 1 )); then
    failed=("${todo[@]}")
  else
    warn "$label batch failed; retrying packages individually."
    for package in "${todo[@]}"; do
      if ! spin "Install $package" "${command[@]}" "$package"; then failed+=("$package"); fi
    done
  fi
  if (( ${#failed[@]} > 0 )); then
    FAILED_PACKAGES+=("${failed[@]}")
    fail "$label packages unresolved: ${failed[*]}"
  else
    ok "$label packages recovered successfully on retry"
  fi
}

is_required_official() {
  local wanted="$1" package
  for package in "${PLAN_REQUIRED_OFFICIAL[@]}"; do [[ "$package" != "$wanted" ]] || return 0; done
  return 1
}

phase_packages() {
  step "Install packages / $PROFILE"
  FAILED_PACKAGES=()
  install_package_set Official pacman "${PLAN_OFFICIAL[@]}"
  local package
  for package in "${FAILED_PACKAGES[@]}"; do
    if is_required_official "$package"; then
      fail 'A required desktop package failed; no existing configs have been replaced.'
      return 1
    fi
  done
  if [[ "$NO_AUR" -eq 1 ]]; then
    warn 'AUR disabled. Themes and Waypaper must already be installed, or those features will be unavailable.'
    return 0
  fi
  if ! ensure_aur_helper; then
    fail 'AUR helper setup failed; continuing desktop setup without the requested AUR packages.'
    return 0
  fi
  install_package_set AUR "$AUR_HELPER" "${PLAN_AUR[@]}"
}

service_in_use() {
  local state
  state=$(systemctl is-enabled "$1" 2>/dev/null || true)
  case "$state" in enabled|enabled-runtime|linked|linked-runtime|alias) return 0 ;; esac
  systemctl is-active --quiet "$1" 2>/dev/null
}

enable_unit() {
  local scope="$1" unit="$2" state
  local -a query=(systemctl) command=(sudo systemctl)
  if [[ "$scope" == user ]]; then query+=(--user); command=(systemctl --user); fi
  if [[ "$DRY_RUN" -eq 1 ]]; then run "${command[@]}" enable "$unit"; return 0; fi
  state=$("${query[@]}" is-enabled "$unit" 2>/dev/null || true)
  case "$state" in
    enabled|enabled-runtime|alias) skip "$unit already enabled"; return 0 ;;
    static|indirect|generated) skip "$unit is managed automatically ($state)"; return 0 ;;
    masked|masked-runtime) warn "$unit is masked; leaving the user's choice intact"; return 0 ;;
    ''|not-found) warn "$unit unavailable in the $scope manager; not enabled"; return 0 ;;
  esac
  if ! run "${command[@]}" enable "$unit"; then
    if [[ "$scope" == user ]]; then warn "Could not enable $unit; retry from a user login session."
    else fail "Could not enable $unit"; fi
  fi
}

write_wwan_unit() {
  local source="$DOTFILES_ROOT/services/wwan-enable.service"
  [[ -f "$source" ]] || { fail 'WWAN service template is missing'; return 1; }
  if [[ -e "$WWAN_UNIT_PATH" || -L "$WWAN_UNIT_PATH" ]]; then
    if cmp -s -- "$source" "$WWAN_UNIT_PATH"; then skip 'WWAN unit already matches'; return 0; fi
    fail "Refusing to overwrite an existing custom unit: $WWAN_UNIT_PATH"; return 1
  fi
  run sudo install -m 644 -- "$source" "$WWAN_UNIT_PATH" || return 1
  run sudo systemctl daemon-reload
}

phase_services() {
  step 'Enable desktop services'
  local unit
  check_display_manager
  if [[ "$WITH_WWAN" -eq 1 ]]; then write_wwan_unit; fi
  for unit in "${PLAN_SYSTEM_SERVICES[@]}"; do
    if [[ "$DRY_RUN" -eq 0 && "$unit" == NetworkManager.service ]] && { service_in_use systemd-networkd.service || service_in_use dhcpcd.service; }; then
      warn 'Another network service is in use; NetworkManager is not enabled automatically.'; continue
    fi
    if [[ "$DRY_RUN" -eq 0 && "$unit" == power-profiles-daemon.service ]] && service_in_use tlp.service; then
      warn 'TLP is in use; keeping it and not enabling power-profiles-daemon.'; continue
    fi
    enable_unit system "$unit"
  done
  for unit in "${PLAN_USER_SERVICES[@]}"; do enable_unit user "$unit"; done
  say 'Services are enabled for future logins/boots, not restarted. Server/firewall services are untouched.'
}

collect_scripts() {
  local file
  SCRIPT_PATHS=()
  for file in "$DOTFILES_ROOT/hyprland/scripts/"*.sh "$DOTFILES_ROOT/hyprland/whatsong.sh" \
    "$DOTFILES_ROOT/waybar/scripts/"*.sh "$DOTFILES_ROOT/swaync/scripts/"*.sh \
    "$DOTFILES_ROOT/rofi/launchers/"*.sh "$DOTFILES_ROOT/rofi/launchers/type-6/"*.sh \
    "$DOTFILES_ROOT/rofi/launchers/rofi-bluetooth"; do
    [[ ! -f "$file" ]] || SCRIPT_PATHS+=("$file")
  done
}

seed_file() {
  local source="$1" target="$2"
  if [[ -e "$target" || -L "$target" ]]; then skip "Already present: $target"; return 0; fi
  run cp -n -- "$source" "$target"
}

normalize_qt_path() {
  local target="$HOME/.config/qt6ct/qt6ct.conf" temp line
  if [[ "$DRY_RUN" -eq 1 ]]; then dry 'Normalize qt6ct palette path for this HOME (back up before editing)'; return 0; fi
  [[ -f "$target" ]] || { warn 'qt6ct.conf missing; palette path not normalized'; return 0; }
  make_temp "$target" || return 1
  temp="$NEW_TEMP"
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in color_scheme_path=*) line="color_scheme_path=$HOME/.config/qt6ct/colors/matugen.conf" ;; esac
    printf '%s\n' "$line" >>"$temp" || return 1
  done <"$target"
  replace_file "$target" "$temp"
}

# A shell opt-out must also survive subsequent wallpaper changes. Use a private
# Matugen config plus a templates symlink, never edit the repository's config.
prepare_private_palette() {
  (( ${#PLAN_OWNED_DIRS[@]} > 0 )) || return 0
  local target="$HOME/.config/matugen" dest="$BACKUP_DIR/home/.config/matugen" temp
  if [[ "$DRY_RUN" -eq 1 ]]; then
    dry "Prepare $target as a private palette config without the Zsh output; preserve any existing root"
    return 0
  fi
  if ! private_matugen_root; then
    mkdir -p -- "$HOME/.config" || return 1
    prepare_backup || return 1
    if [[ -e "$target" || -L "$target" ]]; then
      [[ ! -e "$dest" && ! -L "$dest" ]] || { fail "Backup collision: $dest"; return 1; }
      mkdir -p -- "$(dirname -- "$dest")" || return 1
      if ! mv -T -- "$target" "$dest"; then fail 'Cannot preserve the existing Matugen directory'; return 1; fi
      printf 'moved\t%s\t%s\n' "$target" "$dest" >>"$BACKUP_DIR/manifest.tsv" || return 1
    fi
    if ! mkdir -- "$target"; then
      if [[ ! -e "$target" && ! -L "$target" && ( -e "$dest" || -L "$dest" ) ]]; then mv -T -- "$dest" "$target" || true; fi
      return 1
    fi
    printf '%s\n' "$DOTFILES_ROOT" >"$target/.hypryoru-managed" || return 1
    printf 'created\t%s\t-\n' "$target" >>"$BACKUP_DIR/manifest.tsv" || return 1
  fi
  make_temp "$target/config.toml" || return 1
  temp="$NEW_TEMP"
  render_palette_config >"$temp" || return 1
  replace_file "$target/config.toml" "$temp"
}

path_uri() {
  local LC_ALL=C path="$1" char code i
  printf 'file://'
  for ((i=0; i<${#path}; i++)); do
    char="${path:i:1}"
    case "$char" in
      [a-zA-Z0-9/_.~-]) printf '%s' "$char" ;;
      *) printf -v code '%02X' "'$char"; printf '%%%s' "$code" ;;
    esac
  done
}

seed_bookmarks() {
  local target="$HOME/.config/gtk-3.0/bookmarks" key directory fallback temp
  if [[ -e "$target" || -L "$target" ]]; then skip 'Existing GTK bookmarks preserved'; return 0; fi
  if [[ "$DRY_RUN" -eq 1 ]]; then dry 'Seed GTK bookmarks only if absent, using actual XDG user directories'; return 0; fi
  make_temp "$target" || return 1
  temp="$NEW_TEMP"
  for key in DOCUMENTS MUSIC PICTURES VIDEOS DOWNLOAD; do
    case "$key" in DOWNLOAD) fallback=Downloads ;; *) fallback="${key,,}"; fallback="${fallback^}" ;; esac
    directory=$(xdg-user-dir "$key" 2>/dev/null || true)
    [[ -n "$directory" ]] || directory="$HOME/$fallback"
    path_uri "$directory" >>"$temp"
    printf '\n' >>"$temp"
  done
  replace_file "$target" "$temp"
}

desktop_exists() {
  local desktop="$1" directory
  local -a dirs=()
  IFS=: read -r -a dirs <<<"${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
  dirs=("${XDG_DATA_HOME:-$HOME/.local/share}" "${dirs[@]}")
  for directory in "${dirs[@]}"; do
    [[ ! -f "$directory/applications/$desktop" ]] || return 0
  done
  return 1
}

set_mime_group() {
  local desktop="$1"; shift
  local mime
  if [[ "$DRY_RUN" -eq 1 ]]; then dry "Set MIME defaults to $desktop only if its desktop entry is installed: $*"; return 0; fi
  if ! desktop_exists "$desktop"; then skip "Default application not installed: $desktop"; return 0; fi
  preserve_file "$HOME/.config/mimeapps.list" || return 1
  for mime in "$@"; do run xdg-mime default "$desktop" "$mime" || return 1; done
}

set_gtk_preference() {
  local key="$1" value="$2" old schema=org.gnome.desktop.interface
  if [[ "$DRY_RUN" -eq 1 ]]; then run gsettings set "$schema" "$key" "$value"; return 0; fi
  if [[ "$(gsettings writable "$schema" "$key" 2>/dev/null || true)" != true ]]; then
    warn "GTK preference is not writable in this session: $key"; return 0
  fi
  old=$(gsettings get "$schema" "$key") || return 1
  prepare_backup || return 1
  printf 'gsettings set %q %q %q\n' "$schema" "$key" "$old" >>"$BACKUP_DIR/restore-gsettings.sh" || return 1
  run gsettings set "$schema" "$key" "$value"
}

apply_defaults() {
  [[ "$SET_DEFAULTS" -eq 1 ]] || { skip 'Application defaults and GTK preferences left unchanged'; return 0; }
  local mode='dark' gtk_theme='adw-gtk3-dark' color_scheme='prefer-dark'
  if [[ -r "$HOME/.cache/matugen/current-mode" ]]; then
    IFS= read -r mode <"$HOME/.cache/matugen/current-mode" || true
    if [[ "$mode" == light ]]; then gtk_theme='adw-gtk3'; color_scheme='prefer-light'; fi
  fi
  set_mime_group chromium.desktop text/html x-scheme-handler/http x-scheme-handler/https
  set_mime_group org.gnome.Evince.desktop application/pdf application/postscript
  if [[ "$DRY_RUN" -eq 0 ]] && desktop_exists org.xfce.ristretto.desktop; then
    set_mime_group org.xfce.ristretto.desktop image/png image/jpeg image/webp image/gif
  else
    set_mime_group imv.desktop image/png image/jpeg image/webp image/gif
  fi
  if [[ "$DRY_RUN" -eq 1 ]] || command -v gsettings >/dev/null 2>&1; then
    set_gtk_preference gtk-theme "$gtk_theme"
    set_gtk_preference color-scheme "$color_scheme"
    set_gtk_preference font-name 'Adwaita Sans Medium 11'
    if [[ "$NO_AUR" -eq 0 ]]; then
      set_gtk_preference icon-theme kora-pgrey
      set_gtk_preference cursor-theme Bibata-Modern-Classic
    fi
  else
    warn 'gsettings unavailable; GTK preferences were not applied.'
  fi
}

phase_dotfiles() {
  step 'Link and prepare configs'
  local entry script file
  prepare_private_palette
  for entry in "${PLAN_LINKS[@]}"; do link_one "${entry%%:*}" "${entry#*:}"; done
  if [[ "$WITH_SHELL" -eq 1 ]]; then ensure_zshenv; else skip 'Zsh config, frameworks, and ZDOTDIR left untouched'; fi
  if [[ "$DRY_RUN" -eq 1 ]]; then dry "Prepare ${#PLAN_LINKS[@]} selected config links"
  else ok "${#PLAN_LINKS[@]} selected config links ready"; fi
  [[ "$LINK_ONLY" -eq 0 ]] || return 0
  collect_scripts
  for script in "${SCRIPT_PATHS[@]}"; do [[ -x "$script" ]] || run chmod +x -- "$script"; done
  run mkdir -p -- "$HOME/Pictures/wallpapers" "$HOME/Pictures/Screenshots" \
    "$HOME/.cache/matugen" "$HOME/.cache/hyprlock" "${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-thumbs" \
    "$HOME/.config/swaync/matugen" "$HOME/.config/matugen/themes" \
    "$HOME/.config/btop/themes" "$HOME/.config/qt6ct/colors" \
    "$HOME/.local/bin" "$HOME/.local/share/fonts"
  [[ "$WITH_SHELL" -eq 0 ]] || run mkdir -p -- "$HOME/.config/zsh/generated"
  normalize_qt_path
  for file in "$DOTFILES_ROOT/hyprland/wallpapers/"*; do
    [[ ! -f "$file" ]] || seed_file "$file" "$HOME/Pictures/wallpapers/${file##*/}"
  done
  seed_file "$DOTFILES_ROOT/waypaper/config.ini.example" "$HOME/.config/waypaper/config.ini"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    preserve_file "$HOME/.config/user-dirs.dirs"
    preserve_file "$HOME/.config/user-dirs.locale"
  fi
  run xdg-user-dirs-update
  seed_bookmarks
  apply_defaults
  if ! spin 'Refresh font cache' fc-cache -f; then warn 'Font cache refresh failed; fonts may need a refresh at next login.'; fi
}

clone_framework() {
  local label="$1" url="$2" target="$3" marker="$4"
  if [[ -s "$target/$marker" ]]; then skip "$label already installed"; return 0; fi
  if [[ -e "$target" || -L "$target" ]]; then fail "Incomplete $label directory; inspect it before retrying: $target"; return 1; fi
  spin "Install $label" git clone --depth=1 -- "$url" "$target"
}

phase_shell() {
  step 'Prepare zsh'
  clone_framework oh-my-zsh https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh" oh-my-zsh.sh
  clone_framework powerlevel10k https://github.com/romkatv/powerlevel10k.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k" powerlevel10k.zsh-theme
  if [[ "$CHANGE_SHELL" -eq 1 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then dry 'Change the account login shell to zsh with chsh'
    else
      local current user zsh_path
      user=$(id -un)
      current=$(getent passwd "$user" | cut -d: -f7)
      zsh_path=$(command -v zsh)
      if [[ "$current" == "$zsh_path" || "$current" == /bin/zsh || "$current" == /usr/bin/zsh ]]; then skip 'Login shell already zsh'
      else
        prepare_backup
        printf 'chsh -s %q\n' "$current" >"$BACKUP_DIR/restore-shell.sh"
        run chsh -s "$zsh_path"
      fi
    fi
  else
    skip 'Login shell left unchanged (--change-shell to opt in)'
  fi
  run env ZDOTDIR=/dev/null zsh -f -n "$HOME/.config/zsh/.zshrc"
}

phase_theming() {
  step 'Generate the palette'
  local wall='' mode='dark'
  if [[ -r "$HOME/.cache/matugen/current-wallpaper" ]]; then
    IFS= read -r wall <"$HOME/.cache/matugen/current-wallpaper" || true
    [[ -f "$wall" ]] || wall=''
  fi
  if [[ -z "$wall" ]]; then
    if [[ -f "$HOME/Pictures/wallpapers/mystical-night-in-town.jpg" ]]; then wall="$HOME/Pictures/wallpapers/mystical-night-in-town.jpg"
    else wall="$DOTFILES_ROOT/hyprland/wallpapers/mystical-night-in-town.jpg"; fi
  fi
  [[ -f "$wall" ]] || wall="$DOTFILES_ROOT/hyprland/wallpapers/anime3.png"
  [[ -f "$wall" ]] || { fail 'No seed wallpaper available for palette generation'; return 1; }
  if [[ -r "$HOME/.cache/matugen/current-mode" ]]; then
    IFS= read -r mode <"$HOME/.cache/matugen/current-mode" || true
    [[ "$mode" == light || "$mode" == dark ]] || mode='dark'
  fi
  say 'Generate themes only; wallpaper is restored at login. Template hooks may refresh running apps.'
  spin 'Generate matugen themes' matugen image "$wall" --mode "$mode" --type scheme-tonal-spot --prefer closest-to-fallback
}

check_bin() {
  if command -v "$1" >/dev/null 2>&1; then vpass "Command: $1"; else vfail "Missing command: $1"; fi
}

verify_defaults() {
  local file="$HOME/.config/mimeapps.list" line desktop defaults=0
  local -A unavailable=()
  [[ -r "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      '[Default Applications]') defaults=1; continue ;;
      '['*) defaults=0; continue ;;
      ''|'#'*) continue ;;
    esac
    [[ "$defaults" -eq 1 && "$line" == *=* ]] || continue
    desktop="${line#*=}"; desktop="${desktop%%;*}"
    if [[ -n "$desktop" && -z "${unavailable[$desktop]+present}" ]] && ! desktop_exists "$desktop"; then
      unavailable["$desktop"]=1
      vwarn "MIME default references an unavailable app: $desktop"
    fi
  done <"$file"
}

phase_verify() {
  step 'Verify the installation'
  local entry target binary file state package before="$FAIL_COUNT" checked=0
  for entry in "${PLAN_LINKS[@]}"; do
    target="$HOME/${entry%%:*}"
    if [[ -L "$target" && "$target" -ef "$DOTFILES_ROOT/${entry#*:}" ]]; then vpass "Config link: $target"
    else vfail "Missing/broken/incorrect config link: $target"; fi
  done
  if [[ "$WITH_SHELL" -eq 1 ]]; then
    if grep -Fqx 'export ZDOTDIR="$HOME/.config/zsh"' "$HOME/.zshenv" 2>/dev/null; then vpass 'ZDOTDIR configured'
    else vfail '~/.zshenv does not configure the expected ZDOTDIR'; fi
  elif private_matugen_root && [[ -r "$HOME/.config/matugen/config.toml" && -s "$HOME/.config/matugen/config.toml" ]] &&
    ! grep -q '^\[templates.shell\]' "$HOME/.config/matugen/config.toml"; then
    vpass 'Private palette config leaves the unselected shell alone'
  else
    vfail 'Private Matugen config is missing or still manages the unselected shell'
  fi
  if [[ "$LINK_ONLY" -eq 1 ]]; then say 'Link-only verification complete; dependencies and generated themes were not checked.'; return 0; fi
  for binary in "${PLAN_COMMANDS[@]}"; do check_bin "$binary"; done
  if [[ -x /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 ]]; then vpass 'Polkit authentication agent'
  else vfail 'Polkit authentication agent missing'; fi
  if [[ "$NO_AUR" -eq 1 ]] && ! command -v waypaper >/dev/null 2>&1; then vwarn 'Wallpaper picker unavailable (--no-aur)'; fi
  for file in "${PLAN_SOURCE_FILES[@]}"; do
    if [[ -s "$DOTFILES_ROOT/$file" ]]; then vpass "Source config: $file"; else vfail "Empty/missing config: $file"; fi
  done
  collect_scripts
  for file in "${SCRIPT_PATHS[@]}"; do
    if [[ -x "$file" ]]; then vpass "Executable launcher: ${file#"$DOTFILES_ROOT/"}"
    else vfail "Launcher is not executable: $file"; fi
  done
  while IFS= read -r file; do
    checked=$((checked + 1))
    if [[ -s "$file" ]]; then vpass "Generated theme: $file"; else vfail "Missing/empty generated theme: $file"; fi
  done < <(palette_outputs)
  (( checked > 0 )) || vfail 'No matugen template outputs were found'
  if [[ "$WITH_SHELL" -eq 1 ]]; then
    if [[ -s "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]]; then vpass 'oh-my-zsh installed'; else vfail 'oh-my-zsh is missing/incomplete'; fi
    if [[ -s "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k/powerlevel10k.zsh-theme" ]]; then vpass 'powerlevel10k installed'
    else vfail 'powerlevel10k is missing/incomplete'; fi
    if command -v zsh >/dev/null 2>&1; then
      if env ZDOTDIR=/dev/null zsh -f -n "$HOME/.config/zsh/.zshrc"; then vpass 'zshrc syntax'; else vfail 'zshrc syntax'; fi
    fi
  fi
  if command -v pacman >/dev/null 2>&1; then
    for package in adwaita-fonts ttf-jetbrains-mono-nerd ttf-go-nerd ttf-martian-mono-nerd; do
      if pacman -Q -- "$package" >/dev/null 2>&1; then vpass "Font package: $package"; else vwarn "Font package not installed: $package"; fi
    done
    log "Installed versions: $(pacman -Q hyprland matugen waybar 2>/dev/null || true)"
  fi
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    for entry in "${PLAN_SYSTEM_SERVICES[@]}"; do
      state=$(systemctl is-enabled "$entry" 2>/dev/null || true)
      case "$state" in enabled|enabled-runtime|static|alias) vpass "Service: $entry ($state)" ;; *) vwarn "Service not enabled: $entry (${state:-unavailable})" ;; esac
    done
  fi
  verify_defaults
  if [[ "$FAIL_COUNT" -eq "$before" ]]; then ok "Verification complete ($checked generated themes checked)"
  else say 'Verification found failures; see the messages above.'; fi
}

cleanup_exit() {
  local directory
  _restore_cursor
  cleanup_gum_runtime
  if [[ -n "$ACTIVE_PID" ]]; then kill "$ACTIVE_PID" 2>/dev/null || true; wait "$ACTIVE_PID" 2>/dev/null || true; fi
  if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true; wait "$SUDO_KEEPALIVE_PID" 2>/dev/null || true; fi
  if (( ${#TEMP_FILES[@]} > 0 )); then rm -f -- "${TEMP_FILES[@]}"; fi
  for directory in "${TEMP_DIRS[@]}"; do
    if [[ "$directory" == "${TMPDIR:-/tmp}/hypryoru-aur."* && -d "$directory" && ! -L "$directory" ]]; then
      rm -rf -- "$directory"
    fi
  done
  return 0
}

stop_sudo_keepalive() {
  if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
    kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    wait "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    SUDO_KEEPALIVE_PID=''
  fi
}

execute_plan() {
  activate_plan
  local phase
  for phase in "${PLAN_PHASES[@]}"; do
    if [[ "$phase" == phase_verify && "$DRY_RUN" -eq 1 ]]; then
      step 'Verification after installation'
      dry 'Check the commands, links, palette outputs, and services for the selected components'
    else
      "$phase"
    fi
    COMPLETED_PHASES=$((COMPLETED_PHASES + 1))
    if [[ "$phase" == phase_preflight && "$CHECK_ONLY" -eq 0 ]]; then init_runtime; fi
  done
}

on_err() {
  local line="$1"
  trap - ERR
  set +e
  _restore_cursor
  fail "Stopped at install.sh:$line. Existing backups are retained."
  stop_sudo_keepalive
  if [[ "$LOG_ENABLED" -eq 1 ]]; then
    _term err "  Recent command output (full log: $LOG_FILE):"
    tail -n 12 -- "$LOG_FILE" >&2
  fi
  final_summary
  ui_results
  exit 1
}

main() {
  SCRIPT_START=$(date +%s)
  setup_ui
  parse_args "$@"
  setup_ui
  if [[ "$HELP" -eq 1 ]]; then usage; return 0; fi
  if (( DRY_RUN == 0 && CHECK_ONLY == 0 && ASSUME_YES == 0 )) && [[ ! -t 0 || ! -t 1 ]]; then
    arg_error 'Installation without a terminal requires --yes; use --dry-run to preview first'
    return 2
  fi
  trap 'on_err "$LINENO"' ERR
  trap cleanup_exit EXIT
  trap 'printf "\nInterrupted; backups are retained.\n" >&2; exit 130' INT
  trap 'printf "\nTerminated; backups are retained.\n" >&2; exit 143' TERM
  load_packages
  select_ui_backend
  banner
  if ! prepare_wizard_plan; then
    if [[ "$GUM_CACHE_CHANGED" -eq 1 ]]; then
      _term out '' '  Cancelled. No desktop settings or packages changed; approved UI cache changes were kept.'
    else
      _term out '' '  Cancelled. No files or settings changed.'
    fi
    trap - ERR
    return "$UI_ABORT_CODE"
  fi
  section '04 / Execute the reviewed plan'
  execute_plan
  stop_sudo_keepalive
  final_summary
  ui_results
  trap - ERR
  (( FAIL_COUNT == 0 ))
}

# Sourceable by sandbox tests without parsing arguments, installing traps, or writing.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
