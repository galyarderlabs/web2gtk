import os
import sys
import argparse
from urllib.parse import urlparse
from web2gtk.manifest import AppManifest, slugify
from web2gtk.generator import install_app, uninstall_app
from web2gtk.engine.runner import run_manifest
from web2gtk.exporter import export_standalone, export_arch_pkgbuild


def cmd_create(args):
    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Deduce name from URL if not given
    name = args.name
    if not name:
        domain = urlparse(url).netloc
        # remove www. and tld
        parts = domain.replace("www.", "").split(".")
        name = parts[0].capitalize() if parts else "WebApp"

    slug = args.slug or slugify(name)
    if not slug.endswith("-gtk"):
        slug += "-gtk"

    app_id = args.id or f"io.github.web2gtk.{slug.replace('-', '_')}"
    icon_name = args.icon_name or slug

    print(f"==> Membuat web app untuk '{name}' ({url})...")
    manifest = AppManifest(
        name=name,
        url=url,
        slug=slug,
        app_id=app_id,
        icon=icon_name,
        stealth=not args.no_stealth,
        persistent_storage=not args.no_persistent,
        system_tray=not args.no_tray
    )

    install_app(manifest, icon_path_or_url=args.icon)
    print(f"==> Berhasil diinstall!")
    print(f"    - Launcher: ~/.local/bin/{manifest.slug}")
    print(f"    - Desktop:  ~/.local/share/applications/{manifest.slug}.desktop")
    print(f"    - Manifest: {manifest.manifest_path}")
    print(f"    - Storage:  {manifest.data_dir} (Persistent SQLite Cookies & LocalStorage)")
    print(f"\nLu bisa langsung jalankan '{manifest.slug}' di terminal atau cari '{manifest.name}' di menu aplikasi.")

    if args.run:
        print(f"\n==> Menjalankan {manifest.name}...")
        run_manifest(manifest)


def cmd_list(args):
    apps = AppManifest.list_all()
    if not apps:
        print("Belum ada web app yang dibuat dengan web2gtk.")
        print("Jalankan: web2gtk create <url> --name <nama>")
        return

    print(f"{'SLUG':<20} {'NAMA':<22} {'URL':<35} {'TRAY':<6} {'STEALTH':<8}")
    print("-" * 95)
    for app in apps:
        tray = "Yes" if app.system_tray else "No"
        stealth = "Yes" if app.stealth else "No"
        print(f"{app.slug:<20} {app.name:<22} {app.url:<35} {tray:<6} {stealth:<8}")


def cmd_remove(args):
    slug = args.slug
    print(f"==> Menghapus web app '{slug}'...")
    uninstall_app(slug, purge_data=args.purge)
    print(f"==> Web app '{slug}' berhasil dihapus dari sistem.")
    if args.purge:
        print("    Data session dan cookies juga telah dibersihkan.")


def cmd_run(args):
    try:
        manifest = AppManifest.load(args.slug)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    run_manifest(manifest)


def cmd_info(args):
    try:
        manifest = AppManifest.load(args.slug)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Nama:        {manifest.name}")
    print(f"Slug:        {manifest.slug}")
    print(f"URL:         {manifest.url}")
    print(f"App ID:      {manifest.app_id}")
    print(f"Icon:        {manifest.icon}")
    print(f"System Tray: {'Ya' if manifest.system_tray else 'Tidak'}")
    print(f"Anti-Bot:    {'Ya' if manifest.stealth else 'Tidak'}")
    print(f"Data Dir:    {manifest.data_dir}")
    print(f"Cache Dir:   {manifest.cache_dir}")
    print(f"Config Dir:  {manifest.config_dir}")


def cmd_export(args):
    try:
        manifest = AppManifest.load(args.slug)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    fmt = args.format.lower()
    output_dir = args.output or "dist"

    print(f"==> Exporting '{manifest.name}' ({manifest.slug}) format={fmt}...")
    if fmt in ("standalone", "tar", "tar.gz"):
        out_path = export_standalone(manifest, output_dir=output_dir)
        print(f"==> Berhasil dibuat paket standalone installer:")
        print(f"    - Tarball:    {out_path}")
        print(f"    - Direktori:  {os.path.splitext(os.path.splitext(out_path)[0])[0]}")
        print(f"\nUntuk membagikan ke orang lain:")
        print(f"  Kirim file '{out_path}'.")
        print(f"  Penerima tinggal ekstrak dan jalankan './install.sh'!")
    elif fmt in ("arch", "pkgbuild"):
        out_path = export_arch_pkgbuild(manifest, output_dir=output_dir)
        print(f"==> Berhasil digenerate direktori PKGBUILD:")
        print(f"    - Path: {out_path}")
        print(f"\nUntuk build paket Arch:")
        print(f"  cd {out_path} && makepkg -si")
    else:
        print(f"Format export tidak didukung: {fmt}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="web2gtk",
        description="Lightweight native GTK4/Libadwaita desktop web app generator for Linux"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: create
    create_parser = subparsers.add_parser("create", help="Create and install a new web app")
    create_parser.add_argument("url", help="Target website URL (e.g. https://claude.ai)")
    create_parser.add_argument("--name", "-n", help="Display name for the application")
    create_parser.add_argument("--slug", "-s", help="Custom executable slug (default: name-gtk)")
    create_parser.add_argument("--id", help="Custom desktop Application ID")
    create_parser.add_argument("--icon", "-i", help="Path to custom icon file (PNG/SVG/ICO)")
    create_parser.add_argument("--icon-name", help="Existing system icon name")
    create_parser.add_argument("--no-tray", action="store_true", help="Disable D-Bus system tray")
    create_parser.add_argument("--no-stealth", action="store_true", help="Disable anti-bot stealth script")
    create_parser.add_argument("--no-persistent", action="store_true", help="Use ephemeral in-memory session")
    create_parser.add_argument("--run", "-r", action="store_true", help="Launch immediately after creation")
    create_parser.set_defaults(func=cmd_create)

    # Command: list
    list_parser = subparsers.add_parser("list", help="List all installed web apps")
    list_parser.set_defaults(func=cmd_list)

    # Command: remove
    remove_parser = subparsers.add_parser("remove", aliases=["uninstall"], help="Remove an installed web app")
    remove_parser.add_argument("slug", help="Slug of the app to remove")
    remove_parser.add_argument("--purge", "-p", action="store_true", help="Also delete saved sessions and cookies")
    remove_parser.set_defaults(func=cmd_remove)

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run an installed app by slug")
    run_parser.add_argument("slug", help="Slug of the app to run")
    run_parser.set_defaults(func=cmd_run)

    # Command: info
    info_parser = subparsers.add_parser("info", help="Show details of an installed app")
    info_parser.add_argument("slug", help="Slug of the app")
    info_parser.set_defaults(func=cmd_info)

    # Command: export
    export_parser = subparsers.add_parser("export", help="Export app into standalone bundle or PKGBUILD")
    export_parser.add_argument("slug", help="Slug of the app to export")
    export_parser.add_argument("--format", "-f", choices=["standalone", "arch"], default="standalone", help="Export format (default: standalone)")
    export_parser.add_argument("--output", "-o", default="dist", help="Output directory (default: dist)")
    export_parser.set_defaults(func=cmd_export)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
