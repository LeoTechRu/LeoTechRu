#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROBE_REPO_PATH="${PROBE_REPO_PATH:-/int/bridge}"
PROBE_STATE_DIR="${PROBE_STATE_DIR:-$HOME/.local/state/probe-monitor}"
PROBE_RUNTIME_ROOT="${PROBE_RUNTIME_ROOT:-$HOME/.local/share/probe-monitor}"
DEFAULT_OUT="$PROBE_STATE_DIR/audit/machine-audit-latest.md"
OUT_FILE="${1:-${PROBE_AUDIT_OUT_FILE:-$DEFAULT_OUT}}"
TS="$(date -Is)"

mkdir -p "$(dirname "$OUT_FILE")"

{
  echo "# Machine Audit Snapshot"
  echo
  echo "Generated at: $TS"
  echo
  echo "## Scope"
  echo "- Probe Monitor + openclaw"
  echo
  echo "## Git status (targeted)"
  git -C "$PROBE_REPO_PATH" status --short \
    bridge \
    probes \
    config \
    ops \
    tests \
    | sed 's/^/- /'
  echo
  echo "## Cron lines (cleaner)"
  (crontab -l 2>/dev/null || true) | rg -n 'probe-agent-orphan-cleaner|cleanup-agent-orphans\.sh|cleanup_agent_orphans\.sh' || true
  echo
  echo "## OpenClaw user service"
  systemctl --user list-unit-files --type=service | rg -n 'openclaw-gateway' || true
  echo
  echo "## Probe runtime tree (depth 2)"
  find "$PROBE_RUNTIME_ROOT" -maxdepth 2 -mindepth 1 -printf '%M %u:%g %p\n' 2>/dev/null || true
  echo
  echo "## Probe state tree (depth 2)"
  find "$PROBE_STATE_DIR" -maxdepth 2 -mindepth 1 -printf '%M %u:%g %p\n' 2>/dev/null || true
} > "$OUT_FILE"

echo "audit snapshot written: $OUT_FILE"
