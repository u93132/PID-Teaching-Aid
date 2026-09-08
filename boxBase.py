# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk


class ToolTip:
    # Hover hint for a widget: shows after a short delay, hides on
    # leave or click
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text   = text
        self.delay  = delay
        self.tip    = None
        self.after_id = None
        widget.bind('<Enter>', self.schedule)
        widget.bind('<Leave>', self.hide)
        widget.bind('<ButtonPress>', self.hide)

    def schedule(self, event=None):
        self.after_id = self.widget.after(self.delay, self.show)

    def show(self):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)   # no window frame
        self.tip.wm_geometry(f'+{x}+{y}')
        tk.Label(self.tip, text=self.text, bg='lightyellow',
                 relief='solid', borderwidth=1, padx=4).pack()

    def hide(self, event=None):
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class SliderBox:
    # One gain control: a label row, then [-] [slider] [+] on one
    # line. The +/- buttons nudge by 1% of the range; every value
    # change (drag, nudge, or set) fires `command` through the
    # Scale's own callback, so there is a single notification path
    def __init__(self, parent, text, from_, to, initial, command):
        self.label = ttk.Label(parent, text=text)
        self.label.pack(anchor='w', pady=(10, 0))
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill='x', pady=5)

        step = (to - from_) * 0.01
        self.MinusButton = tk.Button(self.frame, text='-', width=2,
                                     command=lambda: self.Step(-step))
        self.MinusButton .grid(row=0, column=0, padx=2)
        self.Scale = ttk.Scale(self.frame, from_=from_, to=to,
                               orient='horizontal',
                               command=lambda x: command())
        self.Scale.set(initial)
        self.Scale .grid(row=0, column=1, sticky='ew', padx=2)
        self.frame.grid_columnconfigure(1, weight=1)
        self.PlusButton = tk.Button(self.frame, text='+', width=2,
                                    command=lambda: self.Step(step))
        self.PlusButton .grid(row=0, column=2, padx=2)

    def get(self):
        return float(self.Scale.get())

    def set(self, value):
        self.Scale.set(value)

    def Step(self, delta):
        lo = float(self.Scale.cget('from'))
        hi = float(self.Scale.cget('to'))
        self.Scale.set(min(hi, max(lo, self.get() + delta)))

    def SetState(self, enabled):
        s = 'normal' if enabled else 'disabled'
        self.Scale.state(['!disabled'] if enabled else ['disabled'])
        self.MinusButton.config(state=s)
        self.PlusButton .config(state=s)
