#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_base.py — Docker tab 基类，提供 Treeview + checkbox 通用逻辑
"""

from tkinter import (
    ttk, Frame, Label, StringVar, Scrollbar,
    VERTICAL, HORIZONTAL, LEFT, RIGHT, BOTH, X, Y, END, W, E, FLAT,
)
from ui.theme import (
    C, F_SMALL, F_TINY, F_BTN,
    RoundButton, ConfirmDialog, InfoDialog,
)


class DockerTabBase(Frame):
    """Base class for Docker management tabs."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.root = app  # 主 Tk 窗口
        self._checked = set()
        self.item_map = {}
        self._build()

    def _build(self):
        outer = Frame(self, bg=C["bg"])
        outer.pack(fill=BOTH, expand=True, padx=16, pady=12)

        tb = Frame(outer, bg=C["bg"])
        tb.pack(fill=X, pady=(0, 6))
        self._build_toolbar(tb)

        wrap = Frame(outer, bg=C["border"], bd=1, relief=FLAT)
        wrap.pack(fill=BOTH, expand=True, pady=(0, 6))
        inner = Frame(wrap, bg=C["tree_bg"], padx=1, pady=1)
        inner.pack(fill=BOTH, expand=True)

        ysb = Scrollbar(inner, orient=VERTICAL)
        xsb = Scrollbar(inner, orient=HORIZONTAL)
        self.tree = ttk.Treeview(inner, style='Docker.Treeview',
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

        sf = Frame(outer, bg=C["bg"])
        sf.pack(fill=X)
        self.status_var = StringVar(value="Ready")
        Label(sf, textvariable=self.status_var, bg=C["bg"], fg=C["text3"],
              font=F_TINY, anchor=W).pack(side=LEFT)

    def _build_toolbar(self, parent):
        """Override in subclass."""
        pass

    def load(self):
        """Override in subclass to load data."""
        pass

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
        if iid in self._checked:
            self._checked.discard(iid)
        else:
            self._checked.add(iid)
        checked = iid in self._checked
        ck = "[x]" if checked else "[ ]"
        vals = list(self.tree.item(iid, 'values'))
        vals[0] = ck
        self.tree.item(iid, values=vals)
        old_tags = self.tree.item(iid, 'tags')
        if old_tags:
            base = old_tags[0].replace('_checked', '')
            new_tag = f'{base}_checked' if checked else base
            self.tree.item(iid, tags=(new_tag,))
        self._update_check_count()

    def _update_check_count(self):
        """Override in subclass."""
        pass

    def _check_all(self):
        for iid in self.tree.get_children():
            if iid not in self._checked:
                self._toggle_check(iid)
        self._update_check_count()

    def _clear_checks(self):
        self._checked.clear()
        self._reload_rows()

    def _make_btn(self, parent, text, cmd, **kw):
        return RoundButton(parent, text=text, command=cmd,
                            bg=kw.pop('bg', C["btn_bg"]),
                            fg=kw.pop('fg', C["text"]),
                            hover_bg=kw.pop('hover_bg', C["btn_hover"]),
                            padx=kw.pop('padx', 10), **kw)

    def _setup_columns(self, cols, widths, anchors=None, headings=None):
        self.tree.config(columns=cols)
        anchors = anchors or {}
        headings = headings or {}
        for c in cols:
            self.tree.heading(c, text=headings.get(c, c))
            self.tree.column(c, width=widths.get(c, 120),
                             anchor=anchors.get(c, W),
                             minwidth=30)

    def _clear_tree(self):
        for c in self.tree.get_children():
            self.tree.delete(c)
        self.item_map.clear()
        self._checked.clear()

    def _insert_row(self, iid, values, idx):
        tag = 'odd' if idx % 2 else 'even'
        self.tree.insert('', END, iid=iid, values=values, tags=(tag,))
        self.tree.tag_configure('odd', background=C["tree_row1"])
        self.tree.tag_configure('even', background=C["tree_row2"])
        self.tree.tag_configure('odd_checked', background="#1a2a40")
        self.tree.tag_configure('even_checked', background="#162538")

    def _show_result(self, title, results):
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        msg = f"Success: {ok}, Failed: {fail}"
        if fail:
            err_details = "\n".join(
                r.message for r in results if not r.success
            )[:500]
            InfoDialog(self.root, title, msg + "\n\n" + err_details,
                       msg_color=C["orange"])
        else:
            InfoDialog(self.root, title, msg,
                       msg_color=C["green"])
