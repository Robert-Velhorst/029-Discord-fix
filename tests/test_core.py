import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from discord_fix.importer import deep_link, read_package
from discord_fix.store import Store


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = Store(self.path / "test.sqlite")

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def package(self, bad=False):
        path = self.path / "data.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(
                "messages/c123/channel.json",
                json.dumps({"id": "123", "name": "project", "guild": {"id": "456"}}),
            )
            items = [
                {
                    "ID": "789",
                    "Timestamp": "2026-09-12 10:00:00+00:00",
                    "Contents": "Wat is afgesproken?",
                }
            ]
            if bad:
                items.append({"ID": "javascript:bad"})
            z.writestr("messages/c123/messages.json", json.dumps(items))
            z.writestr("../../never-extract.txt", "must not be extracted")
        return path

    def test_import_and_partial_errors(self):
        rows, errors = read_package(self.package(True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 2)
        self.assertFalse((self.path / "never-extract.txt").exists())
        self.assertEqual(deep_link(rows[0]), "https://discord.com/channels/456/123/789")

    def test_reimport_preserves_user_state_and_restart(self):
        rows, _ = read_package(self.package())
        self.store.ingest(rows)
        self.store.update("789", "important")
        self.store.update("789", "complete")
        rows[0]["content"] = "Bijgewerkt"
        self.store.ingest(rows)
        self.store.db.close()
        self.store = Store(self.path / "test.sqlite")
        row = self.store.query()[0]
        self.assertEqual(
            (row["content"], row["state"], row["important"]), ("Bijgewerkt", "complete", 1)
        )
        self.assertEqual(len(self.store.query()), 1)

    def test_workflow_views_and_snooze(self):
        self.store.ingest(read_package(self.package())[0])
        self.assertEqual(self.store.query("Needs Reply"), [])
        self.store.update("789", "reply")
        self.assertEqual(len(self.store.query("Needs Reply")), 1)
        self.store.update(
            "789", "later", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        )
        self.assertEqual(self.store.query("Needs Reply"), [])
        self.assertEqual(len(self.store.query("Later")), 1)
        with self.store.db:
            self.store.db.execute("UPDATE messages SET until='2000-01-01T00:00:00+00:00'")
        self.assertEqual(len(self.store.query("Needs Reply")), 1)

    def test_validation_search_and_unknown_context(self):
        self.store.ingest(read_package(self.package())[0])
        self.assertEqual(len(self.store.query(search="AFGESPROKEN")), 1)
        self.assertEqual(self.store.query(search="' OR 1=1"), [])
        with self.assertRaises(ValueError):
            self.store.update("789", "later", "2020-01-01")
        self.assertIsNone(deep_link(dict(guild="")))

    def test_ui_flow(self):
        import tkinter as tk
        from unittest.mock import patch

        from discord_fix.__main__ import App

        root = tk.Tk()
        root.withdraw()
        try:
            self.store.ingest(read_package(self.package())[0])
            app = App(root, self.store)
            self.assertEqual(app.tree.column("message", "width"), 440)
            app._column_resize_pending = True
            app.tree.column("message", width=510)
            app._column_resize_end(None)
            self.assertEqual(self.store.settings()["column_widths"]["message"], 510)
            app.store.save_settings({"theme": "onyx", "density": "spacious"})
            app.apply_style()
            self.assertEqual(app.palette["background"], "#000000")
            app.adjust_text_size(1)
            self.assertEqual(self.store.settings()["message_font_size"], 12)
            app.set_view("Needs Reply")
            self.assertEqual(app.view.get(), "Needs Reply")
            app.set_view("Everything")
            app.tree.selection_set("789")
            app.select()
            app.act("important")
            app.view.set("Important Now")
            app.refresh()
            self.assertEqual(len(app.tree.get_children()), 1)
            app.act("complete")
            self.assertEqual(len(app.tree.get_children()), 0)
            root.update()
            with patch("discord_fix.__main__.webbrowser.open", return_value=True):
                url = app.open_web_dashboard()
            self.assertEqual(
                app.browser_pairing_window.title(), "Connect the English browser extension"
            )
            self.assertTrue(url.startswith("http://127.0.0.1:"))
            first_window = app.browser_pairing_window
            with patch("discord_fix.__main__.webbrowser.open", return_value=True):
                self.assertEqual(app.open_web_dashboard(), url)
            self.assertFalse(first_window.winfo_exists())
            app.dashboard_server.stop()
            root.after_cancel(app.timer)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
