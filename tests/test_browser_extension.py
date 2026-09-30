import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser-extension"


class BrowserExtensionTests(unittest.TestCase):
    def test_extension_has_only_side_panel_and_local_companion_access(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertEqual(set(manifest["permissions"]), {"sidePanel", "storage"})
        self.assertEqual(manifest["optional_host_permissions"], ["http://127.0.0.1/*"])
        self.assertEqual(manifest["optional_permissions"], ["nativeMessaging"])
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

    def test_side_panel_copy_is_english_and_accessible(self):
        page = (EXTENSION / "sidepanel.html").read_text(encoding="utf-8")
        script = (EXTENSION / "sidepanel.js").read_text(encoding="utf-8")
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        visible_copy = (page + script).lower()

        self.assertIn('<html lang="en"', page)
        self.assertIn('aria-live="polite"', page)
        self.assertIn('<label for="dashboard-url">', page)
        self.assertIn('class="visually-hidden" for="search"', page)
        self.assertIn('aria-label="Display settings"', page)
        self.assertIn('aria-label="Refresh dashboard"', page)
        self.assertIn('new Intl.DateTimeFormat("en-GB"', script)
        self.assertIn("SOURCE_STATUS_TITLES[source.status]", script)
        self.assertNotIn("source.label", script)
        self.assertIn("personal follow-ups alongside discord", manifest["description"].lower())

        for dutch_phrase in (
            "alleen-lezen",
            "focus naast discord",
            "verbind je lokale dashboard",
            "zoek in je overzicht",
            "jouw weergave",
            "status onbekend",
            "geen berichten gevonden",
            "open origineel in discord",
        ):
            with self.subTest(dutch_phrase=dutch_phrase):
                self.assertNotIn(dutch_phrase, visible_copy)

        guide = (ROOT / "BROWSER-EXTENSION.md").read_text(encoding="utf-8").lower()
        self.assertIn("# discord fix browser side panel", guide)
        self.assertNotIn("de browserextensie", guide)


if __name__ == "__main__":
    unittest.main()
