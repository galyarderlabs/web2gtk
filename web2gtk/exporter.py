import os
import shutil
import stat
import tarfile
from typing import Optional
from web2gtk.manifest import AppManifest
from web2gtk.icons import SIZES, ICON_BASE

WEB2GTK_DIR = os.path.dirname(os.path.abspath(__file__))


def export_standalone(manifest: AppManifest, output_dir: str = "dist") -> str:
    """Bundle app into a portable standalone installer package with self-contained runtime."""
    os.makedirs(output_dir, exist_ok=True)
    bundle_name = f"{manifest.slug}-installer"
    bundle_dir = os.path.join(output_dir, bundle_name)

    # Clean existing bundle dir
    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)

    os.makedirs(os.path.join(bundle_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(bundle_dir, "app"), exist_ok=True)

    # 1. Copy Icons
    for size in SIZES:
        src_icon = os.path.join(ICON_BASE, f"{size}x{size}", "apps", f"{manifest.icon}.png")
        if os.path.exists(src_icon):
            shutil.copy2(src_icon, os.path.join(bundle_dir, "assets", f"{size}x{size}.png"))

    # 2. Copy Engine Runtime
    shutil.copy2(os.path.join(WEB2GTK_DIR, "manifest.py"), os.path.join(bundle_dir, "app", "manifest.py"))
    shutil.copy2(os.path.join(WEB2GTK_DIR, "engine", "window.py"), os.path.join(bundle_dir, "app", "window.py"))
    shutil.copy2(os.path.join(WEB2GTK_DIR, "engine", "tray.py"), os.path.join(bundle_dir, "app", "tray.py"))
    shutil.copy2(os.path.join(WEB2GTK_DIR, "engine", "adblock.py"), os.path.join(bundle_dir, "app", "adblock.py"))

    # Runner script inside app/
    runner_src = f"""#!/usr/bin/env python3
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')

from gi.repository import Adw, Gio
from manifest import AppManifest
from window import Web2GtkWindow
from tray import StatusNotifierTray


class StandaloneApp(Adw.Application):
    def __init__(self, manifest):
        super().__init__(
            application_id=manifest.app_id,
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.manifest = manifest
        self.win = None
        self.tray = None

    def do_activate(self):
        if not self.win:
            self.win = Web2GtkWindow(self, self.manifest)
            if self.manifest.system_tray:
                self.tray = StatusNotifierTray(self, self.win, self.manifest)
                self.win.tray = self.tray
        self.win.set_visible(True)
        self.win.present()
        self.win.web_view.grab_focus()

    def do_open(self, files, hint):
        self.do_activate()
        if files:
            for f in files:
                uri = f.get_uri()
                if uri and uri.startswith(("http://", "https://")):
                    self.win.web_view.load_uri(uri)
                    break


def main():
    manifest_path = os.path.expanduser("~/.config/{manifest.slug}/manifest.json")
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        manifest_path = sys.argv[1]
        argv = [sys.argv[0]] + sys.argv[2:]
    else:
        argv = sys.argv

    manifest = AppManifest.load(manifest_path)
    app = StandaloneApp(manifest)
    sys.exit(app.run(argv))


if __name__ == "__main__":
    main()
"""
    with open(os.path.join(bundle_dir, "app", "runner.py"), "w", encoding="utf-8") as f:
        f.write(runner_src)

    with open(os.path.join(bundle_dir, "app", "__init__.py"), "w", encoding="utf-8") as f:
        f.write('"""Self-contained standalone app engine."""\n')

    # 3. Save Manifest copy
    shutil.copy2(manifest.manifest_path, os.path.join(bundle_dir, "manifest.json"))

    # 4. Generate install.sh
    install_sh = f"""#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
APP_SHARE="$HOME/.local/share/{manifest.slug}"
CONFIG_DIR="$HOME/.config/{manifest.slug}"

echo "==> Memasang {manifest.name} ke sistem user..."

# Create dirs
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$APP_SHARE/app"
mkdir -p "$CONFIG_DIR"

# Copy runtime and config
cp -r "$SCRIPT_DIR/app/"* "$APP_SHARE/app/"
cp "$SCRIPT_DIR/manifest.json" "$CONFIG_DIR/manifest.json"

# Install icons
for size in 32 128 256; do
    if [ -f "$SCRIPT_DIR/assets/${{size}}x${{size}}.png" ]; then
        mkdir -p "$ICON_BASE/${{size}}x${{size}}/apps"
        cp "$SCRIPT_DIR/assets/${{size}}x${{size}}.png" "$ICON_BASE/${{size}}x${{size}}/apps/{manifest.icon}.png"
    fi
done

# Launcher script
LAUNCHER="$BIN_DIR/{manifest.slug}"
cat << 'EOF' > "$LAUNCHER"
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/{manifest.slug}/app/runner.py" "$@"
EOF
chmod +x "$LAUNCHER"

# Desktop file
DESKTOP_FILE="$DESKTOP_DIR/{manifest.slug}.desktop"
cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name={manifest.name}
Comment=Native desktop web client for {manifest.name}
Exec=$LAUNCHER %U
Icon={manifest.icon}
Terminal=false
Categories=Network;WebBrowser;Utility;
StartupWMClass={manifest.app_id}
MimeType=x-scheme-handler/{manifest.slug};
Keywords=web;{manifest.name.lower()};
EOF

# Refresh caches
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
fi

echo "==> Done! {manifest.name} successfully installed."
echo "    Can be launched via terminal: {manifest.slug}"
echo "    or search for '{manifest.name}' in your application menu."
"""
    install_path = os.path.join(bundle_dir, "install.sh")
    with open(install_path, "w", encoding="utf-8") as f:
        f.write(install_sh)
    os.chmod(install_path, 0o755)

    # 5. Generate uninstall.sh
    uninstall_sh = f"""#!/usr/bin/env bash
set -e

echo "==> Removing {manifest.name} from system..."

rm -f "$HOME/.local/bin/{manifest.slug}"
rm -f "$HOME/.local/share/applications/{manifest.slug}.desktop"

for size in 32 128 256; do
    rm -f "$HOME/.local/share/icons/hicolor/${{size}}x${{size}}/apps/{manifest.icon}.png"
done

if [ "$1" == "--purge" ]; then
    echo "==> Purging session data and cookies..."
    rm -rf "$HOME/.local/share/{manifest.slug}"
    rm -rf "$HOME/.cache/{manifest.slug}"
    rm -rf "$HOME/.config/{manifest.slug}"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "==> {manifest.name} successfully removed."
"""
    uninstall_path = os.path.join(bundle_dir, "uninstall.sh")
    with open(uninstall_path, "w", encoding="utf-8") as f:
        f.write(uninstall_sh)
    os.chmod(uninstall_path, 0o755)

    # 6. Readme
    readme_txt = f"""{manifest.name} Desktop App (Standalone Installer)
===================================================

Native GTK4/Libadwaita desktop application for {manifest.name} ({manifest.url}).
Built using web2gtk.

Installation:
  ./install.sh

Uninstallation:
  ./uninstall.sh
  (or ./uninstall.sh --purge to remove session cookies & persistent storage)

System Requirements:
  - Python 3.10+
  - PyGObject, GTK4, Libadwaita, WebKitGTK 6.0
"""
    with open(os.path.join(bundle_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme_txt)

    # 7. Compress into tar.gz
    tar_path = os.path.join(output_dir, f"{bundle_name}.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_name)

    return tar_path


def export_arch_pkgbuild(manifest: AppManifest, output_dir: str = "dist") -> str:
    """Generate an Arch Linux PKGBUILD directory for the app."""
    pkg_dir = os.path.join(output_dir, f"{manifest.slug}-pkgbuild")
    os.makedirs(pkg_dir, exist_ok=True)

    pkgbuild_content = f"""# Maintainer: Galyarder Labs <muhamadgalihsaputra@users.noreply.github.com>
pkgname={manifest.slug}
pkgver=0.1.0
pkgrel=1
pkgdesc="Native GTK4/Libadwaita desktop app for {manifest.name}"
arch=('any')
url="{manifest.url}"
license=('MIT')
depends=(
    'python'
    'python-gobject'
    'gtk4'
    'libadwaita'
    'webkitgtk-6.0'
    'libdbusmenu-glib'
)
source=()
sha256sums=()

package() {{
    # Create target directories
    install -d "${{pkgdir}}/usr/share/${{pkgname}}/app"
    install -d "${{pkgdir}}/usr/share/applications"
    install -d "${{pkgdir}}/usr/bin"

    # Install desktop entry
    cat << EOF > "${{pkgdir}}/usr/share/applications/${{pkgname}}.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name={manifest.name}
Comment=Native desktop web client for {manifest.name}
Exec=/usr/bin/${{pkgname}} %U
Icon={manifest.icon}
Terminal=false
Categories=Network;WebBrowser;Utility;
StartupWMClass={manifest.app_id}
MimeType=x-scheme-handler/${{pkgname}};
Keywords=web;{manifest.name.lower()};
EOF

    # Install binary launcher
    cat << EOF > "${{pkgdir}}/usr/bin/${{pkgname}}"
#!/usr/bin/env bash
exec python3 /usr/share/${{pkgname}}/app/runner.py "\\$@"
EOF
    chmod 755 "${{pkgdir}}/usr/bin/${{pkgname}}"
}}
"""
    with open(os.path.join(pkg_dir, "PKGBUILD"), "w", encoding="utf-8") as f:
        f.write(pkgbuild_content)

    return pkg_dir
