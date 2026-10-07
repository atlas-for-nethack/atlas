#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
# Validate both caches even when the engine is reused by an incremental build.
python3 scripts/package.py pins vendor --ensure
mkdir -p .build/module-cache dist
# App packaging always produces Universal 2, including after a native-only
# engine iteration. Check both binaries before deciding to reuse the runtime.
if [ ! -x engine/runtime/nethack ] || [ ! -x engine/runtime/recover ] || [ engine/winatelier.c -nt engine/runtime/nethack ] || [ engine/apply-beginner-patch.py -nt engine/runtime/nethack ] || [ engine/hints -nt engine/runtime/nethack ] || [ engine/sysconf -nt engine/runtime/nethack ] || [ "${REBUILD_ENGINE:-0}" = 1 ] || ! lipo engine/runtime/nethack -verify_arch arm64 >/dev/null 2>&1 || ! lipo engine/runtime/nethack -verify_arch x86_64 >/dev/null 2>&1 || ! lipo engine/runtime/recover -verify_arch arm64 >/dev/null 2>&1 || ! lipo engine/runtime/recover -verify_arch x86_64 >/dev/null 2>&1; then
  ENGINE_ARCH=universal bash scripts/build-engine.sh
fi
FINAL_APP="$ROOT/dist/Atlas.app"
STAGING="$(mktemp -d "$ROOT/.build/app-staging.XXXXXX")"
APP="$STAGING/Atlas.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
for ARCH in arm64 x86_64; do
  xcrun swiftc -O -target "$ARCH-apple-macos13.0" -module-cache-path "$ROOT/.build/module-cache" native/App.swift native/Recovery.swift native/Playtest.swift native/TilesetImport.swift -o "$ROOT/.build/NetHackAtlas-$ARCH" -framework Cocoa -framework WebKit
done
lipo -create "$ROOT/.build/NetHackAtlas-arm64" "$ROOT/.build/NetHackAtlas-x86_64" -output "$APP/Contents/MacOS/NetHackAtlas"
cp native/Info.plist "$APP/Contents/Info.plist"
python3 scripts/package.py stage "$ROOT" "$APP/Contents/Resources"
python3 scripts/audit-engine-fork.py --report "$APP/Contents/Resources/Source/engine-fork-audit.json"
codesign --force --sign - "$APP/Contents/Resources/engine/nethack"
codesign --force --sign - "$APP/Contents/Resources/engine/recover"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
# The previous complete app remains in place until the staged candidate passes.
python3 scripts/verify-bundle.py --app "$APP"
# Rename complete bundles rather than overwriting executables in a running app.
# Keep the previous inode tree intact so an already running game can finish.
if [ -d "$FINAL_APP" ]; then
  PREVIOUS="$(mktemp -d "$ROOT/.build/previous-app.XXXXXX")"
  mv "$FINAL_APP" "$PREVIOUS/Atlas.app"
fi
mv "$APP" "$FINAL_APP"
rmdir "$STAGING"
printf 'Built %s\n' "$FINAL_APP"
