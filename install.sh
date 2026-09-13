#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"

echo "==> Installing web2gtk into user environment (~/.local/bin)..."

mkdir -p "$BIN_DIR"

chmod +x "$SCRIPT_DIR/bin/web2gtk"
chmod +x "$SCRIPT_DIR/bin/web2gtk-runner"

ln -sf "$SCRIPT_DIR/bin/web2gtk" "$BIN_DIR/web2gtk"
ln -sf "$SCRIPT_DIR/bin/web2gtk-runner" "$BIN_DIR/web2gtk-runner"

# Ensure icon directories exist
mkdir -p "$HOME/.local/share/icons/hicolor/32x32/apps"
mkdir -p "$HOME/.local/share/icons/hicolor/128x128/apps"
mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.config/web2gtk/apps"

echo "==> Done! web2gtk and web2gtk-runner are now active in $BIN_DIR."
echo "    Try running: web2gtk --help"
