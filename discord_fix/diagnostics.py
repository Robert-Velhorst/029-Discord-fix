"""Opt-in packaged smoke test; synthetic temporary data only."""

import json
import tempfile
import tkinter as tk
from pathlib import Path
from urllib.request import urlopen

from . import panels, summaries
from .store import Store
from .web_dashboard import DashboardServer


def run(report_path):
    from .__main__ import App

    result = {"ok": False, "checks": []}
    with tempfile.TemporaryDirectory(prefix="discord-fix-test-") as directory:
        store = Store(Path(directory) / "test.sqlite")
        root = tk.Tk()
        root.withdraw()
        try:
            store.ingest(
                [
                    dict(
                        id="101",
                        channel="10",
                        channel_name="Synthetische test",
                        guild="20",
                        content="Wat gaan we morgen doen?",
                        timestamp="2026-09-12T10:00:00+00:00",
                        attachments="[]",
                    )
                ]
            )
            app = App(root, store)
            app.tree.selection_set("101")
            app.select()
            app.act("important")
            if store.get("101")["important"] != 1:
                raise RuntimeError("Workflowactie niet opgeslagen.")
            result["checks"].append("Native UI selection and persistent priority")
            snapshot = summaries.prepare(store)
            outputs = summaries.build(snapshot, summaries.Extractive())
            summaries.commit(store, snapshot, outputs)
            if len(outputs) != 4:
                raise RuntimeError("Vier samenvattingsniveaus ontbreken.")
            result["checks"].append("Four cited summary levels")
            dashboard = DashboardServer(store.path, demo=True)
            dashboard_url = dashboard.start()
            try:
                with urlopen(dashboard_url, timeout=3) as response:
                    page = response.read().decode("utf-8")
                with urlopen(dashboard_url + "api/dashboard", timeout=3) as response:
                    view = json.loads(response.read())
                if "Jouw Discord-overzicht" not in page or not view["demo"]:
                    raise RuntimeError("Browserdashboard of voorbeeldstatus ontbreekt.")
                if not any(item["id"] == "101" for item in view["items"]):
                    raise RuntimeError("Synthetisch bericht ontbreekt in browserdashboard.")
                if any(item["url"] for item in view["items"]):
                    raise RuntimeError("Voorbeeldberichten mogen geen Discord-links bevatten.")
            finally:
                dashboard.stop()
            result["checks"].append("Local read-only browser dashboard")
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
            result["checks"].append("All desktop dialogs instantiate")
            store.exclude("message", "101")
            if store.summary_records():
                raise RuntimeError("Privacy-uitsluiting mislukt.")
            result["checks"].append("Privacy exclusion")
            root.after_cancel(app.timer)
            result["ok"] = True
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            root.destroy()
            store.db.close()
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
