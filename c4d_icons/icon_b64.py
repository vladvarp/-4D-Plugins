#!/usr/bin/env python3
"""Окно с иконками из этой папки. Клик копирует base64 PNG в буфер обмена.

Строка уже в кавычках — её можно вставить вместо "вставте код иконки" в _ICON_B64.
"""
import base64
import os
import sys
import tkinter as tk
from tkinter import font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

BG = "#1b1d21"
PANEL = "#26292e"
PANEL_RGB = (38, 41, 46, 255)
FG = "#e6ebf0"
MUTED = "#8b95a3"
OK = "#50dc82"
COPIED = "#14323a"

THUMB = 96
CELL_W = 148


def _dpi():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def list_icons():
    found = []
    try:
        names = os.listdir(HERE)
    except OSError:
        return found
    for name in names:
        path = os.path.join(HERE, name)
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXT and os.path.isfile(path):
            found.append(path)
    found.sort(key=lambda p: os.path.basename(p).lower())
    return found


def file_to_b64_literal(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return '"' + data + '"'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Иконки → base64")
        self.configure(bg=BG)
        self.geometry("760x560")
        self.minsize(360, 280)

        self._photos = []
        self._cols = 1
        self._cards = []

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(
            header,
            text="Иконки c4d_icons",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left")
        tk.Button(
            header,
            text="Обновить",
            command=self.reload,
            bg=PANEL,
            fg=FG,
            activebackground="#32363c",
            activeforeground=FG,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        tk.Label(
            self,
            text='Клик по иконке копирует base64 в буфер — вставьте в _ICON_B64.',
            bg=BG,
            fg=MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=16)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        self.scroll = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_wheel)

        self.status = tk.Label(
            self,
            text="",
            bg="#14161a",
            fg=MUTED,
            anchor="w",
            padx=16,
            pady=8,
            font=("Segoe UI", 9),
        )
        self.status.pack(fill="x", side="bottom")
        self.reload()

    def _on_frame_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)
        cols = max(1, event.width // CELL_W)
        if cols != self._cols and self._cards:
            self._cols = cols
            self._place_cards()

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def reload(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self._photos.clear()
        self._cards.clear()

        paths = list_icons()
        if not paths:
            tk.Label(
                self.grid_frame,
                text="В папке нет изображений.\nПоложите PNG рядом с программой и нажмите «Обновить».",
                bg=BG,
                fg=MUTED,
                justify="left",
                font=("Segoe UI", 10),
            ).grid(row=0, column=0, sticky="w", padx=8, pady=12)
            self.status.configure(text=HERE, fg=MUTED)
            return

        name_font = tkfont.Font(family="Segoe UI", size=9)
        for path in paths:
            card = tk.Frame(self.grid_frame, bg=PANEL, cursor="hand2", padx=8, pady=8)
            photo = self._load_thumb(path)
            img_label = tk.Label(card, image=photo, bg=PANEL, cursor="hand2")
            img_label.pack()
            base = os.path.basename(path)
            shown = base if len(base) <= 18 else base[:16] + "…"
            name = tk.Label(
                card, text=shown, bg=PANEL, fg=FG, font=name_font, cursor="hand2",
            )
            name.pack(pady=(6, 0))
            for widget in (card, img_label, name):
                widget.bind("<Button-1>", lambda e, p=path, c=card: self.copy(p, c))
            self._cards.append(card)

        width = self.canvas.winfo_width()
        self._cols = max(1, (width if width > 1 else 760) // CELL_W)
        self._place_cards()
        self.status.configure(
            text="%d — клик копирует строку для _ICON_B64" % len(paths),
            fg=MUTED,
        )

    def _place_cards(self):
        for i, card in enumerate(self._cards):
            row, col = divmod(i, self._cols)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="n")

    def _load_thumb(self, path):
        photo = None
        try:
            from PIL import Image, ImageTk
            src = Image.open(path).convert("RGBA")
            src.thumbnail((THUMB - 8, THUMB - 8), Image.LANCZOS)
            plate = Image.new("RGBA", (THUMB, THUMB), PANEL_RGB)
            x = (THUMB - src.width) // 2
            y = (THUMB - src.height) // 2
            plate.alpha_composite(src, (x, y))
            photo = ImageTk.PhotoImage(plate)
        except Exception:
            try:
                photo = tk.PhotoImage(file=path)
                side = max(photo.width(), photo.height())
                if side > THUMB:
                    factor = max(1, side // THUMB)
                    photo = photo.subsample(factor, factor)
                elif side < THUMB // 2:
                    photo = photo.zoom(2, 2)
            except Exception:
                photo = tk.PhotoImage(width=THUMB, height=THUMB)
        self._photos.append(photo)
        return photo

    def copy(self, path, card):
        try:
            literal = file_to_b64_literal(path)
        except OSError as exc:
            self.status.configure(text="Не удалось прочитать файл: %s" % exc, fg="#ff6464")
            return
        self.clipboard_clear()
        self.clipboard_append(literal)
        self.update()
        self.status.configure(text="Скопировано: %s" % os.path.basename(path), fg=OK)
        self._paint(card, COPIED)
        self.after(700, lambda c=card: self._paint(c, PANEL))

    def _paint(self, card, color):
        if not card.winfo_exists():
            return
        card.configure(bg=color)
        for child in card.winfo_children():
            child.configure(bg=color)


def main():
    _dpi()
    App().mainloop()


if __name__ == "__main__":
    main()
