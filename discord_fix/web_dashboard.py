"""Loopback-only, read-only browser dashboard for the local Discord Fix database."""

import argparse
import json
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .importer import deep_link

ALLOWED_VIEWS = {
    "Overview": "1=1",
    "Important Now": "effective_state='open' AND important=1",
    "Needs Reply": "effective_state='open' AND reply=1",
    "Conversations": "1=1",
    "Later": "effective_state='later'",
    "Everything": "1=1",
}

SOURCE_LABELS = {
    "synced": "Gesynchroniseerd",
    "partial": "Gedeeltelijk",
    "imported": "Geïmporteerd",
    "stale": "Verouderd",
    "pending": "Wacht op sync",
    "revoked": "Toegang ingetrokken",
    "offline": "Offline",
    "error": "Fout",
}


def dashboard_data(database_path, view="Overview", search="", demo=False):
    """Read a fresh snapshot without modifying message, workflow, or notification data."""
    if view not in ALLOWED_VIEWS:
        raise ValueError("Onbekende dashboardweergave.")
    if len(search) > 160:
        raise ValueError("De zoekopdracht is te lang.")

    current = datetime.now(timezone.utc)
    stamp = current.isoformat()
    effective_state = (
        "CASE WHEN state='later' AND until IS NOT NULL AND until<=? THEN 'open' ELSE state END"
    )
    database_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True, timeout=5)) as database:
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA query_only=ON")
        database.execute("PRAGMA busy_timeout=5000")
        with database:
            database.execute("SELECT 1")

        common_table = f"""
            WITH normalized AS (
                SELECT id, channel, channel_name, guild, content, search_text, timestamp, author,
                    state, until, important, reply, deadline, deleted,
                    source_id, {effective_state} AS effective_state
                FROM messages
            )
        """
        counts_row = database.execute(
            common_table
            + """
            SELECT COUNT(*) AS total,
                COALESCE(SUM(effective_state='open' AND important=1),0) AS important,
                COALESCE(SUM(effective_state='open' AND reply=1),0) AS reply,
                COALESCE(SUM(effective_state='later'),0) AS later,
                COALESCE(SUM(NOT (effective_state='later' OR
                    (effective_state='open' AND (important=1 OR reply=1)))),0) AS other
            FROM normalized
            """,
            (stamp,),
        ).fetchone()

        clause = ALLOWED_VIEWS[view]
        parameters = [stamp]
        if search:
            clause += " AND instr(search_text,?)>0"
            parameters.append(search.casefold())
        order = (
            "CASE WHEN effective_state='open' AND important=1 THEN 0 "
            "WHEN effective_state='open' AND reply=1 THEN 1 ELSE 2 END, timestamp DESC,id DESC"
            if view == "Overview"
            else "timestamp DESC,id DESC"
        )
        records = database.execute(
            common_table
            + f"""
            SELECT * FROM normalized WHERE {clause}
            ORDER BY {order} LIMIT 60
            """,
            parameters,
        ).fetchall()

        settings = {
            row["key"]: json.loads(row["value"])
            for row in database.execute("SELECT key,value FROM settings")
        }
        sync_interval = settings.get("sync_minutes", 5)
        freshness = current - timedelta(minutes=max(15, sync_interval * 3))
        source_rows = database.execute(
            "SELECT kind,name,status,last_sync FROM sources ORDER BY name"
        ).fetchall()

    sources = []
    for row in source_rows:
        status = row["status"]
        if status == "synced" and row["last_sync"]:
            try:
                if datetime.fromisoformat(row["last_sync"]) < freshness:
                    status = "stale"
            except (TypeError, ValueError):
                status = "stale"
        sources.append(
            {
                "kind": row["kind"],
                "name": row["name"],
                "status": status,
                "label": SOURCE_LABELS.get(status, "Status onbekend"),
                "last_sync": row["last_sync"],
            }
        )

    items = []
    for row in records:
        record = dict(row)
        items.append(
            {
                "id": record["id"],
                "channel_name": record["channel_name"],
                "author": record["author"],
                "content": record["content"][:420],
                "timestamp": record["timestamp"],
                "state": record["effective_state"],
                "important": bool(record["important"]),
                "reply": bool(record["reply"]),
                "deadline": record["deadline"],
                "deleted": bool(record["deleted"]),
                "url": None if demo else deep_link(record),
            }
        )

    return {
        "view": view,
        "demo": bool(demo),
        "generated_at": stamp,
        "counts": {
            key: int(counts_row[key]) for key in ("total", "important", "reply", "later", "other")
        },
        "items": items,
        "sources": sources,
    }


class DashboardServer:
    """Serve the companion's dashboard on an ephemeral localhost port."""

    def __init__(self, database_path, demo=False):
        self.database_path = str(Path(database_path).resolve())
        self.demo = bool(demo)
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.thread = None
        self.url = None
        self.html = Path(__file__).with_name("dashboard.html").read_bytes()

    def start(self):
        if self.server:
            return self.url
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "DiscordFixLocalDashboard"
            sys_version = ""

            def log_message(self, _format, *_args):
                return

            def _send(self, status, body, content_type):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'; "
                    "script-src 'unsafe-inline'; connect-src 'self'; "
                    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(body)

            def _reject(self, status=404):
                self._send(status, b"Niet gevonden.", "text/plain; charset=utf-8")

            def do_GET(self):
                host = self.headers.get("Host", "").lower()
                host_name = host.rsplit(":", 1)[0] if ":" in host else host
                if host_name not in {"127.0.0.1", "localhost"}:
                    self._reject(403)
                    return

                parsed = urlsplit(self.path)
                segments = parsed.path.strip("/").split("/", 1)
                if not segments or not secrets.compare_digest(segments[0], owner.token):
                    self._reject()
                    return
                resource = segments[1] if len(segments) > 1 else ""
                if resource in ("", "index.html"):
                    self._send(200, owner.html, "text/html; charset=utf-8")
                    return
                if resource != "api/dashboard":
                    self._reject()
                    return

                params = parse_qs(parsed.query, keep_blank_values=True)
                view = params.get("view", ["Overview"])[0]
                search = params.get("q", [""])[0]
                try:
                    payload = dashboard_data(owner.database_path, view, search, owner.demo)
                except ValueError as exc:
                    body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
                    self._send(400, body, "application/json; charset=utf-8")
                    return
                except (OSError, sqlite3.Error, json.JSONDecodeError):
                    body = b'{"error":"Lokale gegevens zijn tijdelijk niet beschikbaar."}'
                    self._send(503, body, "application/json; charset=utf-8")
                    return
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")

            def do_POST(self):
                self.send_response(405)
                self.send_header("Allow", "GET")
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_PUT = do_POST
            do_PATCH = do_POST
            do_DELETE = do_POST

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.timeout = 1
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/{self.token}/"
        return self.url

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None
            self.thread = None
            self.url = None


def main():
    parser = argparse.ArgumentParser(description="Lokaal, alleen-lezen Discord Fix-dashboard")
    parser.add_argument("--database", required=True, help="Pad naar discord-fix.sqlite")
    parser.add_argument("--demo", action="store_true", help="Toon een voorbeeldgegevensmelding")
    args = parser.parse_args()
    dashboard = DashboardServer(args.database, demo=args.demo)
    print(dashboard.start(), flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        dashboard.stop()


if __name__ == "__main__":
    main()
