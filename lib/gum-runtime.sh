#!/usr/bin/env bash
# Resolve an optional UI runtime before menus: system -> verified cache -> consented
# download. No sudo/package manager, PATH changes, or automatic network access.

GUM_BIN=''
GUM_CACHE_DIR=''
GUM_STAGE=''
GUM_CACHE_CHANGED=0
GUM_DOWNLOADED=0
GUM_DOWNLOAD_APPROVED=0

# Release archive hashes are pinned from upstream checksums.txt. Executable hashes
# were independently calculated from those verified archives. Never fetch a new
# checksum at runtime and then trust whatever executable accompanies it.
gum_runtime_release() {
  [[ "$(uname -s)" == Linux ]] || return 1
  GUM_VERSION=2.0.2
  case "$(uname -m)" in
    x86_64|amd64)
      GUM_ARCH=x86_64
      GUM_ARCHIVE_SHA256=d842e06d93dbed90af48cb8dd10698db6f22e331fc40346bb37bbc753109edc2
      GUM_BINARY_SHA256=279fb12ba05ebfec7ef77707c3874800b42acdc4d62f83d854b780d91db5e034 ;;
    aarch64|arm64)
      GUM_ARCH=arm64
      GUM_ARCHIVE_SHA256=8ebf8b54ec1e8c81f2bb58b59ff9b70998186a4d11375f0cf357b80e0ccfa1d5
      GUM_BINARY_SHA256=fc96f57edf6c01bbe7d69e43373ce15bcefb91032733d5c7f0864a0f898e661e ;;
    *) return 1 ;;
  esac
  GUM_ASSET="gum_${GUM_VERSION}_Linux_${GUM_ARCH}.tar.gz"
  GUM_ARCHIVE_MEMBER="gum_${GUM_VERSION}_Linux_${GUM_ARCH}/gum"
  GUM_DOWNLOAD_URL="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/${GUM_ASSET}"
}

gum_compatible() {
  local binary="$1" capabilities
  [[ -f "$binary" && -x "$binary" ]] || return 1
  capabilities=$("$binary" choose --help </dev/null 2>/dev/null) || return 1
  [[ "$capabilities" == *--no-limit* && "$capabilities" == *--selected* && "$capabilities" == *--output-delimiter* ]]
}

find_system_gum() {
  local candidate
  candidate=$(type -P gum) || return 1
  gum_compatible "$candidate" || return 1
  GUM_BIN="$candidate"
}

gum_hash_matches() {
  local file="$1" expected="$2" actual
  [[ -f "$file" && -r "$file" && ! -L "$file" ]] || return 1
  actual=$(sha256sum <"$file") || return 1
  [[ "${actual%% *}" == "$expected" ]]
}

