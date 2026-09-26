"""Desktop dialogs for sources, privacy, preferences and cited context."""

import json
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import summaries
from .importer import deep_link, snowflake
from .widgets import Scrollable, fit_window


def window(app, title, size="850x620"):
    top = tk.Toplevel(app.root)
    top.title(title)
    fit_window(top, size)
    container = Scrollable(top, padding=18)
    container.pack(fill="both", expand=True)
    frame = container.content
    app.apply_style()
    return top, frame


def read_text(parent, text, height=10, app=None):
    size = app.store.settings()["message_font_size"] if app else 11
    box = tk.Text(parent, wrap="word", height=height, font=("Segoe UI", size), padx=10, pady=10)
    box.pack(fill="both", expand=True, pady=8)
    box.insert("end", text)
    box.configure(state="disabled")
    if app:
        app.apply_native_style(box)
    return box


def sources_panel(app):
    if app.busy:
        messagebox.showinfo("Even wachten", "Wacht tot de huidige verwerking klaar is.")
        return
    top, frame = window(app, "Bronnen en dekking")
    ttk.Label(
        frame,
        text="Een bot leest alleen expliciet gekozen serverkanalen en threads.",
        wraplength=780,
    ).pack(anchor="w")
    tree = ttk.Treeview(frame, columns=("type", "status", "sync"), show="tree headings")
    tree.heading("#0", text="Bron")
    for key, title in [("type", "Type"), ("status", "Status"), ("sync", "Laatste ontvangst")]:
        tree.heading(key, text=title)
        tree.column(key, width=130)
    tree.pack(fill="both", expand=True, pady=12)
    detail = tk.StringVar()
    ttk.Label(frame, textvariable=detail, wraplength=780).pack(anchor="w", pady=8)

    def refresh():
        tree.delete(*tree.get_children())
        for source in app.store.sources():
            tree.insert(
                "",
                "end",
                iid=source["id"],
                text=source["name"],
                values=(source["kind"], source["status"], source["last_sync"] or "Nog nooit"),
            )

    def selected():
        ids = tree.selection()
        return next((s for s in app.store.sources() if ids and s["id"] == ids[0]), None)

    def show(_=None):
        source = selected()
        detail.set(("Bron-ID: " + source["id"] + "\n" + source["detail"]) if source else "")

    tree.bind("<<TreeviewSelect>>", show)

    def connect():
        if app.busy:
            return
        dialog, body = window(app, "Officiële bot koppelen", "720x530")
        ttk.Label(
            body,
            text="Gebruik een bot uit de Discord Developer Portal die een beheerder heeft geïnstalleerd.\nBenodigd: View Channel, Read Message History en toegang tot berichtinhoud.\nGeen gebruikerstokens. Alleen lezen; Discord Fix verstuurt geen berichten.",
            wraplength=660,
        ).pack(anchor="w")
        values = {}
        for key, label, default in [
            ("name", "Naam van deze bron", "Discord-bot"),
            ("channels", "Kanaal- of thread-ID’s, gescheiden door komma’s", ""),
            ("token", "Bot-token (Windows-beveiligde opslag)", ""),
        ]:
            ttk.Label(body, text=label).pack(anchor="w", pady=(12, 2))
            values[key] = tk.StringVar(value=default)
            ttk.Entry(body, textvariable=values[key], show="*" if key == "token" else "").pack(
                fill="x"
            )
        ttk.Label(
            body,
            text="Dekking: maximaal 500 recente berichten per gekozen kanaal per synchronisatie.\nOudere geschiedenis en niet gekozen threads blijven buiten bereik.",
            wraplength=650,
        ).pack(anchor="w", pady=12)
        consent = tk.BooleanVar()
        ttk.Checkbutton(
            body,
            text="Ik mag deze bot en kanalen gebruiken en wil nu verbinding maken.",
            variable=consent,
        ).pack(anchor="w")

        def save():
            try:
                if not consent.get():
                    raise ValueError("Bevestig dat je deze bot en kanalen mag gebruiken.")
                channels = list(
                    dict.fromkeys(
                        snowflake(v.strip())
                        for v in values["channels"].get().split(",")
                        if v.strip()
                    )
                )
                if not channels or len(channels) > 20:
                    raise ValueError("Kies tussen 1 en 20 kanalen.")
                token = values["token"].get().strip()
                from .connector import DiscordBot

                DiscordBot(token)  # local validation only
                ident = "bot-" + uuid.uuid4().hex
                app.vault.save(ident, token)
                app.store.source(
                    ident,
                    "bot",
                    values["name"].get() or "Discord-bot",
                    "pending",
                    "Nog niet geverifieerd",
                    dict(channels=channels),
                )
                dialog.destroy()
                top.destroy()
                app.sync_sources(only=ident)
            except (ValueError, RuntimeError, OSError) as exc:
                messagebox.showerror("Koppelen mislukt", str(exc), parent=dialog)

        ttk.Button(body, text="Veilig opslaan en verbinding testen", command=save).pack(
            anchor="w", pady=16
        )

    def disconnect():
        source = selected()
        if not source or app.busy:
            return
        app.vault.forget(source["id"])
        app.store.source(
            source["id"],
            source["kind"],
            source["name"],
            "disconnected",
            "Losgekoppeld; lokale berichten blijven beschikbaar.",
            source["config"],
        )
        with app.store.db:
            app.store.clear_summaries()
        app.invalidate_summary_windows()
        refresh()
        app.refresh()

    def delete():
        source = selected()
        if not source or app.busy:
            return
        if messagebox.askyesno(
            "Lokale gegevens verwijderen",
            f"Alle lokale berichten van {source['name']} en afgeleide samenvattingen verwijderen? Discord zelf en eerdere exports/back-ups blijven onaangeroerd.",
            parent=top,
        ):
            app.vault.forget(source["id"])
            app.store.delete_source_data(source["id"])
            app.invalidate_summary_windows()
            refresh()
            app.refresh()

    def sync():
        source = selected()
        if source and source["kind"] == "bot":
            top.destroy()
            app.sync_sources(only=source["id"])

    def interval():
        source = selected()
        if not source or app.busy:
            return
        value = simpledialog.askinteger(
            "Samenvattingsinterval",
            "Minuten tussen automatische updates voor deze bron (1–10080):",
            initialvalue=source["config"].get(
                "summary_minutes", app.store.settings()["summary_minutes"]
            ),
            minvalue=1,
            maxvalue=10080,
            parent=top,
        )
        if value:
            app.store.source(
                source["id"],
                source["kind"],
                source["name"],
                source["status"],
                source["detail"],
                source["config"] | {"summary_minutes": value},
                source["next_sync"],
            )
            detail.set(
                "Samenvattingsinterval ingesteld op "
                + str(value)
                + " minuten. Controle vindt plaats op het algemene interval."
            )

    actions = ttk.Frame(frame)
    actions.pack(fill="x")
    for label, command in [
        ("Bot toevoegen", connect),
        ("Synchroniseren", sync),
        ("Loskoppelen", disconnect),
        ("Lokaal verwijderen", delete),
        ("Verversen", refresh),
        ("Interval", interval),
    ]:
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=3)
    refresh()


