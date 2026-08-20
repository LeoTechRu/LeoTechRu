#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Resolve logical SSH target for /int transport layer.

Usage:
  int_ssh_host.sh --logical <dev-intdata|dev-runtime|prod-leon> [--mode auto|tailnet|public]

Output:
  destination to stdout
  selected metadata JSON to stderr
USAGE
}

logical=""
mode="${INT_SSH_MODE:-auto}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --logical)
      logical="${2:-}"
      shift 2
      ;;
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "int_ssh_host.sh: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$logical" ]]; then
  echo "int_ssh_host.sh: --logical is required" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON_BIN:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python"
fi

exec "$python_bin" "$script_dir/int_ssh_resolve.py" \
  --requested-host "$logical" \
  --mode "$mode" \
  --capability int_ssh_resolve \
  --binding-origin "codex/bin/int_ssh_host.sh" \
  --destination-only
