#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${INTDATA_MCP_PYTHON:-$(command -v python3 || true)}
if [ -z "$PYTHON_BIN" ]; then
  echo "python3 not found; set INTDATA_MCP_PYTHON to an absolute interpreter" >&2
  exit 1
fi
case "$PYTHON_BIN" in /*) ;; *) echo "Python interpreter must be absolute" >&2; exit 1 ;; esac
exec "$PYTHON_BIN" "$SCRIPT_DIR/intdata_mcp_registration.py" --python "$PYTHON_BIN" "$@"
