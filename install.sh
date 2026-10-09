#!/usr/bin/env bash
# Dotfiles reproducer — Arch Linux + GDM + Hyprland (Lua) fresh-system install.
#
# Reapplies this repo exactly as it runs on the source machine:
#   Hyprland Lua (hyprland.lua + 9 modules), matugen palette hub, waybar,
#   swaync, rofi type-6/style-9, kitty, btop, gtk3/4, qt6ct, waypaper (backend=none),
#   zsh (OMZ + p10k), fastfetch, fonts, services, mime, gsettings.
#
# Usage:
#   ./install.sh [--profile core|full] [--only-dotfiles] [--no-aur] [--dry-run] [--yes] [--help]
#
# Profiles:
#   full (default) — every explicit package from the source machine (exact repro).
#   core           — minimum to boot Hyprland with a working config (no user apps).
#
# Safety: idempotent, backs up ~/.config + ~/.zshenv, supports --dry-run.
# Arch-only. Run as a normal user with sudo access (not as root).
set -euo pipefail

DOTFILES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/dotfiles-install.log"
BACKUP_DIR="$HOME/.local/state/dotfiles-backup-$(date +%Y%m%d-%H%M%S)"

PROFILE="full"
ONLY_DOTFILES=0
NO_AUR=0
DRY_RUN=0
ASSUME_YES=0

log()  { echo "[install] $*" | tee -a "$LOG_FILE"; }
warn() { echo "[install][WARN] $*" | tee -a "$LOG_FILE" >&2; }
run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    echo "[run] $*" >>"$LOG_FILE"
    eval "$@"
  fi
}

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --profile core|full   core = bootable Hyprland minimum, full = exact source machine (default: full)
  --only-dotfiles       skip pacman/AUR/services, only link configs + shell + theming
  --no-aur              skip AUR packages
  --dry-run             print actions without changing anything
  --yes                 assume yes (non-interactive; passes --noconfirm)
  --help                this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --only-dotfiles) ONLY_DOTFILES=1; shift ;;
    --no-aur) NO_AUR=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done
