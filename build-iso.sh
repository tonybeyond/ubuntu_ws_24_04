#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$ROOT/scripts/build_iso.py" "$@"
