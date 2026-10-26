#!/usr/bin/env bash
# One read-only plan for CLI, guided review, execution, and verification.

PLAN_READY=0
PLAN_COMPONENTS=()
PLAN_LINKS=()
PLAN_OWNED_DIRS=()
PLAN_PHASES=()
PLAN_REQUIRED_OFFICIAL=()
PLAN_OFFICIAL=()
PLAN_AUR=()
PLAN_SYSTEM_SERVICES=()
PLAN_USER_SERVICES=()
PLAN_SOURCE_FILES=()
PLAN_COMMANDS=()
PLAN_CONFIG_ACTIONS=()
PLAN_SERVICE_ACTIONS=()
PLAN_MISSING_OFFICIAL=()
PLAN_MISSING_AUR=()
PLAN_INSTALLED_COUNT=0
PLAN_PACKAGE_STATE=unknown
PLAN_CONFLICT_COUNT=0
PLAN_SCOPE=''
declare -A PLAN_OPTIONS=()

validate_selection() {
  (( WITH_SHELL == 1 || CHANGE_SHELL == 0 )) || { arg_error '--change-shell requires the Zsh component (remove --no-shell)'; return 2; }
  (( ONLY_DOTFILES == 0 || (WITH_GDM == 0 && WITH_WWAN == 0) )) || { arg_error 'GDM/WWAN require system installation, not dotfiles-only'; return 2; }
  (( LINK_ONLY == 0 || (CHANGE_SHELL == 0 && SET_DEFAULTS == 0) )) || { arg_error '--link-only cannot change your shell or application defaults'; return 2; }
}

selected_packages() {
  SEL_OFFICIAL=("${PACMAN_CORE[@]}")
  [[ "$WITH_SHELL" -eq 0 ]] || SEL_OFFICIAL+=("${PACMAN_SHELL[@]}")
  [[ "$PROFILE" != full ]] || SEL_OFFICIAL+=("${PACMAN_EXTRA[@]}")
  SEL_AUR=()
  if [[ "$NO_AUR" -eq 0 ]]; then
    SEL_AUR=("${AUR_CORE[@]}")
    [[ "$PROFILE" != full ]] || SEL_AUR+=("${AUR_EXTRA[@]}")
  fi
  [[ "$WITH_GDM" -eq 0 ]] || SEL_OFFICIAL+=(gdm)
  [[ "$WITH_WWAN" -eq 0 ]] || SEL_OFFICIAL+=(modemmanager modem-manager-gui usb_modeswitch)
}

selected_services() {
  SYSTEM_SERVICES=(NetworkManager.service bluetooth.service power-profiles-daemon.service)
  [[ "$WITH_GDM" -eq 0 ]] || SYSTEM_SERVICES+=(gdm.service)
  [[ "$WITH_WWAN" -eq 0 ]] || SYSTEM_SERVICES+=(ModemManager.service wwan-enable.service)
}