[[ "$PROFILE" == "core" || "$PROFILE" == "full" ]] || { echo "Invalid --profile: $PROFILE" >&2; exit 1; }

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
  fastfetch btop eza fzf fd bat yazi neovim tmux
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
  log "Phase 0: preflight (profile=$PROFILE only-dotfiles=$ONLY_DOTFILES dry-run=$DRY_RUN)"
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "Do not run as root; run as your user (sudo is used internally)." >&2
    exit 1
  fi
  if [[ ! -f /etc/arch-release ]]; then
    echo "Arch Linux only (no /etc/arch-release). Aborting." >&2
    exit 1
  fi
  if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    : >"$LOG_FILE" || true
  fi
  log "Dotfiles root: $DOTFILES_ROOT"
  for d in hyprland waybar rofi kitty matugen swaync zsh waypaper btop fastfetch gtk-setting qt6ct; do
    [[ -d "$DOTFILES_ROOT/$d" ]] || { echo "Missing dir in repo: $d" >&2; exit 1; }
  done
  # Backup anything we are about to replace.
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] mkdir -p $BACKUP_DIR (backup .config entries + .zshenv)"
  else
    mkdir -p "$BACKUP_DIR"
    for entry in "${LINK_MAP[@]}"; do
      target="$HOME/${entry%%:*}"
      if [[ -e "$target" && ! -L "$target" ]]; then
        log "Backing up real dir/file $target"
        cp -a "$target" "$BACKUP_DIR/" 2>/dev/null || true
      fi
    done
    [[ -f "$HOME/.zshenv" ]] && cp -a "$HOME/.zshenv" "$BACKUP_DIR/" 2>/dev/null || true
    log "Backup dir: $BACKUP_DIR"
  fi
  if [[ "$ONLY_DOTFILES" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
    log "Skipping sudo check (only-dotfiles or dry-run needs no privilege)"
  elif ! sudo -v; then
    echo "sudo access required." >&2
    exit 1
  fi
  # Keep sudo alive in background (only when actually changing the system).
  if [[ "$DRY_RUN" -eq 0 && "$ONLY_DOTFILES" -eq 0 ]]; then
    (while true; do sudo -n true 2>/dev/null || break; sleep 50; done) &
    SUDO_KEEPALIVE_PID=$!
    trap 'kill $SUDO_KEEPALIVE_PID 2>/dev/null || true' EXIT
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
    run "sudo reflector --protocol https --latest 5 --sort age --save /etc/pacman.d/mirrorlist || true"
  else
    warn "reflector not installed yet; mirrors left as-is (reflector installed in step 2)"
  fi
}

ensure_aur_helper() {
  if command -v yay >/dev/null 2>&1; then
    log "AUR helper: yay found"
    return
  fi
  if command -v paru >/dev/null 2>&1; then
    log "AUR helper: paru found (yay missing — will use paru)"
    return
  fi
  log "Bootstrapping yay-bin from AUR"
  run "sudo pacman -S --needed --noconfirm base-devel git"
  run "rm -rf /tmp/yay-bin && git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin"
  run "sh -c 'cd /tmp/yay-bin && makepkg -si --noconfirm'"
}

aur_cmd() {
  if command -v yay >/dev/null 2>&1; then echo "yay"; else echo "paru"; fi
}

phase_base() {
  log "Phase 1: base system"
  ensure_pacman_conf
  ensure_reflector
  log "Full system upgrade (pacman -Syu)"
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    run "sudo pacman -Syu --noconfirm"
  else
    run "sudo pacman -Syu"
  fi
  ensure_aur_helper
}

# --------------------------------------------------------------------------
# 2. Packages
# --------------------------------------------------------------------------
phase_packages() {
  log "Phase 2: packages (profile=$PROFILE)"
  local official=("${PACMAN_CORE[@]}")
  local aur=("${AUR_CORE[@]}")
  if [[ "$PROFILE" == "full" ]]; then
    official+=("${PACMAN_EXTRA[@]}")
    aur+=("${AUR_EXTRA[@]}")
  fi
  log "Installing ${#official[@]} official packages"
  # shellcheck disable=SC2086
  run "sudo pacman -S $PACMAN_FLAGS ${official[*]}"
  if [[ "$NO_AUR" -eq 1 ]]; then
    warn "Skipping AUR (--no-aur). Cursor/icon themes + waypaper will be missing."
    return
  fi
  local helper
  helper="$(aur_cmd)"
  log "Installing ${#aur[@]} AUR packages via $helper"
  # shellcheck disable=SC2086
  run "$helper -S $AUR_FLAGS ${aur[*]}"
}

# --------------------------------------------------------------------------
# 3. Services (incl. custom wwan-enable.service found on source machine)
# --------------------------------------------------------------------------
WWAN_UNIT_PATH="/etc/systemd/system/wwan-enable.service"
write_wwan_unit() {
  # Verbatim copy of the source machine's custom unit (Fibocom WWAN modem).
  if [[ -f "$WWAN_UNIT_PATH" ]] && grep -q "Fibocom WWAN Modem" "$WWAN_UNIT_PATH" 2>/dev/null; then
    log "wwan-enable.service already present"
    return
  fi
  log "Installing wwan-enable.service (custom unit from source machine)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] write $WWAN_UNIT_PATH"
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
  log "Phase 3: services"
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
    log "Link OK: $target"
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
  log "Phase 4: dotfiles"
  run "mkdir -p \"$HOME/.config\""
  for entry in "${LINK_MAP[@]}"; do
    link_one "${entry%%:*}" "${entry#*:}"
  done
  # ~/.zshenv must exist BEFORE first zsh start so ZDOTDIR resolves.
  log "Writing ~/.zshenv (ZDOTDIR)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo '[dry-run] write $HOME/.zshenv: export ZDOTDIR="$HOME/.config/zsh"'
  else
    printf 'export ZDOTDIR="$HOME/.config/zsh"\n' >"$HOME/.zshenv"
  fi
  # Executable bits: repo has 644 on two rofi launchers; binds.lua + swaync
  # invoke them directly, so force +x (fresh clones preserve 644 otherwise).
  log "Fixing executable bits on scripts"
  run "chmod +x \"$DOTFILES_ROOT/hyprland/scripts/\"*.sh \"$DOTFILES_ROOT/hyprland/whatsong.sh\""
  run "chmod +x \"$DOTFILES_ROOT/waybar/scripts/\"*.sh"
  run "chmod +x \"$DOTFILES_ROOT/rofi/launchers/\"*.sh \"$DOTFILES_ROOT/rofi/launchers/type-6/\"*.sh \"$DOTFILES_ROOT/rofi/launchers/rofi-bluetooth\""
  # Runtime dirs (matugen/set-wall.sh + waybar + swaync + qt6ct expect them).
  run "mkdir -p \"$HOME/Pictures/wallpapers\" \"$HOME/Pictures/Screenshots\""
  run "mkdir -p \"$HOME/.cache/matugen\" \"$HOME/.cache/hyprlock\" \"\${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-thumbs\""
  run "mkdir -p \"$HOME/.config/qt6ct/colors\" \"$HOME/.local/bin\" \"$HOME/.local/share/fonts\""
  # Seed wallpapers without overwriting the user's 229-file library.
  log "Seeding ~/Pictures/wallpapers from repo (no overwrite)"
  run "cp -n \"$DOTFILES_ROOT/hyprland/wallpapers/\"* \"$HOME/Pictures/wallpapers/\" 2>/dev/null || true"
  # XDG dirs + PROJECTS line (source had XDG_PROJECTS_DIR="$HOME/").
  run "xdg-user-dirs-update || true"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if ! grep -q "XDG_PROJECTS_DIR" "$HOME/.config/user-dirs.dirs" 2>/dev/null; then
      echo 'XDG_PROJECTS_DIR="$HOME/"' >>"$HOME/.config/user-dirs.dirs"
    fi
  else
    echo '[dry-run] ensure XDG_PROJECTS_DIR in ~/.config/user-dirs.dirs'
  fi
  # GTK bookmarks (gitignored user state — regenerate the 5 defaults).
  log "Writing gtk-3.0/bookmarks"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] write bookmarks (Documents Music Pictures Videos Downloads)"
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
    echo "[dry-run] write mimeapps.list"
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
  run "fc-cache -f >/dev/null 2>&1 || true"
  warn "rofi type-6/style-9 references ~/.config/rofi/images/i.jpg which does not exist (blank imagebox, harmless)."
  warn "waypaper stylesheet ~/.config/waypaper/style.css does not exist upstream-side; Waypaper uses its default (harmless)."
}

