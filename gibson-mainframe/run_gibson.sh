#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi
exec "$PYTHON_BIN" -m gibson.cli --serve --with-ftp --with-tn3270 "$@"
