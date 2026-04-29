#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diary GUI (Tkinter)

Features
- Calendar date picker (tkcalendar)
- Daily markdown-like text saved as .txt under Desktop/Diary
- Search across all entries

Dependencies
- Python 3.9+
- tkcalendar: pip install tkcalendar

Run
  python diary_gui.py

Packaging (optional)
  pip install pyinstaller
  pyinstaller -F -w diary_gui.py
"""

from __future__ import annotations

import os
import sys
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from tkcalendar import Calendar
except Exception:
    Calendar = None  # type: ignore


APP_NAME = "日记本"
FOLDER_NAME = "Diary"
FILE_EXT = ".txt"
ENCODING = "utf-8"


def desktop_dir() -> Path:
    # Windows: USERPROFILE\Desktop; macOS/Linux usually have ~/Desktop
    home = Path.home()
    candidates = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        home / "Desktop",
    ]
    for c in candidates:
        if c and c.exists():
            return c
    return home


def diary_root() -> Path:
    return desktop_dir() / FOLDER_NAME


def entry_path(date_str: str) -> Path:
    # date_str: YYYY-MM-DD
    return diary_root() / f"{date_str}{FILE_EXT}"


def ensure_root() -> None:
    diary_root().mkdir(parents=True, exist_ok=True)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_date(date_str: str) -> str:
    date_str = date_str.strip()
    if DATE_RE.match(date_str):
        # validate
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    # try parse common formats
    for fmt in ("%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    raise ValueError("日期格式应为 YYYY-MM-DD")


def load_entry(date_str: str) -> str:
    p = entry_path(date_str)
    if not p.exists():
        return ""
    return p.read_text(encoding=ENCODING)


def save_entry(date_str: str, text: str) -> None:
    ensure_root()
    p = entry_path(date_str)
    p.write_text(text.rstrip() + "\n", encoding=ENCODING)


def list_entries() -> list[Path]:
    root = diary_root()
    if not root.exists():
        return []
    return sorted(root.glob(f"*{FILE_EXT}"))


@dataclass
class SearchHit:
    date: str
    preview: str


def search_entries(keyword: str, limit: int = 200) -> list[SearchHit]:
    keyword = keyword.strip()
    if not keyword:
        return []

    hits: list[SearchHit] = []
    for p in list_entries():
        date = p.stem
        try:
            content = p.read_text(encoding=ENCODING)
        except Exception:
            continue
        if keyword.lower() in content.lower():
            # preview: first matching line
            preview = ""
            for line in content.splitlines():
                if keyword.lower() in line.lower():
                    preview = line.strip()
                    break
            hits.append(SearchHit(date=date, preview=preview))
            if len(hits) >= limit:
                break
    return hits


class DiaryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x680")
        self.minsize(860, 600)

        self.selected_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.status = tk.StringVar(value="")

        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # top controls
        top = ttk.Frame(outer)
        top.pack(fill="x")

        ttk.Label(top, text="日期：").pack(side="left")
        self.date_entry = ttk.Entry(top, width=12, textvariable=self.selected_date)
        self.date_entry.pack(side="left")

        ttk.Button(top, text="打开", command=self.on_open_date).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="今天", command=self.on_today).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="保存 (Ctrl+S)", command=self.on_save).pack(side="left", padx=(12, 0))

        ttk.Separator(outer).pack(fill="x", pady=10)

        # middle split
        mid = ttk.PanedWindow(outer, orient="horizontal")
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid, padding=(0, 0, 10, 0))
        right = ttk.Frame(mid)
        mid.add(left, weight=1)
        mid.add(right, weight=3)

        # calendar
        cal_box = ttk.Labelframe(left, text="日历")
        cal_box.pack(fill="x")
        if Calendar is None:
            ttk.Label(cal_box, text="未安装 tkcalendar\n请先执行：pip install tkcalendar").pack(padx=8, pady=8)
        else:
            self.calendar = Calendar(
                cal_box,
                selectmode="day",
                date_pattern="yyyy-mm-dd",
                showweeknumbers=False,
            )
            self.calendar.pack(padx=6, pady=6, fill="x")
            self.calendar.selection_set(self.selected_date.get())
            self.calendar.bind("<<CalendarSelected>>", self.on_calendar_pick)

        # search
        search_box = ttk.Labelframe(left, text="搜索")
        search_box.pack(fill="both", expand=True, pady=(10, 0))

        srow = ttk.Frame(search_box)
        srow.pack(fill="x", padx=6, pady=6)

        self.search_var = tk.StringVar(value="")
        ttk.Entry(srow, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
        ttk.Button(srow, text="搜", width=6, command=self.on_search).pack(side="left", padx=(6, 0))

        self.search_list = tk.Listbox(search_box, height=10)
        self.search_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.search_list.bind("<Double-Button-1>", self.on_search_open)

        # editor
        editor_box = ttk.Labelframe(right, text="内容")
        editor_box.pack(fill="both", expand=True)

        self.text = tk.Text(editor_box, wrap="word", undo=True)
        self.text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(editor_box, orient="vertical", command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)

        # status bar
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Label(bar, textvariable=self.status, foreground="#555").pack(side="left")

        # keybind
        self.bind_all("<Control-s>", lambda e: self.on_save())

    def _load_current(self) -> None:
        try:
            d = normalize_date(self.selected_date.get())
        except Exception:
            d = datetime.now().strftime("%Y-%m-%d")
            self.selected_date.set(d)

        content = load_entry(d)
        self.text.delete("1.0", "end")
        if not content:
            # template
            now = datetime.now().strftime("%H:%M")
            content = f"# {d}\n\n- 时间：{now}\n- 心情：\n\n今天发生的事：\n\n收获/反思：\n\n"
        self.text.insert("1.0", content)
        self._set_status(d)

    def _set_status(self, date_str: str, extra: str = "") -> None:
        root = diary_root()
        p = entry_path(date_str)
        msg = f"保存位置：{root}    文件：{p.name}"
        if extra:
            msg += f"    {extra}"
        self.status.set(msg)

    def on_calendar_pick(self, _evt=None) -> None:
        if Calendar is None:
            return
        d = self.calendar.get_date()
        self.selected_date.set(d)
        self._load_current()

    def on_today(self) -> None:
        d = datetime.now().strftime("%Y-%m-%d")
        self.selected_date.set(d)
        if Calendar is not None:
            self.calendar.selection_set(d)
        self._load_current()

    def on_open_date(self) -> None:
        try:
            d = normalize_date(self.selected_date.get())
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        self.selected_date.set(d)
        if Calendar is not None:
            try:
                self.calendar.selection_set(d)
            except Exception:
                pass
        self._load_current()

    def on_save(self) -> None:
        try:
            d = normalize_date(self.selected_date.get())
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        text = self.text.get("1.0", "end")
        try:
            save_entry(d, text)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"保存失败：{e}")
            return
        self._set_status(d, "已保存")

    def on_search(self) -> None:
        kw = self.search_var.get().strip()
        self.search_list.delete(0, "end")
        if not kw:
            return
        hits = search_entries(kw)
        if not hits:
            self.search_list.insert("end", "（无结果）")
            return
        for h in hits:
            line = f"{h.date}  |  {h.preview}" if h.preview else h.date
            self.search_list.insert("end", line)

    def on_search_open(self, _evt=None) -> None:
        sel = self.search_list.curselection()
        if not sel:
            return
        val = self.search_list.get(sel[0])
        if val.startswith("（"):
            return
        date = val.split("|")[0].strip().split()[0]
        self.selected_date.set(date)
        if Calendar is not None:
            try:
                self.calendar.selection_set(date)
            except Exception:
                pass
        self._load_current()


def main() -> int:
    if sys.platform.startswith("win"):
        # better DPI scaling on Windows
        try:
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = DiaryApp()

    # warn about missing tkcalendar
    if Calendar is None:
        messagebox.showwarning(
            APP_NAME,
            "检测到未安装 tkcalendar，日历控件无法显示。\n\n请先安装：\n  pip install tkcalendar\n\n安装后重新运行即可。",
        )

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