gum_owned_permissions() {
  local path="$1" mode
  [[ -O "$path" ]] || return 1
  mode=$(stat -Lc '%a' -- "$path") || return 1
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] && (( (8#$mode & 0022) == 0 ))
}

gum_cache_safe() {
  local cache_home="${XDG_CACHE_HOME:-$HOME/.cache}" path
  [[ "$cache_home" == /* && "$cache_home" != *$'\n'* && "$cache_home" != *$'\t'* ]] || return 1
  GUM_CACHE_DIR="$cache_home/hypryoru/tools/gum/$GUM_VERSION/$GUM_ARCH"
  # An explicitly configured cache-home symlink is allowed if its target is
  # securely owned. App-managed children must never redirect through symlinks.
  for path in "$cache_home" "$cache_home/hypryoru" "$cache_home/hypryoru/tools" \
    "$cache_home/hypryoru/tools/gum" "$cache_home/hypryoru/tools/gum/$GUM_VERSION" "$GUM_CACHE_DIR"; do
    [[ -e "$path" || -L "$path" ]] || continue
    [[ -d "$path" ]] || return 1
    [[ "$path" == "$cache_home" || ! -L "$path" ]] || return 1
    gum_owned_permissions "$path" || return 1
  done
}

gum_download_consent() {
  local answer
  GUM_DOWNLOAD_APPROVED=0
  say "Preparing enhanced interface: pinned Gum $GUM_VERSION for Linux/$GUM_ARCH."
  say "Download from GitHub into $GUM_CACHE_DIR (no sudo or system package changes)."
  say 'Both the archive and executable must match the hashes shipped with this installer.'
  while true; do
    if ! IFS= read -r -p '    Download the verified Gum runtime? [y/N]: ' answer; then return 1; fi
    case "${answer,,}" in
      y|yes) GUM_DOWNLOAD_APPROVED=1; return 0 ;;
      ''|n|no) return 1 ;;
      *) _term err '    Please answer yes or no.' ;;
    esac
  done
}

gum_fetch_archive() {
  local target="$1"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
      --connect-timeout 10 --max-time 120 --retry 1 --output "$target" -- "$GUM_DOWNLOAD_URL"
  else
    wget --https-only --timeout=30 --tries=2 --max-redirect=5 --output-document="$target" -- "$GUM_DOWNLOAD_URL"
  fi
}

cleanup_gum_runtime() {
  [[ -n "$GUM_STAGE" && -n "$GUM_CACHE_DIR" ]] || return 0
  if [[ "$GUM_STAGE" == "$GUM_CACHE_DIR/.download."* && -d "$GUM_STAGE" && ! -L "$GUM_STAGE" && -O "$GUM_STAGE" ]]; then
    # Extraction writes only these two files. Never recursively delete a cache.
    rm -f -- "$GUM_STAGE/archive.tar.gz" "$GUM_STAGE/gum" || true
    rmdir -- "$GUM_STAGE" 2>/dev/null || true
  fi
  GUM_STAGE=''
}

download_gum_runtime() {
  [[ "$GUM_DOWNLOAD_APPROVED" -eq 1 ]] || return 1
  GUM_DOWNLOAD_APPROVED=0
  local target="$GUM_CACHE_DIR/gum" old_umask backup=''
  GUM_CACHE_CHANGED=1
  old_umask=$(umask)
  umask 077
  if ! mkdir -p -- "$GUM_CACHE_DIR"; then umask "$old_umask"; return 1; fi
  GUM_STAGE=$(mktemp -d "$GUM_CACHE_DIR/.download.XXXXXX") || { umask "$old_umask"; return 1; }
  umask "$old_umask"
  gum_cache_safe || return 1
  say 'Downloading the UI runtime; the desktop installer has not started.'
  gum_fetch_archive "$GUM_STAGE/archive.tar.gz" || return 1
  if ! gum_hash_matches "$GUM_STAGE/archive.tar.gz" "$GUM_ARCHIVE_SHA256"; then
    _term err '  Gum archive verification failed. Nothing from the download was executed.'
    return 1
  fi
  # Read only the pinned executable member to stdout: never unpack arbitrary
  # paths, permissions, or symlinks from an archive into the cache or HOME.
  tar -xOf "$GUM_STAGE/archive.tar.gz" "$GUM_ARCHIVE_MEMBER" >"$GUM_STAGE/gum" || return 1
  if ! gum_hash_matches "$GUM_STAGE/gum" "$GUM_BINARY_SHA256"; then
    _term err '  Gum executable verification failed. Nothing from the download was executed.'
    return 1
  fi
  chmod 700 -- "$GUM_STAGE/gum" || return 1
  gum_compatible "$GUM_STAGE/gum" || return 1
  if [[ -e "$target" || -L "$target" ]]; then
    [[ -f "$target" && ! -L "$target" && -O "$target" ]] || return 1
    backup="$target.unverified-$RUN_ID"
    [[ ! -e "$backup" && ! -L "$backup" ]] || return 1
    mv -T -- "$target" "$backup" || return 1
    say "Previous unusable cached runtime preserved at $backup"
  fi
  if ! mv -T -- "$GUM_STAGE/gum" "$target"; then
    if [[ -n "$backup" && ! -e "$target" && ! -L "$target" ]]; then mv -T -- "$backup" "$target" || true; fi
    return 1
  fi
  GUM_BIN="$target"
  GUM_DOWNLOADED=1
  say 'Enhanced interface ready. The verified runtime will be reused next time.'
}

prepare_gum_runtime() {
  # Also guard the resolver itself, not only its caller. Explicit read-only and
  # automation modes must not even inspect the cache or execute UI helpers.
  [[ "$UI_SESSION" -eq 1 && "$UI_MODE" != plain && "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 && "$CHECK_ONLY" -eq 0 && "$QUIET" -eq 0 ]] || return 1
  GUM_BIN=''
  if find_system_gum; then return 0; fi
  if ! gum_runtime_release; then say 'No pinned Gum runtime is available for this platform.'; return 1; fi
  if ! command -v sha256sum >/dev/null 2>&1; then say 'Cannot verify a UI runtime without sha256sum.'; return 1; fi
  if ! gum_cache_safe; then say 'UI cache location is not safely owned; it will not be modified.'; return 1; fi
  local candidate="$GUM_CACHE_DIR/gum" tool
  if [[ -e "$candidate" || -L "$candidate" ]]; then
    if [[ ! -f "$candidate" || -L "$candidate" || ! -O "$candidate" ]]; then
      say 'Unexpected file at the UI runtime path; leaving it untouched.'; return 1
    fi
    if gum_owned_permissions "$candidate" && gum_hash_matches "$candidate" "$GUM_BINARY_SHA256" && gum_compatible "$candidate"; then
      GUM_BIN="$candidate"
      return 0
    fi
    _term err '  Cached Gum was not verified and runnable; it will not be used.'
  fi
  if [[ "$EUID" -eq 0 ]]; then say 'UI runtime downloads require a normal user, not root.'; return 1; fi
  for tool in tar stat mktemp chmod mv; do
    if ! command -v "$tool" >/dev/null 2>&1; then say "UI runtime preparation needs $tool; using plain prompts."; return 1; fi
  done
  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    say 'UI runtime download needs curl or wget; no packages will be installed automatically.'; return 1
  fi
  if ! gum_download_consent; then say 'UI runtime download declined; using numbered prompts.'; return 1; fi
  if download_gum_runtime; then
    cleanup_gum_runtime
    return 0
  fi
  cleanup_gum_runtime
  GUM_BIN=''
  say 'Could not prepare the enhanced interface; continuing with numbered prompts.'
  return 1
}
