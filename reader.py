# -*- coding: utf-8 -*-
"""摸鱼看小说神器 - EPUB/TXT 阅读器"""

import json
import os
import re
import html
import sys
import time
import traceback
import ctypes
from pathlib import Path

APP_NAME = "摸鱼看书"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "NovelReader"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROGRESS_FILE = CONFIG_DIR / "progress.json"
LOG_FILE = CONFIG_DIR / "error.log"


def log_error(msg):
    """写 %APPDATA%\\NovelReader\\error.log：pythonw/独立版下没有控制台，文件是唯一可靠出口。"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n" + "-" * 60 + "\n")
    except Exception:
        pass


def fatal(msg):
    """GUI 可能根本不可用：只用 Win32 MessageBox + 文件日志兜底，绝不能无声退出。"""
    log_error(msg)
    try:
        ctypes.windll.user32.MessageBoxW(None, msg[-1800:], f"{APP_NAME} - 启动失败", 0x10)
    except Exception:
        pass
    sys.exit(1)


try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, font as tkfont, ttk
except Exception:
    fatal(
        "tkinter 不可用，界面无法创建。\n\n"
        f"当前解释器：{sys.executable}\n"
        f"Python：{sys.version.split()[0]}\n\n"
        "请使用带 tcl/tk 的 Python 3（安装时勾选 tcl/tk and IDLE）。\n\n"
        + traceback.format_exc()
    )

try:
    import ebooklib
    from ebooklib import epub
    from lxml import etree
except ImportError:
    # ebooklib 只有读 EPUB 才需要；只看 TXT 不装它也能用
    ebooklib = None
    epub = None
    etree = None

DEFAULT_CONFIG = {
    "font_family": "微软雅黑",
    "font_size": 14,
    "bg_color": "#f5f0e8",
    "fg_color": "#2c2c2c",
    "line_spacing": 1.6,
    "width": 400,
    "height": 600,
    "always_on_top": False,
    "opacity": 0.95,        # 鼠标在窗口内时的透明度
    "ghost_alpha": 0.15,    # 鼠标移开后变淡到的透明度
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
        if epub is None:
            raise RuntimeError(
                "EPUB 需要 ebooklib，当前解释器没有安装。\n"
                f'请在命令行执行：\n  "{sys.executable}" -m pip install ebooklib\n'
                "（TXT 无需该依赖，可直接打开）"
            )
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
            # EPUB3 导航文档不是正文，跳过。
            # 证据：ebooklib 读回的 nav 项 type=EpubNav 但 .properties 不回填（OPF 里明明有）
            # 所以三种判定一起上：properties / EpubNav 类型 / 惯例 id。
            props = getattr(item, "properties", None) or []
            if "nav" in props or isinstance(item, epub.EpubNav) or item.id == "nav":
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


# 章节标题：「第X章/回/节/卷/集/部/篇」单独成行（标题里不带句号等）
CHAPTER_RE = re.compile(
    r"^\s*(第\s*[0-9０-９零〇一二三四五六七八九十百千万两]+\s*"
    r"[章回节卷集部篇][^。！？\n]{0,30})\s*$"
)


def decode_text(data):
    """自动识别 txt 编码：BOM → UTF-16 → UTF-8 → GB18030。"""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if data[:3] == b"\xef\xbb\xbf":
        return data.decode("utf-8-sig", errors="replace")
    sample = data[:4000] or data
    if sample.count(0) > len(sample) // 4:
        # 无 BOM 的 UTF-16：按空字节在奇偶位猜字节序
        le = sum(1 for b in sample[1::2] if b == 0)
        be = sum(1 for b in sample[0::2] if b == 0)
        try:
            return data.decode("utf-16-le" if le >= be else "utf-16-be")
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gb18030")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")


class TxtLoader:
    """纯文本加载：自动识别编码，按「第X章」等标题切分章节。"""

    def __init__(self):
        self.chapters = []
        self.toc = []

    def load(self, filepath):
        self.chapters = []
        self.toc = []
        text = Path(filepath).read_bytes()
        text = decode_text(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff \t\n")

        chapters = self._split_by_headings(text)
        if len(chapters) < 2:
            chapters = self._split_by_size(text)

        seen = set()
        for title, body in chapters:
            body = body.strip()
            if not body:
                continue
            if title in seen:
                title = f"{title} ({len(self.chapters) + 1})"
            seen.add(title)
            idx = len(self.chapters)
            self.chapters.append((title, body))
            self.toc.append((title, idx))

    def _split_by_headings(self, text):
        parts = []
        title = None
        buf = []
        for line in text.split("\n"):
            m = CHAPTER_RE.match(line)
            if m:
                if buf:
                    parts.append((title or "前言", "\n".join(buf)))
                    buf = []
                title = re.sub(r"\s+", " ", m.group(1)).strip()
            else:
                buf.append(line)
        if buf:
            parts.append((title or "正文", "\n".join(buf)))
        return [(t, b) for t, b in parts if b.strip()]

    def _split_by_size(self, text, target=1800):
        """找不到章节标题时，按段落把长文切成若干节。"""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        segs = []
        if paragraphs:
            segs = self._pack(paragraphs, "\n\n", target)
        if len(segs) <= 1:
            # 没有空行分隔的整块长文，退回按行切
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            segs = self._pack(lines, "\n", target)
        return [(f"第 {i + 1} 节", s) for i, s in enumerate(segs)]

    @staticmethod
    def _pack(items, sep, target):
        segs, buf, size = [], [], 0
        for item in items:
            if size and size + len(item) > target:
                segs.append(sep.join(buf))
                buf, size = [], 0
            buf.append(item)
            size += len(item)
        if buf:
            segs.append(sep.join(buf))
        return segs


class BookLoader:
    """按扩展名/文件头自动选择 EPUB 或 TXT 加载器。"""

    def __init__(self):
        self.chapters = []
        self.toc = []

    def load(self, filepath):
        loader = self._pick_loader(filepath)
        loader.load(filepath)
        self.chapters = loader.chapters
        self.toc = loader.toc

    @staticmethod
    def _pick_loader(filepath):
        ext = Path(filepath).suffix.lower()
        if ext == ".epub":
            return EpubLoader()
        if ext in (".txt", ".text"):
            return TxtLoader()
        # 未知扩展名：按文件头猜（EPUB 本质是 zip）
        try:
            with open(filepath, "rb") as f:
                magic = f.read(2)
        except OSError:
            magic = b""
        return EpubLoader() if magic == b"PK" else TxtLoader()

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
        self.loader = BookLoader()
        self.current_chapter = 0
        self.current_book_path = ""

        self._build_ui()
        self._restore_geometry()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.report_callback_exception = _report_callback_exception
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
        file_menu.add_command(label="打开书籍...", command=self._on_open, accelerator="Ctrl+O")
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
        view_menu.add_command(label="恢复默认背景色", command=self._restore_default_color)
        view_menu.add_separator()
        view_menu.add_command(label="透明度...", command=self._open_opacity_dialog)
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

        self._chapter_var = tk.StringVar(value="请打开 EPUB/TXT 书籍")
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
        self._ghost_alpha = self.cfg["ghost_alpha"]
        self._fade_paused = False
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
            title="打开电子书",
            filetypes=[
                ("电子书", "*.epub *.txt *.text"),
                ("EPUB 文件", "*.epub"),
                ("TXT 文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self._open_book(path)

    def _open_book(self, path):
        try:
            self.loader.load(path)
        except Exception as e:
            # 对话框只给人能读的话，完整 traceback 进 error.log
            log_error(f"打开失败：{path}\n{traceback.format_exc()}")
            messagebox.showerror("打开失败", f"无法读取文件：\n{path}\n\n{e}")
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
            if not self._fade_paused:
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

    def _restore_default_color(self):
        """一键改回默认米黄 #f5f0e8（选色框里翻不到这个色，单给个入口）。"""
        default_bg = DEFAULT_CONFIG["bg_color"]
        self.cfg["bg_color"] = default_bg
        self.root.configure(bg=default_bg)
        self.text.config(bg=default_bg)
        save_config(self.cfg)
        self.status.config(text="背景色已恢复默认")

    # ── 透明度调节 ─────────────────────────────────────
    def _open_opacity_dialog(self):
        """两个滑条：正常显示时的透明度 + 鼠标移开后的透明度。拖动即生效，关窗自动保存。"""
        win = tk.Toplevel(self.root)
        win.title("透明度")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg=self.cfg["bg_color"])

        # 调节期间暂停"移开变淡"，否则鼠标移到对话框上主窗口就隐身了，没法所见即所得
        self._fade_paused = True
        self.root.attributes("-alpha", self._fade_alpha)

        panel = tk.Frame(win, bg=self.cfg["bg_color"], padx=12, pady=10)
        panel.pack(fill=tk.BOTH, expand=True)

        tk.Label(panel, text="窗口透明度（鼠标在窗口内）", bg=self.cfg["bg_color"],
                 fg=self.cfg["fg_color"], font=("微软雅黑", 9)).pack(anchor="w")
        s_norm = tk.Scale(panel, from_=100, to=30, orient=tk.HORIZONTAL, length=240,
                          showvalue=True, bg=self.cfg["bg_color"], fg=self.cfg["fg_color"],
                          highlightthickness=0, font=("微软雅黑", 9),
                          command=lambda v: self._set_opacity(int(v) / 100))
        s_norm.set(round(self.cfg["opacity"] * 100))
        s_norm.pack(fill=tk.X)

        tk.Label(panel, text="移开后透明度（鼠标离开窗口）", bg=self.cfg["bg_color"],
                 fg=self.cfg["fg_color"], font=("微软雅黑", 9)).pack(anchor="w", pady=(8, 0))
        s_ghost = tk.Scale(panel, from_=60, to=5, orient=tk.HORIZONTAL, length=240,
                           showvalue=True, bg=self.cfg["bg_color"], fg=self.cfg["fg_color"],
                           highlightthickness=0, font=("微软雅黑", 9),
                           command=lambda v: self._set_ghost_alpha(int(v) / 100))
        s_ghost.set(round(self.cfg["ghost_alpha"] * 100))
        s_ghost.pack(fill=tk.X)

        tk.Label(panel, text="默认 95% / 15%，改动会记住", bg=self.cfg["bg_color"],
                 fg="#888888", font=("微软雅黑", 8)).pack(anchor="w", pady=(6, 0))

        def on_close():
            self._fade_paused = False
            try:
                self.root.attributes(
                    "-alpha", self._fade_alpha if self._mouse_in else self._ghost_alpha)
            except Exception:
                pass
            save_config(self.cfg)
            win.destroy()

        btn = tk.Button(panel, text="关闭", command=on_close, font=("微软雅黑", 9),
                        bg=self.cfg["bg_color"], fg=self.cfg["fg_color"], relief="flat", padx=10)
        btn.pack(anchor="e", pady=(8, 0))
        win.protocol("WM_DELETE_WINDOW", on_close)

    def _set_opacity(self, val):
        """正常显示（鼠标在窗口内）的透明度。val: 0.3~1.0"""
        val = max(0.3, min(1.0, round(val, 2)))
        self.cfg["opacity"] = val
        self._fade_alpha = val
        if getattr(self, "_mouse_in", True):
            self.root.attributes("-alpha", val)
        save_config(self.cfg)

    def _set_ghost_alpha(self, val):
        """鼠标移开后变淡到的透明度。val: 0.05~0.6"""
        val = max(0.05, min(0.6, round(val, 2)))
        self.cfg["ghost_alpha"] = val
        self._ghost_alpha = val
        if getattr(self, "_mouse_in", True) is False:
            self.root.attributes("-alpha", val)
        save_config(self.cfg)

    def _update_line_spacing(self):
        spacing = int(self.cfg["font_size"] * (self.cfg["line_spacing"] - 1))
        self.text.config(spacing1=0, spacing2=spacing, spacing3=0)

    def _show_help(self):
        messagebox.showinfo("快捷键", """快捷键说明

Ctrl+O    打开书籍（EPUB/TXT）
Ctrl++    字体放大
Ctrl+-    字体缩小
Ctrl+Q    退出

← →       上/下一章
↑ ↓ / 滚轮  平滑滚动
PageUp/Down  翻页
Space     下一页
Escape    最小化窗口

透明度可在「视图 → 透明度...」里调节
（默认 95% / 移开后 15%）
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


def _excepthook(exc_type, exc, tb):
    fatal("未捕获异常：\n\n" + "".join(traceback.format_exception(exc_type, exc, tb)))


def _report_callback_exception(exc, val, tb):
    """Tk 回调异常不走 excepthook，pythonw 下默认零输出 → 必须自己落日志+弹框（不退出）。"""
    text = "".join(traceback.format_exception(exc, val, tb))
    log_error(f"GUI 回调异常：\n{text}")
    try:
        ctypes.windll.user32.MessageBoxW(None, text[-1800:], f"{APP_NAME} - 界面错误", 0x10)
    except Exception:
        pass


def main(argv=None):
    sys.excepthook = _excepthook
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    # 启动上下文进日志：下次再"没反应"，看一眼 error.log 就知道跑在哪、带了什么参数
    log_error(
        f"START {time.strftime('%Y-%m-%d %H:%M:%S')} | exe={sys.executable} | "
        f"py={sys.version.split()[0]} | frozen={getattr(sys, 'frozen', False)} | argv={argv}"
    )
    try:
        app = ReaderApp()
        # 拖文件到快捷方式/命令行传参：取第一个存在的文件
        for arg in argv:
            if os.path.exists(arg):
                app._open_book(arg)
                break
        app.run()
    except Exception:
        _excepthook(*sys.exc_info())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
