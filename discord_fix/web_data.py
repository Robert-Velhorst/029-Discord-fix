"""Consistent local browser snapshots, grouping and source-linked details."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .importer import deep_link
from .priority import priority_reasons
from .store import DEFAULTS
from .summaries import digest, validate_entries

VIEWS = {"Overview", "Important Now", "Needs Reply", "Conversations", "Later", "Everything"}
PAGE_SIZE = 60
WORKFLOW_FIELDS = ("state", "until", "priority_override", "reply_override", "deadline")


@contextmanager
def snapshot(path):
    database = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    database.row_factory = sqlite3.Row
    try:
        database.execute("PRAGMA query_only=ON")
        database.execute("BEGIN")
        yield database
    finally:
        database.close()


def revision(row):
    generation = row["workflow_revision"] if "workflow_revision" in row.keys() else 0
    return hashlib.sha256(
        json.dumps(
            [generation, *[row[key] for key in (*WORKFLOW_FIELDS, "important", "reply", "deleted")]]
        ).encode()
    ).hexdigest()


def settings_from(database):
    keys = (
        "user_id",
        "important_people",
        "important_servers",
        "important_channels",
        "important_topics",
        "sync_minutes",
    )
    settings = {key: DEFAULTS[key] for key in keys}
    for row in database.execute("SELECT key,value FROM settings"):
        if row["key"] in settings:
            settings[row["key"]] = json.loads(row["value"])
    return settings


def sources_from(database, settings, current):
    sources = {}
    for row in database.execute("SELECT id,kind,name,status,last_sync FROM sources ORDER BY name"):
        source = dict(row)
        if source["status"] == "synced":
            try:
                date = datetime.fromisoformat(source["last_sync"] or "")
                if date < current - timedelta(minutes=max(15, settings["sync_minutes"] * 3)):
                    source["status"] = "stale"
            except (ValueError, TypeError):
                source["status"] = "stale"
        source["coverage"] = (
            "Own sent messages from an export; other people's replies are not included."
            if source["kind"] == "import"
            else "Selected channels only; older history may be outside the bounded sync window."
        )
        sources[source["id"]] = source
    return sources


def group_records(records):
    """Known threads and reply components, with an explicit channel fallback."""
    lookup = {row["id"]: row for row in records}
    parents = {ident: ident for ident in lookup}
    connected = set()

    def root(ident):
        while parents[ident] != ident:
            parents[ident] = parents[parents[ident]]
            ident = parents[ident]
        return ident

    for row in records:
        other = lookup.get(row["reply_to"])
        if other and all(row[key] == other[key] for key in ("source_id", "guild", "channel")):
            first, second = root(row["id"]), root(other["id"])
            parents[max(first, second)] = min(first, second)
            connected.update((row["id"], other["id"]))
    groups, membership = {}, {}
    for row in records:
        if row["parent_channel"]:
            kind, target = "thread", row["conversation"] or row["channel"]
        elif row["conversation"] and row["conversation"] != row["channel"]:
            kind, target = "conversation", row["conversation"]
        elif row["id"] in connected:
            kind, target = "reply", root(row["id"])
        else:
            kind, target = "channel", row["channel"]
        key = hashlib.sha256(
            json.dumps([row["source_id"], row["guild"], row["channel"], kind, target]).encode()
        ).hexdigest()
        membership[row["id"]] = key
        groups.setdefault(
            key,
            {
                "id": key,
                "kind": kind,
                "channel_name": row["channel_name"],
                "guild": row["guild"],
                "source_id": row["source_id"],
                "members": [],
            },
        )["members"].append(row)
    return groups, membership


def effective(row, current):
    result = dict(row)
    if result["state"] == "later" and result["until"] and result["until"] <= current.isoformat():
        result["state"] = "open"
    return result


def item_from(row, settings, sources, current, demo, full=False):
    record = effective(row, current)
    original = "" if record["deleted"] else record["content"]
    limit = 1_000_000 if full else 420
    return {
        **{
            key: record[key]
            for key in (
                "id",
                "channel",
                "channel_name",
                "guild",
                "author",
                "timestamp",
                "state",
                "until",
                "deadline",
                "parent_channel",
                "conversation",
                "imported_at",
                "edited_at",
            )
        },
        "content": original[:limit],
        "content_truncated": len(original) > limit,
        "important": bool(record["important"]),
        "reply": bool(record["reply"]),
        "deleted": bool(record["deleted"]),
        "url": None if demo else deep_link(record),
        "source": sources.get(
            record["source_id"],
            {
                "id": record["source_id"],
                "name": "Unavailable source",
                "status": "unknown",
                "kind": record["source_kind"],
                "coverage": "Coverage unavailable.",
            },
        ),
        "reasons": priority_reasons(record, settings),
        "revision": revision(row),
    }


def page_data(
    database_path,
    view="Overview",
    search="",
    demo=False,
    offset=0,
    anchor=None,
    conversation="",
    since="",
    pinned=None,
):
    if view not in VIEWS or len(search) > 160:
        raise ValueError("Invalid view or search.")
    if pinned is not None and (
        not isinstance(pinned, list)
        or len(pinned) > 100
        or any(not isinstance(key, str) or len(key) != 64 for key in pinned)
    ):
        raise ValueError("Invalid pinned selection.")
    if type(offset) is not int or offset < 0 or offset > 2**63 - 1:
        raise ValueError("Invalid page offset.")
    if anchor is not None and (type(anchor) is not int or not 0 <= anchor <= 2**63 - 1):
        raise ValueError("Invalid snapshot boundary.")
    if since:
        date = datetime.fromisoformat(since)
        if date.tzinfo is None:
            raise ValueError("Visit time must include a timezone.")
        since = date.astimezone(timezone.utc).isoformat()
    current = datetime.now(timezone.utc)
    with snapshot(database_path) as database:
        settings = settings_from(database)
        sources = sources_from(database, settings, current)
        maximum = database.execute(
            "SELECT COALESCE((SELECT seq FROM sqlite_sequence WHERE name='browser_message_sequence'),0)"
        ).fetchone()[0]
        anchor = maximum if anchor is None else min(anchor, maximum)
        new_items = bool(
            database.execute(
                "SELECT 1 FROM browser_message_sequence WHERE sequence>? LIMIT 1", (anchor,)
            ).fetchone()
        )
        records = [
            dict(row)
            for row in database.execute(
                "SELECT sequence,id,source_id,guild,channel,channel_name,conversation,parent_channel,reply_to,timestamp,state,until,important,reply,deleted,author FROM messages JOIN browser_message_sequence ON message_id=messages.id WHERE sequence<=?",
                (anchor,),
            )
        ]
        groups, membership = group_records(records)
        matched = {
            row["id"]
            for row in database.execute(
                "SELECT id FROM messages JOIN browser_message_sequence ON message_id=messages.id WHERE sequence<=? AND instr(search_text,?)>0 AND (?='' OR imported_at>? OR edited_at>?)",
                (anchor, search.strip().casefold(), since, since, since),
            )
        }
        counts = {"total": len(records), "important": 0, "reply": 0, "later": 0, "other": 0}
        candidates = []
        for raw in records:
            row = effective(raw, current)
            active = not row["deleted"]
            important = active and row["state"] == "open" and row["important"]
            reply = active and row["state"] == "open" and row["reply"]
            later = active and row["state"] == "later"
            counts["important"] += int(bool(important))
            counts["reply"] += int(bool(reply))
            counts["later"] += int(bool(later))
            counts["other"] += int(not (important or reply or later))
            if row["id"] not in matched or (conversation and membership[row["id"]] != conversation):
                continue
            if pinned is not None and membership[row["id"]] not in pinned:
                continue
            if (
                view == "Important Now"
                and not important
                or view == "Needs Reply"
                and not reply
                or view == "Later"
                and not later
            ):
                continue
            candidates.append(row)
        candidates.sort(key=lambda row: (row["timestamp"], len(row["id"]), row["id"]), reverse=True)
        if view == "Overview":
            candidates.sort(
                key=lambda row: (
                    0
                    if row["state"] == "open" and row["important"] and not row["deleted"]
                    else 1
                    if row["state"] == "open" and row["reply"] and not row["deleted"]
                    else 2
                )
            )
        selected_groups = []
        if view == "Conversations" and not conversation:
            by_group = {}
            for row in candidates:
                by_group.setdefault(membership[row["id"]], row)
            total = len(by_group)
            page_offset = min(offset, max(0, (total - 1) // PAGE_SIZE * PAGE_SIZE))
            for key, latest in list(by_group.items())[page_offset : page_offset + PAGE_SIZE]:
                group = groups[key]
                members = [effective(row, current) for row in group["members"]]
                selected_groups.append(
                    {
                        key_: group[key_]
                        for key_ in ("id", "kind", "channel_name", "guild", "source_id")
                    }
                    | {
                        "count": len(members),
                        "matched": sum(row["id"] in matched for row in members),
                        "open_replies": sum(
                            row["state"] == "open" and row["reply"] and not row["deleted"]
                            for row in members
                        ),
                        "timestamp": latest["timestamp"],
                        "participants": list(dict.fromkeys(row["author"] for row in members))[:8],
                    }
                )
            candidates = []
        else:
            total = len(candidates)
            page_offset = min(offset, max(0, (total - 1) // PAGE_SIZE * PAGE_SIZE))
            candidates = candidates[page_offset : page_offset + PAGE_SIZE]
        items = []
        for row in candidates:
            raw = database.execute("SELECT * FROM messages WHERE id=?", (row["id"],)).fetchone()
            items.append(
                item_from(raw, settings, sources, current, demo)
                | {"conversation_key": membership[row["id"]]}
            )
    return {
        "view": view,
        "demo": bool(demo),
        "generated_at": current.isoformat(),
        "counts": counts,
        "items": items,
        "sources": list(sources.values()),
        "groups": selected_groups,
        "pagination": {
            "offset": page_offset,
            "limit": PAGE_SIZE,
            "total": total,
            "anchor": anchor,
            "has_more": page_offset + PAGE_SIZE < total,
        },
        "new_items": new_items,
    }


def message_data(database_path, ident, demo=False):
    with snapshot(database_path) as database:
        row = database.execute("SELECT * FROM messages WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Message unavailable.")
        current = datetime.now(timezone.utc)
        settings = settings_from(database)
        return item_from(
            row, settings, sources_from(database, settings, current), current, demo, full=True
        )


def summary_data(database_path, scope="personal", target="*", offset=0, demo=False):
    if (
        scope not in {"personal", "conversation", "channel", "server"}
        or not isinstance(target, str)
        or len(target) > 128
        or type(offset) is not int
        or offset < 0
    ):
        raise ValueError("Invalid summary selection.")
    with snapshot(database_path) as database:
        summary = database.execute(
            "SELECT * FROM summaries WHERE scope=? AND target=?", (scope, target)
        ).fetchone()
        if summary is None:
            return {"entries": [], "available": False, "total": 0}
        body = json.loads(summary["body"])
        if not isinstance(body, dict):
            return {"entries": [], "available": False, "total": 0, "needs_refresh": True}
        exclusions = {
            (row["scope"], row["target"]) for row in database.execute("SELECT * FROM exclusions")
        }
        sources = {
            row["id"]: dict(row) for row in database.execute("SELECT id,kind,status FROM sources")
        }
        evidence = {}
        for row in database.execute("SELECT * FROM messages"):
            source = sources.get(row["source_id"], {})
            scopes = {
                ("source", row["source_id"]),
                ("server", row["guild"]),
                ("channel", row["channel"]),
                ("channel", row["parent_channel"] or row["channel"]),
                ("conversation", row["conversation"]),
                ("message", row["id"]),
            }
            if (
                ("personal", "*") in exclusions
                or scopes & exclusions
                or row["deleted"]
                or source.get("kind") == "bot"
                and source.get("status") not in {"synced", "partial"}
            ):
                continue
            evidence[row["id"]] = dict(row)
        # Reject the whole saved summary rather than exposing text derived from
        # an excluded, removed or edited source through another hierarchy level.
        entries = body.get("entries", [])
        hashes = body.get("source_hashes")
        try:
            if not isinstance(entries, list) or not isinstance(hashes, dict) or not hashes:
                raise ValueError("Missing saved evidence.")
            for ident, expected in hashes.items():
                if ident not in evidence or expected != digest(
                    {
                        key: evidence[ident][key]
                        for key in (
                            "content",
                            "author",
                            "timestamp",
                            "edited_at",
                            "channel",
                            "guild",
                            "parent_channel",
                        )
                    }
                ):
                    raise ValueError("Saved evidence changed.")
            for start in range(0, len(entries), 500):
                validate_entries(entries[start : start + 500], [evidence[key] for key in hashes])
        except (ValueError, TypeError, KeyError):
            return {"entries": [], "available": False, "total": 0, "needs_refresh": True}
        page = []
        for entry in entries[offset : offset + 30]:
            page.append(
                {
                    "category": entry["category"],
                    "text": entry["text"],
                    "basis": "Source excerpt; not independent verification."
                    if summary["model"].startswith("Lokale")
                    else "Interpretation; verify the cited messages.",
                    "citations": [
                        {
                            "id": c["id"],
                            "quote": c["quote"],
                            "url": None if demo else deep_link(evidence[c["id"]]),
                        }
                        for c in entry["citations"]
                    ],
                }
            )
        return {
            "available": True,
            "entries": page,
            "total": len(entries),
            "offset": offset,
            "has_more": offset + 30 < len(entries),
            "generated_at": summary["generated_at"],
            "model": "Local text extraction (no generative AI)"
            if summary["model"].startswith("Lokale")
            else summary["model"],
            "scope": scope,
            "target": target,
            "correction": summary["note"],
            "coverage": "Only available, permitted messages included in this saved summary; history may be incomplete.",
        }
