#!/usr/bin/env bash
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
# _______________________________________________________________________

# Compatibility entry point: all presentation and actions live in one controller.
set -euo pipefail
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python -B "$dir/connectivity/menu.py" wifi "$@"