# --------------------------------------------------------------------------
# 5. Shell: oh-my-zsh + powerlevel10k + default shell
# --------------------------------------------------------------------------
phase_shell() {
  log "Phase 5: shell"
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    log "Installing oh-my-zsh (unattended)"
    run "sh -c \"\$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\" \"\" --unattended"
  else
    log "oh-my-zsh already present"
  fi
  local p10k_dir="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k"
  if [[ ! -d "$p10k_dir" ]]; then
    log "Installing powerlevel10k"
    run "git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \"$p10k_dir\""
  else
    log "powerlevel10k already present"
  fi
  if [[ "$SHELL" != "/usr/bin/zsh" && "$SHELL" != "/bin/zsh" ]]; then
    log "Setting default shell to zsh (needs password)"
    run "chsh -s /usr/bin/zsh || chsh -s /bin/zsh"
  fi
  run "zsh -n \"\$HOME/.config/zsh/.zshrc\" && echo 'zshrc syntax OK' || echo 'zshrc check skipped/failed'"
}

# --------------------------------------------------------------------------
# 6. Theming: one matugen run regenerates all 12 outputs + wallpaper
# --------------------------------------------------------------------------
phase_theming() {
  log "Phase 6: theming (matugen)"
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
    warn "matugen not installed; skipping palette generation"
    return
  fi
  log "Generating palette from $wall"
  run "matugen image \"$wall\" --mode dark --type scheme-tonal-spot --prefer closest-to-fallback || true"
}

