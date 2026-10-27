#!/usr/bin/env bash
# Author: ae. Orland
# GitHub: https://github.com/ae-orlando
# _______________________________________________________________________

# Compatibility entry point: native drawer by default, --legacy for Rofi.
set -euo pipefail
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python -B "$dir/connectivity/launch.py" wifi "$@"
