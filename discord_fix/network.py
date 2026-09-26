"""Bounded JSON requests; never follow redirects with credentials or private data."""

import json
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpFailure(Exception):
    def __init__(self, status, headers=None, body=None):
        self.status, self.headers, self.body = status, headers or {}, body or {}
        super().__init__("HTTP " + str(status))


def request_json(url, headers=None, payload=None, timeout=30):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **(headers or {})}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("Antwoord is groter dan 8 MB.")
            return json.loads(raw), dict(response.headers)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read(65536))
        except (ValueError, UnicodeError):
            body = {}
        finally:
            exc.close()
        raise HttpFailure(exc.code, dict(exc.headers), body) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError(
            "Verbinding mislukt of verlopen. Controleer netwerk en provider."
        ) from None
