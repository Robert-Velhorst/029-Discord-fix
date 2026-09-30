"""Optional DPAPI session discovery; no port scanning or persistent cleartext URL."""

import json
import re
from urllib.parse import urlsplit

from .network import request_json

SESSION_KEY = "browser-session"
HOST_NAME = "com.discordfix.companion"


def connection_url(value):
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("Invalid local connection address.")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or not parsed.port
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[A-Za-z0-9_-]{20,128}/", parsed.path)
    ):
        raise ValueError("Invalid local connection address.")
    return value


def publish(vault, url, session_id):
    vault.save(SESSION_KEY, json.dumps({"url": connection_url(url), "session_id": session_id}))


def clear(vault, session_id):
    try:
        current = json.loads(vault.read(SESSION_KEY) or "{}")
        if isinstance(current, dict) and current.get("session_id") == session_id:
            vault.forget(SESSION_KEY)
    except (OSError, ValueError, RuntimeError):
        # A stale encrypted record cannot pair without a live matching handshake.
        return


def discover(vault, transport=request_json):
    encrypted = vault.directory / (SESSION_KEY + ".dpapi")
    if not encrypted.is_file() or encrypted.stat().st_size > 8192:
        raise ValueError("Open Browserdashboard in the desktop app first.")
    record = json.loads(vault.read(SESSION_KEY))
    if not isinstance(record, dict):
        raise ValueError("Open Browserdashboard again to refresh the connection.")
    url = connection_url(record.get("url"))
    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", session_id):
        raise ValueError("Open Browserdashboard again to refresh the connection.")
    body, _headers = transport(url + "api/session", timeout=3)
    if (
        not isinstance(body, dict)
        or body.get("application") != "DiscordFix"
        or type(body.get("protocol")) is not int
        or body.get("protocol") != 1
        or body.get("session_id") != session_id
        or body.get("demo") is not False
    ):
        raise ValueError("The desktop session has expired. Open Browserdashboard again.")
    return url