def settings_panel(app):
    if app.busy:
        messagebox.showinfo("Even wachten", "Wacht tot de huidige verwerking klaar is.")
        return
    top, frame = window(app, "Instellingen", "880x820")
    tabs = ttk.Notebook(frame)
    tabs.pack(fill="both", expand=True)
    config = app.store.settings()
    values = {}
    pages = {}
    for name in ("Prioriteit", "AI en planning", "Weergave en meldingen"):
        pages[name] = ttk.Frame(tabs, padding=12)
        tabs.add(pages[name], text=name)

    def field(page, key, label):
        parent = pages[page]
        ttk.Label(parent, text=label, wraplength=760).pack(anchor="w", pady=(8, 2))
        value = config[key]
        values[key] = tk.StringVar(
            value=", ".join(value) if isinstance(value, list) else str(value)
        )
        ttk.Entry(parent, textvariable=values[key]).pack(fill="x")

    for key, label in [
        ("user_id", "Jouw Discord-gebruikers-ID (voor vermeldingen)"),
        ("important_people", "Belangrijke personen: gebruikers-ID’s, komma’s"),
        ("important_servers", "Belangrijke servers: ID’s, komma’s"),
        ("important_channels", "Belangrijke kanalen: ID’s, komma’s"),
        ("important_topics", "Belangrijke onderwerpen: woorden, komma’s"),
    ]:
        field("Prioriteit", key, label)
    ai = pages["AI en planning"]
    ttk.Label(
        ai,
        text="Tekstregels werken zonder model. Ollama verwerkt lokaal. Externe AI verstuurt\nberichttekst, auteur, tijdstip en bericht-ID naar het gekozen adres.",
        wraplength=760,
    ).pack(anchor="w")
    values["provider"] = tk.StringVar(value=config["provider"])
    ttk.Combobox(
        ai,
        textvariable=values["provider"],
        values=["extractive", "ollama", "external"],
        state="readonly",
    ).pack(fill="x", pady=8)
    for key, label in [
        ("endpoint", "Exact endpoint (Ollama /api/chat of externe /chat/completions)"),
        ("model", "Naam van een geïnstalleerd / beschikbaar model"),
        ("summary_minutes", "Interval samenvattingen, minuten"),
        ("sync_minutes", "Interval bot-synchronisatie, minuten"),
    ]:
        field("AI en planning", key, label)
    ttk.Label(ai, text="Nieuwe API-sleutel (leeg laten behoudt bestaande sleutel)").pack(
        anchor="w", pady=(8, 2)
    )
    secret = tk.StringVar()
    ttk.Entry(ai, textvariable=secret, show="*").pack(fill="x")
    consent = tk.BooleanVar(
        value=bool(config["external_consent"] and config["external_consent"] == config["endpoint"])
    )
    ttk.Checkbutton(
        ai,
        text="Ik geef toestemming voor verwerking bij dit externe adres en eventuele providerkosten.",
        variable=consent,
    ).pack(anchor="w", pady=8)
    for page, key, label in [
        ("AI en planning", "auto_summaries", "Automatisch samenvatten terwijl de app open is"),
        ("AI en planning", "auto_sync", "Automatisch gekozen botbronnen synchroniseren"),
        ("Weergave en meldingen", "high_contrast", "Hoog contrast"),
        ("Weergave en meldingen", "notify_priority", "Nieuwe belangrijke berichten"),
        ("Weergave en meldingen", "notify_summary", "Gewijzigde samenvattingen"),
        ("Weergave en meldingen", "notify_snooze", "Teruggekeerde uitgestelde berichten"),
        ("Weergave en meldingen", "notify_source", "Bronfouten of ingetrokken toegang"),
        ("Weergave en meldingen", "notify_deadline", "Naderende deadlines"),
    ]:
        values[key] = tk.BooleanVar(value=config[key])
        ttk.Checkbutton(pages[page], text=label, variable=values[key]).pack(anchor="w", pady=4)
    display = pages["Weergave en meldingen"]
    ttk.Label(
        display,
        text=(
            "Deze weergave-instellingen gelden voor Discord Fix. Ze veranderen de officiële "
            "Discord-app niet. Versleep kolomranden in het overzicht om iedere kolom apart "
            "in te stellen; de breedtes worden bewaard. Sneltoetsen: Ctrl+1–5 voor weergaven, "
            "Ctrl+Plus/Min voor tekst en Ctrl+0 voor standaardtekst. F6 wisselt tussen zoeken, "
            "berichten en berichtdetails."
        ),
        wraplength=760,
    ).pack(anchor="w", pady=(0, 12))
    theme_labels = {
        "light": "Licht",
        "ash": "Discord Ash",
        "dark": "Discord Dark",
        "onyx": "Onyx zwart",
    }
    theme_ids = {label: key for key, label in theme_labels.items()}
    ttk.Label(display, text="Kleurthema").pack(anchor="w")
    values["theme"] = tk.StringVar(value=theme_labels[config["theme"]])
    ttk.Combobox(
        display,
        textvariable=values["theme"],
        values=list(theme_ids),
        state="readonly",
    ).pack(fill="x", pady=(2, 8))
    field("Weergave en meldingen", "font_size", "Bedieningstekst (9–24)")
    field("Weergave en meldingen", "message_font_size", "Berichttekst (9–32)")
    density_labels = {
        "compact": "Compact",
        "comfortable": "Standaard",
        "spacious": "Ruim",
    }
    density_ids = {label: key for key, label in density_labels.items()}
    ttk.Label(display, text="Regelafstand").pack(anchor="w")
    values["density"] = tk.StringVar(value=density_labels[config["density"]])
    ttk.Combobox(
        display,
        textvariable=values["density"],
        values=list(density_ids),
        state="readonly",
    ).pack(fill="x", pady=(2, 8))
    field(
        "Weergave en meldingen",
        "retention_days",
        "Bewaartermijn in dagen; 0 = onbeperkt. Verwijdert ook afgehandelde berichten.",
    )

    def save():
        if app.busy:
            messagebox.showinfo("Even wachten", "Wacht tot de huidige verwerking klaar is.")
            return
        try:
            changes = {k: v.get() for k, v in values.items()}
            for key in (
                "summary_minutes",
                "sync_minutes",
                "font_size",
                "message_font_size",
                "retention_days",
            ):
                changes[key] = int(changes[key])
            changes["theme"] = theme_ids[changes["theme"]]
            changes["density"] = density_ids[changes["density"]]
            for key in (
                "important_people",
                "important_servers",
                "important_channels",
                "important_topics",
            ):
                changes[key] = [v.strip() for v in changes[key].split(",") if v.strip()]
            for key in ("important_people", "important_servers", "important_channels"):
                for ident in changes[key]:
                    snowflake(ident)
            if changes["user_id"]:
                snowflake(changes["user_id"])
            changes["external_consent"] = (
                changes["endpoint"] if changes["provider"] == "external" and consent.get() else ""
            )
            if changes["provider"] != "extractive":
                summaries.validate_endpoint(
                    changes["provider"], changes["endpoint"], changes["external_consent"]
                )
                if not changes["model"].strip():
                    raise ValueError("Vul een beschikbaar model in.")
            if (
                changes["retention_days"] != config["retention_days"]
                and changes["retention_days"] > 0
            ):
                if not messagebox.askyesno(
                    "Bewaartermijn toepassen",
                    "Berichten ouder dan deze termijn worden lokaal verwijderd, ook bij volgende synchronisaties. Bestaande exports/back-ups blijven bestaan. Doorgaan?",
                    parent=top,
                ):
                    return
            if secret.get():
                app.vault.save("ai-" + summaries.digest(changes["endpoint"])[:32], secret.get())
            app.store.save_settings(changes)
            app.store.apply_retention()
            app.invalidate_summary_windows()
            app.apply_style()
            app.refresh()
            top.destroy()
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror("Instellingen niet opgeslagen", str(exc), parent=top)

    ttk.Button(frame, text="Instellingen opslaan", command=save).pack(anchor="e", pady=12)


