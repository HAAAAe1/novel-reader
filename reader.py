# -*- coding: utf-8 -*-
"""摸鱼看小说神器 - EPUB阅读器"""

import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont, ttk
import json
import os
import re
import html
from pathlib import Path

try:
    import ebooklib
    from ebooklib import epub
    from lxml import etree
except ImportError:
    raise SystemExit("需要安装 ebooklib: pip install ebooklib")

APP_NAME = "摸鱼看书"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "NovelReader"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROGRESS_FILE = CONFIG_DIR / "progress.json"

DEFAULT_CONFIG = {
    "font_family": "微软雅黑",
    "font_size": 14,
    "bg_color": "#f5f0e8",
    "fg_color": "#2c2c2c",
    "line_spacing": 1.6,
    "width": 400,
    "height": 600,
    "always_on_top": False,
    "opacity": 0.95,
}


def html_to_text(html_str):
    if not html_str:
        return ""
    try:
        tree = etree.HTML(html_str)
        for br in tree.xpath("//br"):
            br.tail = "\n" + (br.tail or "")
        for p in tree.xpath("//p | //div | //h1 | //h2 | //h3 | //h4"):
            p.text = "\n" + (p.text or "")
            if len(p):
                last = p[-1]
                last.tail = (last.tail or "") + "\n"
        text = etree.tostring(tree, method="text", encoding="unicode")
        lines = [line.strip() for line in text.splitlines()]
        result = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    result.append("")
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False
        return "\n".join(result).strip()
    except Exception:
        text = re.sub(r"<br\s*/?>", "\n", html_str, flags=re.I)
        text = re.sub(r"</p>|</div>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_progress():
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_progress(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class EpubLoader:
    def __init__(self):
        self.book = None
        self.chapters = []
        self.toc = []

    def load(self, filepath):
        self.book = epub.read_epub(filepath)
        self.chapters = []
        self.toc = []

        toc_titles = {}
        try:
            def _collect_toc(items):
                for item in items:
                    if isinstance(item, epub.Link):
                        toc_titles[item.href.split("#")[0]] = item.title
                        if item.children:
                            _collect_toc(item.children)
                    elif isinstance(item, tuple) and len(item) == 2:
                        _collect_toc(item[1])
            _collect_toc(self.book.toc)
        except Exception:
            for item in self.book.toc:
                if isinstance(item, epub.Link):
                    toc_titles[item.href.split("#")[0]] = item.title

        seen_titles = set()
        spine_ids = [item[0] for item in self.book.spine]

        for item_id in spine_ids:
            item = self.book.get_item_with_id(item_id)
            if item is None:
                continue
            content = item.get_content().decode("utf-8", errors="replace")
            text = html_to_text(content)
            if not text or len(text) < 10:
                continue

            href = item.get_name()
            title = toc_titles.get(href, "")
            if not title:
                try:
                    tree = etree.HTML(content)
                    h = tree.xpath("//title/text() | //h1/text() | //h2/text() | //h3/text()")
                    if h:
                        title = h[0].strip()
                except Exception:
                    pass
            if not title:
                title = f"第 {len(self.chapters) + 1} 章"
            if title in seen_titles:
                title = f"{title} ({len(self.chapters) + 1})"
            seen_titles.add(title)

            idx = len(self.chapters)
            self.chapters.append((title, text))
            self.toc.append((title, idx))

    def get_chapter_count(self):
        return len(self.chapters)

    def get_chapter(self, index):
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return ("", "")


class ReaderApp:
    def __init__(self):
        self.cfg = load_config()
        self.progress = load_progress()
        self.loader = EpubLoader()
        self.current_chapter = 0
        self.current_book_path = ""

        self._build_ui()
        self._restore_geometry()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg=self.cfg["bg_color"])
        self.root.attributes("-topmost", self.cfg["always_on_top"])
        self.root.attributes("-alpha", self.cfg["opacity"])
        self.root.minsize(120, 100)

        self._build_menu()
        self._build_toolbar()
        self._build_text_area()
        self._build_status_bar()
        self._bind_events()

        last_book = self.progress.get("last_book", "")
        if last_book and os.path.exists(last_book):
            self._open_book(last_book)

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开 EPUB...", command=self._on_open, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        self._topmost_var = tk.BooleanVar(value=self.cfg["always_on_top"])
        view_menu.add_checkbutton(label="窗口置顶", variable=self._topmost_var, command=self._toggle_topmost)
        view_menu.add_separator()
        view_menu.add_command(label="字体放大", command=lambda: self._change_font_size(1), accelerator="Ctrl++")
        view_menu.add_command(label="字体缩小", command=lambda: self._change_font_size(-1), accelerator="Ctrl+-")
        view_menu.add_separator()
        view_menu.add_command(label="背景色...", command=self._pick_bg_color)
        menubar.add_cascade(label="视图", menu=view_menu)

        menubar.add_command(label="目录", command=self._show_toc_panel)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="快捷键说明", command=self._show_help)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_toolbar(self):
        tb = tk.Frame(self.root, bg=self.cfg["bg_color"], height=28)
        tb.pack(fill=tk.X, padx=4, pady=(2, 0))

        btn_style = {"bg": self.cfg["bg_color"], "fg": self.cfg["fg_color"],
                     "relief": "flat", "padx": 4, "pady": 0, "font": ("微软雅黑", 9)}

        self._btn_prev = tk.Button(tb, text="◀", command=self._prev_chapter, **btn_style)
        self._btn_prev.pack(side=tk.LEFT)

        self._chapter_var = tk.StringVar(value="请打开 EPUB 文件")
        self._chapter_combo = ttk.Combobox(tb, textvariable=self._chapter_var,
                                           state="readonly", width=30, font=("微软雅黑", 9))
        self._chapter_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self._chapter_combo.bind("<<ComboboxSelected>>", self._on_chapter_select)

        self._btn_next = tk.Button(tb, text="▶", command=self._next_chapter, **btn_style)
        self._btn_next.pack(side=tk.LEFT)

        self._btn_open = tk.Button(tb, text="📂", command=self._on_open, **btn_style)
        self._btn_open.pack(side=tk.RIGHT)

    def _build_text_area(self):
        frame = tk.Frame(self.root, bg=self.cfg["bg_color"])
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.text = tk.Text(
            frame, wrap=tk.WORD,
            font=(self.cfg["font_family"], self.cfg["font_size"]),
            bg=self.cfg["bg_color"], fg=self.cfg["fg_color"],
            relief=tk.FLAT, padx=8, pady=6,
            spacing1=0, spacing3=0,
            state=tk.DISABLED, cursor="arrow",
            selectbackground="#b0c4de", selectforeground=self.cfg["fg_color"],
        )
        self.text.pack(fill=tk.BOTH, expand=True)
        self._update_line_spacing()

    def _build_status_bar(self):
        self.status = tk.Label(
            self.root, text="就绪",
            bg=self.cfg["bg_color"], fg="#888888",
            font=("微软雅黑", 8), anchor="w", padx=6,
        )
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    def _bind_events(self):
        self.root.bind("<Control-o>", lambda e: self._on_open())
        self.root.bind("<Control-plus>", lambda e: self._change_font_size(1))
        self.root.bind("<Control-equal>", lambda e: self._change_font_size(1))
        self.root.bind("<Control-minus>", lambda e: self._change_font_size(-1))
        self.root.bind("<Control-q>", lambda e: self._on_quit())

        self.text.bind("<Left>", lambda e: (self._prev_chapter(), "break")[1])
        self.text.bind("<Right>", lambda e: (self._next_chapter(), "break")[1])
        self.text.bind("<Prior>", lambda e: (self._scroll_view(-1), "break")[1])
        self.text.bind("<Next>", lambda e: (self._scroll_view(1), "break")[1])
        self.text.bind("<Up>", lambda e: (self._scroll_view(-1), "break")[1])
        self.text.bind("<Down>", lambda e: (self._scroll_view(1), "break")[1])
        self.text.bind("<space>", lambda e: (self._scroll_view(1), "break")[1])
        self.text.bind("<Escape>", lambda e: self.root.iconify())

        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<Button-1>", lambda e: self.text.focus_set())

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        # 鼠标离开自动变淡
        self._fade_alpha = self.cfg["opacity"]
        self._ghost_alpha = 0.15
        self._mouse_in = True
        self._check_mouse_hover()

    def _restore_geometry(self):
        w = self.cfg.get("width", 400)
        h = self.cfg.get("height", 600)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── 书操作 ──────────────────────────────────────────
    def _on_open(self):
        path = filedialog.askopenfilename(
            title="打开 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub"), ("所有文件", "*.*")],
        )
        if path:
            self._open_book(path)

    def _open_book(self, path):
        try:
            self.loader.load(path)
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            messagebox.showerror("打开失败", f"无法读取 EPUB 文件:\n{e}\n\n{err[-500:]}")
            return

        self.current_book_path = path
        self._rebuild_toc_menu()

        book_progress = self.progress.get("books", {}).get(path, {})
        self.current_chapter = book_progress.get("chapter", 0)

        self._load_chapter(self.current_chapter)
        self.root.title(f"{APP_NAME} - {os.path.basename(path)}")

    def _rebuild_toc_menu(self):
        chapter_titles = [t for t, _ in self.loader.toc]
        self._chapter_combo["values"] = chapter_titles

    def _show_toc_panel(self):
        if not self.loader.toc:
            return
        win = tk.Toplevel(self.root)
        win.title("目录")
        win.geometry("350x500")
        win.attributes("-topmost", True)

        search_var = tk.StringVar()
        search_entry = tk.Entry(win, textvariable=search_var, font=("微软雅黑", 10))
        search_entry.pack(fill=tk.X, padx=6, pady=(6, 2))

        listbox = tk.Listbox(win, font=("微软雅黑", 10), activestyle="none")
        listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        toc_data = list(self.loader.toc)
        for title, _ in toc_data:
            listbox.insert(tk.END, title)

        for i, (_, idx) in enumerate(toc_data):
            if idx == self.current_chapter:
                listbox.selection_set(i)
                listbox.see(i)
                break

        def on_select(event=None):
            sel = listbox.curselection()
            if sel:
                # 从显示的列表找对应的 toc_data 索引
                clicked_title = listbox.get(sel[0])
                for title, idx in toc_data:
                    if title == clicked_title:
                        self._load_chapter(idx)
                        win.destroy()
                        return
        listbox.bind("<Double-Button-1>", on_select)

        def on_search(*args):
            keyword = search_var.get().strip().lower()
            listbox.delete(0, tk.END)
            for title, idx in toc_data:
                if not keyword or keyword in title.lower():
                    listbox.insert(tk.END, title)
        search_var.trace_add("write", on_search)

        search_entry.focus_set()

    def _on_chapter_select(self, event=None):
        sel = self._chapter_combo.current()
        if sel >= 0 and sel < len(self.loader.toc):
            _, idx = self.loader.toc[sel]
            if idx != self.current_chapter:
                self._load_chapter(idx)

    def _load_chapter(self, chapter_idx):
        if not self.loader.chapters:
            return
        chapter_idx = max(0, min(chapter_idx, len(self.loader.chapters) - 1))
        self.current_chapter = chapter_idx

        title, text = self.loader.get_chapter(chapter_idx)
        for i, (_, idx) in enumerate(self.loader.toc):
            if idx == chapter_idx:
                self._chapter_combo.current(i)
                self._chapter_var.set(title[:50])
                break

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", text)
        self.text.config(state=tk.DISABLED)
        self.text.see("1.0")

        total_chapters = self.loader.get_chapter_count()
        self.status.config(
            text=f"第 {self.current_chapter + 1}/{total_chapters} 章  |  ← → 翻章  滚轮滚动"
        )
        self._save_progress()

    # ── 滚动 ───────────────────────────────────────────
    def _scroll_view(self, direction):
        self.text.yview_scroll(direction, "units")

    def _on_mousewheel(self, event):
        if event.delta > 0:
            self.text.yview_scroll(-2, "units")
        elif event.delta < 0:
            self.text.yview_scroll(2, "units")
        return "break"

    def _prev_chapter(self):
        if self.current_chapter > 0:
            self._load_chapter(self.current_chapter - 1)

    def _next_chapter(self):
        if self.current_chapter < self.loader.get_chapter_count() - 1:
            self._load_chapter(self.current_chapter + 1)

    # ── 透明度 ─────────────────────────────────────────
    def _check_mouse_hover(self):
        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            wx = self.root.winfo_rootx()
            wy = self.root.winfo_rooty()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()
            inside = wx <= x <= wx + ww and wy <= y <= wy + wh
            if inside and not self._mouse_in:
                self._mouse_in = True
                self.root.attributes("-alpha", self._fade_alpha)
            elif not inside and self._mouse_in:
                self._mouse_in = False
                self.root.attributes("-alpha", self._ghost_alpha)
        except Exception:
            pass
        self.root.after(200, self._check_mouse_hover)

    # ── 设置 ────────────────────────────────────────────
    def _toggle_topmost(self):
        val = self._topmost_var.get()
        self.root.attributes("-topmost", val)
        self.cfg["always_on_top"] = val
        save_config(self.cfg)

    def _change_font_size(self, delta):
        new_size = max(10, min(32, self.cfg["font_size"] + delta))
        self.cfg["font_size"] = new_size
        self.text.config(font=(self.cfg["font_family"], new_size))
        save_config(self.cfg)

    def _pick_bg_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(initialcolor=self.cfg["bg_color"], title="选择背景色")
        if color[1]:
            self.cfg["bg_color"] = color[1]
            self.root.configure(bg=color[1])
            self.text.config(bg=color[1])
            save_config(self.cfg)

    def _update_line_spacing(self):
        spacing = int(self.cfg["font_size"] * (self.cfg["line_spacing"] - 1))
        self.text.config(spacing1=0, spacing2=spacing, spacing3=0)

    def _show_help(self):
        messagebox.showinfo("快捷键", """快捷键说明

Ctrl+O    打开 EPUB
Ctrl++    字体放大
Ctrl+-    字体缩小
Ctrl+Q    退出

← →       上/下一章
↑ ↓ / 滚轮  平滑滚动
PageUp/Down  翻页
Space     下一页
""")

    def _save_progress(self):
        if not self.current_book_path:
            return
        if "books" not in self.progress:
            self.progress["books"] = {}
        self.progress["last_book"] = self.current_book_path
        self.progress["books"][self.current_book_path] = {
            "chapter": self.current_chapter,
            "scroll": self.text.yview()[0],
        }
        try:
            geo = self.root.geometry()
            match = re.match(r"(\d+)x(\d+)", geo)
            if match:
                self.cfg["width"] = int(match.group(1))
                self.cfg["height"] = int(match.group(2))
                save_config(self.cfg)
        except Exception:
            pass
        save_progress(self.progress)

    def _on_quit(self):
        self._save_progress()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ReaderApp()
    app.run()
