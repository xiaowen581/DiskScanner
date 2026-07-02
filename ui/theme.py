#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme.py — 公共设计系统：颜色、字体、自定义组件、对话框
"""

import os
import sys
import platform
import subprocess
import tkinter.font as tkfont
from tkinter import (
    ttk, Frame, Label, Canvas, Scrollbar, Toplevel,
    VERTICAL, LEFT, RIGHT, BOTH, X, Y, END, E, W, FLAT,
)


# ── 检测中文字体 ──

def _detect_font():
    try:
        r = subprocess.run(['fc-list', ':lang=zh', 'family'],
                           capture_output=True, text=True, timeout=3)
        for name in ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei"):
            if name in r.stdout:
                return name
    except Exception:
        pass
    return "sans-serif"

_CN = _detect_font()


# ── 调色板 — 现代深色 (参考 GitHub Dark / VS Code) ──

C = {
    "bg":         "#0d1117",
    "surface":    "#161b22",
    "surface2":   "#1c2128",
    "border":     "#30363d",
    "border2":    "#21262d",
    "input_bg":   "#0d1117",
    "text":       "#e6edf3",
    "text2":      "#8b949e",
    "text3":      "#484f58",
    "accent":     "#58a6ff",
    "green":      "#3fb950",
    "red":        "#f85149",
    "orange":     "#d29922",
    "purple":     "#bc8cff",
    "cyan":       "#79c0ff",
    "tree_bg":    "#0d1117",
    "tree_row1":  "#0d1117",
    "tree_row2":  "#161b22",
    "tree_head":  "#161b22",
    "tree_sel":   "#1f6feb33",
    "btn_bg":     "#21262d",
    "btn_hover":  "#30363d",
}

# ── 字体 ──

F_TITLE   = (_CN, 16, "bold")
F_SUB     = (_CN, 10)
F_BODY    = (_CN, 10)
F_SMALL   = (_CN, 9)
F_TINY    = (_CN, 8)
F_BIG     = (_CN, 20, "bold")
F_STAT    = (_CN, 13, "bold")
F_MONO    = ("Consolas", 10) if platform.system() == "Windows" else ("Monospace", 10)
F_BTN     = (_CN, 9, "bold")


# ══════════════════════════════════════════════════════════
#  自定义按钮 (Canvas 实现圆角 + 悬停效果)
# ══════════════════════════════════════════════════════════

class RoundButton(Canvas):
    """带圆角和悬停效果的按钮"""
    def __init__(self, parent, text, command, bg=None, fg=None,
                 hover_bg=None, radius=6, padx=14, pady=5, font=F_BTN, **kw):
        self._bg = bg or C["btn_bg"]
        self._fg = fg or C["text"]
        self._hover = hover_bg or C["btn_hover"]
        self._cmd = command
        self._radius = radius
        self._text = text
        self._font = font

        try:
            tf = tkfont.Font(font=font)
            tw = tf.measure(text)
            th = tf.metrics("linespace")
        except Exception:
            tw = len(text) * 8
            th = 14

        w = int(tw + padx * 2)
        h = int(th + pady * 2)
        self._bw, self._bh = w, h

        super().__init__(parent, width=w, height=h,
                         bg=parent.cget("bg"), highlightthickness=0, **kw)
        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._hover))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())

    def _draw(self, fill):
        self.delete("all")
        r, w, h = self._radius, self._bw, self._bh
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=fill, outline="")
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=fill, outline="")
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=fill, outline="")
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=fill, outline="")
        self.create_rectangle(r, 0, w-r, h, fill=fill, outline="")
        self.create_rectangle(0, r, w, h-r, fill=fill, outline="")
        self.create_text(w//2, h//2, text=self._text, fill=self._fg, font=self._font)

    def config(self, bg=None, fg=None, **kw):
        if bg:
            self._bg = bg
            self._draw(self._bg)
        if fg:
            self._fg = fg
            self._draw(self._bg)


# ══════════════════════════════════════════════════════════
#  统计卡片
# ══════════════════════════════════════════════════════════

class StatCard(Frame):
    def __init__(self, parent, label, color=C["text"], **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._val = Label(self, text="--", bg=C["surface"], fg=color,
                          font=F_BIG, anchor=W)
        self._val.pack(anchor=W, padx=14, pady=(10, 0))
        self._lbl = Label(self, text=label, bg=C["surface"], fg=C["text2"],
                          font=F_SMALL, anchor=W)
        self._lbl.pack(anchor=W, padx=14, pady=(0, 10))

    def set_value(self, val):
        self._val.config(text=val)


# ══════════════════════════════════════════════════════════
#  自定义对话框
# ══════════════════════════════════════════════════════════

# 测试模式：设为 True 时对话框自动跳过，不弹窗
_DIALOG_AUTO_DISMISS = False


class ConfirmDialog:
    """暗色主题的确认对话框"""

    def __init__(self, parent, title, summary, items, confirm_text="Delete",
                 confirm_bg="#da3633", confirm_hover="#f85149"):
        if _DIALOG_AUTO_DISMISS:
            self.result = True
            self.win = None
            return

        self.result = False
        self.win = Toplevel(parent)
        self.win.title(title)
        self.win.geometry("700x520")
        self.win.minsize(500, 380)
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        try:
            self.win.grab_set()
        except Exception:
            pass

        hdr = Frame(self.win, bg=C["surface"], padx=20, pady=14)
        hdr.pack(fill=X)
        Label(hdr, text=title, bg=C["surface"], fg=C["red"],
              font=(_CN, 14, "bold")).pack(anchor=W)
        Label(hdr, text=summary, bg=C["surface"], fg=C["text2"],
              font=F_SMALL, justify=LEFT, wraplength=640).pack(anchor=W, pady=(6, 0))

        list_frame = Frame(self.win, bg=C["bg"], padx=16, pady=8)
        list_frame.pack(fill=BOTH, expand=True)

        cols = ("type", "path", "size")
        tree = ttk.Treeview(list_frame, columns=cols, show='headings',
                             style='Scan.Treeview')
        tree.heading("type", text="Type")
        tree.heading("path", text="Path")
        tree.heading("size", text="Size")
        tree.column("type", width=60, anchor='center', minwidth=50)
        tree.column("path", width=440, minwidth=200)
        tree.column("size", width=100, anchor=E, minwidth=70)

        ysb = Scrollbar(list_frame, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        ysb.pack(side=RIGHT, fill=Y)

        for i, (lbl, detail) in enumerate(items):
            tag = 'odd' if i % 2 else 'even'
            tree.insert('', END, values=(lbl, detail[0], detail[1]), tags=(tag,))
        tree.tag_configure('odd', background=C["tree_row1"])
        tree.tag_configure('even', background=C["tree_row2"])

        btn_bar = Frame(self.win, bg=C["surface"], padx=20, pady=14)
        btn_bar.pack(fill=X, side=BOTTOM)

        Label(btn_bar, text="This cannot be undone!",
              bg=C["surface"], fg=C["text3"], font=F_SMALL).pack(side=LEFT)

        cancel_btn = RoundButton(btn_bar, text="Cancel",
                                  command=self._on_cancel,
                                  bg=C["btn_bg"], fg=C["text"])
        cancel_btn.pack(side=RIGHT, padx=(8, 0))

        confirm_btn = RoundButton(btn_bar, text=confirm_text,
                                   command=self._on_confirm,
                                   bg=confirm_bg, fg="#ffffff",
                                   hover_bg=confirm_hover)
        confirm_btn.pack(side=RIGHT)

        self.win.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        x = px + (pw - 700) // 2
        y = py + (ph - 520) // 2
        self.win.geometry(f"+{x}+{y}")

        self.win.bind('<Escape>', lambda e: self._on_cancel())

        try:
            self.win.wait_window()
        except Exception:
            self.result = False

    def _on_confirm(self):
        self.result = True
        self.win.destroy()

    def _on_cancel(self):
        self.result = False
        self.win.destroy()


class InfoDialog:
    """暗色主题信息对话框"""

    def __init__(self, parent, title, message, msg_color=None):
        if _DIALOG_AUTO_DISMISS:
            self.win = None
            return

        self.win = Toplevel(parent)
        self.win.title(title)
        self.win.geometry("480x200")
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        try:
            self.win.grab_set()
        except Exception:
            pass

        body = Frame(self.win, bg=C["bg"], padx=24, pady=20)
        body.pack(fill=BOTH, expand=True)

        Label(body, text=title, bg=C["bg"],
              fg=msg_color or C["accent"],
              font=(_CN, 13, "bold")).pack(anchor=W)
        Label(body, text=message, bg=C["bg"], fg=C["text"],
              font=F_BODY, justify=LEFT, wraplength=420).pack(anchor=W, pady=(10, 0))

        btn_bar = Frame(self.win, bg=C["surface"], padx=20, pady=12)
        btn_bar.pack(fill=X, side=BOTTOM)
        ok_btn = RoundButton(btn_bar, text="OK", command=self._close,
                              bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff")
        ok_btn.pack(side=RIGHT)

        self.win.update_idletasks()
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - 480) // 2
        y = py + (ph - 200) // 2
        self.win.geometry(f"+{x}+{y}")
        self.win.bind('<Escape>', lambda e: self._close())
        self.win.bind('<Return>', lambda e: self._close())
        try:
            self.win.wait_window()
        except Exception:
            pass

    def _close(self):
        self.win.destroy()


# ══════════════════════════════════════════════════════════
#  ttk 样式初始化
# ══════════════════════════════════════════════════════════

def setup_styles(style):
    """配置所有 ttk 样式 (传入 ttk.Style 实例)"""
    s = style
    c = C

    # Scanner Treeview
    s.configure('Scan.Treeview',
                 background=c["tree_bg"], foreground=c["text"],
                 fieldbackground=c["tree_bg"], font=F_BODY,
                 rowheight=28, borderwidth=0)
    s.configure('Scan.Treeview.Heading',
                 background=c["tree_head"], foreground=c["text2"],
                 font=F_BTN, relief='flat', padding=(8, 5))
    s.map('Scan.Treeview',
          background=[('selected', c["tree_sel"])],
          foreground=[('selected', c["accent"])])

    # Docker Treeview
    s.configure('Docker.Treeview',
                 background=c["tree_bg"], foreground=c["text"],
                 fieldbackground=c["tree_bg"], font=F_BODY,
                 rowheight=28, borderwidth=0)
    s.configure('Docker.Treeview.Heading',
                 background=c["tree_head"], foreground=c["text2"],
                 font=F_BTN, relief='flat', padding=(8, 5))
    s.map('Docker.Treeview',
          background=[('selected', c["tree_sel"])],
          foreground=[('selected', c["accent"])])

    # Progressbar
    s.configure('Scan.Horizontal.TProgressbar',
                 troughcolor=c["surface"], background=c["accent"],
                 borderwidth=0, thickness=4)

    # Separator
    s.configure('Dark.TSeparator', background=c["border"])

    # Notebook (主标签页)
    s.configure('Dark.TNotebook', background=c["bg"], borderwidth=0)
    s.configure('Dark.TNotebook.Tab',
                 background=c["surface"], foreground=c["text2"],
                 padding=[16, 8], font=F_BTN)
    s.map('Dark.TNotebook.Tab',
          background=[('selected', c["bg"])],
          foreground=[('selected', c["accent"])])

    # Sub-Notebook (Docker 子标签页)
    s.configure('Sub.TNotebook', background=c["bg"], borderwidth=0)
    s.configure('Sub.TNotebook.Tab',
                 background=c["surface2"], foreground=c["text2"],
                 padding=[12, 6], font=F_SMALL)
    s.map('Sub.TNotebook.Tab',
          background=[('selected', c["bg"])],
          foreground=[('selected', c["cyan"])])


# ══════════════════════════════════════════════════════════
#  时间格式化工具函数
# ══════════════════════════════════════════════════════════

def fmt_time(ts):
    if not ts or ts == 0:
        return "N/A"
    try:
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "N/A"
