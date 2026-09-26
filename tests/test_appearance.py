import tempfile
import unittest
from pathlib import Path

from discord_fix.appearance import PALETTES, contrast_ratio, palette_for
from discord_fix.store import Store


class AppearanceTests(unittest.TestCase):
    def test_all_theme_text_and_selected_states_meet_readability_target(self):
        for theme in PALETTES:
            with self.subTest(theme=theme):
                palette = palette_for(theme)
                self.assertGreaterEqual(
                    contrast_ratio(palette["foreground"], palette["surface"]), 4.5
                )
                self.assertGreaterEqual(contrast_ratio(palette["muted"], palette["surface"]), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(palette["accent_text"], palette["accent"]), 4.5
                )

    def test_high_contrast_overrides_theme(self):
        palette = palette_for("light", high_contrast=True)
        self.assertEqual(palette["background"], "#000000")
        self.assertGreaterEqual(contrast_ratio(palette["accent_text"], palette["accent"]), 4.5)
        with self.assertRaises(ValueError):
            palette_for("unknown")

    def test_display_preferences_validate_and_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.sqlite"
            store = Store(path)
            self.assertEqual(store.settings()["theme"], "light")
            widths = dict(date=145, channel=180, message=620, state=130)
            store.save_settings(
                {
                    "theme": "ash",
                    "density": "spacious",
                    "font_size": 13,
                    "message_font_size": 18,
                    "column_widths": widths,
                }
            )
            store.db.close()

            reopened = Store(path)
            settings = reopened.settings()
            self.assertEqual(settings["theme"], "ash")
            self.assertEqual(settings["density"], "spacious")
            self.assertEqual(settings["font_size"], 13)
            self.assertEqual(settings["message_font_size"], 18)
            self.assertEqual(settings["column_widths"], widths)
            reopened.db.close()

    def test_invalid_display_preferences_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "settings.sqlite")
            for changes in (
                {"theme": "neon"},
                {"density": "tiny"},
                {"message_font_size": 33},
                {"column_widths": {"message": 500}},
                {"column_widths": {"date": 10, "channel": 150, "message": 440, "state": 120}},
            ):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    store.save_settings(changes)
            store.db.close()


if __name__ == "__main__":
    unittest.main()
