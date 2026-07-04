#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scanner_frame.py — File Scanner 标签页
包含扫描、排序、过滤、删除、导出等全部功能
"""

import os
import sys
import shutil
import threading
import json
import csv
from tkinter import (
    ttk, Frame, Label, Entry, Button, StringVar,
    BooleanVar, Checkbutton, Menu, Canvas, Scrollbar,
    filedialog, messagebox, HORIZONTAL, VERTICAL, BOTH, LEFT,
    RIGHT, TOP, BOTTOM, X, Y, END, W, E, FLAT,
)

_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _script_dir)

from disk_scanner import (
    Scanner, ScanResult, FileNode, DirNode,
    format_size, parse_size_filter, sort_nodes,
)
from ui.theme import (
    C, F_TITLE, F_BODY, F_SMALL, F_TINY, F_BIG, F_MONO, F_BTN,
    RoundButton, StatCard, ConfirmDialog, InfoDialog, fmt_time,
)


class ScannerFrame(Frame):
    """磁盘扫描器标签页"""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.root = app  # app 是主 Tk 窗口

        # 状态
        self.result = None
        self.scan_path = ""
        self.view_mode = "dirs"
        self.sort_col = "size"
        self.sort_reverse = True
        self.item_map = {}
        self._scanning = False
        self._scan_result = None
        self._scan_error = None
        self._scan_thread = None
        self._page = 0
        self._page_size = 200
        self._sorted_items = []
        self._total_items = 0
        self._checked_paths = set()

        self._build_ui()

    def _build_ui(self):
        outer = Frame(self, bg=C["bg"])
        outer.pack(fill=BOTH, expand=True, padx=16, pady=12)

        self._build_header(outer)
        self._build_controls(outer)
        self._build_stats(outer)
        self._build_toolbar(outer)
        self._build_tree(outer)
        self._build_detail(outer)
        self._build_statusbar(outer)
        self._build_context_menu()

    def _build_header(self, parent):
        hdr = Frame(parent, bg=C["bg"])
        hdr.pack(fill=X, pady=(0, 10))

        left = Frame(hdr, bg=C["bg"])
        left.pack(side=LEFT)
        Label(left, text="DiskScanner", bg=C["bg"], fg=C["accent"],
              font=F_TITLE).pack(side=LEFT)
        Label(left, text=" v1.0 ", bg=C["surface"], fg=C["text2"],
              font=F_TINY, padx=6, pady=2).pack(side=LEFT, padx=(10, 0))

        self._new_scan_btn = RoundButton(hdr, text="New Scan",
                                          command=self._reset_scan,
                                          bg=C["btn_bg"], fg=C["text"])
        self._new_scan_btn.pack(side=RIGHT)

    def _build_controls(self, parent):
        card = Frame(parent, bg=C["surface"], padx=16, pady=12)
        card.pack(fill=X, pady=(0, 10))

        r1 = Frame(card, bg=C["surface"])
        r1.pack(fill=X, pady=(0, 8))

        Label(r1, text="PATH", bg=C["surface"], fg=C["text2"],
              font=F_TINY).pack(side=LEFT, padx=(0, 8))

        self.path_var = StringVar(value=os.path.expanduser("~"))
        self.path_entry = Entry(r1, textvariable=self.path_var, font=F_MONO,
                                 bg=C["input_bg"], fg=C["text"],
                                 insertbackground=C["accent"], relief=FLAT, bd=6,
                                 highlightthickness=1, highlightcolor=C["accent"],
                                 highlightbackground=C["border"])
        self.path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.path_entry.bind('<Return>', lambda e: self._start_scan())

        self._browse_btn = RoundButton(r1, text="Browse", command=self._browse,
                                        bg=C["btn_bg"], fg=C["text"])
        self._browse_btn.pack(side=LEFT, padx=(0, 8))

        self._scan_btn = RoundButton(r1, text="START SCAN", command=self._start_scan,
                                      bg=C["accent"], fg="#ffffff",
                                      hover_bg="#79c0ff")
        self._scan_btn.pack(side=LEFT)

        r2 = Frame(card, bg=C["surface"])
        r2.pack(fill=X)

        Label(r2, text="MIN SIZE", bg=C["surface"], fg=C["text3"],
              font=F_TINY).pack(side=LEFT)
        self.min_size_var = StringVar()
        Entry(r2, textvariable=self.min_size_var, font=F_SMALL, width=10,
              bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
              relief=FLAT, bd=4, highlightthickness=1,
              highlightcolor=C["accent"], highlightbackground=C["border"]).pack(side=LEFT, padx=(6, 16))

        Label(r2, text="EXT FILTER", bg=C["surface"], fg=C["text3"],
              font=F_TINY).pack(side=LEFT)
        self.ext_var = StringVar()
        Entry(r2, textvariable=self.ext_var, font=F_SMALL, width=14,
              bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
              relief=FLAT, bd=4, highlightthickness=1,
              highlightcolor=C["accent"], highlightbackground=C["border"]).pack(side=LEFT, padx=(6, 16))

        self.follow_sym = BooleanVar(value=False)
        Checkbutton(r2, text="Follow symlinks", variable=self.follow_sym,
                     bg=C["surface"], fg=C["text3"], selectcolor=C["input_bg"],
                     activebackground=C["surface"], activeforeground=C["text2"],
                     font=F_SMALL).pack(side=LEFT)

        self.progress = ttk.Progressbar(card, mode='indeterminate',
                                         style='Scan.Horizontal.TProgressbar')
        self.progress.pack(fill=X, pady=(8, 0))

    def _build_stats(self, parent):
        row = Frame(parent, bg=C["bg"])
        row.pack(fill=X, pady=(0, 10))

        self.sc_size  = StatCard(row, "TOTAL SIZE", C["green"])
        self.sc_size.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        self.sc_files = StatCard(row, "FILES", C["text"])
        self.sc_files.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_dirs  = StatCard(row, "DIRS", C["orange"])
        self.sc_dirs.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_time  = StatCard(row, "DURATION", C["purple"])
        self.sc_time.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_skip  = StatCard(row, "SKIPPED", C["orange"])
        self.sc_skip.pack(side=LEFT, fill=X, expand=True, padx=(3, 0))

    def _build_toolbar(self, parent):
        tb = Frame(parent, bg=C["bg"])
        tb.pack(fill=X, pady=(0, 6))

        self.view_dirs_btn = RoundButton(tb, text="DIRS", command=lambda: self._switch("dirs"),
                                          bg=C["accent"], fg="#ffffff",
                                          hover_bg=C["accent"], padx=12)
        self.view_dirs_btn.pack(side=LEFT, padx=(0, 2))
        self.view_files_btn = RoundButton(tb, text="FILES", command=lambda: self._switch("files"),
                                           bg=C["btn_bg"], fg=C["text"],
                                           hover_bg=C["btn_hover"], padx=12)
        self.view_files_btn.pack(side=LEFT, padx=(0, 8))

        Frame(tb, bg=C["border"], width=1).pack(side=LEFT, fill=Y, padx=8)

        self._check_all_btn = RoundButton(tb, text="CHECK PAGE", command=self._check_all_on_page,
                                            bg=C["btn_bg"], fg=C["text"], padx=8)
        self._check_all_btn.pack(side=LEFT, padx=(0, 2))
        self._del_btn = RoundButton(tb, text="DELETE", command=self._delete_checked,
                                     bg="#da3633", fg="#ffffff", hover_bg="#f85149", padx=10)
        self._del_btn.pack(side=LEFT, padx=(0, 2))
        self._clear_btn = RoundButton(tb, text="CLEAR", command=self._clear_all_checks,
                                       bg=C["btn_bg"], fg=C["text"], padx=8)
        self._clear_btn.pack(side=LEFT, padx=(0, 4))
        RoundButton(tb, text="CSV", command=lambda: self._export("csv"),
                     bg=C["btn_bg"], fg=C["text"], padx=10).pack(side=LEFT, padx=2)
        RoundButton(tb, text="JSON", command=lambda: self._export("json"),
                     bg=C["btn_bg"], fg=C["text"], padx=10).pack(side=LEFT, padx=2)

        self.tree_title = Label(tb, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self.tree_title.pack(side=RIGHT)

        pg = Frame(tb, bg=C["bg"])
        pg.pack(side=RIGHT, padx=(8, 4))
        self._prev_btn = RoundButton(pg, text="<", command=self._prev_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        self._prev_btn.pack(side=LEFT, padx=1)
        self._page_label = Label(pg, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self._page_label.pack(side=LEFT, padx=6)
        self._next_btn = RoundButton(pg, text=">", command=self._next_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        self._next_btn.pack(side=LEFT, padx=1)

    def _build_tree(self, parent):
        wrap = Frame(parent, bg=C["border"], bd=1, relief=FLAT)
        wrap.pack(fill=BOTH, expand=True, pady=(0, 6))

        inner = Frame(wrap, bg=C["tree_bg"], padx=1, pady=1)
        inner.pack(fill=BOTH, expand=True)

        ysb = Scrollbar(inner, orient=VERTICAL)
        xsb = Scrollbar(inner, orient=HORIZONTAL)
        self.tree = ttk.Treeview(inner, style='Scan.Treeview',
                                  yscrollcommand=ysb.set, xscrollcommand=xsb.set,
                                  selectmode='extended', show='headings')
        ysb.config(command=self.tree.yview)
        xsb.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        xsb.grid(row=1, column=0, sticky='ew')
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        self.tree.bind('<Button-1>', self._on_click)
        self.tree.bind('<Double-1>', self._on_dblclick)
        self.tree.bind('<Button-3>', self._on_rightclick)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

    def _build_detail(self, parent):
        det = Frame(parent, bg=C["surface"], padx=14, pady=8)
        det.pack(fill=X, pady=(0, 4))

        self.detail_var = StringVar(value="Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        Label(det, textvariable=self.detail_var, bg=C["surface"], fg=C["text2"],
              font=F_SMALL, anchor=W).pack(side=LEFT, fill=X, expand=True)
        self.del_cmd_var = StringVar()
        Label(det, textvariable=self.del_cmd_var, bg=C["surface"], fg=C["red"],
              font=F_MONO, anchor=E).pack(side=RIGHT)

    def _build_statusbar(self, parent):
        sf = Frame(parent, bg=C["bg"])
        sf.pack(fill=X)
        self.status_var = StringVar(value="Ready")
        Label(sf, textvariable=self.status_var, bg=C["bg"], fg=C["text3"],
              font=F_TINY, anchor=W).pack(side=LEFT)

    def _build_context_menu(self):
        self.ctx_menu = Menu(self.root, tearoff=0,
                              bg=C["surface"], fg=C["text"],
                              activebackground=C["accent"],
                              activeforeground="#ffffff",
                              font=F_SMALL, borderwidth=1,
                              relief=FLAT)

    # ══════════════════════════════════════════════════════
    #  扫描逻辑
    # ══════════════════════════════════════════════════════

    def _reset_scan(self):
        self.result = None
        self._checked_paths.clear()
        self._clear_tree()
        for sc in (self.sc_size, self.sc_files, self.sc_dirs, self.sc_time, self.sc_skip):
            sc.set_value("--")
        self.status_var.set("Ready")
        self.tree_title.config(text="")
        self.detail_var.set("Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        self.del_cmd_var.set("")

    def _browse(self):
        path = filedialog.askdirectory(title="Select directory",
                                        initialdir=self.path_var.get() or "/")
        if path:
            self.path_var.set(path)

    def _start_scan(self):
        if self._scanning:
            return
        path = self.path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please enter a path")
            return
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            messagebox.showerror("Error", f"Path not found:\n{abs_path}")
            return
        if not os.path.isdir(abs_path):
            messagebox.showerror("Error", f"Not a directory:\n{abs_path}")
            return

        self._scanning = True
        self._scan_result = None
        self._scan_error = None
        self.scan_path = abs_path
        self.status_var.set(f"Scanning {abs_path} ...")
        self.progress.start(12)
        self._clear_tree()

        def do_scan():
            try:
                scanner = Scanner(follow_symlinks=self.follow_sym.get())
                self._scan_result = scanner.scan(abs_path)
            except Exception as e:
                self._scan_error = str(e)

        self._scan_thread = threading.Thread(target=do_scan, daemon=True)
        self._scan_thread.start()
        self.root.after(300, self._check_scan_done)

    def _check_scan_done(self):
        if self._scan_thread and self._scan_thread.is_alive():
            self.root.after(300, self._check_scan_done)
            return
        self.progress.stop()
        self._scanning = False

        if self._scan_error:
            messagebox.showerror("Scan Error", self._scan_error)
            self.status_var.set("Scan failed")
            return

        r = self._scan_result
        self.result = r
        skip_txt = f"  |  Skipped {r.skipped_count}" if r.skipped_count else ""
        self.status_var.set(
            f"Done: {r.total_files:,} files, {r.total_dirs:,} dirs, "
            f"{r.scan_duration:.2f}s{skip_txt}")
        self._update_stats(r)
        self._render()

    def _update_stats(self, r):
        self.sc_size.set_value(format_size(r.total_size))
        self.sc_files.set_value(f"{r.total_files:,}")
        self.sc_dirs.set_value(f"{r.total_dirs:,}")
        self.sc_time.set_value(f"{r.scan_duration:.2f}s")
        self.sc_skip.set_value(str(r.skipped_count) if r.skipped_count else "0")

    def _render(self):
        if not self.result:
            return
        r = self.result

        files = list(r.all_files)
        ms = parse_size_filter(self.min_size_var.get().strip())
        ext_str = self.ext_var.get().strip()
        exts = []
        if ext_str:
            exts = [e.strip().lower() if e.strip().startswith('.')
                    else f'.{e.strip().lower()}' for e in ext_str.split(',') if e.strip()]
        if ms > 0:
            files = [f for f in files if f.size >= ms]
        if exts:
            files = [f for f in files if f.extension in exts]

        dirs = r.all_dirs
        if ms > 0 or exts:
            dp = set(f.parent_path for f in files)
            dirs = [d for d in dirs if d.path in dp or d.path == r.root.path]

        sort_mode = self._sort_mode_key()
        all_items = sort_nodes(dirs if self.view_mode == "dirs" else files, sort_mode)
        self._sorted_items = all_items
        self._total_items = len(all_items)

        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page > max_page:
            self._page = max_page
        if self._page < 0:
            self._page = 0

        start = self._page * self._page_size
        end = start + self._page_size
        items = all_items[start:end]
        self.item_map = {}

        for c in self.tree.get_children():
            self.tree.delete(c)

        is_dirs = self.view_mode == "dirs"
        arrow_d = " v" if (self.sort_col == "size" and self.sort_reverse) else \
                  (" ^" if self.sort_col == "size" else "")

        if is_dirs:
            cols = ("check", "path", "size", "files", "subdirs", "pct", "modified")
            self.tree.config(columns=cols)
            self.tree.heading("check", text="")
            self.tree.heading("path", text="Path", command=lambda: self._sort_by("path"))
            self.tree.heading("size", text=f"Size{arrow_d}", command=lambda: self._sort_by("size"))
            self.tree.heading("files", text="Files", command=lambda: self._sort_by("files"))
            self.tree.heading("subdirs", text="SubDirs", command=lambda: self._sort_by("subdirs"))
            self.tree.heading("pct", text="%")
            self.tree.heading("modified", text="Modified", command=lambda: self._sort_by("modified"))
            self.tree.column("check", width=36, anchor='center', minwidth=30, stretch=False)
            self.tree.column("path", width=500, minwidth=200)
            self.tree.column("size", width=110, anchor=E, minwidth=80)
            self.tree.column("files", width=80, anchor=E, minwidth=60)
            self.tree.column("subdirs", width=80, anchor=E, minwidth=60)
            self.tree.column("pct", width=70, anchor=E, minwidth=50)
            self.tree.column("modified", width=150, minwidth=100)
        else:
            cols = ("check", "path", "size", "ext", "pct", "modified")
            self.tree.config(columns=cols)
            self.tree.heading("check", text="")
            self.tree.heading("path", text="Path", command=lambda: self._sort_by("path"))
            self.tree.heading("size", text=f"Size{arrow_d}", command=lambda: self._sort_by("size"))
            self.tree.heading("ext", text="Type", command=lambda: self._sort_by("ext"))
            self.tree.heading("pct", text="%")
            self.tree.heading("modified", text="Modified", command=lambda: self._sort_by("modified"))
            self.tree.column("check", width=36, anchor='center', minwidth=30, stretch=False)
            self.tree.column("path", width=540, minwidth=200)
            self.tree.column("size", width=110, anchor=E, minwidth=80)
            self.tree.column("ext", width=80, minwidth=50)
            self.tree.column("pct", width=70, anchor=E, minwidth=50)
            self.tree.column("modified", width=150, minwidth=100)

        total = max(r.total_size, 1)
        for i, node in enumerate(items):
            iid = str(i)
            self.item_map[iid] = node
            pct = f"{node.size / total * 100:.1f}%"
            checked = node.path in self._checked_paths
            ck = "[x]" if checked else "[ ]"
            base_tag = 'odd' if i % 2 else 'even'
            tag = f'{base_tag}_checked' if checked else base_tag
            if is_dirs:
                vals = (ck, node.path, format_size(node.size), node.file_count,
                        node.dir_count, pct, fmt_time(node.modified))
            else:
                vals = (ck, node.path, format_size(node.size), node.extension or "-",
                        pct, fmt_time(node.modified))
            self.tree.insert('', END, iid=iid, values=vals, tags=(tag,))

        self.tree.tag_configure('odd', background=C["tree_row1"])
        self.tree.tag_configure('even', background=C["tree_row2"])
        self.tree.tag_configure('odd_checked', background=C["checked_odd"])
        self.tree.tag_configure('even_checked', background=C["checked_even"])

        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        checked_count = len(self._checked_paths)
        if checked_count > 0:
            self.tree_title.config(
                text=f"{vlabel} ({self._total_items:,})  |  Checked: {checked_count}")
        else:
            self.tree_title.config(text=f"{vlabel} ({self._total_items:,})")

        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._total_items == 0:
            self._page_label.config(text="")
        else:
            self._page_label.config(text=f"{self._page + 1}/{max_page + 1}")

    # ── 分页导航 ──

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render()

    def _next_page(self):
        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._render()

    # ── 排序 ──

    def _sort_mode_key(self):
        if self.sort_col == "size":
            return "size-desc" if self.sort_reverse else "size-asc"
        elif self.sort_col in ("name", "path"):
            return "name"
        elif self.sort_col == "modified":
            return "modified"
        return "size-desc"

    def _sort_by(self, col):
        if col == self.sort_col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = True
        self._page = 0
        self._render()

    # ── 视图切换 ──

    def _switch(self, mode):
        self.view_mode = mode
        self._page = 0
        if mode == "dirs":
            self.view_dirs_btn._bg = C["accent"]
            self.view_dirs_btn._fg = "#ffffff"
            self.view_dirs_btn._draw(C["accent"])
            self.view_files_btn._bg = C["btn_bg"]
            self.view_files_btn._fg = C["text"]
            self.view_files_btn._draw(C["btn_bg"])
        else:
            self.view_dirs_btn._bg = C["btn_bg"]
            self.view_dirs_btn._fg = C["text"]
            self.view_dirs_btn._draw(C["btn_bg"])
            self.view_files_btn._bg = C["accent"]
            self.view_files_btn._fg = "#ffffff"
            self.view_files_btn._draw(C["accent"])
        self._render()

    # ── 事件处理 ──

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        node = self.item_map.get(sel[0])
        if not node:
            return
        if isinstance(node, DirNode):
            cmd = f'rm -rf "{node.path}"'
            info = (f"[DIR] {node.path}   {format_size(node.size)}"
                    f"   Files: {node.file_count}  SubDirs: {node.dir_count}")
        else:
            cmd = f'rm "{node.path}"'
            info = f"[FILE] {node.path}   {format_size(node.size)}   {node.extension or '?'}"
        self.detail_var.set(info)
        self.del_cmd_var.set(f"$ {cmd}")

    def _on_dblclick(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        node = self.item_map.get(sel[0])
        if not node:
            return
        if os.path.isdir(node.path):
            self.path_var.set(node.path)
            messagebox.showinfo("Info", f"Scan path set to:\n{node.path}")
        else:
            self.path_var.set(os.path.dirname(node.path))

    def _on_rightclick(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        self._ctx_sel = sel
        m = self.ctx_menu
        m.delete(0, END)

        iid = sel[0]
        node = self.item_map.get(iid)
        if node:
            if node.path in self._checked_paths:
                m.add_command(label="  Uncheck", command=lambda: self._toggle_check(iid))
            else:
                m.add_command(label="  Check", command=lambda: self._toggle_check(iid))

        m.add_command(label="  Check all on page", command=self._check_all_on_page)
        m.add_command(label="  Uncheck all on page", command=self._uncheck_all_on_page)
        m.add_separator()
        m.add_command(label="  Copy path", command=self._ctx_copy_path)
        m.add_command(label="  Copy parent dir", command=self._ctx_copy_dir)
        m.add_separator()
        m.add_command(label="  Scan this dir", command=lambda: self._ctx_scan(sel))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _ctx_copy_path(self):
        sel = self.tree.selection()
        if sel:
            node = self.item_map.get(sel[0])
            if node:
                self.root.clipboard_clear()
                self.root.clipboard_append(node.path)
                self.status_var.set(f"Copied: {node.path}")

    def _ctx_copy_dir(self):
        sel = self.tree.selection()
        if sel:
            node = self.item_map.get(sel[0])
            if node:
                d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
                self.root.clipboard_clear()
                self.root.clipboard_append(d)
                self.status_var.set(f"Copied: {d}")

    def _ctx_scan(self, sel):
        node = self.item_map.get(sel[0])
        if node:
            d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
            self.path_var.set(d)
            self._start_scan()

    # ── 勾选操作 ──

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region not in ('cell', 'heading'):
            return
        col = self.tree.identify_column(event.x)
        if col == '#1':
            iid = self.tree.identify_row(event.y)
            if iid:
                self._toggle_check(iid)
                return "break"

    def _toggle_check(self, iid):
        node = self.item_map.get(iid)
        if not node:
            return
        if node.path in self._checked_paths:
            self._checked_paths.discard(node.path)
        else:
            self._checked_paths.add(node.path)
        self._update_row_check(iid, node.path)
        self._update_check_count()

    def _update_row_check(self, iid, path):
        checked = path in self._checked_paths
        ck = "[x]" if checked else "[ ]"
        vals = list(self.tree.item(iid, 'values'))
        vals[0] = ck
        self.tree.item(iid, values=vals)
        old_tags = self.tree.item(iid, 'tags')
        if old_tags:
            base = old_tags[0].replace('_checked', '')
            new_tag = f'{base}_checked' if checked else base
            self.tree.item(iid, tags=(new_tag,))

    def _update_check_count(self):
        count = len(self._checked_paths)
        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        if count > 0:
            self.tree_title.config(
                text=f"{vlabel} ({self._total_items:,})  |  Checked: {count}")
        else:
            self.tree_title.config(text=f"{vlabel} ({self._total_items:,})")

    def _check_all_on_page(self):
        for iid in self.tree.get_children():
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.add(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _uncheck_all_on_page(self):
        for iid in self.tree.get_children():
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.discard(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _clear_all_checks(self):
        self._checked_paths.clear()
        self._render()

    # ── 删除 ──

    def _delete_checked(self):
        if not self._checked_paths:
            InfoDialog(self.root, "Info",
                       "No items checked.\nClick the checkbox column to select items.")
            return

        nodes = []
        all_nodes = list(self.result.all_dirs) + list(self.result.all_files) if self.result else []
        for n in all_nodes:
            if n.path in self._checked_paths:
                nodes.append(n)

        if not nodes:
            self._checked_paths.clear()
            return

        count = len(nodes)
        total_size = sum(n.size for n in nodes)
        dir_count = sum(1 for n in nodes if isinstance(n, DirNode))
        file_count = count - dir_count

        summary = (f"{count} items: {file_count} files, {dir_count} dirs, "
                   f"total {format_size(total_size)}")

        items = []
        for n in nodes:
            lbl = "DIR" if isinstance(n, DirNode) else "FILE"
            items.append((lbl, (n.path, format_size(n.size))))

        dlg = ConfirmDialog(self.root, "Confirm Delete", summary, items,
                             confirm_text=f"Delete {count}")
        if not dlg.result:
            return

        self._batch_delete_nodes(nodes)

    def _batch_delete_nodes(self, nodes):
        if not nodes:
            return

        safe_nodes = []
        blocked = []
        scan_root = os.path.realpath(self.scan_path) if self.scan_path else ""

        for node in nodes:
            target = os.path.realpath(node.path)
            if not scan_root:
                blocked.append((node.path, "No scan path set"))
            elif target == scan_root:
                blocked.append((node.path, "Cannot delete scan root itself"))
            elif not target.startswith(scan_root + os.sep) and target != scan_root:
                blocked.append((node.path, f"Outside scan path: {scan_root}"))
            else:
                safe_nodes.append(node)

        if blocked:
            blocked_msg = "\n".join(f"  {p}: {r}" for p, r in blocked[:10])
            if len(blocked) > 10:
                blocked_msg += f"\n  ... and {len(blocked) - 10} more"
            InfoDialog(self.root, "Security Check Failed",
                       f"{len(blocked)} item(s) blocked for safety:\n\n{blocked_msg}",
                       msg_color=C["red"])
            if not safe_nodes:
                return

        total = len(safe_nodes)
        deleted = 0
        errors = []

        self._del_btn.config(state='disabled')

        for i, node in enumerate(safe_nodes):
            try:
                if isinstance(node, DirNode):
                    shutil.rmtree(node.path, ignore_errors=False)
                else:
                    os.remove(node.path)
                deleted += 1
                self._checked_paths.discard(node.path)
            except Exception as e:
                errors.append(f"{node.path}: {e}")

            if (i + 1) % 50 == 0:
                self.status_var.set(f"Deleting... {i + 1}/{total}")
                self.root.update_idletasks()

        self._del_btn.config(state='normal')

        blocked_count = len(blocked)
        summary_parts = [f"Deleted: {deleted}/{total}"]
        if errors:
            summary_parts.append(f"Failed: {len(errors)}")
        if blocked_count:
            summary_parts.append(f"Blocked: {blocked_count}")

        if errors:
            err_detail = "\n".join(errors[:15])
            InfoDialog(self.root, "Partial Failure",
                       ", ".join(summary_parts) + "\n\n" + err_detail,
                       msg_color=C["orange"])
        else:
            InfoDialog(self.root, "Done", ", ".join(summary_parts),
                       msg_color=C["green"])

        self.status_var.set(
            f"Deleted {deleted}/{total}" +
            (f", failed {len(errors)}" if errors else "") +
            (f", blocked {blocked_count}" if blocked_count else ""))
        self._page = 0
        self._render()

    # ── 导出 ──

    def _export(self, fmt):
        if not self.result:
            messagebox.showwarning("Warning", "Please scan first")
            return
        r = self.result
        ext = "json" if fmt == "json" else "csv"
        path = filedialog.asksaveasfilename(
            title="Export", defaultextension=f".{ext}",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")],
            initialfile=f"disk_scan.{ext}")
        if not path:
            return
        try:
            if fmt == "json":
                def to_dict(n):
                    b = {"name": n.name, "path": n.path, "size": n.size,
                         "size_human": format_size(n.size), "modified": fmt_time(n.modified)}
                    if isinstance(n, FileNode):
                        b["type"] = "file"; b["extension"] = n.extension
                    else:
                        b["type"] = "directory"
                        b["file_count"] = n.file_count; b["dir_count"] = n.dir_count
                    return b
                data = {
                    "summary": {"total_size": r.total_size,
                                 "total_size_human": format_size(r.total_size),
                                 "total_files": r.total_files, "total_dirs": r.total_dirs},
                    "directories": [to_dict(d) for d in sort_nodes(r.all_dirs, "size-desc")],
                    "files": [to_dict(f) for f in sort_nodes(r.all_files, "size-desc")],
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Type", "Name", "Path", "Size(bytes)", "Size", "Modified"])
                    for n in sort_nodes(r.all_dirs, "size-desc"):
                        w.writerow(["Dir", n.name, n.path, n.size, format_size(n.size), fmt_time(n.modified)])
                    for n in sort_nodes(r.all_files, "size-desc"):
                        w.writerow(["File", n.name, n.path, n.size, format_size(n.size), fmt_time(n.modified)])
            messagebox.showinfo("Export OK", f"Saved to:\n{path}")
            self.status_var.set(f"Exported: {path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _clear_tree(self):
        for c in self.tree.get_children():
            self.tree.delete(c)
        self.item_map.clear()
        self._checked_paths.clear()

