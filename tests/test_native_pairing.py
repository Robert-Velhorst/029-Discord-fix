import io
import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from discord_fix.browser_pairing import HOST_NAME, SESSION_KEY, connection_url, discover, publish
from discord_fix.native_host import MAX_REQUEST, read_message, serve, write_message
from discord_fix.vault import Vault
from discord_fix.web_dashboard import DashboardServer

ORIGIN = "chrome-extension://" + "a" * 32 + "/"
ADDRESS = "http://127.0.0.1:4567/abcdefghijklmnopqrstuvwxyz/"


def frame(value):
    stream = io.BytesIO()
    write_message(stream, value)
    stream.seek(0)
    return stream


class PartialReader(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2))


class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data" / "secrets").mkdir(parents=True)
        self.manifest = {"name": HOST_NAME, "type": "stdio", "allowed_origins": [ORIGIN]}
        self.write_config()

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self):
        (self.root / (HOST_NAME + ".json")).write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.root / "discord-fix-pairing.json").write_text(
            json.dumps({"data_directory": str(self.root / "data")}), encoding="utf-8"
        )

    def request(self, payload=None, origin=ORIGIN, lookup=None, raw=None):
        output = io.BytesIO()
        incoming = raw if raw is not None else frame(payload or {"command": "pair", "protocol": 1})
        status = serve(
            incoming, output, origin, self.root, lookup=lookup or (lambda _vault: ADDRESS)
        )
        output.seek(0)
        return status, read_message(output)

    def test_utf8_framing_and_partial_reads(self):
        value = {"text": "Résumé 😀"}
        data = frame(value).getvalue()
        self.assertEqual(struct.unpack("=I", data[:4])[0], len(data[4:]))
        self.assertEqual(read_message(PartialReader(data)), value)

    def test_invalid_frames_fail_without_discovery(self):
        for data in (
            b"",
            b"\x01",
            struct.pack("=I", MAX_REQUEST + 1),
            struct.pack("=I", 8) + b"{}",
            frame([]).getvalue(),
        ):
            with self.subTest(data=data), patch("discord_fix.native_host.discover") as lookup:
                status, body = self.request(raw=io.BytesIO(data), lookup=lookup)
                self.assertEqual(status, 1)
                self.assertFalse(body["ok"])
                lookup.assert_not_called()

    def test_only_exact_pair_protocol_is_accepted(self):
        for payload in (
            {"command": "pair", "protocol": True},
            {"command": "pair", "protocol": 2},
            {"command": "send", "protocol": 1},
            {"command": "pair", "protocol": 1, "url": ADDRESS},
        ):
            with self.subTest(payload=payload), patch("discord_fix.native_host.discover") as lookup:
                status, _body = self.request(payload=payload, lookup=lookup)
                self.assertEqual(status, 1)
                lookup.assert_not_called()

    def test_unknown_origin_is_rejected_before_reading_secrets(self):
        for origin in ("", "https://discord.com", ORIGIN.replace("a", "b"), ORIGIN + "?key=secret"):
            with self.subTest(origin=origin), patch("discord_fix.native_host.Vault") as vault:
                self.assertEqual(self.request(origin=origin)[0], 1)
                vault.assert_not_called()
        self.manifest["allowed_origins"] = ["chrome-extension://*/"]
        self.write_config()
        self.assertEqual(self.request()[0], 1)

    def test_success_and_sanitized_failure(self):
        status, body = self.request()
        self.assertEqual(status, 0)
        self.assertEqual(body, {"ok": True, "url": ADDRESS, "protocol": 1})

        def failure(_vault):
            raise RuntimeError("Private token: " + ADDRESS)

        status, body = self.request(lookup=failure)
        self.assertEqual(status, 1)
        self.assertNotIn(ADDRESS, json.dumps(body))
        self.assertNotIn("Traceback", json.dumps(body))
        self.assertEqual(self.request(lookup=lambda _vault: "https://example.com")[0], 1)

    def test_strict_loopback_addresses(self):
        self.assertEqual(connection_url(ADDRESS), ADDRESS)
        for value in (
            None,
            "https://127.0.0.1:4567/abcdefghijklmnopqrstuvwxyz/",
            ADDRESS.replace("127.0.0.1", "localhost"),
            ADDRESS + "?secret=1",
            ADDRESS.replace("4567", "0"),
            ADDRESS.replace("4567", "65536"),
            ADDRESS.replace("http://", "http://name:password@"),
            ADDRESS.replace("abcdefghijklmnopqrstuvwxyz", "short"),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                connection_url(value)


@unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = Vault(self.root / "secrets")
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.stop()
        self.temp.cleanup()

    def start_server(self, **options):
        server = DashboardServer(self.root / "unused.sqlite", pairing_vault=self.vault, **options)
        self.servers.append(server)
        server.start()
        return server

    def test_real_loopback_handshake_and_encrypted_session_cleanup(self):
        server = self.start_server()
        self.assertTrue(server.pairing_ready)
        self.assertEqual(discover(self.vault), server.url)
        self.assertNotIn(
            server.url.encode(), (self.vault.directory / (SESSION_KEY + ".dpapi")).read_bytes()
        )
        server.stop()
        self.assertEqual(self.vault.read(SESSION_KEY), "")
        with self.assertRaises(ValueError):
            discover(self.vault)

    def test_older_server_does_not_clear_newer_session(self):
        older = self.start_server()
        newer = self.start_server()
        older.stop()
        self.assertEqual(discover(self.vault), newer.url)

    def test_demo_and_mismatched_sessions_are_rejected(self):
        server = self.start_server(demo=True)
        self.assertFalse(server.pairing_ready)
        publish(self.vault, server.url, server.session_id)
        with self.assertRaises(ValueError):
            discover(self.vault)
        server = self.start_server()
        publish(self.vault, server.url, "x" * 24)
        with self.assertRaises(ValueError):
            discover(self.vault)

    def test_invalid_encrypted_records_do_not_trigger_network_access(self):
        for record in (
            {"url": "https://example.com", "session_id": "x" * 24},
            {"url": ADDRESS, "session_id": None},
            [],
        ):
            self.vault.save(SESSION_KEY, json.dumps(record))
            with patch("discord_fix.browser_pairing.request_json") as network:
                with self.assertRaises(ValueError):
                    discover(self.vault, transport=network)
                network.assert_not_called()
        path = self.vault.directory / (SESSION_KEY + ".dpapi")
        path.write_bytes(b"x" * 8193)
        with self.assertRaises(ValueError), patch.object(self.vault, "read") as decrypt:
            discover(self.vault)
        decrypt.assert_not_called()


@unittest.skipUnless(os.name == "nt", "Windows preparation script")
class NativeInstallerTests(unittest.TestCase):
    def test_prepare_only_exact_origins_and_backup_without_browser_registration(self):
        import winreg

        def registrations():
            result = []
            for browser in ("Google\\Chrome", "Microsoft\\Edge"):
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        "Software\\" + browser + "\\NativeMessagingHosts\\" + HOST_NAME,
                    ) as key:
                        result.append(winreg.QueryValueEx(key, ""))
                except FileNotFoundError:
                    result.append(None)
            return result

        before = registrations()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            executable = directory / "source.exe"
            executable.write_bytes(b"synthetic executable fixture")
            target = directory / "installed"
            script = Path(__file__).resolve().parents[1] / "Install-Browser-Pairing.ps1"
            command = [
                "powershell.exe",
                "-NoProfile",
                "-File",
                str(script),
                "-ExtensionId",
                "a" * 32,
                "-Browser",
                "Chrome",
                "-HostExecutable",
                str(executable),
                "-InstallDirectory",
                str(target),
                "-DataDirectory",
                str(directory / "data"),
            ]
            for _iteration in range(2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("No browser registry entry was changed", result.stdout)
            manifest = json.loads((target / (HOST_NAME + ".json")).read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["allowed_origins"], [ORIGIN])
            self.assertEqual(manifest["path"], str(target / "DiscordFixPairing.exe"))
            self.assertEqual(
                (target / "DiscordFixPairing.exe").read_bytes(), executable.read_bytes()
            )
            self.assertEqual(len(list(target.glob("*.previous.*"))), 3)
            before_files = set(target.iterdir())
            result = subprocess.run(
                command + ["-WhatIf"], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No files or browser registrations were changed", result.stdout)
            self.assertEqual(set(target.iterdir()), before_files)
            invalid = command.copy()
            invalid[invalid.index("-ExtensionId") + 1] = "invalid"
            self.assertNotEqual(
                subprocess.run(invalid, capture_output=True, timeout=30).returncode, 0
            )
        self.assertEqual(registrations(), before)


if __name__ == "__main__":
    unittest.main()
