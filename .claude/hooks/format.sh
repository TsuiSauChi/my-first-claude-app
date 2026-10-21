#!/usr/bin/env bash
# PostToolUse hook: format the file Claude just wrote or edited.
# Reads the hook JSON on stdin; .py goes to ruff, web/doc files to Prettier 2
# (the last Prettier that runs on this machine's Node 12). Other files are left alone.
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
file="$(python3 -c 'import json, sys
d = json.load(sys.stdin)
print((d.get("tool_response") or {}).get("filePath") or (d.get("tool_input") or {}).get("file_path") or "")')"

# Only format real files inside this repo
[ -n "$file" ] && [ -f "$file" ] || exit 0
case "$file" in "$root"/*) ;; *) exit 0 ;; esac

case "$file" in
  *.py)
    "$root/image-upload/.venv/bin/ruff" format --quiet "$file"
    ;;
  *.html|*.css|*.js|*.json|*.md)
    npx --yes prettier@2.8.8 --write --loglevel warn "$file"
    ;;
esac
