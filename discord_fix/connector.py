"""Official, read-only Discord bot REST adapter with explicit channel scope."""

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

from .importer import snowflake
from .network import HttpFailure, request_json

_COOLDOWNS = {}


class RateLimited(Exception):
    def __init__(self, seconds):
        self.seconds = max(1, min(float(seconds), 86400))
        super().__init__(
            "Discord vraagt om een pauze van " + str(round(self.seconds)) + " seconden."
        )


class AccessDenied(Exception):
    pass


def can_read(guild, member, channel, user_id):
    """Discord role union, everyone/role/member overwrite order."""
    if str(guild.get("owner_id")) == user_id:
        return True
    role_ids = {str(r) for r in member["roles"]} | {str(guild["id"])}
    permissions = 0
    for role in guild["roles"]:
        if str(role["id"]) in role_ids:
            permissions |= int(role["permissions"])
    if permissions & 8:
        return True
    overwrites = channel.get("permission_overwrites", [])
    everyone = next(
        (o for o in overwrites if str(o["id"]) == str(guild["id"]) and o["type"] == 0), None
    )
    if everyone:
        permissions = (permissions & ~int(everyone["deny"])) | int(everyone["allow"])
    allow, deny = 0, 0
    for overwrite in overwrites:
        if (
            overwrite["type"] == 0
            and str(overwrite["id"]) in role_ids
            and str(overwrite["id"]) != str(guild["id"])
        ):
            allow |= int(overwrite["allow"])
            deny |= int(overwrite["deny"])
    permissions = (permissions & ~deny) | allow
    personal = next((o for o in overwrites if o["type"] == 1 and str(o["id"]) == user_id), None)
    if personal:
        permissions = (permissions & ~int(personal["deny"])) | int(personal["allow"])
    required = (1 << 10) | (1 << 16)
    return permissions & required == required


