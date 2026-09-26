import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser-extension"


class BrowserExtensionTests(unittest.TestCase):
    def test_extension_has_only_side_panel_and_local_companion_access(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(set(manifest["permissions"]), {"sidePanel", "storage"})
        self.assertEqual(manifest["optional_host_permissions"], ["http://127.0.0.1/*"])
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("content_scripts", manifest)
        self.assertNotIn("tabs", manifest["permissions"])
        self.assertEqual(manifest["side_panel"]["default_path"], "sidepanel.html")

    def test_side_panel_uses_packaged_resources_and_no_remote_script_or_frame(self):
        page = (EXTENSION / "sidepanel.html").read_text(encoding="utf-8").lower()
        script = (EXTENSION / "sidepanel.js").read_text(encoding="utf-8")

        self.assertIn('src="sidepanel.js"', page)
        self.assertIn('href="sidepanel.css"', page)
        self.assertNotIn("<iframe", page)
        self.assertNotIn('<script src="http', page)
        self.assertNotIn("innerhtml", script.lower())
        self.assertIn('credentials: "omit"', script)
        self.assertIn('redirect: "error"', script)
        self.assertIn("http://127.0.0.1/*", script)


if __name__ == "__main__":
    unittest.main()
