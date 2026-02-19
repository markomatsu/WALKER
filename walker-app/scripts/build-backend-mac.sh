#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_BACKEND="$(cd "$APP_ROOT/../walker" && pwd)"
APP_BACKEND="$APP_ROOT/backend"
VENV_PY="$ROOT_BACKEND/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Python venv not found at $VENV_PY" >&2
  exit 1
fi

"$VENV_PY" -m pip show pyinstaller >/dev/null 2>&1 || "$VENV_PY" -m pip install pyinstaller

mkdir -p "$APP_BACKEND"
rm -rf "$APP_BACKEND/walker-backend" "$APP_BACKEND/build" "$APP_BACKEND/walker-backend.spec" 2>/dev/null || true

"$VENV_PY" -m PyInstaller \
  --name walker-backend \
  --clean \
  --distpath "$APP_BACKEND" \
  --workpath "$APP_BACKEND/build" \
  --specpath "$APP_BACKEND" \
  --add-binary "/opt/homebrew/opt/llvm/lib/libclang.dylib:." \
  --add-binary "/opt/homebrew/opt/llvm/lib/libLLVM.dylib:." \
  --add-binary "/opt/homebrew/opt/z3/lib/libz3.4.15.dylib:." \
  --add-binary "/opt/homebrew/opt/zstd/lib/libzstd.1.dylib:." \
  "$ROOT_BACKEND/test_engine.py"

chmod +x "$APP_BACKEND/walker-backend/walker-backend"

echo "Backend built at $APP_BACKEND/walker-backend"
