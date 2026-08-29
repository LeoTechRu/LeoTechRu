#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "OpenSpec управляется глобально через @fission-ai/openspec: openspec --version"
echo "Coordination предоставляет intData Node только через установленную команду: intnode coord --help"
