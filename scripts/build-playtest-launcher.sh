#!/bin/sh
# Development-only companion. Uses this checkout and Apple's Python 3.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
test -x 'dist/Atlas.app/Contents/MacOS/NetHackAtlas' || ./scripts/build-app.sh
mkdir -p .build/module-cache dist
STAGE=$(mktemp -d "$ROOT/.build/playtest-launcher.XXXXXX")
APP="$STAGE/Atlas Environment Playtests.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
xcrun swiftc -parse-as-library -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache native/EnvironmentLauncher.swift -o "$APP/Contents/MacOS/EnvironmentLauncher" -framework Cocoa
printf '%s\n' "$ROOT" > "$APP/Contents/Resources/workspace.txt"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Atlas Environment Playtests</string>
<key>CFBundleIdentifier</key><string>run.nethack.atlas.playtests</string>
<key>CFBundleExecutable</key><string>EnvironmentLauncher</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - "$APP"
if [ -d 'dist/Atlas Environment Playtests.app' ]; then
  mv 'dist/Atlas Environment Playtests.app' "$STAGE/previous.app"
fi
mv "$APP" dist/
printf 'Built %s/dist/Atlas Environment Playtests.app\n' "$ROOT"
