"""Explainable rules; manual overrides always win."""

import json
from datetime import datetime, timezone


def classify(row, settings):
    if row.get("deleted"):
        return 0, 0, ["Verwijderd bij de bron; geen actieve opvolging."]
    reasons = []
    me = settings.get("user_id", "")
    own = row.get("source_kind") == "import" or (me and row.get("author_id") == me)
    reply = bool(
        me
        and not own
        and (me in json.loads(row.get("mentions", "[]")) or row.get("reply_author") == me)
    )
    if reply:
        reasons.append("Je bent genoemd of dit is een antwoord op jouw bericht.")
    for field, key, label in [
        ("author_id", "important_people", "Belangrijke persoon"),
        ("guild", "important_servers", "Belangrijke server"),
        ("channel", "important_channels", "Belangrijk kanaal"),
    ]:
        if row.get(field) in settings.get(key, []):
            reasons.append(label + " volgens je instellingen.")
    for topic in settings.get("important_topics", []):
        if topic and topic.casefold() in row["content"].casefold():
            reasons.append("Onderwerp uit je instellingen: " + topic)
    if (
        row.get("deadline")
        and (datetime.fromisoformat(row["deadline"]) - datetime.now(timezone.utc)).total_seconds()
        <= 172800
    ):
        reasons.append("Jouw deadline valt binnen 48 uur of is verstreken.")
    important = bool(reasons)
    if row.get("priority_override") is not None:
        important = bool(row["priority_override"])
        reasons.insert(
            0, "Jouw prioriteitskeuze: " + ("belangrijk." if important else "niet belangrijk.")
        )
    if row.get("reply_override") is not None:
        reply = bool(row["reply_override"])
        reasons.insert(0, "Jouw keuze voor opvolging: " + ("ja." if reply else "nee."))
    return int(important), int(reply), reasons or ["Geen prioriteitsregel van toepassing."]
