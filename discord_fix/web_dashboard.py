"""Loopback dashboard with read-only snapshots and explicit local follow-up actions."""

import argparse
import json
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .browser_pairing import clear, publish
from .web_data import message_data, page_data, summary_data
from .web_workflow import WorkflowConflict, apply_workflow

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


def dashboard_data(database_path, view="Overview", search="", demo=False, **options):
    payload = page_data(database_path, view, search, demo, **options)
    for source in payload["sources"]:
        source["label"] = SOURCE_LABELS.get(source["status"], "Status onbekend")
    return payload


class DashboardServer:
    """Serve the companion's dashboard on an ephemeral localhost port."""

    def __init__(self, database_path, demo=False, pairing_vault=None):
        self.database_path = str(Path(database_path).resolve())
        self.demo = bool(demo)
        self.token = secrets.token_urlsafe(32)
        self.write_nonce = secrets.token_urlsafe(32)
        self.session_id = secrets.token_urlsafe(24)
        self.pairing_vault = pairing_vault
        self.pairing_ready = False
        self.workflow_lock = threading.Lock()
        self.undo = {}
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
                self._send(status, b"Not found.", "text/plain; charset=utf-8")

            def do_GET(self):
                host = self.headers.get("Host", "").lower()
                if host not in {
                    urlsplit(owner.url).netloc,
                    urlsplit(owner.url).netloc.replace("127.0.0.1", "localhost"),
                }:
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
                if resource == "api/session":
                    body = json.dumps(
                        {
                            "application": "DiscordFix",
                            "protocol": 1,
                            "session_id": owner.session_id,
                            "demo": owner.demo,
                        }
                    ).encode()
                    self._send(200, body, "application/json; charset=utf-8")
                    return
                if resource not in {"api/dashboard", "api/message", "api/summaries"}:
                    self._reject()
                    return

                params = parse_qs(parsed.query, keep_blank_values=True)
                view = params.get("view", ["Overview"])[0]
                search = params.get("q", [""])[0]
                try:
                    if resource == "api/message":
                        payload = message_data(
                            owner.database_path, params.get("id", [""])[0], owner.demo
                        )
                    elif resource == "api/summaries":
                        payload = summary_data(
                            owner.database_path,
                            params.get("scope", ["personal"])[0],
                            params.get("target", ["*"])[0],
                            int(params.get("offset", ["0"])[0]),
                            demo=owner.demo,
                        )
                    else:
                        payload = dashboard_data(
                            owner.database_path,
                            view,
                            search,
                            owner.demo,
                            offset=int(params.get("offset", ["0"])[0]),
                            anchor=int(params["anchor"][0]) if "anchor" in params else None,
                            conversation=params.get("conversation", [""])[0],
                            since=params.get("since", [""])[0],
                            pinned=params["pins"][0].split(",")
                            if params.get("pins", [""])[0]
                            else []
                            if "pins" in params
                            else None,
                        )
                        payload["workflow"] = {
                            "enabled": not owner.demo,
                            "nonce": owner.write_nonce if not owner.demo else "",
                        }
                except ValueError as exc:
                    body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
                    self._send(400, body, "application/json; charset=utf-8")
                    return
                except (OSError, sqlite3.Error, json.JSONDecodeError):
                    body = b'{"error":"Local data is temporarily unavailable."}'
                    self._send(503, body, "application/json; charset=utf-8")
                    return
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")

            def do_POST(self):
                parsed = urlsplit(self.path)
                if parsed.path != f"/{owner.token}/api/workflow":
                    self.send_response(405)
                    self.send_header("Allow", "GET")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                origin = self.headers.get("Origin", "")
                try:
                    origin_url = urlsplit(origin)
                except ValueError:
                    self._reject(403)
                    return
                local_origins = {
                    owner.url.split("/" + owner.token)[0],
                    owner.url.split("/" + owner.token)[0].replace("127.0.0.1", "localhost"),
                }
                extension_origin = (
                    origin_url.scheme == "chrome-extension"
                    and len(origin_url.netloc) == 32
                    and all(c in "abcdefghijklmnop" for c in origin_url.netloc)
                    and not origin_url.path
                )
                if (
                    owner.demo
                    or (origin and origin not in local_origins and not extension_origin)
                    or not secrets.compare_digest(
                        self.headers.get("X-Discord-Fix-Nonce", ""), owner.write_nonce
                    )
                    or self.headers.get("Host")
                    not in {urlsplit(value).netloc for value in local_origins}
                ):
                    self._reject(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if (
                        not 1 <= length <= 4096
                        or self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                    ):
                        raise ValueError("Use a small JSON action request.")
                    self.connection.settimeout(5)
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("Invalid action request.")
                    with owner.workflow_lock:
                        ticket = payload.get("undo", "")
                        if not isinstance(ticket, str):
                            raise ValueError("Invalid undo ticket.")
                        previous = owner.undo.get(ticket)
                        changed = apply_workflow(owner.database_path, payload, previous)
                        if payload.get("action") == "undo":
                            owner.undo.pop(ticket, None)
                            result = {
                                "id": changed["id"],
                                "revision": changed["revision"],
                                "undo": "",
                            }
                        else:
                            ticket = secrets.token_urlsafe(24)
                            owner.undo[ticket] = changed
                            if len(owner.undo) > 500:
                                owner.undo.pop(next(iter(owner.undo)))
                            result = {
                                "id": changed["id"],
                                "revision": changed["revision"],
                                "undo": ticket,
                            }
                    self._send(200, json.dumps(result).encode(), "application/json")
                except WorkflowConflict as exc:
                    self._send(409, json.dumps({"error": str(exc)}).encode(), "application/json")
                except (ValueError, TypeError, KeyError):
                    self._send(
                        400, b'{"error":"Invalid local action request."}', "application/json"
                    )
                except (OSError, sqlite3.Error):
                    self._send(
                        503,
                        b'{"error":"Local data is temporarily unavailable."}',
                        "application/json",
                    )

            def _unsupported_write(self):
                self.send_response(405)
                self.send_header("Allow", "GET")
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_PUT = _unsupported_write
            do_PATCH = _unsupported_write
            do_DELETE = _unsupported_write

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.timeout = 1
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/{self.token}/"
        if self.pairing_vault is not None and not self.demo:
            try:
                publish(self.pairing_vault, self.url, self.session_id)
                self.pairing_ready = True
            except (OSError, RuntimeError, ValueError):
                self.pairing_ready = False
        return self.url

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            if self.pairing_vault is not None:
                clear(self.pairing_vault, self.session_id)
            self.pairing_ready = False
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
