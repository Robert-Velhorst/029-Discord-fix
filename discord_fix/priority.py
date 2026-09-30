"""Explainable rules; manual overrides always win."""

import json
from datetime import datetime, timezone


def classification(row, settings):
    if row.get("deleted"):
        return 0, 0, [("deleted", "")]
    reasons = []
    me = settings.get("user_id", "")
    own = row.get("source_kind") == "import" or (me and row.get("author_id") == me)
    reply = bool(
        me
        and not own
        and (me in json.loads(row.get("mentions", "[]")) or row.get("reply_author") == me)
    )
    if reply:
        reasons.append(("mentioned_or_replied", ""))
    for field, key, code in [
        ("author_id", "important_people", "person"),
        ("guild", "important_servers", "server"),
        ("channel", "important_channels", "channel"),
    ]:
        if row.get(field) in settings.get(key, []):
            reasons.append((code, row[field]))
    for topic in settings.get("important_topics", []):
        if topic and topic.casefold() in row["content"].casefold():
            reasons.append(("topic", topic))
    if (
        row.get("deadline")
        and (datetime.fromisoformat(row["deadline"]) - datetime.now(timezone.utc)).total_seconds()
        <= 172800
    ):
        reasons.append(("deadline", ""))
    important = bool(reasons)
    if row.get("priority_override") is not None:
        important = bool(row["priority_override"])
        reasons.insert(0, ("priority_on" if important else "priority_off", ""))
    if row.get("reply_override") is not None:
        reply = bool(row["reply_override"])
        reasons.insert(0, ("reply_on" if reply else "reply_off", ""))
    return int(important), int(reply), reasons or [("none", "")]


REASON_TEXT = {
    "nl": {
        "deleted": "Verwijderd bij de bron; geen actieve opvolging.",
        "mentioned_or_replied": "Je bent genoemd of dit is een antwoord op jouw bericht.",
        "person": "Belangrijke persoon volgens je instellingen.",
        "server": "Belangrijke server volgens je instellingen.",
        "channel": "Belangrijk kanaal volgens je instellingen.",
        "topic": "Onderwerp uit je instellingen: {argument}",
        "deadline": "Jouw deadline valt binnen 48 uur of is verstreken.",
        "priority_on": "Jouw prioriteitskeuze: belangrijk.",
        "priority_off": "Jouw prioriteitskeuze: niet belangrijk.",
        "reply_on": "Jouw keuze voor opvolging: ja.",
        "reply_off": "Jouw keuze voor opvolging: nee.",
        "none": "Geen prioriteitsregel van toepassing.",
    },
    "en": {
        "deleted": "Deleted at the source; no active follow-up.",
        "mentioned_or_replied": "You were mentioned or this replies to your message.",
        "person": "An important person from your settings.",
        "server": "An important server from your settings.",
        "channel": "An important channel from your settings.",
        "topic": "A topic from your settings: {argument}",
        "deadline": "Your deadline is within 48 hours or has passed.",
        "priority_on": "You marked this as important.",
        "priority_off": "You marked this as not important.",
        "reply_on": "You marked this as needing a reply.",
        "reply_off": "You marked this as not needing a reply.",
        "none": "No priority rule applies.",
    },
}


def priority_reasons(row, settings, language="en"):
    _, _, reasons = classification(row, settings)
    return [
        {
            "code": code,
            "argument": argument,
            "text": REASON_TEXT[language][code].format(argument=argument),
        }
        for code, argument in reasons
    ]


def classify(row, settings):
    important, reply, _ = classification(row, settings)
    return important, reply, [reason["text"] for reason in priority_reasons(row, settings, "nl")]