def privacy_panel(app):
    if app.busy:
        messagebox.showinfo(
            "Even wachten", "Privacy wijzigen kan zodra de lopende verwerking klaar is."
        )
        return
    top, frame = window(app, "Privacy en gegevens")
    ttk.Label(
        frame,
        text="Uitgesloten tekst gaat niet naar samenvattingen op enig niveau.\nBij een wijziging worden bestaande overzichten en correcties gewist om doorlekken te voorkomen.\nBerichten blijven wel beschikbaar in Alles.",
        wraplength=780,
    ).pack(anchor="w")
    tree = ttk.Treeview(frame, columns=("target",), show="tree headings")
    tree.heading("#0", text="Niveau")
    tree.heading("target", text="ID")
    tree.pack(fill="both", expand=True, pady=12)

    def refresh():
        tree.delete(*tree.get_children())
        for i, row in enumerate(app.store.exclusions()):
            tree.insert("", "end", iid=str(i), text=row["scope"], values=(row["target"],))

    scope = tk.StringVar(value="personal")
    target = tk.StringVar(value="*")
    ttk.Combobox(
        frame,
        textvariable=scope,
        values=["personal", "source", "server", "channel", "conversation", "message"],
        state="readonly",
    ).pack(fill="x")
    ttk.Entry(frame, textvariable=target).pack(fill="x", pady=8)

    def exclude():
        if app.busy:
            return
        app.store.exclude(scope.get(), "*" if scope.get() == "personal" else target.get().strip())
        app.invalidate_summary_windows()
        refresh()

    def include():
        if tree.selection() and not app.busy:
            row = tree.item(tree.selection()[0])
            app.store.exclude(row["text"], str(row["values"][0]), False)
            app.invalidate_summary_windows()
            refresh()

    ttk.Button(frame, text="Uitsluiten van alle samenvattingen", command=exclude).pack(anchor="w")
    ttk.Button(frame, text="Geselecteerde uitsluiting opheffen", command=include).pack(
        anchor="w", pady=6
    )

    def backup():
        path = filedialog.asksaveasfilename(
            defaultextension=".sqlite", filetypes=[("SQLite back-up", "*.sqlite")], parent=top
        )
        if path:
            try:
                app.store.backup(path)
                messagebox.showinfo(
                    "Back-up gereed",
                    "Lokale database gekopieerd. Geheimen zijn niet inbegrepen.",
                    parent=top,
                )
            except (ValueError, OSError) as exc:
                messagebox.showerror("Back-up mislukt", str(exc), parent=top)

    ttk.Button(frame, text="Databaseback-up maken…", command=backup).pack(anchor="w")
    ttk.Label(
        frame,
        text="Berichten: lokale SQLite onder je Windows-account, niet apart versleuteld.\nTokens: Windows DPAPI. Geen telemetrie. Exports en back-ups vallen buiten bewaartermijnen.",
        wraplength=780,
    ).pack(anchor="w", pady=12)
    refresh()