build_plan() {
  validate_selection || return 2
  local option entry
  PLAN_READY=0
  PLAN_OPTIONS=()
  for option in PROFILE ONLY_DOTFILES LINK_ONLY CHECK_ONLY DRY_RUN NO_AUR WITH_SHELL WITH_GDM WITH_WWAN CHANGE_SHELL SET_DEFAULTS; do
    PLAN_OPTIONS["$option"]="${!option}"
  done
  PLAN_COMPONENTS=(desktop palette)
  [[ "$WITH_SHELL" -eq 0 ]] || PLAN_COMPONENTS+=(shell)
  [[ "$NO_AUR" -eq 1 ]] || PLAN_COMPONENTS+=(aur)
  [[ "$PROFILE" != full ]] || PLAN_COMPONENTS+=(extras)
  [[ "$WITH_GDM" -eq 0 ]] || PLAN_COMPONENTS+=(gdm)
  [[ "$WITH_WWAN" -eq 0 ]] || PLAN_COMPONENTS+=(wwan)
  selected_packages
  selected_services
  PLAN_OFFICIAL=("${SEL_OFFICIAL[@]}")
  PLAN_AUR=("${SEL_AUR[@]}")
  PLAN_REQUIRED_OFFICIAL=("${PACMAN_CORE[@]}")
  [[ "$WITH_SHELL" -eq 0 ]] || PLAN_REQUIRED_OFFICIAL+=("${PACMAN_SHELL[@]}")
  [[ "$WITH_GDM" -eq 0 ]] || PLAN_REQUIRED_OFFICIAL+=(gdm)
  [[ "$WITH_WWAN" -eq 0 ]] || PLAN_REQUIRED_OFFICIAL+=(modemmanager modem-manager-gui usb_modeswitch)
  PLAN_LINKS=()
  PLAN_OWNED_DIRS=()
  for entry in "${LINK_MAP[@]}"; do
    if [[ "$WITH_SHELL" -eq 0 ]]; then
      case "$entry" in
        '.config/zsh:zsh') continue ;;
        '.config/matugen:matugen')
          # Keep the canonical repo config intact. A private runtime config omits
          # the shell template, including for later wallpaper/theme changes.
          PLAN_OWNED_DIRS+=(.config/matugen)
          PLAN_LINKS+=('.config/matugen/templates:matugen/templates')
          continue ;;
      esac
    fi
    PLAN_LINKS+=("$entry")
  done
  PLAN_SOURCE_FILES=(hyprland/hyprland.lua hyprland/scripts/palette.py waybar/config.jsonc matugen/config.toml waypaper/config.ini.example)
  [[ "$WITH_SHELL" -eq 0 ]] || PLAN_SOURCE_FILES+=(zsh/.zshrc)
  PLAN_COMMANDS=(Hyprland kitty nautilus chromium imv rofi hyprctl hyprlock hypridle hyprsunset
    waybar swaync swaync-client nm-applet awww awww-daemon grim slurp wl-copy playerctl wpctl
    brightnessctl matugen magick python3 pavucontrol bluetoothctl nmcli checkupdates jq notify-send
    xdg-open xdg-user-dirs-update git)
  [[ "$WITH_SHELL" -eq 0 ]] || PLAN_COMMANDS+=(zsh)
  [[ "$NO_AUR" -eq 1 ]] || PLAN_COMMANDS+=(waypaper)
  if [[ "$PROFILE" == full && "$NO_AUR" -eq 0 ]]; then PLAN_COMMANDS+=(spotify); fi
  PLAN_SYSTEM_SERVICES=()
  PLAN_USER_SERVICES=()
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    PLAN_SYSTEM_SERVICES=("${SYSTEM_SERVICES[@]}")
    PLAN_USER_SERVICES=("${USER_SERVICES[@]}")
  fi
  PLAN_SCOPE='Desktop, packages, and services'
  [[ "$ONLY_DOTFILES" -eq 0 ]] || PLAN_SCOPE='Desktop configs and palette; no system packages/services'
  [[ "$LINK_ONLY" -eq 0 ]] || PLAN_SCOPE='Selected config links only; no downloads or palette generation'
  [[ "$CHECK_ONLY" -eq 0 ]] || PLAN_SCOPE='Read-only verification; no repairs'
  PLAN_PHASES=(phase_preflight)
  if [[ "$CHECK_ONLY" -eq 0 ]]; then
    if [[ "$ONLY_DOTFILES" -eq 0 ]]; then PLAN_PHASES+=(phase_base phase_packages phase_services); fi
    PLAN_PHASES+=(phase_dotfiles)
    if [[ "$LINK_ONLY" -eq 0 ]]; then
      [[ "$WITH_SHELL" -eq 0 ]] || PLAN_PHASES+=(phase_shell)
      PLAN_PHASES+=(phase_theming)
    fi
  fi
  PLAN_PHASES+=(phase_verify)
  TOTAL_PHASES=${#PLAN_PHASES[@]}
  PLAN_READY=1
}

# Restore reviewed choices before applying. Presentation never executes a second,
# independently assembled set of actions.
activate_plan() {
  [[ "$PLAN_READY" -eq 1 ]] || { fail 'No reviewed installation plan is available'; return 1; }
  local option
  for option in "${!PLAN_OPTIONS[@]}"; do printf -v "$option" '%s' "${PLAN_OPTIONS[$option]}"; done
}

private_matugen_root() {
  local root="$HOME/.config/matugen"
  [[ ! -L "$root" && -d "$root" && -f "$root/.hypryoru-managed" ]] &&
    [[ "$(<"$root/.hypryoru-managed")" == "$DOTFILES_ROOT" ]]
}

