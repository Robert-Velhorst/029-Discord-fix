import json
import tempfile
import unittest
from pathlib import Path

from discord_fix import summaries
from discord_fix.connector import (
    AccessDenied,
    DiscordBot,
    RateLimited,
    apply_sync,
    can_read,
    sync_failure,
)
from discord_fix.network import HttpFailure
from discord_fix.store import Store
from discord_fix.vault import Vault


def record(ident="101", **changes):
    return (
        dict(
            id=ident,
            channel="10",
            channel_name="Project",
            guild="20",
            content="We hebben besloten om morgen te beginnen.",
            timestamp="2026-09-12T10:00:00+00:00",
            attachments="[]",
            author="Alex",
            author_id="30",
        )
        | changes
    )


class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = Store(self.path / "test.sqlite")

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def summarize(self, force=False, provider=None):
        snapshot = summaries.prepare(self.store)
        result = summaries.build(snapshot, provider or summaries.Extractive(), force)
        summaries.commit(self.store, snapshot, result)
        return result

    def test_all_summary_levels_have_valid_sources(self):
        self.store.ingest(
            [
                record(),
                record(
                    "102",
                    channel="11",
                    conversation="11",
                    parent_channel="10",
                    content="Wie maakt dit af?",
                ),
            ]
        )
        output = self.summarize()
        self.assertEqual(
            {s["scope"] for s in output}, {"conversation", "channel", "server", "personal"}
        )
        personal = next(s for s in output if s["scope"] == "personal")
        body = json.loads(personal["body"])
        self.assertEqual(set(body["source_hashes"]), {"101", "102"})
        summaries.validate_entries(body["entries"], self.store.summary_records())

    def test_every_exclusion_scope_blocks_higher_levels(self):
        for scope, target in [
            ("source", "legacy-import"),
            ("server", "20"),
            ("channel", "10"),
            ("conversation", "10"),
            ("message", "101"),
            ("personal", "*"),
        ]:
            with self.subTest(scope=scope):
                self.store.ingest([record()])
                self.summarize()
                summaries.correct(self.store, "personal", "*", "Private correctie")
                self.store.exclude(scope, target)
                self.assertEqual(self.store.summary_records(), [])
                self.assertEqual(
                    self.store.db.execute("SELECT count(*) FROM summary_notes").fetchone()[0], 0
                )
                self.assertEqual(self.summarize(), [])
                self.store.exclude(scope, target, False)

    def test_parent_channel_excludes_threads(self):
        self.store.ingest([record(parent_channel="5")])
        self.store.exclude("channel", "5")
        self.assertEqual(self.store.summary_records(), [])

    def test_privacy_race_rejects_provider_result(self):
        self.store.ingest([record()])
        snapshot = summaries.prepare(self.store)
        output = summaries.build(snapshot, summaries.Extractive())
        self.store.exclude("message", "101")
        with self.assertRaises(ValueError):
            summaries.commit(self.store, snapshot, output)

    def test_incremental_cache_edit_and_full_reconciliation(self):
        class Counter(summaries.Extractive):
            def __init__(self):
                self.ids = []

            def summarize(self, rows):
                self.ids.extend(r["id"] for r in rows)
                return super().summarize(rows)

        provider = Counter()
        self.store.ingest([record()])
        self.summarize(provider=provider)
        self.summarize(provider=provider)
        self.assertEqual(provider.ids, ["101"])
        self.store.ingest([record("102", content="Wat gebeurt er daarna?")])
        self.summarize(provider=provider)
        self.assertEqual(provider.ids, ["101", "102"])
        self.store.ingest([record(content="We hebben besloten om te wachten.")])
        self.summarize(provider=provider)
        self.assertEqual(len(provider.ids), 4)
        self.summarize(force=True, provider=provider)
        self.assertEqual(len(provider.ids), 6)

    def test_false_citation_and_external_consent_rejected(self):
        entries = [
            dict(category="facts", text="claim", citations=[dict(id="101", quote="Invented")])
        ]
        with self.assertRaises(ValueError):
            summaries.validate_entries(entries, [record()])
        for kind, url, consent in [
            ("ollama", "http://example.org/api/chat", ""),
            ("external", "https://example.org/v1/chat/completions", ""),
            ("external", "http://example.org", "http://example.org"),
        ]:
            with self.assertRaises(ValueError):
                summaries.validate_endpoint(kind, url, consent)

    def test_provider_contract_and_untrusted_instructions(self):
        captured = []

        def transport(url, **kwargs):
            captured.append(kwargs["payload"])
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "entries": [
                                dict(
                                    category="facts",
                                    text="Candidate",
                                    citations=[dict(id="101", quote="We hebben besloten")],
                                )
                            ]
                        }
                    )
                }
            }, {}

        provider = summaries.ChatProvider(
            "ollama", "http://127.0.0.1:11434/api/chat", "test", transport=transport
        )
        result = provider.summarize([record()])
        self.assertIn("AI-interpretatie", result[0]["basis"])
        self.assertEqual(captured[0]["messages"][1]["role"], "user")

    def test_manual_override_dominates_rules_and_reimport(self):
        self.store.save_settings(dict(important_people=["30"], user_id="99"))
        self.store.ingest([record(mentions='["99"]')], source_id="bot-test", source_kind="bot")
        self.assertEqual(self.store.get("101")["important"], 1)
        self.assertEqual(self.store.get("101")["reply"], 1)
        self.store.update("101", "important")
        self.store.update("101", "reply")
        self.store.ingest([record(mentions='["99"]')], source_id="bot-test", source_kind="bot")
        self.assertEqual(self.store.get("101")["important"], 0)
        self.assertEqual(self.store.get("101")["reply"], 0)
        self.store.update("101", "reset_rules")
        self.assertEqual(self.store.get("101")["important"], 1)

    def test_revocation_stops_ai_and_keeps_local_messages(self):
        self.store.source("bot-test", "bot", "Test", "pending", config={"channels": ["10"]})
        source = self.store.sources()[0]
        apply_sync(
            self.store,
            source,
            ([record()], [dict(channel="10", ids=["101"], exhausted=True)], "test"),
        )
        self.assertEqual(len(self.store.summary_records()), 1)
        self.summarize()
        sync_failure(self.store, source, AccessDenied("Geen toegang"))
        self.assertEqual(self.store.summary_records(), [])
        self.assertEqual(len(self.store.query()), 1)
        self.assertEqual(self.store.sources()[0]["status"], "revoked")

    def test_deleted_messages_only_in_complete_scanned_window(self):
        self.store.source("bot-test", "bot", "Test", "pending")
        source = self.store.sources()[0]
        self.store.ingest([record("90"), record("100"), record("110")], "bot-test", "bot")
        apply_sync(
            self.store,
            source,
            ([record("100")], [dict(channel="10", ids=["100"], exhausted=False)], "test"),
        )
        self.assertEqual(self.store.get("90")["deleted"], 0)
        self.assertEqual(self.store.get("110")["deleted"], 1)
        self.assertEqual(self.store.get("110")["content"], "")

    def test_read_permissions_overwrites(self):
        guild = dict(
            id="20", owner_id="1", roles=[dict(id="20", permissions=str((1 << 10) | (1 << 16)))]
        )
        member = dict(roles=[])
        self.assertTrue(can_read(guild, member, {}, "30"))
        channel = dict(permission_overwrites=[dict(id="30", type=1, deny=str(1 << 16), allow="0")])
        self.assertFalse(can_read(guild, member, channel, "30"))

    def test_bot_rejects_user_identity_and_respects_rate_limit(self):
        client = DiscordBot(
            "synthetic-token", transport=lambda *a, **k: ({"id": "30", "bot": False}, {})
        )
        with self.assertRaises(AccessDenied):
            client.collect(["10"])

        def limited(*args, **kwargs):
            raise HttpFailure(429, body={"retry_after": 120})

        with self.assertRaises(RateLimited) as caught:
            DiscordBot("synthetic-rate-limited-token", transport=limited).identity()
        self.assertEqual(caught.exception.seconds, 120)

    def test_official_bot_request_contract(self):
        requests = []

        def transport(url, **kwargs):
            requests.append((url, kwargs))
            route = url.removeprefix("https://discord.com/api/v10")
            payload = {
                "/users/@me": {"id": "30", "bot": True},
                "/channels/10": {"id": "10", "type": 0, "guild_id": "20", "name": "Project"},
                "/guilds/20": {
                    "id": "20",
                    "owner_id": "1",
                    "roles": [{"id": "20", "permissions": str((1 << 10) | (1 << 16))}],
                },
                "/guilds/20/members/30": {"roles": []},
                "/channels/10/messages?limit=100": [
                    {
                        "id": "101",
                        "channel_id": "10",
                        "author": {"id": "40", "username": "Alex"},
                        "content": "Hoi",
                        "timestamp": "2026-09-12T10:00:00Z",
                    }
                ],
            }[route]
            return payload, {}

        rows, windows, _ = DiscordBot("synthetic-token", transport=transport).collect(["10"])
        self.assertEqual(rows[0]["author"], "Alex")
        self.assertTrue(windows[0]["exhausted"])
        self.assertTrue(
            all(k["headers"]["Authorization"] == "Bot synthetic-token" for _, k in requests)
        )
        self.assertTrue(all("payload" not in k for _, k in requests))

    def test_retention_backup_and_export(self):
        self.store.ingest([record(timestamp="2000-01-01T00:00:00+00:00")])
        self.store.backup(self.path / "backup.sqlite")
        self.assertEqual(self.store.export_data()["messages"][0]["id"], "101")
        self.store.save_settings(dict(retention_days=30))
        self.assertEqual(self.store.apply_retention(), 1)
        backup = Store(self.path / "backup.sqlite")
        self.assertEqual(len(backup.query()), 1)
        backup.db.close()

    def test_windows_secret_roundtrip_no_plaintext(self):
        import os

        if os.name != "nt":
            self.skipTest("Windows DPAPI test")
        vault = Vault(self.path / "secrets")
        vault.save("test", "synthetic-secret-123")
        self.assertEqual(vault.read("test"), "synthetic-secret-123")
        self.assertNotIn(b"synthetic-secret-123", (self.path / "secrets/test.dpapi").read_bytes())
        vault.forget("test")
        self.assertEqual(vault.read("test"), "")

    def test_fulltext_index_tracks_edits_and_deletions(self):
        self.store.ingest([record(content="Unieke zoekterm voor vandaag")])
        self.assertEqual(len(self.store.query(search="zoekterm vandaag", fulltext=True)), 1)
        self.store.ingest([record(content="Helemaal gewijzigd")])
        self.assertEqual(self.store.query(search="zoekterm", fulltext=True), [])
        self.assertEqual(len(self.store.query(search="gewijzigd", fulltext=True)), 1)
        self.store.delete_source_data("legacy-import")
        self.assertEqual(self.store.query(search="gewijzigd", fulltext=True), [])

    def test_initial_database_migrates_without_losing_workflow(self):
        import sqlite3

        initial = self.path / "initial.sqlite"
        connection = sqlite3.connect(initial)
        connection.executescript("""
            CREATE TABLE messages(id TEXT PRIMARY KEY,channel TEXT NOT NULL,channel_name TEXT NOT NULL,
                guild TEXT NOT NULL,content TEXT NOT NULL,timestamp TEXT NOT NULL,attachments TEXT NOT NULL,
                imported_at TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'open',until TEXT,
                important INTEGER NOT NULL DEFAULT 0,reply INTEGER NOT NULL DEFAULT 0);
            INSERT INTO messages VALUES('101','10','Project','20','Bewaren','2026-09-12T10:00:00+00:00',
                '[]','2026-09-12T10:00:00+00:00','complete',NULL,1,0);
        """)
        connection.close()
        migrated = Store(initial)
        try:
            row = migrated.get("101")
            self.assertEqual(
                (row["content"], row["state"], row["important"], row["priority_override"]),
                ("Bewaren", "complete", 1, 1),
            )
            self.assertEqual(len(migrated.query(search="Bewaren", fulltext=True)), 1)
        finally:
            migrated.db.close()

    def test_failed_provider_preserves_messages_and_previous_summary(self):
        self.store.ingest([record()])
        previous = self.summarize()
        self.store.ingest([record("102", content="Nieuw bericht")])

        class Broken(summaries.Extractive):
            def summarize(self, rows):
                raise RuntimeError("Provider offline")

        with self.assertRaises(RuntimeError):
            summaries.build(summaries.prepare(self.store), Broken(), force=True)
        self.assertEqual(len(self.store.query()), 2)
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM summaries").fetchone()[0], len(previous)
        )

    def test_new_source_data_keeps_previous_bot_information(self):
        self.store.ingest([record(content="Botinhoud")], "bot-test", "bot")
        self.store.update("101", "complete")
        self.store.ingest([record(content="Persoonlijk exportfragment")], "second-import", "import")
        self.assertEqual(self.store.get("101")["content"], "Botinhoud")
        self.assertEqual(self.store.get("101")["state"], "complete")

    def test_native_panels_and_scrollable_actions(self):
        import tkinter as tk

        from discord_fix import panels
        from discord_fix.__main__ import App
        from discord_fix.widgets import Scrollable

        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root, self.store)
            self.assertTrue(any(isinstance(child, Scrollable) for child in root.winfo_children()))
            for panel in (
                panels.sources_panel,
                panels.settings_panel,
                panels.privacy_panel,
                panels.summaries_panel,
                panels.notifications_panel,
            ):
                panel(app)
                root.update_idletasks()
                for child in root.winfo_children():
                    if isinstance(child, tk.Toplevel):
                        child.destroy()
                app.summary_windows.clear()
            root.after_cancel(app.timer)
        finally:
            root.destroy()

    def test_single_instance_lock(self):
        from discord_fix.instance import InstanceLock

        lock = InstanceLock(self.path / "instance.lock")
        try:
            with self.assertRaises(RuntimeError):
                InstanceLock(self.path / "instance.lock")
        finally:
            lock.close()

    def test_http_transport_rejects_redirects(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        from discord_fix.network import request_json

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/never-follow")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HttpFailure) as failure:
                request_json(
                    "http://127.0.0.1:" + str(server.server_port),
                    headers={"Authorization": "synthetic"},
                )
            self.assertEqual(failure.exception.status, 302)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_sync_transaction_rolls_back_all_writes_on_error(self):
        self.store.source("bot-test", "bot", "Test", "pending")
        source = self.store.sources()[0]
        self.store.ingest([record(content="Origineel")], "bot-test", "bot")
        with self.assertRaises(ValueError):
            apply_sync(
                self.store,
                source,
                (
                    [record(content="Niet bewaren")],
                    [dict(channel="10", ids=["invalid"], exhausted=False)],
                    "test",
                ),
            )
        self.assertEqual(self.store.get("101")["content"], "Origineel")

    def test_external_keys_are_scoped_to_exact_endpoint(self):
        names = []

        class FakeVault:
            def read(self, name):
                names.append(name)
                return "synthetic"

        config = self.store.settings() | dict(
            provider="external",
            model="synthetic",
            endpoint="https://first.example/v1/chat/completions",
            external_consent="https://first.example/v1/chat/completions",
        )
        summaries.create_provider(config, FakeVault())
        config.update(
            endpoint="https://second.example/v1/chat/completions",
            external_consent="https://second.example/v1/chat/completions",
        )
        summaries.create_provider(config, FakeVault())
        self.assertNotEqual(names[0], names[1])

    def test_model_incremental_update_receives_previous_summary(self):
        captured = []

        def transport(url, **kwargs):
            data = json.loads(kwargs["payload"]["messages"][1]["content"])
            captured.append(data)
            entries = list(data["previous_summary"])
            for row in data["new_records"]:
                entries.append(
                    dict(
                        category="facts",
                        text=row["content"],
                        citations=[dict(id=row["id"], quote=row["content"])],
                    )
                )
            return {"message": {"content": json.dumps({"entries": entries})}}, {}

        provider = summaries.ChatProvider(
            "ollama", "http://127.0.0.1:11434/api/chat", "synthetic", transport=transport
        )
        self.store.ingest([record()])
        self.summarize(provider=provider)
        self.store.ingest([record("102", content="Nieuw besluit")])
        self.summarize(provider=provider)
        self.assertEqual(len(captured[1]["previous_summary"]), 1)
        self.assertEqual([r["id"] for r in captured[1]["new_records"]], ["102"])

    def test_automatic_per_source_interval_and_manual_refresh(self):
        self.store.ingest([record()])
        self.store.source("legacy-import", config={"summary_minutes": 1440})
        self.summarize()
        self.store.ingest([record("102", content="Nieuw beschikbaar")])
        snapshot = summaries.prepare(self.store)
        deferred = summaries.build(snapshot, summaries.Extractive(), automatic=True)
        personal = next(s for s in deferred if s["scope"] == "personal")
        self.assertEqual(set(json.loads(personal["body"])["source_hashes"]), {"101"})
        manual = self.summarize()
        personal = next(s for s in manual if s["scope"] == "personal")
        self.assertEqual(set(json.loads(personal["body"])["source_hashes"]), {"101", "102"})


if __name__ == "__main__":
    unittest.main()