def summaries_panel(app):
    top, frame = window(app, "Contextoverzichten", "1050x780")
    app.summary_windows.append(top)
    ttk.Label(
        frame,
        text="Bronfragmenten en AI-interpretaties blijven herkenbaar. Open een bron om een claim te controleren.",
        wraplength=980,
    ).pack(anchor="w")
    selectors = ttk.Frame(frame)
    selectors.pack(fill="x", pady=8)
    options = tk.StringVar()
    combo = ttk.Combobox(selectors, textvariable=options, state="readonly", width=60)
    combo.pack(side="left", fill="x", expand=True)
    meta = tk.StringVar()
    ttk.Label(frame, textvariable=meta, wraplength=980).pack(anchor="w")
    tree = ttk.Treeview(frame, columns=("text",), show="tree headings")
    tree.heading("#0", text="Soort")
    tree.heading("text", text="Onderdeel")
    tree.column("#0", width=140)
    tree.column("text", width=750)
    tree.pack(fill="both", expand=True, pady=8)
    evidence = tk.Text(
        frame, height=9, wrap="word", font=("Segoe UI", app.store.settings()["message_font_size"])
    )
    evidence.pack(fill="x")
    evidence.configure(state="disabled")
    app.apply_native_style(evidence)
    choices, entries, refs = {}, [], []

    def refresh():
        choices.clear()
        for row in app.store.db.execute("SELECT * FROM summaries ORDER BY scope,target"):
            label = row["scope"] + " · " + row["target"]
            choices[label] = dict(row)
        combo["values"] = list(choices)
        if options.get() not in choices:
            options.set(next(iter(choices), ""))
        show()

    def show(_=None):
        tree.delete(*tree.get_children())
        entries.clear()
        refs.clear()
        evidence.configure(state="normal")
        evidence.delete("1.0", "end")
        evidence.configure(state="disabled")
        row = choices.get(options.get())
        if not row:
            meta.set("Nog geen overzichten. Kies Verversen om toegestane berichten te verwerken.")
            return
        body = json.loads(row["body"])
        available = app.store.summary_records()
        allowed = {
            r["id"]: summaries.digest(
                {
                    k: r[k]
                    for k in (
                        "content",
                        "author",
                        "timestamp",
                        "edited_at",
                        "channel",
                        "guild",
                        "parent_channel",
                    )
                }
            )
            for r in available
        }
        if any(allowed.get(k) != v for k, v in body["source_hashes"].items()):
            meta.set(
                "Bronbereik of privacy gewijzigd. Ververs eerst; oude inhoud wordt niet getoond."
            )
            evidence.configure(state="normal")
            evidence.delete("1.0", "end")
            evidence.configure(state="disabled")
            return
        entries.extend(body["entries"])
        scope_keys = {
            "conversation": lambda r: r["conversation"],
            "channel": lambda r: r["parent_channel"] or r["channel"],
            "server": lambda r: r["guild"] or "unknown",
            "personal": lambda r: "*",
        }
        current_ids = {r["id"] for r in available if scope_keys[row["scope"]](r) == row["target"]}
        pending = len(current_ids - set(body["source_hashes"]))
        meta.set(
            f"{row['model']} · versie {row['version']} · {row['generated_at']}\n{body['coverage']}\nNog niet meegenomen: {pending} nieuw beschikbare berichten.\nWijzigingen: {body.get('changes', {})}. Onderliggende niveaus: {len(body.get('children', []))}.\nJouw correctie: {row['note'] or 'Geen'}"
        )
        for i, entry in enumerate(entries):
            tree.insert(
                "",
                "end",
                iid=str(i),
                text=entry["category"],
                values=(entry["text"].replace("\n", " ")[:180],),
            )

    def select(_=None):
        refs.clear()
        evidence.configure(state="normal")
        evidence.delete("1.0", "end")
        if tree.selection():
            entry = entries[int(tree.selection()[0])]
            evidence.insert("end", entry["basis"] + "\n\n" + entry["text"] + "\n\nBronnen:\n")
            for citation in entry["citations"]:
                row = app.store.get(citation["id"])
                if row:
                    refs.append(row)
                    evidence.insert(
                        "end",
                        row["author"]
                        + " · "
                        + row["timestamp"]
                        + " · "
                        + row["channel_name"]
                        + "\n"
                        + citation["quote"]
                        + "\n"
                        + (deep_link(row) or "Originele link niet beschikbaar")
                        + "\n\n",
                    )
        evidence.configure(state="disabled")

    combo.bind("<<ComboboxSelected>>", show)
    tree.bind("<<TreeviewSelect>>", select)

    def open_sources():
        if not refs:
            return
        dialog, body = window(app, "Bronberichten", "700x480")
        for row in refs:
            ttk.Button(
                body,
                text=row["author"] + " · " + row["channel_name"] + " · " + row["id"],
                command=lambda r=row: app.show_context(r),
            ).pack(fill="x", pady=4)

    def correction():
        row = choices.get(options.get())
        if row and not app.busy:
            note = simpledialog.askstring(
                "Correctie",
                "Jouw correctie of toelichting (apart van bron en AI):",
                initialvalue=row["note"],
                parent=top,
            )
            if note is not None:
                summaries.correct(app.store, row["scope"], row["target"], note)
                refresh()

    def children():
        row = choices.get(options.get())
        if not row:
            return
        _, body = window(app, "Onderliggende overzichten", "650x420")
        for child in json.loads(row["body"]).get("children", []):
            label = child["scope"] + " · " + child["target"]

            def choose(value=label):
                options.set(value)
                show()
                top.lift()

            ttk.Button(body, text=label, command=choose).pack(fill="x", pady=4)

    def regenerate(force=False):
        top.destroy()
        app.refresh_summaries(force=force)

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=12)
    for label, command in [
        ("Verversen", regenerate),
        ("Volledig herberekenen", lambda: regenerate(True)),
        ("Bronnen openen", open_sources),
        ("Onderliggende niveaus", children),
        ("Corrigeren", correction),
    ]:
        ttk.Button(buttons, text=label, command=command).pack(side="left", padx=4)

    def delete():
        if not app.busy and messagebox.askyesno(
            "Overzichten wissen",
            "Alle lokale samenvattingen en correcties wissen? Berichten blijven bestaan.",
            parent=top,
        ):
            with app.store.db:
                app.store.clear_summaries()
            refresh()

    ttk.Button(buttons, text="Overzichten wissen", command=delete).pack(side="left", padx=4)
    refresh()


def notifications_panel(app):
    top, frame = window(app, "Meldingen")
    rows = app.store.db.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 200").fetchall()
    read_text(
        frame,
        "\n\n".join(r["created_at"] + " · " + r["text"] for r in rows) or "Geen meldingen.",
        app=app,
    )

    def read():
        with app.store.db:
            app.store.db.execute("UPDATE notifications SET read=1")
        top.destroy()
        app.refresh()

    ttk.Button(frame, text="Alles als gelezen markeren", command=read).pack(anchor="e")
