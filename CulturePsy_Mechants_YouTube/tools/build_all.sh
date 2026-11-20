#!/bin/sh
# Reconstruit tout ce qui dépend du texte, de la voix et du montage, puis lance les audits de texte et de montage.
set -e
cd "$(dirname "$0")/.."
if python3 -c "import json,sys; sys.exit(0 if json.load(open('src/data/config.json'))['voix'] else 1)"; then
  python3 tools/align_voice.py
fi
python3 tools/build_text.py
python3 tools/resolve_montage.py
python3 tools/audit_text.py || true
python3 tools/audit_montage.py || true
