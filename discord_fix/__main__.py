import json
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import panels, summaries
from .appearance import palette_for
from .connector import DiscordBot, apply_sync, sync_failure
from .importer import deep_link, read_package
from .store import Store
from .vault import Vault
from .widgets import Scrollable, fit_window


class App:
    def __init__(self, root, store):
        self.root, self.store = root, store
        self.rows, self.selected = {}, None
        self.busy = False
        self.closed = False
        self.cancelled = threading.Event()
        self.vault = Vault(Path(store.path).parent / "secrets")
        self.last_sync = self.last_summary = 0
        self.page = 0
        self.last_filter = None
        self.summary_windows = []
        self.dashboard_server = None
        self._column_resize_pending = False
        root.title("Discord Fix — lokaal overzicht")
        fit_window(root, "1180x900", minimum=(900, 720))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 11))
        style.configure("Treeview", rowheight=34)
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        scrollable = Scrollable(root)
        scrollable.pack(fill="both", expand=True)
        main = scrollable.content
        ttk.Label(main, text="Discord Fix", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Rust in je gesprekken. Jij bepaalt wat aandacht krijgt.").pack(
            anchor="w", pady=(0, 12)
        )
        self.coverage = tk.StringVar()
        ttk.Label(main, textvariable=self.coverage, wraplength=1050).pack(anchor="w")
        tools = ttk.Frame(main)
        tools.pack(fill="x", pady=8)
        for label, command in [
            ("Browserdashboard", self.open_web_dashboard),
            ("Bronnen", lambda: panels.sources_panel(self)),
            ("Contextoverzichten", lambda: panels.summaries_panel(self)),
            ("Privacy", lambda: panels.privacy_panel(self)),
            ("Instellingen", lambda: panels.settings_panel(self)),
            ("Meldingen", lambda: panels.notifications_panel(self)),
        ]:
            ttk.Button(tools, text=label, command=command).pack(side="left", padx=(0, 6))
        self.focus = tk.BooleanVar()
        ttk.Checkbutton(
            tools, text="Focusmodus", variable=self.focus, command=self.focus_mode
        ).pack(side="left")
        self.metadata_tools = tools
        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=16)
        self.import_button = ttk.Button(
            bar, text="Discord-datapakket importeren…", command=self.import_data
        )
        self.import_button.pack(side="left")
        ttk.Button(bar, text="Lokale gegevens exporteren…", command=self.export).pack(
            side="left", padx=8
        )
        self.search = tk.StringVar()
        ttk.Label(bar, text="Zoeken:").pack(side="left", padx=(12, 4))
        entry = ttk.Entry(bar, textvariable=self.search)
        entry.pack(side="left", fill="x", expand=True)
        self.search_entry = entry
        self.fulltext = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Woorden", variable=self.fulltext, command=self.refresh).pack(
            side="left", padx=6
        )
        self.search.trace_add("write", lambda *_: self.refresh())
        self.view = tk.StringVar(value="Everything")
        nav = ttk.Frame(main)
        nav.pack(fill="x", pady=(0, 12))
        self.view_options = [
            ("Important Now", "Nu belangrijk"),
            ("Needs Reply", "Opvolgen"),
            ("Conversations", "Gesprekken"),
            ("Later", "Later"),
            ("Everything", "Alles"),
        ]
        for value, label in self.view_options:
            ttk.Radiobutton(
                nav, text=label, value=value, variable=self.view, command=self.refresh
            ).pack(side="left", padx=(0, 18))
        for index, (value, _) in enumerate(self.view_options, start=1):
            root.bind(
                f"<Control-Key-{index}>",
                lambda _event, selected=value: self.set_view(selected),
            )
        root.bind("<Control-f>", lambda _: entry.focus_set())
        root.bind("<Control-plus>", lambda _: self.adjust_text_size(1))
        root.bind("<Control-equal>", lambda _: self.adjust_text_size(1))
        root.bind("<Control-minus>", lambda _: self.adjust_text_size(-1))
        root.bind("<Control-0>", lambda _: self.adjust_text_size(0))
        root.bind("<F6>", self.cycle_primary_focus)
        self.status = tk.StringVar(
            value="Importeer een datapakket om te beginnen. Er staan geen voorbeeldberichten in je inbox."
        )
        ttk.Label(main, textvariable=self.status, wraplength=1000).pack(anchor="w", pady=(0, 8))
        table = ttk.Frame(main)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table,
            height=3,
            columns=("channel", "message", "state"),
            show="tree headings",
            selectmode="browse",
        )
        widths = self.store.settings()["column_widths"]
        for key, title, setting in [
            ("#0", "Datum", "date"),
            ("channel", "Kanaal", "channel"),
            ("message", "Bericht", "message"),
            ("state", "Status", "state"),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=widths[setting], minwidth=60, stretch=False)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(
            yscrollcommand=scroll.set,
            xscrollcommand=horizontal.set,
        )
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.bind("<ButtonPress-1>", self._column_resize_start, add="+")
        self.tree.bind("<ButtonRelease-1>", self._column_resize_end, add="+")
        pager = ttk.Frame(main)
        pager.pack(fill="x")
        ttk.Button(pager, text="Vorige 200", command=lambda: self.paginate(-1)).pack(side="left")
        ttk.Button(pager, text="Volgende 200", command=lambda: self.paginate(1)).pack(
            side="left", padx=8
        )
        self.page_label = tk.StringVar()
        ttk.Label(pager, textvariable=self.page_label).pack(side="left")
        self.detail = tk.Text(
            main,
            height=4,
            wrap="word",
            font=("Segoe UI", self.store.settings()["message_font_size"]),
            padx=12,
            pady=10,
        )
        self.detail.pack(fill="x", pady=12)
        self.detail.configure(state="disabled")
        actions = ttk.Frame(main)
        actions.pack(fill="x")
        self.buttons = []
        for index, (label, action) in enumerate(
            [
                ("Afhandelen", "complete"),
                ("Heropenen", "reopen"),
                ("Negeren", "dismiss"),
                ("Belangrijk aan/uit", "important"),
                ("Opvolgen aan/uit", "reply"),
                ("1 uur later", "later"),
                ("Kies uitstelmoment…", "choose_later"),
                ("Deadline instellen…", "deadline"),
                ("Automatische regels herstellen", "reset_rules"),
            ]
        ):
            button = ttk.Button(actions, text=label, command=lambda a=action: self.act(a))
            button.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 5), pady=2)
            actions.columnconfigure(index % 3, weight=1)
            self.buttons.append(button)
        self.open_button = ttk.Button(
            main, text="Origineel openen in Discord", command=self.open_original
        )
        self.open_button.pack(anchor="w", pady=(10, 0))
        more = ttk.Frame(main)
        more.pack(fill="x")
        ttk.Button(
            more,
            text="Volledige beschikbare context",
            command=lambda: self.show_context(self.rows.get(self.selected)),
        ).pack(side="left")
        ttk.Button(more, text="Bericht uitsluiten van AI", command=self.exclude_selected).pack(
            side="left", padx=8
        )
        ttk.Button(more, text="Deadline wissen", command=lambda: self.act("clear_deadline")).pack(
            side="left"
        )
        self.apply_style()
        self.refresh()
        self.timer = root.after(30000, self.tick)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def tick(self):
        if not self.busy:
            self.store.maintenance()
            if self.store.apply_retention():
                self.invalidate_summary_windows()
        self.refresh()
        settings = self.store.settings()
        if (
            not self.busy
            and settings["auto_sync"]
            and time.monotonic() - self.last_sync >= settings["sync_minutes"] * 60
        ):
            self.sync_sources(automatic=True)
        elif (
            not self.busy
            and settings["auto_summaries"]
            and time.monotonic() - self.last_summary >= settings["summary_minutes"] * 60
        ):
            self.refresh_summaries(automatic=True)
        self.timer = self.root.after(30000, self.tick)

    def refresh(self):
        previous = self.selected
        self.tree.delete(*self.tree.get_children())
        filters = (self.view.get(), self.search.get())
        if (filters, self.fulltext.get()) != self.last_filter:
            self.page = 0
            self.last_filter = (filters, self.fulltext.get())
        rows = self.store.query(
            *filters, limit=200, offset=self.page * 200, fulltext=self.fulltext.get()
        )
        self.page_label.set(f"Pagina {self.page + 1} · maximaal 200 berichten per pagina")
        self.rows = {r["id"]: r for r in rows}
        groups = {}
        for row in rows:
            parent = ""
            if self.view.get() == "Conversations":
                parent = "channel:" + row["conversation"]
                if parent not in groups:
                    self.tree.insert("", "end", iid=parent, text=row["channel_name"], open=True)
                    groups[parent] = True
            state = {
                "open": "Open",
                "later": "Uitgesteld",
                "complete": "Afgehandeld",
                "dismissed": "Genegeerd",
            }[row["state"]]
            if row["important"]:
                state += " · belangrijk"
            if row["deleted"]:
                state = "Verwijderd bij bron"
            self.tree.insert(
                parent,
                "end",
                iid=row["id"],
                text=row["timestamp"][:16].replace("T", " ") + " UTC",
                values=(row["channel_name"], row["content"].replace("\n", " ")[:180], state),
            )
        if not self.busy:
            self.status.set(
                f"{len(rows)} berichten op deze pagina. Kies een bericht voor uitleg en acties."
                if rows
                else "Geen berichten hier. Kies Alles, een vorige pagina, of importeer een datapakket."
            )
        sources = self.store.sources()
        unread = self.store.db.execute(
            "SELECT count(*) FROM notifications WHERE read=0"
        ).fetchone()[0]
        self.coverage.set(
            f"{len(sources)} bronnen · {unread} nieuwe meldingen · AI: {self.store.settings()['provider']}\nImports: eigen verzonden tekst. Bot: alleen gekozen kanalen; ontvangst en dekking staan bij Bronnen."
        )
        if previous in self.rows:
            self.tree.selection_set(previous)
        self.select()

    def select(self, _=None):
        selection = self.tree.selection()
        self.selected = selection[0] if selection and selection[0] in self.rows else None
        row = self.rows.get(self.selected)
        for button in self.buttons:
            button.configure(state="normal" if row else "disabled")
        self.open_button.configure(state="normal" if row and deep_link(row) else "disabled")
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if row:
            reason = " ".join(json.loads(row["reason"]))
            source = next((s for s in self.store.sources() if s["id"] == row["source_id"]), {})
            context = (
                ""
                if self.focus.get()
                else f"Auteur: {row['author']} · Kanaal: {row['channel_name']}\nBron: {source.get('name', row['source_id'])} · {source.get('status', 'onbekend')} · Ontvangen: {row['imported_at']}\n"
            )
            self.detail.insert(
                "end",
                (row["content"] if not row["deleted"] else "[Verwijderd bij de bron]")
                + "\n\n"
                + context
                + f"{reason} Opvolgen: {'ja' if row['reply'] else 'nee'}.\n"
                + (f"Keert terug: {row['until']}\n" if row["until"] else "")
                + (f"Deadline: {row['deadline']}\n" if row["deadline"] else "")
                + "\n\nBijlagen (niet gedownload): "
                + row["attachments"],
            )
        self.detail.configure(state="disabled")

    def act(self, action):
        if self.selected:
            until = (
                (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                if action == "later"
                else None
            )
            if action in ("choose_later", "deadline"):
                value = simpledialog.askstring(
                    "Kies tijdstip",
                    "Lokale datum en tijd: JJJJ-MM-DD UU:MM",
                    initialvalue=(datetime.now().astimezone() + timedelta(days=1)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                )
                if value is None:
                    return
                try:
                    until = datetime.strptime(value, "%Y-%m-%d %H:%M").astimezone().isoformat()
                except ValueError:
                    messagebox.showerror("Ongeldige datum", "Gebruik JJJJ-MM-DD UU:MM.")
                    return
                action = "later" if action == "choose_later" else action
            try:
                self.store.update(self.selected, action, until)
                self.refresh()
            except ValueError as exc:
                messagebox.showerror("Actie mislukt", str(exc))

    def open_original(self):
        if self.selected:
            url = deep_link(self.rows[self.selected])
            if url:
                webbrowser.open(url)

    def import_data(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[("Discord-datapakket", "*.zip")])
        if not path:
            return

        def finish(payload):
            records, errors = payload
            try:
                import hashlib

                source_id = (
                    "import-" + hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:20]
                )
                self.store.source(
                    source_id,
                    name=Path(path).name,
                    detail=f"Alleen eigen verzonden berichten. {len(errors)} importfouten.",
                )
                self.store.ingest(records, source_id)
                self.store.apply_retention()
                self.invalidate_summary_windows()
            except Exception as exc:
                messagebox.showerror("Opslaan mislukt", str(exc))
                return
            self.view.set("Everything")
            self.refresh()
            messagebox.showinfo(
                "Import voltooid",
                f"{len(records)} geldige records verwerkt (herimport werkt bestaande berichten bij).\n{len(errors)} fouten.\n"
                + "\n".join(errors[:12]),
            )
            if errors:
                _, frame = panels.window(self, "Volledig importverslag")
                panels.read_text(frame, "\n".join(errors), app=self)

        self.run_job("Datapakket wordt lokaal gelezen…", lambda: read_package(path), finish)

    def export(self):
        import json

        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")]
        )
        if path:
            try:
                Path(path).write_text(
                    json.dumps(self.store.export_data(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                messagebox.showinfo(
                    "Export voltooid", "Berichten en persoonlijke statussen zijn geëxporteerd."
                )
            except OSError as exc:
                messagebox.showerror("Export mislukt", str(exc))

    def run_job(self, label, work, done, failed=None, automatic=False):
        if self.busy:
            return
        self.busy = True
        self.import_button.configure(state="disabled")
        self.status.set(label)
        result = queue.Queue()

        def execute():
            try:
                result.put((work(), None))
            except Exception as exc:
                result.put((None, exc))

        threading.Thread(target=execute, daemon=True).start()

        def poll():
            if self.closed:
                return
            try:
                value, error = result.get_nowait()
            except queue.Empty:
                self.root.after(100, poll)
                return
            self.busy = False
            self.import_button.configure(state="normal")
            try:
                if error:
                    if failed:
                        failed(error)
                    with self.store.db:
                        self.store.notify(
                            "job-error:" + type(error).__name__ + label,
                            "summary",
                            "Verwerking mislukt: "
                            + str(error)
                            + ". Automatische taken proberen het bij het volgende interval opnieuw.",
                        )
                    if not automatic:
                        messagebox.showerror("Verwerking mislukt", str(error))
                    self.status.set("Verwerking mislukt: " + str(error))
                else:
                    done(value)
            except Exception as exc:
                messagebox.showerror("Resultaat niet opgeslagen", str(exc))
            self.refresh()

        self.root.after(100, poll)

    def sync_sources(self, only=None, automatic=False):
        if self.busy:
            return
        self.last_sync = time.monotonic()
        sources = [
            s
            for s in self.store.sources()
            if s["kind"] == "bot"
            and s["status"] != "disconnected"
            and (not only or s["id"] == only)
        ]
        sources = [
            s
            for s in sources
            if not s["next_sync"]
            or datetime.fromisoformat(s["next_sync"]) <= datetime.now(timezone.utc)
        ]
        if not sources:
            if not automatic:
                messagebox.showinfo(
                    "Geen bron beschikbaar",
                    "Voeg een botbron toe of wacht tot de rate-limitpauze voorbij is.",
                )
            return
        try:
            tokens = {s["id"]: self.vault.read(s["id"]) for s in sources}
        except (RuntimeError, OSError) as exc:
            with self.store.db:
                self.store.notify(
                    "vault-error",
                    "source",
                    "Botgeheim kon niet worden gelezen. Koppel de bot opnieuw.",
                )
            if not automatic:
                messagebox.showerror("Geheim niet beschikbaar", str(exc))
            return

        def work():
            results = []
            for source in sources:
                if self.cancelled.is_set():
                    break
                try:
                    results.append(
                        (
                            source,
                            DiscordBot(tokens[source["id"]], cancelled=self.cancelled).collect(
                                source["config"]["channels"]
                            ),
                            None,
                        )
                    )
                except Exception as exc:
                    results.append((source, None, exc))
            return results

        def finish(results):
            self.invalidate_summary_windows()
            for source, result, error in results:
                if error:
                    sync_failure(self.store, source, error)
                else:
                    apply_sync(self.store, source, result)
            self.store.apply_retention()
            self.refresh()
            if not automatic:
                panels.sources_panel(self)

        self.run_job("Officiële Discord-bronnen worden gelezen…", work, finish, automatic=automatic)

    def refresh_summaries(self, force=False, automatic=False):
        if self.busy:
            return
        self.last_summary = time.monotonic()
        try:
            provider = summaries.create_provider(self.store.settings(), self.vault)
            snapshot = summaries.prepare(self.store)
        except (ValueError, RuntimeError, OSError) as exc:
            if not automatic:
                messagebox.showerror("Provider niet beschikbaar", str(exc))
            return

        def finish(outputs):
            summaries.commit(self.store, snapshot, outputs)
            if not automatic:
                panels.summaries_panel(self)

        self.run_job(
            "Contextoverzichten worden bijgewerkt…",
            lambda: summaries.build(snapshot, provider, force, self.cancelled, automatic),
            finish,
            automatic=automatic,
        )

    def exclude_selected(self):
        if self.selected and not self.busy:
            self.store.exclude("message", self.selected)
            self.invalidate_summary_windows()
            self.status.set("Bericht uitgesloten; afgeleide overzichten gewist.")

    def paginate(self, direction):
        self.page = max(0, self.page + direction)
        self.refresh()

    def set_view(self, value):
        self.view.set(value)
        self.refresh()
        return "break"

    def adjust_text_size(self, direction):
        settings = self.store.settings()
        if direction:
            control_size = min(24, max(9, settings["font_size"] + direction))
            message_size = min(32, max(9, settings["message_font_size"] + direction))
        else:
            control_size = message_size = 11
        self.store.save_settings({"font_size": control_size, "message_font_size": message_size})
        self.apply_style()
        self.refresh()
        return "break"

    def cycle_primary_focus(self, _event=None):
        primary = (self.search_entry, self.tree, self.detail)
        try:
            index = primary.index(self.root.focus_get())
        except ValueError:
            index = -1
        primary[(index + 1) % len(primary)].focus_set()
        return "break"

    def _column_resize_start(self, event):
        self._column_resize_pending = self.tree.identify_region(event.x, event.y) == "separator"

    def _column_resize_end(self, _event):
        if not self._column_resize_pending:
            return
        self._column_resize_pending = False
        widths = {
            setting: int(self.tree.column(column, "width"))
            for column, setting in (
                ("#0", "date"),
                ("channel", "channel"),
                ("message", "message"),
                ("state", "state"),
            )
        }
        try:
            self.store.save_settings({"column_widths": widths})
        except ValueError as exc:
            self.status.set(str(exc))

    def focus_mode(self):
        self.tree.configure(
            displaycolumns=("message", "state")
            if self.focus.get()
            else ("channel", "message", "state")
        )
        self.select()

    def apply_style(self):
        settings = self.store.settings()
        size = settings["font_size"]
        message_size = settings["message_font_size"]
        density_padding = {"compact": 0, "comfortable": 12, "spacious": 24}[settings["density"]]
        self.palette = palette_for(settings["theme"], settings["high_contrast"])
        background = self.palette["background"]
        surface = self.palette["surface"]
        foreground = self.palette["foreground"]
        muted = self.palette["muted"]
        accent = self.palette["accent"]
        accent_text = self.palette["accent_text"]
        style = ttk.Style(self.root)
        style.configure(".", font=("Segoe UI", size), background=background, foreground=foreground)
        style.configure("TFrame", background=background)
        style.configure("TLabel", background=background, foreground=foreground)
        style.configure(
            "TButton",
            background=surface,
            foreground=foreground,
            bordercolor=foreground,
            focuscolor=accent,
        )
        style.map(
            "TButton",
            background=[("disabled", background), ("pressed", accent), ("active", accent)],
            foreground=[("disabled", muted), ("pressed", accent_text), ("active", accent_text)],
        )
        for control in ("TCheckbutton", "TRadiobutton"):
            style.configure(
                control, background=background, foreground=foreground, focuscolor=accent
            )
            style.map(control, foreground=[("disabled", muted)])
        style.configure(
            "TEntry", fieldbackground=surface, foreground=foreground, bordercolor=foreground
        )
        style.map("TEntry", foreground=[("disabled", muted)])
        style.configure("TCombobox", fieldbackground=surface, foreground=foreground)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", surface), ("disabled", background)],
            foreground=[("readonly", foreground), ("disabled", muted)],
        )
        style.configure("TNotebook", background=background, bordercolor=foreground)
        style.configure("TNotebook.Tab", background=surface, foreground=foreground, padding=(10, 6))
        style.map(
            "TNotebook.Tab",
            background=[("selected", accent), ("active", surface)],
            foreground=[("selected", accent_text), ("active", foreground)],
        )
        style.configure(
            "Treeview",
            font=("Segoe UI", message_size),
            rowheight=message_size * 2 + density_padding,
            background=surface,
            foreground=foreground,
            fieldbackground=surface,
        )
        style.map(
            "Treeview",
            background=[("selected", accent)],
            foreground=[("selected", accent_text)],
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", size, "bold"),
            background=surface,
            foreground=foreground,
            relief="flat",
        )
        style.map(
            "Treeview.Heading",
            background=[("active", accent)],
            foreground=[("active", accent_text)],
        )
        style.configure(
            "TScrollbar",
            background=accent,
            troughcolor=background,
            bordercolor=foreground,
            arrowcolor=foreground,
        )
        style.configure("Title.TLabel", font=("Segoe UI", max(18, size * 2), "bold"))
        self.root.configure(background=background)
        self.detail.configure(
            font=("Segoe UI", message_size),
            background=surface,
            foreground=foreground,
            insertbackground=foreground,
            selectbackground=accent,
            selectforeground=accent_text,
        )
        self._apply_native_palette(self.root)

    def apply_native_style(self, widget):
        if not hasattr(self, "palette"):
            return
        widget.configure(
            font=("Segoe UI", self.store.settings()["message_font_size"]),
            background=self.palette["surface"],
            foreground=self.palette["foreground"],
            insertbackground=self.palette["foreground"],
            selectbackground=self.palette["accent"],
            selectforeground=self.palette["accent_text"],
        )

    def _apply_native_palette(self, widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Canvas):
                child.configure(background=self.palette["background"])
            elif isinstance(child, tk.Text):
                self.apply_native_style(child)
            elif isinstance(child, tk.Toplevel):
                child.configure(background=self.palette["background"])
            self._apply_native_palette(child)

    def show_context(self, row):
        if not row:
            return
        _, frame = panels.window(self, "Beschikbare gesprekscontext", "900x720")
        data = self.store.query(channel=row["conversation"])
        panels.read_text(
            frame,
            "\n\n".join(
                r["author"]
                + " · "
                + r["timestamp"]
                + "\n"
                + ("[Verwijderd bij bron]" if r["deleted"] else r["content"])
                for r in reversed(data)
            ),
            app=self,
        )
        link = deep_link(row)
        if link:
            ttk.Button(
                frame,
                text="Geselecteerd origineel openen in Discord",
                command=lambda: webbrowser.open(link),
            ).pack(anchor="w")

    def close(self):
        self.closed = True
        self.cancelled.set()
        self.root.after_cancel(self.timer)
        if self.dashboard_server:
            self.dashboard_server.stop()
        self.root.destroy()

    def open_web_dashboard(self):
        if not getattr(self, "dashboard_server", None):
            from .web_dashboard import DashboardServer

            self.dashboard_server = DashboardServer(self.store.path)
        url = self.dashboard_server.start()
        opened = webbrowser.open(url)
        self.status.set(
            "Alleen-lezen browserdashboard geopend op deze computer. "
            if opened
            else f"Browserdashboard: {url}"
        )
        return url

    def invalidate_summary_windows(self):
        for window in self.summary_windows:
            if window.winfo_exists():
                window.destroy()
        self.summary_windows.clear()


def main():
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from .diagnostics import run

        raise SystemExit(run(sys.argv[2]))
    from .instance import InstanceLock

    directory = (
        Path(os.environ["DISCORD_FIX_DATA_DIR"])
        if os.environ.get("DISCORD_FIX_DATA_DIR")
        else Path(os.environ.get("LOCALAPPDATA", Path.cwd() / "data")) / "DiscordFix"
    )
    directory.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    try:
        lock = InstanceLock(directory / "instance.lock")
    except RuntimeError as exc:
        root.withdraw()
        messagebox.showinfo("Discord Fix", str(exc))
        root.destroy()
        return
    try:
        store = Store(directory / "discord-fix.sqlite")
        try:
            App(root, store)
            root.mainloop()
        finally:
            store.db.close()
    finally:
        lock.close()


if __name__ == "__main__":
    main()
