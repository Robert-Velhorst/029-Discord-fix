"""Scrollable desktop content with keyboard focus visibility."""

import tkinter as tk
from tkinter import ttk


def fit_window(window, requested, minimum=(640, 480)):
    """Size and center a window inside the available screen area."""
    width, height = (int(value) for value in requested.lower().split("x", 1))
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    width = min(width, max(320, screen_width - 80))
    height = min(height, max(240, screen_height - 96))
    window.minsize(min(minimum[0], width), min(minimum[1], height))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class Scrollable(ttk.Frame):
    def __init__(self, parent, padding=16):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = ttk.Frame(self.canvas, padding=padding)
        self.item = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self.resize)
        self.canvas.bind("<Configure>", self.resize)
        self.bind("<Map>", lambda _: self.after_idle(self.bind_focus))
        self.canvas.bind(
            "<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units")
        )

    def resize(self, _=None):
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth())
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self.item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def bind_focus(self):
        def walk(widget):
            widget.bind("<FocusIn>", self.reveal, add="+")
            for child in widget.winfo_children():
                walk(child)

        walk(self.content)

    def reveal(self, event):
        widget = event.widget
        if not widget.winfo_ismapped():
            return
        top = widget.winfo_rooty() - self.canvas.winfo_rooty()
        height = self.content.winfo_height()
        current = self.canvas.canvasy(0)
        if top < 0:
            self.canvas.yview_moveto(max(0, (current + top) / height))
        elif top + widget.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_moveto(
                (current + top + widget.winfo_height() - self.canvas.winfo_height()) / height
            )
