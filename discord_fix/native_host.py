"""Single-request Chrome/Edge native host restricted to explicit extension origins."""

import json
import os
import re
import struct
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .browser_pairing import HOST_NAME, connection_url, discover
from .vault import Vault

MAX_REQUEST = 4096


def extension_origin(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("Invalid extension origin.")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "chrome-extension"
        or not re.fullmatch("[a-p]{32}", parsed.netloc)
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid extension origin.")
    return "chrome-extension://" + parsed.netloc + "/"


def read_exact(stream, size):
    result = bytearray()
    while len(result) < size:
        part = stream.read(size - len(result))
        if not part:
            raise ValueError("Incomplete native message.")
        result.extend(part)
    return bytes(result)


def read_message(stream):
    length = struct.unpack("=I", read_exact(stream, 4))[0]
    if not 1 <= length <= MAX_REQUEST:
        raise ValueError("Invalid native message size.")
    value = json.loads(read_exact(stream, length))
    if not isinstance(value, dict):
        raise ValueError("Invalid native message.")
    return value


def write_message(stream, value):
    data = json.dumps(value, ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_REQUEST:
        raise ValueError("Native response too large.")
    stream.write(struct.pack("=I", len(data)))
    stream.write(data)
    stream.flush()


def read_config(directory, origin):
    canonical = extension_origin(origin)
    manifest_path = Path(directory) / (HOST_NAME + ".json")
    config_path = Path(directory) / "discord-fix-pairing.json"
    if manifest_path.stat().st_size > 8192 or config_path.stat().st_size > 4096:
        raise ValueError("Invalid host configuration.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("name") != HOST_NAME
        or manifest.get("type") != "stdio"
        or not isinstance(manifest.get("allowed_origins"), list)
        or not 1 <= len(manifest["allowed_origins"]) <= 10
        or any(extension_origin(value) != value for value in manifest["allowed_origins"])
        or canonical not in manifest["allowed_origins"]
    ):
        raise ValueError("This extension is not allowed to pair.")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    data_directory = config.get("data_directory") if isinstance(config, dict) else None
    if not isinstance(data_directory, str) or not Path(data_directory).is_absolute():
        raise ValueError("Invalid companion data directory.")
    # Do not create a new secrets directory while probing an absent installation.
    secrets_directory = Path(data_directory) / "secrets"
    if not secrets_directory.is_dir():
        raise ValueError("Open Browserdashboard in the desktop app first.")
    return Vault(secrets_directory)


def serve(input_stream, output_stream, origin, directory, lookup=discover):
    try:
        vault = read_config(directory, origin)
        payload = read_message(input_stream)
        if (
            payload != {"command": "pair", "protocol": 1}
            or type(payload.get("protocol")) is not int
        ):
            raise ValueError("Unsupported pairing request.")
        url = connection_url(lookup(vault))
        result = {"ok": True, "url": url, "protocol": 1}
    except (OSError, ValueError, RuntimeError, TypeError):
        result = {
            "ok": False,
            "error": "Pairing unavailable. Open Browserdashboard, check the host registration, or paste its private address manually.",
        }
    except Exception:
        # Provider/socket failures must not put a URL, exception, or traceback in IPC.
        result = {
            "ok": False,
            "error": "The desktop session is unavailable. Use the manual connection or try again.",
        }
    write_message(output_stream, result)
    return 0 if result["ok"] else 1


def main():
    if os.name == "nt":
        import msvcrt

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    directory = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
    origin = sys.argv[1] if len(sys.argv) > 1 else ""
    return serve(sys.stdin.buffer, sys.stdout.buffer, origin, directory)
