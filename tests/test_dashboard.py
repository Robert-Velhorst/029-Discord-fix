import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from discord_fix.store import Store
from discord_fix.web_dashboard import DashboardServer, dashboard_data


def sample(ident, content):
    return dict(
        id=ident,
        channel="123",
        channel_name="planning-test",
        guild="456",
        content=content,
        timestamp="2026-09-23T10:00:00+00:00",
        attachments="[]",
        author="Synthetische gebruiker",
        author_id="789",
    )


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "dashboard.sqlite"
        self.store = Store(self.path)
        self.store.source(
            "preview", "import", "Voorbeeldbron", "imported", config={"token": "do not expose"}
        )
        self.store.ingest(
            [
                sample("101", "Een synthetische vraag over de preview"),
                sample("102", "Een tweede synthetisch bericht"),
            ],
            source_id="preview",
            source_kind="import",
        )
        self.store.update("101", "important")
        self.store.update("101", "reply")

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def assert_http_error(self, request, expected_status):
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        try:
            self.assertEqual(error.exception.code, expected_status)
        finally:
            error.exception.close()

    def test_snapshot_is_read_only_and_normalizes_expired_snoozes(self):
        deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.store.update("102", "later", deadline)
        with self.store.db:
            self.store.db.execute(
                "UPDATE messages SET until='2000-01-01T00:00:00+00:00' WHERE id='102'"
            )
        raw_state = self.store.db.execute(
            "SELECT state,until FROM messages WHERE id='102'"
        ).fetchone()
        audits_before = self.store.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        notifications_before = self.store.db.execute(
            "SELECT COUNT(*) FROM notifications"
        ).fetchone()[0]

        result = dashboard_data(self.path)

        self.assertEqual(result["counts"]["total"], 2)
        self.assertEqual(result["counts"]["important"], 1)
        self.assertEqual(result["counts"]["reply"], 1)
        self.assertEqual(result["counts"]["later"], 0)
        self.assertEqual(
            next(row for row in result["items"] if row["id"] == "102")["state"], "open"
        )
        self.assertEqual(
            tuple(raw_state),
            tuple(
                self.store.db.execute("SELECT state,until FROM messages WHERE id='102'").fetchone()
            ),
        )
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], audits_before
        )
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
            notifications_before,
        )
        self.assertTrue(result["items"][0]["url"].startswith("https://discord.com/channels/"))
        self.assertNotIn("token", json.dumps(result, ensure_ascii=False))

    def test_browser_dashboard_is_token_gated_local_and_live(self):
        dashboard = DashboardServer(self.path, demo=True)
        base_url = dashboard.start()
        try:
            with urlopen(base_url, timeout=3) as response:
                page = response.read().decode("utf-8")
                self.assertIn("Jouw Discord-overzicht", page)
                self.assertIn("Voorbeeldgegevens", page)
                self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)

            query = urlencode({"view": "Important Now", "q": "synthetische vraag"})
            with urlopen(base_url + "api/dashboard?" + query, timeout=3) as response:
                snapshot = json.loads(response.read())
            self.assertTrue(snapshot["demo"])
            self.assertEqual([item["id"] for item in snapshot["items"]], ["101"])
            self.assertEqual(snapshot["sources"][0]["name"], "Voorbeeldbron")
            self.assertNotIn("token", json.dumps(snapshot, ensure_ascii=False))

            self.assert_http_error(base_url + "api/dashboard?view=made-up", 400)

            bad_host = Request(base_url, headers={"Host": "attacker.example"})
            self.assert_http_error(bad_host, 403)

            self.assert_http_error(base_url.replace(dashboard.token, "wrong-token"), 404)

            write_request = Request(base_url + "api/dashboard", data=b"{}", method="POST")
            self.assert_http_error(write_request, 405)

            self.store.ingest(
                [sample("103", "Nieuw lokaal bericht")],
                source_id="preview",
                source_kind="import",
            )
            with urlopen(base_url + "api/dashboard?view=Everything", timeout=3) as response:
                refreshed = json.loads(response.read())
            self.assertEqual(refreshed["counts"]["total"], 3)
            self.assertEqual(refreshed["items"][0]["id"], "103")
        finally:
            dashboard.stop()


if __name__ == "__main__":
    unittest.main()
