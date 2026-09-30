import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from discord_fix import summaries
from discord_fix.store import Store
from discord_fix.web_dashboard import DashboardServer
from discord_fix.web_data import message_data, page_data, summary_data
from discord_fix.web_workflow import WorkflowConflict, apply_workflow


def record(ident, **values):
    return (
        dict(
            id=str(ident),
            channel="123",
            channel_name="Test planning",
            guild="456",
            content="Please review this decision? " + str(ident),
            timestamp="2026-09-30T10:00:00+00:00",
            attachments="[]",
            author="Synthetic author",
            author_id="789",
        )
        | values
    )


class BrowserWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite"
        self.store = Store(self.path)
        self.store.source(
            "test", "import", "Synthetic export", "imported", config={"token": "secret"}
        )

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def ingest(self, records, source="test"):
        self.store.ingest(records, source_id=source, source_kind="import")

    def test_all_pages_and_full_content_reachable(self):
        self.ingest([record(i, content="needle " + "x" * 1500) for i in range(100, 245)])
        first = page_data(self.path, "Everything", "needle")
        self.assertEqual(first["pagination"]["total"], 145)
        self.assertEqual(len(first["items"]), 60)
        second = page_data(
            self.path, "Everything", "needle", offset=60, anchor=first["pagination"]["anchor"]
        )
        third = page_data(
            self.path, "Everything", "needle", offset=120, anchor=first["pagination"]["anchor"]
        )
        ids = [item["id"] for page in (first, second, third) for item in page["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {str(i) for i in range(100, 245)})
        detail = message_data(self.path, "100")
        self.assertGreater(len(detail["content"]), 420)
        self.assertTrue(first["items"][0]["content_truncated"])
        self.assertFalse(detail["content_truncated"])
        self.assertNotIn("secret", json.dumps(detail))

    def test_new_import_does_not_shift_existing_page_boundary(self):
        self.ingest([record(i) for i in range(100, 180)])
        first = page_data(self.path, "Everything")
        self.ingest([record(999, timestamp="2026-10-01T00:00:00+00:00")])
        second = page_data(self.path, "Everything", offset=60, anchor=first["pagination"]["anchor"])
        self.assertEqual(second["pagination"]["total"], 80)
        self.assertTrue(second["new_items"])
        self.assertNotIn("999", [item["id"] for item in second["items"]])

    def test_grouping_uses_threads_replies_and_source_boundaries(self):
        self.store.source("other", "import", "Other export", "imported")
        self.ingest(
            [
                record(100),
                record(101, reply_to="100"),
                record(102),
                record(103, channel="124", parent_channel="123", conversation="124"),
                record(104, channel="124", parent_channel="123", conversation="124"),
            ]
        )
        self.ingest([record(105, reply_to="100")], "other")
        page = page_data(self.path, "Conversations")
        self.assertEqual(len(page["groups"]), 4)
        self.assertEqual(sorted(group["count"] for group in page["groups"]), [1, 1, 2, 2])
        group = next(group for group in page["groups"] if group["kind"] == "reply")
        members = page_data(self.path, "Conversations", conversation=group["id"])
        self.assertEqual({item["id"] for item in members["items"]}, {"100", "101"})
        pinned = page_data(self.path, "Conversations", pinned=[group["id"]])
        self.assertEqual(pinned["pagination"]["total"], 1)
        self.assertEqual(page_data(self.path, "Conversations", pinned=[])["groups"], [])

    def test_deleted_highest_row_does_not_allow_new_import_into_old_boundary(self):
        self.ingest([record(100), record(101)])
        before = page_data(self.path, "Everything")
        with self.store.db:
            self.store.db.execute("DELETE FROM messages WHERE id='101'")
        self.ingest([record(102)])
        after = page_data(self.path, "Everything", anchor=before["pagination"]["anchor"])
        self.assertEqual([item["id"] for item in after["items"]], ["100"])
        self.assertTrue(after["new_items"])
        self.assertEqual(
            self.store.db.execute(
                "SELECT COUNT(*) FROM browser_message_sequence WHERE message_id='101'"
            ).fetchone()[0],
            0,
        )

    def test_reopening_store_does_not_report_fictitious_new_messages(self):
        self.ingest([record(100), record(101)])
        before = page_data(self.path)
        self.store.db.close()
        self.store = Store(self.path)
        after = page_data(self.path, anchor=before["pagination"]["anchor"])
        self.assertEqual(after["pagination"]["anchor"], before["pagination"]["anchor"])
        self.assertFalse(after["new_items"])

    def test_priority_reason_is_english_and_preserves_manual_override(self):
        self.ingest([record(100)])
        self.store.save_settings({"important_topics": ["decision"]})
        self.store.update("100", "important")
        item = message_data(self.path, "100")
        self.assertFalse(item["important"])
        self.assertEqual(item["reasons"][0]["code"], "priority_off")
        self.assertEqual(item["reasons"][0]["text"], "You marked this as not important.")
        self.assertIn("topic", {reason["code"] for reason in item["reasons"]})

    def test_since_last_visit_uses_receipt_or_edit_not_original_date(self):
        self.ingest([record(100), record(101)])
        visit = datetime.now(timezone.utc).isoformat()
        with self.store.db:
            self.store.db.execute(
                "UPDATE messages SET imported_at='2020-01-01T00:00:00+00:00',edited_at='' "
            )
            self.store.db.execute(
                "UPDATE messages SET edited_at=? WHERE id='101'",
                ((datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),),
            )
        data = page_data(self.path, "Everything", since=visit)
        self.assertEqual([item["id"] for item in data["items"]], ["101"])
        with self.assertRaises(ValueError):
            page_data(self.path, since="2026-01-01")

    def test_workflow_snooze_undo_and_conflicts_preserve_text(self):
        self.ingest([record(100)])
        original = message_data(self.path, "100")
        changed = apply_workflow(
            self.path, dict(id="100", action="later", minutes=60, revision=original["revision"])
        )
        self.assertEqual(self.store.get("100")["state"], "later")
        with self.assertRaises(WorkflowConflict):
            apply_workflow(
                self.path, dict(id="100", action="complete", revision=original["revision"])
            )
        apply_workflow(
            self.path, dict(id="100", action="undo", revision=changed["revision"]), changed
        )
        self.assertEqual(self.store.get("100")["state"], "open")
        self.assertEqual(self.store.get("100")["content"], original["content"])
        changed = apply_workflow(
            self.path,
            dict(id="100", action="important", revision=message_data(self.path, "100")["revision"]),
        )
        self.assertEqual(message_data(self.path, "100")["revision"], changed["revision"])
        self.assertTrue(message_data(self.path, "100")["important"])
        self.store.update("100", "reply")
        with self.assertRaises(WorkflowConflict):
            apply_workflow(
                self.path, dict(id="100", action="undo", revision=changed["revision"]), changed
            )

    def test_invalid_actions_and_deleted_messages_do_not_write(self):
        self.ingest([record(100)])
        item = message_data(self.path, "100")
        for payload in [
            dict(action="send"),
            dict(action="later", minutes=True),
            dict(action="later", minutes=0),
            dict(action="undo"),
        ]:
            with self.assertRaises(ValueError):
                apply_workflow(self.path, dict(id="100", revision=item["revision"]) | payload)
        self.assertEqual(self.store.get("100")["state"], "open")
        with self.store.db:
            self.store.db.execute("UPDATE messages SET deleted=1 WHERE id='100'")
        self.assertEqual(message_data(self.path, "100")["content"], "")
        with self.assertRaises(WorkflowConflict):
            apply_workflow(self.path, dict(id="100", action="complete", revision=item["revision"]))

    def summarize(self):
        snapshot = summaries.prepare(self.store)
        summaries.commit(self.store, snapshot, summaries.build(snapshot, summaries.Extractive()))

    def test_undo_rejects_intervening_changes_even_if_state_returns_to_same_value(self):
        self.ingest([record(100)])
        initial = message_data(self.path, "100")
        changed = apply_workflow(
            self.path, dict(id="100", action="complete", revision=initial["revision"])
        )
        self.store.update("100", "reopen")
        self.store.update("100", "complete")
        latest = message_data(self.path, "100")
        self.assertNotEqual(latest["revision"], changed["revision"])
        with self.assertRaises(WorkflowConflict):
            apply_workflow(
                self.path, dict(id="100", action="undo", revision=latest["revision"]), changed
            )

    def test_saved_summary_pages_and_evidence_fail_closed_after_edit(self):
        self.ingest([record(i) for i in range(100, 145)])
        self.summarize()
        first = summary_data(self.path)
        self.assertEqual(first["total"], 45)
        self.assertEqual(len(first["entries"]), 30)
        self.assertEqual(len(summary_data(self.path, offset=30)["entries"]), 15)
        self.assertEqual(first["model"], "Local text extraction (no generative AI)")
        self.assertIsNone(summary_data(self.path, demo=True)["entries"][0]["citations"][0]["url"])
        with self.store.db:
            # Preserve the cited quote but change the surrounding source: hashes must catch it.
            self.store.db.execute("UPDATE messages SET content=content||' changed' WHERE id='100'")
        self.assertTrue(summary_data(self.path)["needs_refresh"])
        self.assertEqual(summary_data(self.path)["entries"], [])

    def test_saved_summary_rejects_excluded_uncited_source_and_malformed_body(self):
        self.ingest([record(100), record(101)])
        self.summarize()
        with self.store.db:
            row = self.store.db.execute(
                "SELECT body FROM summaries WHERE scope='personal'"
            ).fetchone()
            body = json.loads(row["body"])
            body["entries"] = [body["entries"][0]]
            self.store.db.execute(
                "UPDATE summaries SET body=? WHERE scope='personal'", (json.dumps(body),)
            )
            self.store.db.execute("INSERT INTO exclusions VALUES('message','101')")
        self.assertTrue(summary_data(self.path)["needs_refresh"])
        with self.store.db:
            self.store.db.execute("UPDATE summaries SET body='[]' WHERE scope='personal'")
        self.assertFalse(summary_data(self.path)["available"])

    def request(self, server, payload, **headers):
        request = Request(
            server.url + "api/workflow",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "X-Discord-Fix-Nonce": server.write_nonce}
            | headers,
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, error.read()
            finally:
                error.close()

    def test_http_action_authentication_and_undo_replay(self):
        self.ingest([record(100)])
        server = DashboardServer(self.path)
        server.start()
        try:
            payload = dict(
                id="100", action="complete", revision=message_data(self.path, "100")["revision"]
            )
            for headers in [
                {"X-Discord-Fix-Nonce": "wrong"},
                {"Origin": "https://attacker.example"},
                {"Origin": "http://["},
                {"Host": "127.0.0.1:1"},
                {"Content-Type": "text/plain"},
            ]:
                status, _ = self.request(server, payload, **headers)
                self.assertIn(status, (400, 403))
            self.assertEqual(self.store.get("100")["state"], "open")
            status, changed = self.request(server, payload, Origin="chrome-extension://" + "a" * 32)
            self.assertEqual(status, 200)
            self.assertEqual(self.request(server, payload)[0], 409)
            undo_payload = dict(
                id="100", action="undo", revision=changed["revision"], undo=changed["undo"]
            )
            self.assertEqual(self.request(server, undo_payload)[0], 200)
            self.assertEqual(self.request(server, undo_payload)[0], 409)
            self.assertEqual(self.store.get("100")["state"], "open")
        finally:
            server.stop()

    def test_demo_never_enables_local_writes(self):
        self.ingest([record(100)])
        server = DashboardServer(self.path, demo=True)
        server.start()
        try:
            with urlopen(server.url + "api/dashboard") as response:
                data = json.loads(response.read())
            self.assertFalse(data["workflow"]["enabled"])
            self.assertEqual(data["workflow"]["nonce"], "")
            self.assertEqual(
                self.request(
                    server, dict(id="100", action="complete", revision=data["items"][0]["revision"])
                )[0],
                403,
            )
        finally:
            server.stop()
