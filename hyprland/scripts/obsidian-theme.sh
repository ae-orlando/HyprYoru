#!/usr/bin/env bash
# Push the matugen-generated Obsidian CSS into every registered vault.
# Called as a matugen post_hook after ~/.config/obsidian/matugen.css is written.
set -euo pipefail

central="${HOME}/.config/obsidian/matugen.css"
[[ -f "$central" ]] || exit 0

python3 - "$central" <<'PY'
import json
import pathlib
import sys

central = sys.argv[1]
obsidian_json = pathlib.Path.home() / ".config" / "obsidian" / "obsidian.json"
if not obsidian_json.is_file():
    raise SystemExit(0)

try:
    data = json.loads(obsidian_json.read_text())
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

for info in (data.get("vaults") or {}).values():
    vpath = info.get("path")
    if not vpath:
        continue
    vault = pathlib.Path(vpath)
    if not vault.is_dir():
        continue
    obsidian_dir = vault / ".obsidian"
    snippets = obsidian_dir / "snippets"
    snippets.mkdir(parents=True, exist_ok=True)
    link = snippets / "matugen.css"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(central)

    appearance = obsidian_dir / "appearance.json"
    try:
        app = json.loads(appearance.read_text()) if appearance.is_file() else {}
    except (OSError, json.JSONDecodeError):
        app = {}
    snippets_list = app.setdefault("enabledCssSnippets", [])
    if "matugen" not in snippets_list:
        snippets_list.append("matugen")
    appearance.write_text(json.dumps(app, indent=2) + "\n")
PY
