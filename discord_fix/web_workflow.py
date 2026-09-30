"""Explicit local workflow writes with optimistic conflict detection and Undo."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from .priority import classify
from .web_data import WORKFLOW_FIELDS, revision, settings_from


class WorkflowConflict(ValueError):
    pass


def apply_workflow(path, payload, undo=None):
    ident, action = payload.get("id"), payload.get("action")
    if not isinstance(ident, str) or not ident or len(ident) > 128:
        raise ValueError("Choose a valid message.")
    if action not in {"complete", "dismiss", "reopen", "later", "important", "reply", "undo"}:
        raise ValueError("Choose a supported local action.")
    database = sqlite3.connect(path, timeout=5)
    database.row_factory = sqlite3.Row
    try:
        database.execute("BEGIN IMMEDIATE")
        row = database.execute("SELECT * FROM messages WHERE id=?", (ident,)).fetchone()
        if row is None or row["deleted"]:
            raise WorkflowConflict("This message is no longer available. Refresh the dashboard.")
        if payload.get("revision") != revision(row):
            raise WorkflowConflict("This item changed elsewhere. Refresh before trying again.")
        before = {key: row[key] for key in WORKFLOW_FIELDS}
        after = dict(before)
        if action == "undo":
            if not undo or undo["id"] != ident or undo["revision"] != revision(row):
                raise WorkflowConflict("Undo is no longer available for this item.")
            after = undo["before"]
        elif action == "later":
            minutes = payload.get("minutes")
            if type(minutes) is not int or not 1 <= minutes <= 525600:
                raise ValueError("Choose a snooze time between one minute and one year.")
            after.update(
                state="later",
                until=(datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(),
            )
        elif action in {"important", "reply"}:
            after["priority_override" if action == "important" else "reply_override"] = (
                1 - row[action]
            )
        else:
            after.update(
                state={"complete": "complete", "dismiss": "dismissed", "reopen": "open"}[action],
                until=None,
            )
        revised = dict(row) | after
        important, reply, reasons = classify(revised, settings_from(database))
        revised.update(important=important, reply=reply)
        database.execute(
            "UPDATE messages SET state=?,until=?,priority_override=?,reply_override=?,deadline=?,important=?,reply=?,reason=? WHERE id=?",
            (
                *[after[key] for key in WORKFLOW_FIELDS],
                important,
                reply,
                json.dumps(reasons, ensure_ascii=False),
                ident,
            ),
        )
        database.execute(
            "INSERT INTO audit(timestamp,action,target,detail) VALUES (?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                "browser_" + action,
                ident,
                "Local workflow only",
            ),
        )
        saved = database.execute("SELECT * FROM messages WHERE id=?", (ident,)).fetchone()
        result = {"id": ident, "revision": revision(saved), "before": before}
        database.commit()
        return result
    finally:
        database.close()