inspect_plan() {
  local installed='' package entry target source root nested state
  local -A present=()
  PLAN_MISSING_OFFICIAL=()
  PLAN_MISSING_AUR=()
  PLAN_INSTALLED_COUNT=0
  PLAN_PACKAGE_STATE=unknown
  if [[ "${PLAN_OPTIONS[ONLY_DOTFILES]}" -eq 0 && "${PLAN_OPTIONS[CHECK_ONLY]}" -eq 0 ]]; then
    if command -v pacman >/dev/null 2>&1 && installed=$(pacman -Qq 2>/dev/null); then
      PLAN_PACKAGE_STATE=known
      while IFS= read -r package; do [[ -z "$package" ]] || present["$package"]=1; done <<<"$installed"
    fi
    for package in "${PLAN_OFFICIAL[@]}"; do
      if [[ -n "${present[$package]+yes}" ]]; then PLAN_INSTALLED_COUNT=$((PLAN_INSTALLED_COUNT + 1))
      else PLAN_MISSING_OFFICIAL+=("$package"); fi
    done
    for package in "${PLAN_AUR[@]}"; do
      if [[ -n "${present[$package]+yes}" ]]; then PLAN_INSTALLED_COUNT=$((PLAN_INSTALLED_COUNT + 1))
      else PLAN_MISSING_AUR+=("$package"); fi
    done
  fi
  PLAN_CONFIG_ACTIONS=()
  PLAN_CONFLICT_COUNT=0
  for root in "${PLAN_OWNED_DIRS[@]}"; do
    target="$HOME/$root"
    if private_matugen_root; then PLAN_CONFIG_ACTIONS+=("REFRESH owned private palette config if changed; preserve edits first: $target/config.toml")
    elif [[ -e "$target" || -L "$target" ]]; then
      PLAN_CONFIG_ACTIONS+=("PRESERVE + REPLACE with private palette config: $target")
      PLAN_CONFLICT_COUNT=$((PLAN_CONFLICT_COUNT + 1))
    else PLAN_CONFIG_ACTIONS+=("CREATE private palette config: $target"); fi
  done
  for entry in "${PLAN_LINKS[@]}"; do
    target="$HOME/${entry%%:*}"; source="$DOTFILES_ROOT/${entry#*:}"
    nested=0
    for root in "${PLAN_OWNED_DIRS[@]}"; do
      if [[ "$target" == "$HOME/$root/"* ]] && ! private_matugen_root; then nested=1; fi
    done
    if [[ "$nested" -eq 0 && -L "$target" && "$target" -ef "$source" ]]; then
      PLAN_CONFIG_ACTIONS+=("KEEP link: $target")
    elif [[ "$nested" -eq 0 ]] && [[ -e "$target" || -L "$target" ]]; then
      PLAN_CONFIG_ACTIONS+=("PRESERVE + LINK: $target -> $source")
      PLAN_CONFLICT_COUNT=$((PLAN_CONFLICT_COUNT + 1))
    else PLAN_CONFIG_ACTIONS+=("LINK: $target -> $source"); fi
  done
  if [[ "${PLAN_OPTIONS[WITH_SHELL]}" -eq 1 ]]; then
    PLAN_CONFIG_ACTIONS+=('ENSURE managed ZDOTDIR block; preserve other ~/.zshenv statements')
  else PLAN_CONFIG_ACTIONS+=('LEAVE ~/.config/zsh, ~/.zshenv, frameworks, and login shell untouched'); fi
  PLAN_SERVICE_ACTIONS=()
  for entry in "${PLAN_SYSTEM_SERVICES[@]}"; do
    state=$(systemctl is-enabled "$entry" 2>/dev/null || true)
    case "$state" in
      enabled|enabled-runtime|alias|static|indirect|generated) PLAN_SERVICE_ACTIONS+=("KEEP $entry ($state)") ;;
      masked|masked-runtime) PLAN_SERVICE_ACTIONS+=("LEAVE MASKED $entry") ;;
      *)
        if [[ "$entry" == NetworkManager.service ]] && { service_in_use systemd-networkd.service || service_in_use dhcpcd.service; }; then
          PLAN_SERVICE_ACTIONS+=("LEAVE $entry; another network provider is in use")
        elif [[ "$entry" == power-profiles-daemon.service ]] && service_in_use tlp.service; then
          PLAN_SERVICE_ACTIONS+=("LEAVE $entry; TLP is in use")
        else PLAN_SERVICE_ACTIONS+=("ENABLE $entry for a future boot; never start/restart it here"); fi ;;
    esac
  done
  for entry in "${PLAN_USER_SERVICES[@]}"; do PLAN_SERVICE_ACTIONS+=("ENSURE user unit $entry (respect masks/static units)"); done
}

render_palette_config() {
  local line section='' pattern='^\[([^]]+)\]'
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ $pattern ]]; then section="${BASH_REMATCH[1]}"; fi
    if [[ "${PLAN_OPTIONS[WITH_SHELL]:-$WITH_SHELL}" -eq 0 && "$section" == templates.shell ]]; then continue; fi
    printf '%s\n' "$line"
  done <"$DOTFILES_ROOT/matugen/config.toml"
}

palette_outputs() {
  local line path pattern='^[[:space:]]*output_path[[:space:]]*=[[:space:]]*"([^"]+)"'
  while IFS= read -r line; do
    [[ "$line" =~ $pattern ]] || continue
    path="${BASH_REMATCH[1]}"
    if [[ "$path" == '~/'* ]]; then printf '%s/%s\n' "$HOME" "${path#\~/}"; else printf '%s\n' "$path"; fi
  done < <(render_palette_config)
}