class DiscordBot:
    def __init__(self, token, transport=request_json, cancelled=None):
        if (
            not token.strip()
            or token.startswith(("Bot ", "Bearer ", "mfa."))
            or "\n" in token
            or "\r" in token
        ):
            raise ValueError(
                "Voer uitsluitend de bot-tokenwaarde in, zonder prefix of gebruikerstoken."
            )
        self._token, self.transport, self.not_before = token, transport, 0.0
        self.cancelled = cancelled
        self.token_key = hashlib.sha256(token.encode()).hexdigest()

    def get(self, route):
        if self.cancelled and self.cancelled.is_set():
            raise RuntimeError("Synchronisatie geannuleerd.")
        remaining = max(self.not_before, _COOLDOWNS.get(self.token_key, 0)) - time.monotonic()
        if remaining > 0:
            if remaining > 30 or not self.cancelled:
                raise RateLimited(remaining)
            if self.cancelled.wait(remaining):
                raise RuntimeError("Synchronisatie geannuleerd.")
        try:
            payload, headers = self.transport(
                "https://discord.com/api/v10" + route,
                headers={
                    "Authorization": "Bot " + self._token,
                    "User-Agent": "DiscordBot (https://github.com/Robert-Velhorst/029-Discord-fix, 0.4.0)",
                },
            )
        except HttpFailure as exc:
            if exc.status == 429:
                limited = RateLimited(exc.body.get("retry_after", 60))
                _COOLDOWNS[self.token_key] = time.monotonic() + limited.seconds
                raise limited from None
            if exc.status in (401, 403):
                raise AccessDenied(
                    "Bot-token ongeldig of toegang ingetrokken (HTTP " + str(exc.status) + ")."
                ) from None
            raise
        headers = {k.lower(): v for k, v in headers.items()}
        if headers.get("x-ratelimit-remaining") == "0":
            self.not_before = time.monotonic() + float(headers.get("x-ratelimit-reset-after", "1"))
        return payload

    def identity(self):
        user = self.get("/users/@me")
        if user.get("bot") is not True:
            raise AccessDenied("Alleen een officiële bot-identiteit is toegestaan.")
        return user

    def collect(self, channel_ids, max_pages=5):
        """Refresh a bounded recent window; no implicit access to other channels.

        IDs absent inside a completely fetched window may be tombstoned. Older
        history is explicitly outside coverage, never assumed deleted.
        """
        user = self.identity()
        records, windows, details = [], [], []
        for ident in channel_ids:
            ident = snowflake(ident)
            channel = self.get("/channels/" + ident)
            if channel.get("type") not in (0, 5, 10, 11, 12):
                raise AccessDenied(
                    "Alleen server-tekstkanalen en expliciet gekozen threads worden ondersteund."
                )
            guild = snowflake(channel.get("guild_id"))
            permission_channel = (
                self.get("/channels/" + snowflake(channel["parent_id"]))
                if channel["type"] in (10, 11, 12)
                else channel
            )
            guild_data = self.get("/guilds/" + guild)
            member = self.get("/guilds/" + guild + "/members/" + snowflake(user["id"]))
            if not can_read(guild_data, member, permission_channel, str(user["id"])):
                raise AccessDenied("View Channel en Read Message History zijn niet beide verleend.")
            before, seen, exhausted = None, [], False
            for _ in range(max_pages):
                route = (
                    "/channels/"
                    + ident
                    + "/messages?limit=100"
                    + ("&before=" + before if before else "")
                )
                batch = self.get(route)
                if not isinstance(batch, list):
                    raise ValueError("Ongeldig Discord-antwoord.")
                for message in batch:
                    message_id = snowflake(message["id"])
                    if str(message.get("channel_id")) != ident:
                        raise AccessDenied("Antwoord valt buiten het gekozen kanaal.")
                    author = message.get("author") or {}
                    reference = message.get("referenced_message") or {}
                    content = message.get("content", "")
                    if not isinstance(content, str):
                        raise ValueError("Ongeldige berichttekst.")
                    records.append(
                        dict(
                            id=message_id,
                            channel=ident,
                            channel_name=str(channel.get("name", ident)),
                            guild=guild,
                            content=content,
                            timestamp=datetime.fromisoformat(
                                message["timestamp"].replace("Z", "+00:00")
                            )
                            .astimezone(timezone.utc)
                            .isoformat(),
                            attachments=json.dumps(message.get("attachments", [])),
                            author_id=str(author.get("id", "")),
                            author=str(
                                author.get("global_name")
                                or author.get("username")
                                or "Onbekende auteur"
                            ),
                            mentions=json.dumps(
                                [str(m["id"]) for m in message.get("mentions", [])]
                            ),
                            reply_to=str(
                                (message.get("message_reference") or {}).get("message_id", "")
                            ),
                            reply_author=str((reference.get("author") or {}).get("id", "")),
                            edited_at=message.get("edited_timestamp") or "",
                            conversation=ident,
                            parent_channel=str(channel.get("parent_id") or "")
                            if channel["type"] in (10, 11, 12)
                            else "",
                        )
                    )
                    seen.append(message_id)
                if len(batch) < 100:
                    exhausted = True
                    break
                before = str(min(int(m["id"]) for m in batch))
            windows.append(dict(channel=ident, ids=seen, exhausted=exhausted))
            details.append(
                f"{channel.get('name', ident)}: {len(seen)} recente berichten; "
                + ("bereik uitgeput" if exhausted else "oudere geschiedenis buiten bereik")
            )
        return records, windows, "; ".join(details)


def apply_sync(store, source, result):
    records, windows, detail = result
    source_id = source["id"]
    with store.transaction():
        store.ingest(records, source_id, "bot")
        for window in windows:
            seen = set(window["ids"])
            floor = min(map(int, seen)) if seen else None
            for row in store.db.execute(
                "SELECT id FROM messages WHERE source_id=? AND channel=? AND deleted=0",
                (source_id, window["channel"]),
            ).fetchall():
                if row["id"] not in seen and (
                    window["exhausted"] or (floor is not None and int(row["id"]) >= floor)
                ):
                    store.db.execute(
                        "UPDATE messages SET deleted=1,content='',attachments='[]',search_text='',important=0,reply=0 WHERE id=?",
                        (row["id"],),
                    )
        # Cached summaries are revalidated by their source hashes before display.
        store.db.execute(
            "UPDATE sources SET status='synced',detail=?,next_sync=NULL WHERE id=?",
            (
                detail
                + " · Inhoud kan door Discord-intents beperkt zijn; geen persoonlijke DM-toegang.",
                source_id,
            ),
        )
        store.audit("sync", source_id, str(len(records)))


def sync_failure(store, source, error):
    status = (
        "rate_limited"
        if isinstance(error, RateLimited)
        else "revoked"
        if isinstance(error, AccessDenied)
        else "offline"
    )
    delay = error.seconds if isinstance(error, RateLimited) else 300
    retry = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
    with store.db:
        store.db.execute(
            "UPDATE sources SET status=?,detail=?,next_sync=? WHERE id=?",
            (status, str(error), retry, source["id"]),
        )
        store.clear_summaries()
        store.notify(
            "source:" + source["id"] + status, "source", "Bron " + source["name"] + ": " + status
        )
