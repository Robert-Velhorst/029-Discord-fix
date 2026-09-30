"""Transactional local data, migration, privacy and workflow state."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .priority import classify


def now():
    return datetime.now(timezone.utc).isoformat()


DEFAULTS = dict(
    user_id="",
    important_people=[],
    important_servers=[],
    important_channels=[],
    important_topics=[],
    summary_minutes=60,
    sync_minutes=5,
    auto_sync=False,
    auto_summaries=False,
    provider="extractive",
    endpoint="http://127.0.0.1:11434/api/chat",
    model="",
    external_consent="",
    retention_days=0,
    font_size=11,
    message_font_size=11,
    density="comfortable",
    theme="light",
    column_widths={"date": 160, "channel": 150, "message": 440, "state": 120},
    high_contrast=False,
    notify_priority=True,
    notify_summary=True,
    notify_snooze=True,
    notify_source=True,
    notify_deadline=True,
)


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            raise ValueError("Database komt uit een nieuwere appversie.")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY, channel TEXT NOT NULL, channel_name TEXT NOT NULL,
                guild TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL,
                attachments TEXT NOT NULL, imported_at TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'open', until TEXT,
                important INTEGER NOT NULL DEFAULT 0, reply INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS messages_channel ON messages(channel);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,
                status TEXT NOT NULL,last_sync TEXT,detail TEXT NOT NULL DEFAULT '',
                config TEXT NOT NULL DEFAULT '{}',next_sync TEXT);
            CREATE TABLE IF NOT EXISTS exclusions(scope TEXT NOT NULL,target TEXT NOT NULL,PRIMARY KEY(scope,target));
            CREATE TABLE IF NOT EXISTS summaries(scope TEXT NOT NULL,target TEXT NOT NULL,fingerprint TEXT NOT NULL,
                version INTEGER NOT NULL,body TEXT NOT NULL,model TEXT NOT NULL,generated_at TEXT NOT NULL,
                elapsed REAL NOT NULL,note TEXT NOT NULL DEFAULT '',PRIMARY KEY(scope,target));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,timestamp TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,key TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,text TEXT NOT NULL,created_at TEXT NOT NULL,read INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS summary_notes(id INTEGER PRIMARY KEY,scope TEXT NOT NULL,target TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
        additions = dict(
            source_id="TEXT NOT NULL DEFAULT 'legacy-import'",
            source_kind="TEXT NOT NULL DEFAULT 'import'",
            author_id="TEXT NOT NULL DEFAULT ''",
            author="TEXT NOT NULL DEFAULT 'Jij (eigen export)'",
            conversation="TEXT NOT NULL DEFAULT ''",
            parent_channel="TEXT NOT NULL DEFAULT ''",
            mentions="TEXT NOT NULL DEFAULT '[]'",
            reply_to="TEXT NOT NULL DEFAULT ''",
            reply_author="TEXT NOT NULL DEFAULT ''",
            edited_at="TEXT NOT NULL DEFAULT ''",
            deleted="INTEGER NOT NULL DEFAULT 0",
            priority_override="INTEGER",
            reply_override="INTEGER",
            deadline="TEXT",
            reason="TEXT NOT NULL DEFAULT '[]'",
            search_text="TEXT NOT NULL DEFAULT ''",
            workflow_revision="INTEGER NOT NULL DEFAULT 0",
        )
        columns = {r["name"] for r in self.db.execute("PRAGMA table_info(messages)")}
        with self.db:
            for column, definition in additions.items():
                if column not in columns:
                    self.db.execute(f"ALTER TABLE messages ADD COLUMN {column} {definition}")
            if version < 2:
                self.db.execute("UPDATE messages SET conversation=channel WHERE conversation=''")
                self.db.execute(
                    "UPDATE messages SET priority_override=important,reply_override=reply"
                )
                for row in self.db.execute(
                    "SELECT id,content,channel_name FROM messages"
                ).fetchall():
                    self.db.execute(
                        "UPDATE messages SET search_text=? WHERE id=?",
                        ((row["content"] + " " + row["channel_name"]).casefold(), row["id"]),
                    )
                self.db.execute("PRAGMA user_version=2")
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS messages_workflow ON messages(state,important,reply,timestamp)"
            )
            self.db.execute("CREATE INDEX IF NOT EXISTS messages_source ON messages(source_id)")
            if self.db.execute(
                "SELECT 1 FROM messages WHERE source_id='legacy-import' LIMIT 1"
            ).fetchone():
                self.db.execute(
                    "INSERT OR IGNORE INTO sources(id,kind,name,status,detail) VALUES('legacy-import','import','Eerdere import','imported','Alleen eigen verzonden berichten')"
                )
        indexed = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='messages_fts'"
        ).fetchone()
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS browser_message_sequence (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL);
            INSERT INTO browser_message_sequence(message_id)
                SELECT id FROM messages WHERE NOT EXISTS(
                    SELECT 1 FROM browser_message_sequence WHERE message_id=messages.id)
                ORDER BY rowid;
            CREATE TRIGGER IF NOT EXISTS messages_browser_insert AFTER INSERT ON messages BEGIN
                INSERT INTO browser_message_sequence(message_id) VALUES(new.id);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_browser_delete AFTER DELETE ON messages BEGIN
                DELETE FROM browser_message_sequence WHERE message_id=old.id;
            END;
            CREATE TRIGGER IF NOT EXISTS messages_workflow_revision
            AFTER UPDATE OF state,until,priority_override,reply_override,deadline,important,reply,deleted,content,edited_at,channel,guild,parent_channel,author ON messages
            WHEN old.state IS NOT new.state OR old.until IS NOT new.until
                OR old.priority_override IS NOT new.priority_override OR old.reply_override IS NOT new.reply_override
                OR old.deadline IS NOT new.deadline OR old.important IS NOT new.important OR old.reply IS NOT new.reply
                OR old.deleted IS NOT new.deleted OR old.content IS NOT new.content OR old.edited_at IS NOT new.edited_at
                OR old.channel IS NOT new.channel OR old.guild IS NOT new.guild OR old.parent_channel IS NOT new.parent_channel
                OR old.author IS NOT new.author
            BEGIN
                UPDATE messages SET workflow_revision=old.workflow_revision+1 WHERE id=new.id;
            END;
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content,channel_name,author,content='messages',content_rowid='rowid');
            CREATE TRIGGER IF NOT EXISTS messages_insert AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid,content,channel_name,author) VALUES(new.rowid,new.content,new.channel_name,new.author);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_delete AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts,rowid,content,channel_name,author) VALUES('delete',old.rowid,old.content,old.channel_name,old.author);
            END;
            CREATE TRIGGER IF NOT EXISTS messages_update AFTER UPDATE OF content,channel_name,author ON messages BEGIN
                INSERT INTO messages_fts(messages_fts,rowid,content,channel_name,author) VALUES('delete',old.rowid,old.content,old.channel_name,old.author);
                INSERT INTO messages_fts(rowid,content,channel_name,author) VALUES(new.rowid,new.content,new.channel_name,new.author);
            END;
        """)
        if not indexed:
            with self.db:
                self.db.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")

    def settings(self):
        return DEFAULTS | {
            r["key"]: json.loads(r["value"]) for r in self.db.execute("SELECT * FROM settings")
        }

    def save_settings(self, changes):
        if set(changes) - set(DEFAULTS):
            raise ValueError("Onbekende instellingen.")
        config = self.settings() | changes
        if any(
            not isinstance(config[k], int) or not 1 <= config[k] <= 10080
            for k in ("sync_minutes", "summary_minutes")
        ):
            raise ValueError("Interval moet tussen 1 en 10080 minuten liggen.")
        if (
            type(config["retention_days"]) is not int
            or not 0 <= config["retention_days"] <= 36500
            or type(config["font_size"]) is not int
            or not 9 <= config["font_size"] <= 24
            or type(config["message_font_size"]) is not int
            or not 9 <= config["message_font_size"] <= 32
        ):
            raise ValueError("Ongeldige bewaartermijn of lettergrootte.")
        if config["density"] not in {"compact", "comfortable", "spacious"}:
            raise ValueError("Kies een beschikbare regeldichtheid.")
        if config["theme"] not in {"light", "ash", "dark", "onyx"}:
            raise ValueError("Kies een beschikbaar kleurthema.")
        widths = config["column_widths"]
        if (
            not isinstance(widths, dict)
            or set(widths) != {"date", "channel", "message", "state"}
            or any(type(width) is not int or not 60 <= width <= 1200 for width in widths.values())
        ):
            raise ValueError("Kolombreedtes moeten tussen 60 en 1200 pixels liggen.")
        with self.db:
            for key, value in changes.items():
                self.db.execute(
                    "INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value))
                )
            if {
                "user_id",
                "important_people",
                "important_servers",
                "important_channels",
                "important_topics",
            } & set(changes):
                self._reclassify()

    def audit(self, action, target, detail=""):
        self.db.execute(
            "INSERT INTO audit(timestamp,action,target,detail) VALUES (?,?,?,?)",
            (now(), action, target, detail),
        )

    def source(
        self,
        ident,
        kind="import",
        name="",
        status="imported",
        detail="",
        config=None,
        next_sync=None,
    ):
        with self.db:
            self.db.execute(
                """INSERT INTO sources(id,kind,name,status,detail,config,next_sync) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,detail=excluded.detail,
                config=excluded.config,next_sync=excluded.next_sync""",
                (ident, kind, name or ident, status, detail, json.dumps(config or {}), next_sync),
            )

    def sources(self):
        rows = [dict(r) for r in self.db.execute("SELECT * FROM sources ORDER BY name")]
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=max(15, self.settings()["sync_minutes"] * 3)
        )
        for row in rows:
            row["config"] = json.loads(row["config"])
            if (
                row["kind"] == "bot"
                and row["status"] == "synced"
                and (not row["last_sync"] or datetime.fromisoformat(row["last_sync"]) < threshold)
            ):
                row["status"] = "stale"
        return rows

    def get(self, ident):
        row = self.db.execute("SELECT * FROM messages WHERE id=?", (ident,)).fetchone()
        return dict(row) if row else None

    @contextmanager
    def transaction(self):
        marker = "operation_" + uuid.uuid4().hex
        self.db.execute("SAVEPOINT " + marker)
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK TO " + marker)
            self.db.execute("RELEASE " + marker)
            raise
        else:
            self.db.execute("RELEASE " + marker)

    def ingest(self, records, source_id="legacy-import", source_kind="import"):
        stamp, count, settings = now(), 0, self.settings()
        with self.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO sources(id,kind,name,status) VALUES (?,?,?,?)",
                (
                    source_id,
                    source_kind,
                    source_id,
                    "imported" if source_kind == "import" else "pending",
                ),
            )
            for record in records:
                existing = self.get(record["id"])
                if existing and existing["source_kind"] == "bot" and source_kind == "import":
                    continue
                r = (
                    dict(
                        author_id="",
                        author="Jij (eigen export)",
                        mentions="[]",
                        reply_to="",
                        reply_author="",
                        edited_at="",
                        deleted=0,
                        parent_channel="",
                    )
                    | record
                )
                r.update(
                    source_id=source_id,
                    source_kind=source_kind,
                    imported_at=stamp,
                    conversation=record.get("conversation") or record["channel"],
                    search_text=(record["content"] + " " + record["channel_name"]).casefold(),
                )
                preserved = (
                    {k: existing[k] for k in ("priority_override", "reply_override", "deadline")}
                    if existing
                    else {}
                )
                important, reply, reasons = classify(r | preserved, settings)
                r.update(
                    important=important, reply=reply, reason=json.dumps(reasons, ensure_ascii=False)
                )
                fields = "id channel channel_name guild content timestamp attachments imported_at source_id source_kind author_id author conversation parent_channel mentions reply_to reply_author edited_at deleted search_text important reply reason".split()
                updates = ",".join(f"{f}=excluded.{f}" for f in fields if f != "id")
                self.db.execute(
                    f"INSERT INTO messages({','.join(fields)}) VALUES ({','.join('?' for _ in fields)}) ON CONFLICT(id) DO UPDATE SET {updates}",
                    [r[f] for f in fields],
                )
                if not existing and important:
                    self.notify(
                        "priority:" + r["id"],
                        "priority",
                        "Nieuw belangrijk bericht in " + r["channel_name"],
                    )
                count += 1
            self.db.execute("UPDATE sources SET last_sync=? WHERE id=?", (stamp, source_id))
            self.audit("ingest", source_id, str(count))
        return count

    def _reclassify(self):
        settings = self.settings()
        for row in self.db.execute("SELECT * FROM messages").fetchall():
            important, reply, reasons = classify(dict(row), settings)
            self.db.execute(
                "UPDATE messages SET important=?,reply=?,reason=? WHERE id=?",
                (important, reply, json.dumps(reasons, ensure_ascii=False), row["id"]),
            )

    def update(self, ident, action, until=None):
        row = self.get(ident)
        if not row:
            raise ValueError("Bericht niet gevonden.")
        actions = {
            "complete": ("state='complete',until=NULL", ()),
            "dismiss": ("state='dismissed',until=NULL", ()),
            "reopen": ("state='open',until=NULL", ()),
            "important": ("priority_override=?", (1 - row["important"],)),
            "reply": ("reply_override=?", (1 - row["reply"],)),
            "reset_rules": ("priority_override=NULL,reply_override=NULL", ()),
            "clear_deadline": ("deadline=NULL", ()),
        }
        if action in ("later", "deadline"):
            date = datetime.fromisoformat(until)
            if date.tzinfo is None or date <= datetime.now(timezone.utc):
                raise ValueError("Kies een toekomstig tijdstip met tijdzone.")
            sql, values = (
                ("state='later',until=?" if action == "later" else "deadline=?"),
                (date.astimezone(timezone.utc).isoformat(),),
            )
        else:
            if action not in actions:
                raise ValueError("Onbekende actie.")
            sql, values = actions[action]
        with self.db:
            self.db.execute("UPDATE messages SET " + sql + " WHERE id=?", (*values, ident))
            self._reclassify()
            self.audit(action, ident)

    def maintenance(self):
        with self.db:
            for row in self.db.execute(
                "SELECT id,channel_name,until FROM messages WHERE state='later' AND until<=?",
                (now(),),
            ).fetchall():
                self.notify(
                    "snooze:" + row["id"] + row["until"],
                    "snooze",
                    "Uitgesteld bericht terug in " + row["channel_name"],
                )
            self.db.execute(
                "UPDATE messages SET state='open',until=NULL WHERE state='later' AND until<=?",
                (now(),),
            )
            self._reclassify()
            soon = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            for row in self.db.execute(
                "SELECT * FROM messages WHERE state='open' AND deadline<=?", (soon,)
            ).fetchall():
                self.notify(
                    "deadline:" + row["id"] + row["deadline"],
                    "deadline",
                    "Deadline nadert of is verstreken in " + row["channel_name"],
                )

    def query(
        self, view="Everything", search="", limit=None, offset=0, channel=None, fulltext=False
    ):
        with self.db:
            for row in self.db.execute(
                "SELECT id,channel_name,until FROM messages WHERE state='later' AND until<=?",
                (now(),),
            ).fetchall():
                self.notify(
                    "snooze:" + row["id"] + row["until"],
                    "snooze",
                    "Uitgesteld bericht terug in " + row["channel_name"],
                )
            self.db.execute(
                "UPDATE messages SET state='open',until=NULL WHERE state='later' AND until<=?",
                (now(),),
            )
        clauses = {
            "Important Now": "state='open' AND important=1",
            "Needs Reply": "state='open' AND reply=1",
            "Later": "state='later'",
            "Conversations": "1=1",
            "Everything": "1=1",
        }
        sql, params = "SELECT * FROM messages WHERE " + clauses[view], []
        if search.strip():
            if fulltext:
                sql += " AND rowid IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)"
                params.append(
                    " AND ".join('"' + word.replace('"', '""') + '"' for word in search.split())
                )
            else:
                sql += " AND instr(search_text,?)>0"
                params.append(search.casefold())
        if channel:
            sql += " AND conversation=?"
            params.append(channel)
        sql += " ORDER BY timestamp DESC,id DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend((limit, offset))
        return [dict(r) for r in self.db.execute(sql, params)]

    def exclude(self, scope, target, enabled=True):
        if scope not in ("personal", "source", "server", "channel", "conversation", "message"):
            raise ValueError("Ongeldige privacy-scope.")
        with self.db:
            if enabled:
                self.db.execute("INSERT OR IGNORE INTO exclusions VALUES (?,?)", (scope, target))
            else:
                self.db.execute(
                    "DELETE FROM exclusions WHERE scope=? AND target=?", (scope, target)
                )
            self.clear_summaries()
            self.audit("exclude" if enabled else "include", scope + ":" + target)

    def clear_summaries(self):
        self.db.execute("DELETE FROM summaries")
        self.db.execute("DELETE FROM summary_notes")
        self.db.execute("DELETE FROM notifications WHERE kind='summary'")

    def exclusions(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM exclusions ORDER BY scope,target")]

    def summary_records(self):
        exclusions = {(r["scope"], r["target"]) for r in self.exclusions()}
        if ("personal", "*") in exclusions:
            return []
        sources = {s["id"]: s for s in self.sources()}
        rows = []
        for row in self.query():
            source = sources.get(row["source_id"], {})
            if row["deleted"] or (
                source.get("kind") == "bot" and source.get("status") not in ("synced", "partial")
            ):
                continue
            scopes = [
                ("source", row["source_id"]),
                ("server", row["guild"]),
                ("channel", row["parent_channel"] or row["channel"]),
                ("channel", row["channel"]),
                ("conversation", row["conversation"]),
                ("message", row["id"]),
            ]
            if not any(pair in exclusions for pair in scopes):
                rows.append(row)
        return rows

    def privacy_fingerprint(self):
        data = dict(
            exclusions=self.exclusions(),
            sources=self.sources(),
            settings=self.settings(),
            messages=[(r["id"], r["content"], r["edited_at"]) for r in self.summary_records()],
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def notify(self, key, kind, text):
        if self.settings().get("notify_" + kind, True):
            self.db.execute(
                "INSERT OR IGNORE INTO notifications(key,kind,text,created_at) VALUES (?,?,?,?)",
                (key, kind, text, now()),
            )

    def delete_source_data(self, source_id):
        with self.db:
            self.db.execute("DELETE FROM messages WHERE source_id=?", (source_id,))
            self.clear_summaries()
            self.db.execute("DELETE FROM notifications")
            self.db.execute("DELETE FROM sources WHERE id=?", (source_id,))
            self.audit("delete_source", source_id)

    def apply_retention(self):
        days = self.settings()["retention_days"]
        if not days:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self.db:
            count = self.db.execute("DELETE FROM messages WHERE timestamp<?", (cutoff,)).rowcount
            if count:
                self.clear_summaries()
                self.db.execute("DELETE FROM notifications")
                self.audit("retention", "*", str(count))
        return count

    def export_data(self):
        return dict(
            version=2,
            exported_at=now(),
            messages=self.query(),
            sources=self.sources(),
            settings=self.settings(),
            exclusions=self.exclusions(),
            summaries=[dict(r) for r in self.db.execute("SELECT * FROM summaries")],
            corrections=[dict(r) for r in self.db.execute("SELECT * FROM summary_notes")],
        )

    def backup(self, path):
        if Path(path).resolve() == Path(self.path).resolve():
            raise ValueError("Kies een ander bestand voor de back-up.")
        with closing(sqlite3.connect(path)) as destination:
            self.db.backup(destination)
