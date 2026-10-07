#!/usr/bin/env python3
"""Транскрибатор (Tk-версия для старых Mac): видео/аудио -> Markdown через AssemblyAI."""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk

import core

CFG = Path.home() / ".transcriber_tk.json"
BG, PANEL, LINE = "#17181a", "#1f2124", "#2c2f33"
FG, MUTED, ACCENT = "#e8e6e1", "#8d9096", "#d9a441"
GREEN, RED = "#7cc48a", "#e5736b"

try:  # перетаскивание файлов, если библиотека доступна
    from tkinterdnd2 import DND_FILES, TkinterDnD
    Root = TkinterDnD.Tk
except Exception:  # noqa: BLE001
    DND_FILES, Root = None, tk.Tk


def load_cfg():
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def open_path(p):
    p = str(p)
    if sys.platform == "darwin":
        subprocess.Popen(["open", p])
    elif sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", p])


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.q = queue.Queue()
        self.items = {}          # iid -> путь
        self.results = {}        # iid -> .md
        self.pending = []
        self.busy = False
        self.cancel = False

        root.title("Транскрибатор")
        root.geometry("760x760")
        root.minsize(680, 640)
        root.configure(bg=BG)
        self._style()

        main = ttk.Frame(root, style="Bg.TFrame", padding=(26, 22))
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Транскрибатор", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Видео и аудио → текст в Markdown · AssemblyAI",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 14))

        # зона файлов
        self.drop = tk.Frame(main, bg="#1b1d1f", highlightthickness=1,
                             highlightbackground="#3a3e43", highlightcolor=ACCENT)
        self.drop.pack(fill="x")
        tk.Label(self.drop, text="Перетащите видео или аудио сюда" if DND_FILES else
                 "Добавьте видео или аудио", bg="#1b1d1f", fg=FG,
                 font=("Helvetica", 14)).pack(pady=(22, 2))
        tk.Label(self.drop, text="mp4, mkv, mov, mp3, wav, m4a, ogg, flac…",
                 bg="#1b1d1f", fg=MUTED, font=("Helvetica", 11)).pack()
        ttk.Button(self.drop, text="Выбрать файлы", command=self.pick).pack(pady=(10, 22))
        if DND_FILES:
            for w in (self.drop, *self.drop.winfo_children()):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)

        # настройки
        panel = tk.Frame(main, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        panel.pack(fill="x", pady=14)
        inner = ttk.Frame(panel, style="Panel.TFrame", padding=14)
        inner.pack(fill="x")

        ttk.Label(inner, text="API-КЛЮЧ", style="Sec.TLabel").grid(row=0, column=0, sticky="w")
        self.key = tk.StringVar(value=self.cfg.get("key", ""))
        e = ttk.Entry(inner, textvariable=self.key, show="•")
        e.grid(row=1, column=0, sticky="ew", pady=(4, 10), ipady=3)
        ttk.Button(inner, text="Получить ключ",
                   command=lambda: webbrowser.open(core.KEY_URL)).grid(row=1, column=1, padx=(8, 0), pady=(4, 10))

        ttk.Label(inner, text="ПАПКА ДЛЯ РЕЗУЛЬТАТОВ", style="Sec.TLabel").grid(row=2, column=0, sticky="w")
        self.folder = tk.StringVar(value=self.cfg.get("folder", str(Path.home() / "Transcripts")))
        ttk.Entry(inner, textvariable=self.folder).grid(row=3, column=0, sticky="ew", pady=(4, 10), ipady=3)
        bf = ttk.Frame(inner, style="Panel.TFrame")
        bf.grid(row=3, column=1, padx=(8, 0), pady=(4, 10))
        ttk.Button(bf, text="Изменить…", command=self.choose_folder).pack(side="left")
        ttk.Button(bf, text="Открыть", command=self.open_folder).pack(side="left", padx=(6, 0))

        opts = ttk.Frame(inner, style="Panel.TFrame")
        opts.grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Label(opts, text="Язык", style="P.TLabel").pack(side="left")
        self.lang = ttk.Combobox(opts, state="readonly", width=24, values=[n for n, _ in core.LANGS])
        self.lang.current(int(self.cfg.get("lang_idx", 0)))
        self.lang.pack(side="left", padx=(8, 16))
        self.spk = tk.BooleanVar(value=self.cfg.get("spk", False))
        self.stamps = tk.BooleanVar(value=self.cfg.get("stamps", True))
        ttk.Checkbutton(opts, text="Разделять по спикерам", variable=self.spk).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(opts, text="Таймкоды", variable=self.stamps).pack(side="left")
        inner.columnconfigure(0, weight=1)

        # очередь
        hdr = ttk.Frame(main, style="Bg.TFrame")
        hdr.pack(fill="x")
        ttk.Label(hdr, text="ОЧЕРЕДЬ", style="Sec.TLabel", background=BG).pack(side="left")
        ttk.Button(hdr, text="Очистить завершённые", command=self.clear_done).pack(side="right")

        lf = ttk.Frame(main, style="Bg.TFrame")
        lf.pack(fill="both", expand=True, pady=(8, 10))
        self.tree = ttk.Treeview(lf, columns=("state",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Файл", anchor="w")
        self.tree.heading("state", text="Статус", anchor="w")
        self.tree.column("#0", width=420, stretch=True)
        self.tree.column("state", width=220, stretch=False)
        self.tree.tag_configure("done", foreground=GREEN)
        self.tree.tag_configure("err", foreground=RED)
        self.tree.tag_configure("work", foreground=ACCENT)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.show_result)

        self.start = ttk.Button(main, text="Транскрибировать", style="Accent.TButton", command=self.go)
        self.start.pack(fill="x", ipady=6)
        self.note = ttk.Label(main, text="", style="Muted.TLabel")
        self.note.pack(anchor="w", pady=(8, 0))

        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(150, self.poll)

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground="#17181a",
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, font=("Helvetica", 12))
        s.configure("Bg.TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("Title.TLabel", background=BG, font=("Helvetica", 20, "bold"))
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("Sec.TLabel", background=PANEL, foreground=MUTED, font=("Helvetica", 10, "bold"))
        s.configure("P.TLabel", background=PANEL)
        s.configure("TButton", background="#2a2d31", foreground=FG, padding=(12, 6), borderwidth=1, focusthickness=0)
        s.map("TButton", background=[("active", "#32363b"), ("disabled", "#222426")],
              foreground=[("disabled", "#5d6066")])
        s.configure("Accent.TButton", background=ACCENT, foreground="#17181a", font=("Helvetica", 13, "bold"))
        s.map("Accent.TButton", background=[("active", "#e6b556"), ("disabled", "#3a3629")],
              foreground=[("disabled", "#7a7360")])
        s.configure("TEntry", insertcolor=FG, padding=4)
        s.configure("TCombobox", arrowcolor=FG, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", "#17181a")], foreground=[("readonly", FG)])
        root = self.root
        root.option_add("*TCombobox*Listbox.background", PANEL)
        root.option_add("*TCombobox*Listbox.foreground", FG)
        s.configure("TCheckbutton", background=PANEL, foreground=FG, indicatorbackground="#17181a",
                    indicatorforeground=ACCENT)
        s.map("TCheckbutton", background=[("active", PANEL)], indicatorbackground=[("selected", ACCENT)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=30,
                    borderwidth=0)
        s.configure("Treeview.Heading", background=BG, foreground=MUTED, borderwidth=0, font=("Helvetica", 10, "bold"))
        s.map("Treeview", background=[("selected", LINE)])
        s.configure("Vertical.TScrollbar", background="#2a2d31", troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)

    # --- действия ---
    def save_cfg(self):
        self.cfg.update(key=self.key.get().strip(), folder=self.folder.get().strip(),
                        lang_idx=self.lang.current(), spk=self.spk.get(), stamps=self.stamps.get())
        try:
            CFG.write_text(json.dumps(self.cfg, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def pick(self):
        paths = filedialog.askopenfilenames(title="Выберите файлы")
        self.add_files(paths)

    def on_drop(self, e):
        self.add_files(self.root.tk.splitlist(e.data))

    def add_files(self, paths):
        for p in paths:
            pp = Path(p)
            if pp.suffix.lower() not in core.MEDIA_EXT or not pp.is_file():
                continue
            iid = self.tree.insert("", "end", text=pp.name, values=("В очереди",))
            self.items[iid] = str(pp)
            self.pending.append(iid)
        self.refresh()

    def choose_folder(self):
        d = filedialog.askdirectory(title="Папка для результатов", initialdir=self.folder.get() or str(Path.home()))
        if d:
            self.folder.set(d)
            self.save_cfg()

    def open_folder(self):
        p = Path(self.folder.get()).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        open_path(p)

    def show_result(self, _e):
        sel = self.tree.selection()
        if sel and sel[0] in self.results:
            open_path(Path(self.results[sel[0]]).parent)

    def clear_done(self):
        for iid in list(self.tree.get_children()):
            tags = self.tree.item(iid, "tags")
            if "done" in tags or "err" in tags:
                self.tree.delete(iid)
                self.items.pop(iid, None)
        self.refresh()

    def refresh(self):
        self.start.state(["!disabled"] if self.pending and not self.busy else ["disabled"])
        self.note.config(text="Двойной клик по готовому файлу откроет папку с результатом."
                         if self.results else "")

    def set_state(self, iid, text, tag=""):
        if self.tree.exists(iid):
            self.tree.item(iid, values=(text,), tags=(tag,) if tag else ())

    def go(self):
        if not self.key.get().strip():
            self.note.config(text="Сначала вставьте API-ключ.", foreground=RED)
            return
        self.note.config(foreground=MUTED)
        self.save_cfg()
        self.next()

    def next(self):
        if not self.pending:
            self.busy = False
            self.start.config(text="Транскрибировать")
            self.refresh()
            return
        self.busy = True
        iid = self.pending.pop(0)
        self.start.config(text="Идёт обработка…")
        self.refresh()
        code = core.LANGS[self.lang.current()][1]
        args = (self.items[iid], Path(self.folder.get()).expanduser(), self.key.get().strip(),
                code, self.spk.get(), self.stamps.get())
        threading.Thread(target=self.work, args=(iid, args), daemon=True).start()

    def work(self, iid, args):
        try:
            out = core.transcribe(*args, lambda t, p: self.q.put(("p", iid, f"{t} {p}%")),
                                  lambda: self.cancel)
            self.q.put(("ok", iid, out))
        except Exception as e:  # noqa: BLE001
            self.q.put(("err", iid, str(e)))

    def poll(self):
        try:
            while True:
                kind, iid, val = self.q.get_nowait()
                if kind == "p":
                    self.set_state(iid, val, "work")
                elif kind == "ok":
                    self.results[iid] = val
                    self.set_state(iid, "Готово", "done")
                    self.next()
                else:
                    self.set_state(iid, val if len(val) < 60 else val[:57] + "…", "err")
                    self.next()
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def close(self):
        self.cancel = True
        self.save_cfg()
        self.root.destroy()


def main():
    root = Root()
    App(root)
    if "--smoke" in sys.argv:
        root.after(500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
