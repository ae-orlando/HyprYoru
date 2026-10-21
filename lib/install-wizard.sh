#!/usr/bin/env bash
# Optional Gum widgets and equivalent numbered prompts. No package installation.

UI_REPLY=''
UI_SELECTED=()
UI_ABORT_CODE=0
UI_COMPONENT_SHELL='Zsh setup (config + plugins + prompt)'
UI_COMPONENT_AUR='Wallpaper picker + icon/cursor themes (AUR)'
UI_COMPONENT_EXTRAS='Extra apps + development tools'
UI_OPTION_GDM='GDM graphical login'
UI_OPTION_WWAN='Fibocom WWAN modem service'
UI_OPTION_LOGIN='Use Zsh as my account login shell'
UI_OPTION_DEFAULTS='Apply application defaults and GTK preferences'

select_ui_backend() {
  UI_BACKEND=plain
  UI_SESSION=0
  if [[ "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 && "$CHECK_ONLY" -eq 0 && "$QUIET" -eq 0 && -t 0 && -t 1 ]]; then UI_SESSION=1; fi
  [[ "$UI_SESSION" -eq 1 && "$UI_MODE" != plain && "${TERM:-}" != dumb ]] || return 0
  local capabilities='' size rows columns
  size=$(stty size 2>/dev/null || true)
  read -r rows columns <<<"$size"
  if [[ ! "$rows" =~ ^[0-9]+$ || ! "$columns" =~ ^[0-9]+$ ]] || (( rows < 12 || columns < 50 )); then
    say 'Using numbered prompts for this small or unreported terminal size.'
    return 0
  fi
  if command -v gum >/dev/null 2>&1; then capabilities=$(gum choose --help 2>/dev/null || true); fi
  if [[ "$capabilities" == *--no-limit* && "$capabilities" == *--selected* && "$capabilities" == *--output-delimiter* ]]; then
    UI_BACKEND=gum
  else
    say 'Using numbered prompts. Gum is optional and will not be installed automatically.'
  fi
}

gum_run() {
  local -a environment=(env GUM_CHOOSE_CURSOR_FOREGROUND=117 GUM_CHOOSE_HEADER_FOREGROUND=213 GUM_CHOOSE_SELECTED_FOREGROUND=117)
  [[ -n "$C_RESET" ]] || environment+=(NO_COLOR=1)
  "${environment[@]}" gum "$@"
}

ui_closed() {
  local code="${1:-1}"
  UI_ABORT_CODE=0
  if [[ "$code" -eq 130 ]]; then UI_ABORT_CODE=130
  elif [[ "$code" -ne 1 ]]; then
    UI_ABORT_CODE=1
    if [[ "$LOG_ENABLED" -eq 1 || "${COMPLETED_PHASES:-0}" -gt 0 ]]; then
      _term err 'The menu could not complete; the installation result above is unchanged.'
    else
      _term err 'The menu could not complete. No installation will start.'
    fi
  fi
  return 1
}

# Set UI_REPLY in this shell, rather than losing state in command substitution.
ui_choose() {
  local title="$1"; shift
  local -a choices=("$@")
  local answer index height=${#choices[@]} found=0 code
  UI_REPLY=''
  (( height <= 10 )) || height=10
  if [[ "$UI_BACKEND" == gum ]]; then
    if answer=$(gum_run choose --header "$title" --height "$height" --limit 1 --selected '' --cursor '> ' --output-delimiter $'\n' -- "${choices[@]}"); then
      for index in "${!choices[@]}"; do [[ "$answer" != "${choices[$index]}" ]] || found=1; done
      if [[ "$found" -eq 0 ]]; then ui_closed 2; return 1; fi
      UI_REPLY="$answer"
      return 0
    else code=$?; ui_closed "$code"; return 1; fi
  fi
  section "$title"
  for index in "${!choices[@]}"; do field "[$((index + 1))]" "${choices[$index]}"; done
  while true; do
    if ! IFS= read -r -p '    Choose [1], or q to cancel: ' answer; then ui_closed 1; return 1; fi
    case "$answer" in
      q|Q) ui_closed 1; return 1 ;;
      '') answer=1 ;;
    esac
    if [[ "$answer" =~ ^[1-9][0-9]*$ && ${#answer} -le 3 ]]; then
      index=$((10#$answer - 1))
      if (( index < ${#choices[@]} )); then UI_REPLY="${choices[$index]}"; return 0; fi
    fi
    _term err "    Choose a number from 1 to ${#choices[@]}, or q to cancel."
  done
}

ui_multiselect() {
  local title="$1"
  local -n initial_selection="$2" available_choices="$3"
  local choice answer index selected_csv='' code valid
  local -a indices=()
  local -A selected=()
  UI_SELECTED=()
  for choice in "${initial_selection[@]}"; do selected["$choice"]=1; done
  (( ${#available_choices[@]} > 0 )) || return 0
  if [[ "$UI_BACKEND" == gum ]]; then
    # Gum treats a one-item no-limit list as single-choice and selects it on
    # Enter even after untoggling. Use an explicit Include/Skip pair instead.
    if (( ${#available_choices[@]} == 1 )); then
      choice="${available_choices[0]}"
      if [[ -n "${selected[$choice]+yes}" ]]; then ui_choose "$title" "Include $choice" "Skip $choice" || return 1
      else ui_choose "$title" "Skip $choice" "Include $choice" || return 1; fi
      [[ "$UI_REPLY" != "Include $choice" ]] || UI_SELECTED+=("$choice")
      return 0
    fi
    for choice in "${initial_selection[@]}"; do selected_csv+="${selected_csv:+,}$choice"; done
    if answer=$(gum_run choose --no-limit --selected "$selected_csv" --height 8 --header "$title" \
      --cursor '> ' --cursor-prefix '[ ] ' --selected-prefix '[x] ' --unselected-prefix '[ ] ' \
      --output-delimiter $'\n' -- "${available_choices[@]}"); then
      while IFS= read -r choice; do
        [[ -n "$choice" ]] || continue
        valid=0
        for answer in "${available_choices[@]}"; do [[ "$choice" != "$answer" ]] || valid=1; done
        [[ "$valid" -eq 1 ]] || { ui_closed 2; return 1; }
        UI_SELECTED+=("$choice")
      done <<<"$answer"
      return 0
    else code=$?; ui_closed "$code"; return 1; fi
  fi
  while true; do
    section "$title"
    for index in "${!available_choices[@]}"; do
      choice="${available_choices[$index]}"
      if [[ -n "${selected[$choice]+yes}" ]]; then field "[$((index + 1))] [x]" "$choice"
      else field "[$((index + 1))] [ ]" "$choice"; fi
    done
    if ! IFS= read -r -p '    Toggle numbers (e.g. 1 3), Enter to continue, q to cancel: ' answer; then ui_closed 1; return 1; fi
    case "$answer" in
      '') break ;;
      q|Q) ui_closed 1; return 1 ;;
    esac
    IFS=' ' read -r -a indices <<<"${answer//,/ }"
    valid=1
    for index in "${indices[@]}"; do
      if [[ ! "$index" =~ ^[1-9][0-9]*$ || ${#index} -gt 3 ]]; then valid=0; break; fi
      (( 10#$index <= ${#available_choices[@]} )) || { valid=0; break; }
    done
    if [[ "$valid" -eq 0 || ${#indices[@]} -eq 0 ]]; then _term err '    Enter valid option numbers, or press Enter to continue.'; continue; fi
    for index in "${indices[@]}"; do
      choice="${available_choices[$((10#$index - 1))]}"
      if [[ -n "${selected[$choice]+yes}" ]]; then unset 'selected[$choice]'; else selected["$choice"]=1; fi
    done
  done
  for choice in "${available_choices[@]}"; do [[ -z "${selected[$choice]+yes}" ]] || UI_SELECTED+=("$choice"); done
}

ui_welcome() {
  ui_choose '01 / Welcome — what would you like to do?' \
    'Recommended installation' 'Customize installation' 'Preview changes' 'Check existing setup' 'Exit' || return 1
  case "$UI_REPLY" in
    'Customize installation') ui_customize || return 1 ;;
    'Preview changes') DRY_RUN=1 ;;
    'Check existing setup') CHECK_ONLY=1 ;;
    Exit) return 1 ;;
  esac
}

ui_customize() {
  local choice
  local -a options=("$UI_COMPONENT_SHELL") defaults=()
  section '02 / Components'
  say 'Desktop configuration is required. Normal installs also generate its required palette.'
  say 'Unchecked items are left alone, never uninstalled or disabled.'
  [[ "$WITH_SHELL" -eq 0 ]] || defaults+=("$UI_COMPONENT_SHELL")
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    options+=("$UI_COMPONENT_AUR" "$UI_COMPONENT_EXTRAS")
    [[ "$NO_AUR" -eq 1 ]] || defaults+=("$UI_COMPONENT_AUR")
    [[ "$PROFILE" != full ]] || defaults+=("$UI_COMPONENT_EXTRAS")
    say 'AUR choices execute third-party build scripts. Extra apps may need licensed downloads.'
  fi
  ui_multiselect 'Select optional components' defaults options || return 1
  WITH_SHELL=0
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then NO_AUR=1; PROFILE=core; fi
  for choice in "${UI_SELECTED[@]}"; do
    case "$choice" in
      "$UI_COMPONENT_SHELL") WITH_SHELL=1 ;;
      "$UI_COMPONENT_AUR") NO_AUR=0 ;;
      "$UI_COMPONENT_EXTRAS") PROFILE=full ;;
    esac
  done
  if [[ "$WITH_SHELL" -eq 0 ]]; then CHANGE_SHELL=0; fi
  options=(); defaults=()
  if [[ "$ONLY_DOTFILES" -eq 0 ]]; then
    options+=("$UI_OPTION_GDM" "$UI_OPTION_WWAN")
    [[ "$WITH_GDM" -eq 0 ]] || defaults+=("$UI_OPTION_GDM")
    [[ "$WITH_WWAN" -eq 0 ]] || defaults+=("$UI_OPTION_WWAN")
  fi
  if [[ "$LINK_ONLY" -eq 0 ]]; then
    if [[ "$WITH_SHELL" -eq 1 ]]; then
      options+=("$UI_OPTION_LOGIN")
      [[ "$CHANGE_SHELL" -eq 0 ]] || defaults+=("$UI_OPTION_LOGIN")
    fi
    options+=("$UI_OPTION_DEFAULTS")
    [[ "$SET_DEFAULTS" -eq 0 ]] || defaults+=("$UI_OPTION_DEFAULTS")
  fi
  if (( ${#options[@]} > 0 )); then
    ui_multiselect 'Optional system and preference changes' defaults options || return 1
    WITH_GDM=0; WITH_WWAN=0; CHANGE_SHELL=0; SET_DEFAULTS=0
    for choice in "${UI_SELECTED[@]}"; do
      case "$choice" in
        "$UI_OPTION_GDM") WITH_GDM=1 ;;
        "$UI_OPTION_WWAN") WITH_WWAN=1 ;;
        "$UI_OPTION_LOGIN") CHANGE_SHELL=1 ;;
        "$UI_OPTION_DEFAULTS") SET_DEFAULTS=1 ;;
      esac
    done
  fi
  validate_selection
}

show_plan() {
  local disk components='Desktop + palette'
  [[ "${PLAN_OPTIONS[WITH_SHELL]}" -eq 0 ]] || components+=' + Zsh'
  [[ "${PLAN_OPTIONS[NO_AUR]}" -eq 1 ]] || components+=' + AUR assets'
  [[ "${PLAN_OPTIONS[PROFILE]}" != full ]] || components+=' + extra apps'
  section '03 / Review your plan'
  field 'Scope' "$PLAN_SCOPE"
  field 'Components' "$components"
  if [[ "${PLAN_OPTIONS[ONLY_DOTFILES]}" -eq 0 && "${PLAN_OPTIONS[CHECK_ONLY]}" -eq 0 ]]; then
    field 'Selected' "${#PLAN_OFFICIAL[@]} official + ${#PLAN_AUR[@]} AUR packages"
    if [[ "$PLAN_PACKAGE_STATE" == known ]]; then
      field 'To install' "${#PLAN_MISSING_OFFICIAL[@]} official + ${#PLAN_MISSING_AUR[@]} AUR; $PLAN_INSTALLED_COUNT already present"
    else field 'To install' 'Local package state unavailable; checked again before package installation'; fi
    say 'The package phase also performs a full Arch upgrade, including installed system packages.'
  else field 'Packages' 'No package installation in this mode'; fi
  field 'Config links' "${#PLAN_LINKS[@]} selected / $PLAN_CONFLICT_COUNT existing paths to preserve"
  field 'Repository' "$DOTFILES_ROOT"
  field 'Phases' "${#PLAN_PHASES[@]} / same plan used for review and execution"
  if [[ "${PLAN_OPTIONS[DRY_RUN]}" -eq 0 && "${PLAN_OPTIONS[CHECK_ONLY]}" -eq 0 ]]; then
    field 'Backup target' "$BACKUP_DIR"
    field 'Log' "$LOG_FILE"
  else field 'Storage' 'Read-only: no logs, locks, backups, or config changes'; fi
  if [[ "${PLAN_OPTIONS[WITH_GDM]}" -eq 1 ]]; then field 'Login manager' 'Enable GDM only if no other manager owns login'
  else field 'Login manager' 'Keep existing setup'; fi
  [[ "${PLAN_OPTIONS[WITH_WWAN]}" -eq 0 ]] || field 'WWAN' 'Install the source machine-specific Fibocom unit'
  if [[ "${PLAN_OPTIONS[CHANGE_SHELL]}" -eq 1 ]]; then field 'Login shell' 'Change account shell to Zsh'; else field 'Login shell' 'Keep existing account shell'; fi
  if [[ "${PLAN_OPTIONS[SET_DEFAULTS]}" -eq 1 ]]; then field 'Preferences' 'Apply installed-app MIME defaults and GTK preferences'
  else field 'Preferences' 'Keep existing defaults and GTK preferences'; fi
  if [[ "${PLAN_OPTIONS[WITH_SHELL]}" -eq 0 ]]; then say 'Zsh stays untouched; a private Matugen config excludes its shell output.'; fi
  if [[ "${PLAN_OPTIONS[NO_AUR]}" -eq 1 ]]; then say 'Skipping AUR does not provide Waypaper (SUPER+W) or the supplied cursor/icon themes.'; fi
  say 'Kernels/bootloaders/GPU drivers are not added. Server/firewall services are not enabled.'
  disk=$(df -h -- "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || true)
  [[ -z "$disk" ]] || field 'Free in HOME' "$disk"
}

ui_view_text() {
  local title="$1" text="$2"
  section "$title"
  if [[ "$UI_BACKEND" == gum ]]; then printf '%s\n' "$text" | gum_run pager || true
  else _term out "$text"; fi
}

ui_view_file() {
  local title="$1" file="$2"
  [[ -r "$file" ]] || { say "Not available: $file"; return 0; }
  section "$title / $file"
  if [[ "$UI_BACKEND" == gum ]]; then gum_run pager <"$file" || true
  elif command -v less >/dev/null 2>&1 && [[ "${TERM:-}" != dumb ]]; then
    LESSHISTFILE=/dev/null LESSSECURE=1 less -FRX -- "$file" || true
  else cat -- "$file"; fi
}

plan_package_details() {
  printf 'OFFICIAL (%s)\n' "${#PLAN_OFFICIAL[@]}"
  printf '  %s\n' "${PLAN_OFFICIAL[@]}"
  printf '\nAUR (%s)\n' "${#PLAN_AUR[@]}"
  if (( ${#PLAN_AUR[@]} > 0 )); then printf '  %s\n' "${PLAN_AUR[@]}"; fi
  printf '\nUnchecked packages are not removed. Counts do not include resolved dependencies.\n'
}

prepare_wizard_plan() {
  if [[ "$UI_SESSION" -eq 1 && "$SCOPE_EXPLICIT" -eq 0 ]]; then ui_welcome || return 1; fi
  while true; do
    if ! build_plan; then UI_ABORT_CODE=2; return 1; fi
    inspect_plan
    show_plan
    [[ "$UI_SESSION" -eq 1 ]] || return 0
    local action='Install this plan'
    [[ "$DRY_RUN" -eq 0 ]] || action='Run preview (no changes)'
    [[ "$CHECK_ONLY" -eq 0 ]] || action='Run read-only checks'
    ui_choose 'Review complete — choose an action' 'Cancel' "$action" 'Customize components' \
      'View package list' 'View config actions' 'View service actions' || return 1
    case "$UI_REPLY" in
      Cancel) return 1 ;;
      "$action") return 0 ;;
      'Customize components') ui_customize || return 1 ;;
      'View package list') ui_view_text 'Selected package manifests' "$(plan_package_details)" ;;
      'View config actions') ui_view_text 'Config changes and preservation' "$(printf '%s\n' "${PLAN_CONFIG_ACTIONS[@]}")" ;;
      'View service actions') ui_view_text 'Selected service actions' "$(printf '%s\n' "${PLAN_SERVICE_ACTIONS[@]}")" ;;
    esac
  done
}

run_reviewed_checks() {
  local -a args=(--check --ui plain --profile "${PLAN_OPTIONS[PROFILE]}")
  [[ "${PLAN_OPTIONS[NO_AUR]}" -eq 0 ]] || args+=(--no-aur)
  [[ "${PLAN_OPTIONS[WITH_SHELL]}" -eq 1 ]] || args+=(--no-shell)
  if [[ "${PLAN_OPTIONS[LINK_ONLY]}" -eq 1 ]]; then args+=(--link-only)
  elif [[ "${PLAN_OPTIONS[ONLY_DOTFILES]}" -eq 1 ]]; then args+=(--only-dotfiles); fi
  [[ "${PLAN_OPTIONS[WITH_GDM]}" -eq 0 ]] || args+=(--with-gdm)
  [[ "${PLAN_OPTIONS[WITH_WWAN]}" -eq 0 ]] || args+=(--with-wwan)
  if ! bash "$DOTFILES_ROOT/install.sh" "${args[@]}"; then say 'Checks still need attention; the original installation result is unchanged.'; fi
}

ui_results() {
  [[ "$UI_SESSION" -eq 1 ]] || return 0
  local notes
  local -a choices=()
  while true; do
    choices=('Exit' 'View warnings and failures')
    [[ "$LOG_ENABLED" -eq 0 ]] || choices+=('View full log')
    [[ "$BACKUP_READY" -eq 0 ]] || choices+=('Inspect backup manifest')
    [[ "$PLAN_READY" -eq 0 ]] || choices+=('Run read-only verification')
    ui_choose '05 / Results — next steps' "${choices[@]}" || return 0
    case "$UI_REPLY" in
      Exit) return 0 ;;
      'View warnings and failures')
        notes='No warnings or failures.'
        if (( ${#WARN_MESSAGES[@]} + ${#FAIL_MESSAGES[@]} > 0 )); then notes=$(printf '%s\n' "${WARN_MESSAGES[@]}" "${FAIL_MESSAGES[@]}"); fi
        ui_view_text 'Notes' "$notes" ;;
      'View full log') ui_view_file 'Installation log' "$LOG_FILE" ;;
      'Inspect backup manifest') ui_view_file 'Backups (inspect before restoring)' "$BACKUP_DIR/manifest.tsv" ;;
      'Run read-only verification') run_reviewed_checks ;;
    esac
  done
}
