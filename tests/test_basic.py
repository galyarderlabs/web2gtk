import unittest
import os
import shutil
from web2gtk.manifest import AppManifest, slugify
from web2gtk.generator import install_app, uninstall_app


class TestWeb2Gtk(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("My Test App"), "my-test-app")
        self.assertEqual(slugify("Claude AI!"), "claude-ai")

    def test_manifest_creation(self):
        m = AppManifest(name="Test Web", url="https://example.com")
        self.assertEqual(m.slug, "test-web-gtk")
        self.assertEqual(m.app_id, "io.github.web2gtk.test_web_gtk")
        self.assertFalse(m.stealth)
        self.assertTrue(m.persistent_storage)
        self.assertTrue(m.system_tray)
        self.assertTrue(m.adblock)

    def test_install_and_uninstall(self):
        m = AppManifest(name="Mock Unit Test", url="https://example.com", slug="mock-test-gtk")
        # Install without downloading (fallback icon)
        install_app(m)
        
        # Verify files exist
        launcher = os.path.expanduser("~/.local/bin/mock-test-gtk")
        desktop = os.path.expanduser("~/.local/share/applications/mock-test-gtk.desktop")
        manifest_file = m.manifest_path

        self.assertTrue(os.path.exists(launcher))
        self.assertTrue(os.path.exists(desktop))
        self.assertTrue(os.path.exists(manifest_file))

        # Uninstall
        uninstall_app("mock-test-gtk", purge_data=True)
        self.assertFalse(os.path.exists(launcher))
        self.assertFalse(os.path.exists(desktop))
        self.assertFalse(os.path.exists(manifest_file))

    def test_export(self):
        from web2gtk.exporter import export_standalone, export_arch_pkgbuild
        m = AppManifest(name="Export Test App", url="https://example.com", slug="export-test-gtk")
        install_app(m)

        tar_path = export_standalone(m, output_dir="/tmp/web2gtk_test_dist")
        self.assertTrue(os.path.exists(tar_path))
        self.assertTrue(tar_path.endswith(".tar.gz"))

        arch_dir = export_arch_pkgbuild(m, output_dir="/tmp/web2gtk_test_dist")
        self.assertTrue(os.path.exists(os.path.join(arch_dir, "PKGBUILD")))

        # Clean up
        uninstall_app("export-test-gtk", purge_data=True)
        shutil.rmtree("/tmp/web2gtk_test_dist", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
