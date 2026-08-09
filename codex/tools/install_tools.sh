#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/tools/openspec"
npm ci

echo "Готово. Используйте локальную команду:"
echo "  $ROOT_DIR/bin/openspec --version"
echo "coordctl теперь поставляется intData Node: /int/node/coordctl"