# --------------------------------------------------------------------------
# 7. Verify (read-only; never fails the install, just reports)
# --------------------------------------------------------------------------
check_bin() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "  PASS  binary $1"
  else
    echo "  FAIL  binary missing: $1"
  fi
}

phase_verify() {
  log "Phase 7: verify"
  {
    echo "--- binaries referenced by binds/autostart/waybar/swaync ---"
    for b in kitty nautilus chromium spotify rofi hyprctl hyprlock hypridle hyprsunset \
      waybar swaync swaync-client nm-applet polkit-gnome-authentication-agent-1 awww-daemon \
      grim slurp wl-copy playerctl wpctl brightnessctl waypaper matugen \
      pavucontrol bluetoothctl nmcli checkupdates; do
      if [[ "$b" == "polkit-gnome-authentication-agent-1" ]]; then
        [[ -x /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 ]] && echo "  PASS  $b" || echo "  FAIL  $b"
      elif [[ "$b" == "awww-daemon" ]]; then
        command -v awww >/dev/null 2>&1 && echo "  PASS  awww (+daemon)" || echo "  FAIL  awww"
      else
        check_bin "$b"
      fi
    done
    echo "--- symlinks ---"
    for entry in "${LINK_MAP[@]}"; do
      target="$HOME/${entry%%:*}"
      if [[ -L "$target" ]]; then echo "  PASS  link $target"; else echo "  FAIL  not a symlink: $target"; fi
    done
    [[ -f "$HOME/.zshenv" ]] && echo "  PASS  ~/.zshenv" || echo "  FAIL  ~/.zshenv"
    echo "--- configs ---"
    [[ -f "$HOME/.config/hypr/hyprland.lua" ]] && echo "  PASS  hyprland.lua" || echo "  FAIL  hyprland.lua"
    [[ -f "$HOME/.config/waybar/config.jsonc" ]] && echo "  PASS  waybar config.jsonc" || echo "  FAIL  waybar config"
    [[ -f "$HOME/.config/matugen/config.toml" ]] && echo "  PASS  matugen config" || echo "  FAIL  matugen config"
    command -v zsh >/dev/null 2>&1 && zsh -n "$HOME/.config/zsh/.zshrc" 2>/dev/null && echo "  PASS  zshrc syntax" || echo "  WARN  zshrc syntax unchecked"
    command -v fc-list >/dev/null 2>&1 && fc-list | grep -i "JetBrainsMono Nerd" >/dev/null && echo "  PASS  JetBrains Nerd font" || echo "  WARN  JetBrains Nerd font not found"
    fc-list 2>/dev/null | grep -i "GoMono Nerd" >/dev/null && echo "  PASS  GoMono Nerd font" || echo "  WARN  GoMono Nerd font not found (hyprlock labels)"
    echo "--- services (enabled?) ---"
    for svc in gdm.service NetworkManager.service bluetooth.service power-profiles-daemon.service reflector.timer; do
      systemctl is-enabled "$svc" 2>/dev/null | grep "enabled" >/dev/null && echo "  PASS  $svc enabled" || echo "  WARN  $svc not enabled"
    done
    echo "Done. Reboot, pick Hyprland in GDM, then: SUPER+W wallpaper, SUPER+R waybar restart."
  } | tee -a "$LOG_FILE"
}

main() {
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
  log "=== done ==="
}

main "$@"
