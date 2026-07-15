#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ICON_SRC="$ROOT_DIR/nottcontrol/NOTT_app_icon.png"
ICONSET="$ROOT_DIR/nottcontrol/macos/NOTT.iconset"
ICNS_OUT="$ROOT_DIR/nottcontrol/macos/NOTT.icns"
APP_RESOURCES="$ROOT_DIR/NOTTControl.app/Contents/Resources"
LAUNCHER="$ROOT_DIR/NOTTControl.app/Contents/MacOS/NOTTControl"

if [[ ! -f "$ICON_SRC" ]]; then
    echo "error: missing icon source at $ICON_SRC" >&2
    exit 1
fi

rm -rf "$ICONSET"
mkdir -p "$ICONSET"
sips -z 16 16 "$ICON_SRC" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32 "$ICON_SRC" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$ICON_SRC" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64 "$ICON_SRC" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$ICON_SRC" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256 "$ICON_SRC" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$ICON_SRC" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512 "$ICON_SRC" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$ICON_SRC" --out "$ICONSET/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o "$ICNS_OUT"

mkdir -p "$APP_RESOURCES"
cp "$ICNS_OUT" "$APP_RESOURCES/NOTT.icns"
chmod +x "$LAUNCHER"

echo "Built $ICNS_OUT"
echo "Updated $APP_RESOURCES/NOTT.icns"
