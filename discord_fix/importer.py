"""Read only message files in a voluntarily selected Discord data ZIP.

Never extract paths, fetch attachments, or read account/token data.
"""

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

MAX_BYTES = 100 * 1024 * 1024


def snowflake(value):
    value = str(value)
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Ongeldig Discord-ID")
    return value


def read_package(path):
    records, errors = [], []
    with zipfile.ZipFile(path) as archive:
        files = archive.infolist()
        if len(files) > 50000 or sum(f.file_size for f in files) > MAX_BYTES:
            raise ValueError("Pakket te groot: maximaal 100 MB uitgepakt en 50.000 bestanden.")
        names = {f.filename for f in files}
        if len(names) != len(files):
            raise ValueError("Pakket bevat dubbele bestandsnamen; import afgebroken.")
        for f in files:
            p = PurePosixPath(f.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in f.filename:
                errors.append(f"{f.filename}: onveilige archiefnaam overgeslagen")
                continue
            if p.name.lower() not in ("messages.json", "messages.csv") or "messages" not in [
                s.lower() for s in p.parts[:-1]
            ]:
                continue
            try:
                metadata_path = str(p.parent / "channel.json")
                meta = json.loads(archive.read(metadata_path)) if metadata_path in names else {}
                channel = snowflake(meta.get("id", meta.get("ID", p.parent.name.removeprefix("c"))))
                guild_data = meta.get("guild") or {}
                guild = snowflake(guild_data["id"]) if guild_data.get("id") else "@me"
                # Unknown guild context must not be presented as a verified DM.
                if guild == "@me" and meta.get("type") not in (1, 3, "DM", "GROUP_DM"):
                    guild = ""
                text = archive.read(f).decode("utf-8-sig")
                items = (
                    json.loads(text)
                    if p.suffix.lower() == ".json"
                    else list(csv.DictReader(io.StringIO(text)))
                )
                if not isinstance(items, list):
                    raise ValueError("Verwacht een lijst met berichten")
                for index, item in enumerate(items):
                    try:
                        ident = snowflake(item.get("ID", item.get("id")))
                        timestamp = str(item.get("Timestamp", item.get("timestamp", "")))
                        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        if date.tzinfo is None:
                            date = date.replace(tzinfo=timezone.utc)
                        content = item.get(
                            "Contents", item.get("contents", item.get("content", ""))
                        )
                        if not isinstance(content, str):
                            raise ValueError("Berichttekst moet tekst zijn")
                        records.append(
                            dict(
                                id=ident,
                                channel=channel,
                                channel_name=str(meta.get("name") or channel),
                                guild=guild,
                                content=content,
                                timestamp=date.astimezone(timezone.utc).isoformat(),
                                attachments=json.dumps(
                                    item.get("Attachments", item.get("attachments", [])),
                                    ensure_ascii=False,
                                ),
                            )
                        )
                    except (ValueError, TypeError, AttributeError) as exc:
                        errors.append(f"{f.filename}, regel {index + 1}: {exc}")
            except (ValueError, TypeError, AttributeError, UnicodeError, RuntimeError) as exc:
                errors.append(f"{f.filename}: {exc}")
    if not records and not errors:
        raise ValueError(
            "Geen ondersteunde messages.json of messages.csv gevonden in de map messages."
        )
    return records, errors


def deep_link(row):
    if not row["guild"]:
        return None
    guild = row["guild"] if row["guild"] == "@me" else snowflake(row["guild"])
    return (
        f"https://discord.com/channels/{guild}/{snowflake(row['channel'])}/{snowflake(row['id'])}"
    )
