#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESTROYER // UI module
======================
Cinematic 2050 cyberpunk command-center interface (tkinter + custom Canvas).
"""
from __future__ import annotations

import math
import os
import queue
import random
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import font as tkfont
from tkinter import messagebox, simpledialog
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

OPERATOR = "Huzaifa Choudhary"
MODEL = "glm-4.5-flash"
PROVIDER_LABEL = "Z.AI"

def configure(operator: str | None = None, model: str | None = None,
              provider_label: str | None = None) -> None:
    global OPERATOR, MODEL, PROVIDER_LABEL
    if operator:
        OPERATOR = operator
    if model:
        MODEL = model
    if provider_label:
        PROVIDER_LABEL = provider_label

BG = "#050d1a"
PANEL = "#071426"
CYAN = "#00ffcc"
MAGENTA = "#ff00ff"
BLUE = "#2f9bff"
AMBER = "#ffcc00"
RED = "#ff3355"
WHITE = "#ffffff"
DIMTEXT = "#4f8fa0"
BODYTEXT = "#d4fff5"

MONO = "Consolas"
DISPLAY = "Consolas"

STATE_STYLE = {
    "IDLE":      {"color": CYAN,    "amp": 0.14, "var": 0.05, "spin": 0.55, "wave": 2.8,  "dir": 1,  "sub": "STANDBY // AWAITING INPUT"},
    "LISTENING": {"color": BLUE,    "amp": 0.30, "var": 0.30, "spin": 1.00, "wave": 0.90, "dir": -1, "sub": "AUDIO INTAKE ACTIVE"},
    "THINKING":  {"color": MAGENTA, "amp": 0.35, "var": 0.15, "spin": 2.60, "wave": 0.45, "dir": 1,  "sub": "NEURAL INFERENCE RUNNING"},
    "SPEAKING":  {"color": AMBER,   "amp": 0.45, "var": 0.55, "spin": 1.20, "wave": 0.55, "dir": 1,  "sub": "VOICE SYNTHESIS ONLINE"},
}
STATUS_COLORS = {
    "ONLINE": CYAN, "STANDBY": AMBER, "CONNECTING": AMBER,
    "OFFLINE": RED, "ERROR": RED, "NO KEY": RED,
}

def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def blend(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def dim(c: str, f: float) -> str:
    return blend(BG, c, f)

class Telemetry:
    def __init__(self) -> None:
        self.start = time.time()
        self.cpu = self.mem = self.disk = 0.0
        self.down = self.up = 0.0
        self.hist: deque = deque([0.0] * 60, maxlen=60)
        self.simulated = psutil is None
        self._last_net = None
        self._sim = 28.0
        if psutil:
            try:
                psutil.cpu_percent(None)
            except Exception:
                pass

    def sample(self) -> None:
        if psutil:
            try:
                self.cpu = psutil.cpu_percent(None)
                self.mem = psutil.virtual_memory().percent
                self.disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
                n = psutil.net_io_counters()
                now = time.time()
                if self._last_net:
                    dt = max(now - self._last_net[0], 1e-3)
                    self.down = (n.bytes_recv - self._last_net[1]) / dt / 1024
                    self.up = (n.bytes_sent - self._last_net[2]) / dt / 1024
                self._last_net = (now, n.bytes_recv, n.bytes_sent)
            except Exception:
                pass
        else:
            self._sim = max(5.0, min(95.0, self._sim + random.uniform(-9, 9)))
            self.cpu = self._sim
            self.mem = 42 + 6 * math.sin(time.time() / 9)
            self.disk = 57.0
            self.down = max(0.0, random.gauss(120, 80))
            self.up = max(0.0, random.gauss(30, 20))
        self.hist.append(self.cpu)

    @property
    def uptime(self) -> str:
        s = int(time.time() - self.start)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"

class Panel(tk.Frame):
    def __init__(self, parent, title: str, color: str = CYAN) -> None:
        super().__init__(parent, bg=BG, highlightthickness=1,
                         highlightbackground=dim(color, 0.65), highlightcolor=color)
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=f"▌{title}", fg=color, bg=BG, anchor="w",
                 font=(MONO, 9, "bold")).pack(side="left", padx=6, pady=(3, 2))
        tk.Label(head, text="◢◢◢", fg=dim(color, 0.5), bg=BG,
                 font=(MONO, 8)).pack(side="right", padx=6)
        tk.Frame(self, bg=dim(color, 0.5), height=1).pack(fill="x")
        self.body = tk.Frame(self, bg=PANEL)
        self.body.pack(fill="both", expand=True)

class NeonButton(tk.Label):
    def __init__(self, parent, text: str, command, color: str = CYAN, width: int = 13) -> None:
        super().__init__(parent, text=text, fg=color, bg=BG, width=width, padx=8, pady=7,
                         font=(MONO, 10, "bold"), cursor="hand2",
                         highlightthickness=1, highlightbackground=dim(color, 0.6))
        self.color = color
        self.command = command
        self.bind("<Enter>", lambda _e: self.configure(bg=blend(BG, self.color, 0.2), fg=WHITE))
        self.bind("<Leave>", lambda _e: self.configure(bg=BG, fg=self.color))
        self.bind("<ButtonRelease-1>", lambda _e: self.command())

    def set(self, text: str, color: str) -> None:
        self.color = color
        self.configure(text=text, fg=color, highlightbackground=dim(color, 0.6))

class TerminalPanel(tk.Frame):
    TAGS = {"info": CYAN, "sys": "#4fa3c7", "warn": AMBER, "error": RED,
            "user": "#7dffb0", "ai": "#ff7bff", "ambient": "#2b6f78", "ts": "#1f5560"}

    def __init__(self, parent) -> None:
        super().__init__(parent, bg=PANEL)
        self.text = tk.Text(self, bg="#030a14", fg=CYAN, font=(MONO, 9), wrap="word",
                            relief="flat", bd=0, padx=8, pady=6, highlightthickness=0,
                            state="disabled", cursor="arrow", width=46, height=10,
                            insertwidth=0, spacing1=1)
        self.text.pack(fill="both", expand=True)
        for tag, colour in self.TAGS.items():
            self.text.tag_configure(tag, foreground=colour)

    def write(self, ts: str, level: str, msg: str) -> None:
        t = self.text
        t.configure(state="normal")
        t.insert("end", f"{ts} ", "ts")
        t.insert("end", msg + "\n", level if level in self.TAGS else "info")
        if int(t.index("end-1c").split(".")[0]) > 500:
            t.delete("1.0", "80.0")
        t.see("end")
        t.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

class ChatPanel(tk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent, bg=PANEL)
        self.text = tk.Text(self, bg="#030a14", fg=BODYTEXT, font=(MONO, 10), wrap="word",
                            relief="flat", bd=0, padx=8, pady=6, highlightthickness=0,
                            state="disabled", cursor="arrow", width=46, height=8,
                            insertwidth=0, spacing3=4)
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("user_lbl", foreground="#6fd8ff", font=(MONO, 10, "bold"))
        self.text.tag_configure("ai_lbl", foreground=MAGENTA, font=(MONO, 10, "bold"))
        self.text.tag_configure("body", foreground=BODYTEXT)

    def add(self, who: str, text: str) -> None:
        t = self.text
        t.configure(state="normal")
        if who == "user":
            t.insert("end", "MASTER ▸ ", "user_lbl")
        else:
            t.insert("end", "ZAYN ▸ ", "ai_lbl")
        t.insert("end", text + "\n\n", "body")
        t.see("end")
        t.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

class HeaderCanvas(tk.Canvas):
    def __init__(self, parent) -> None:
        super().__init__(parent, bg=BG, height=68, highlightthickness=0)
        self.glitch_until = 0.0
        self.bind("<Configure>", self._static)

    def _static(self, e) -> None:
        self.delete("static")
        w = e.width
        self.create_line(0, 66, w, 66, fill=dim(CYAN, 0.6), width=1, tags="static")
        self.create_line(0, 67, w * 0.35, 67, fill=MAGENTA, width=2, tags="static")
        self.create_line(w * 0.65, 67, w, 67, fill=MAGENTA, width=2, tags="static")

    def draw(self, t: float, state: str, color: str) -> None:
        self.delete("dyn")
        w = self.winfo_width()
        off = 2
        title = "D E S T R O Y E R"
        self.create_text(w / 2 + off, 28, text=title, fill=MAGENTA, font=(DISPLAY, 26, "bold"), tags="dyn")
        self.create_text(w / 2, 28, text=title, fill=CYAN, font=(DISPLAY, 26, "bold"), tags="dyn")
        self.create_text(w / 2, 54, fill=dim(CYAN, 0.6), font=(MONO, 8), tags="dyn",
                         text=f"NEURAL COMMAND CORE  //  BUILT BY MASTER {OPERATOR.upper()}")
        now = datetime.now()
        self.create_text(20, 24, text=now.strftime("%H:%M:%S"), anchor="w", fill=CYAN, font=(MONO, 17, "bold"), tags="dyn")
        self.create_text(20, 48, text=now.strftime("%a %d %b %Y").upper(), anchor="w", fill=dim(CYAN, 0.6), font=(MONO, 8), tags="dyn")
        
        x1, x0 = w - 20, w - 200
        self.create_rectangle(x0, 16, x1, 46, outline=color, width=2, tags="dyn")
        self.create_rectangle(x0 + 4, 20, x1 - 4, 42, outline=dim(color, 0.35), tags="dyn")
        blink = 1.0 if int(t * 2.5) % 2 == 0 else 0.35
        self.create_oval(x0 + 12, 26, x0 + 22, 36, fill=dim(color, blink), outline="", tags="dyn")
        self.create_text(x0 + 32, 31, text=state, anchor="w", fill=color, font=(MONO, 12, "bold"), tags="dyn")
        self.create_text(x1, 56, text="MODE", anchor="e", fill=dim(color, 0.5), font=(MONO, 7), tags="dyn")

class CoreCanvas(tk.Canvas):
    def __init__(self, parent) -> None:
        super().__init__(parent, bg=BG, highlightthickness=0)
        self.color = CYAN
        self.amp = 0.15
        self.spin = 0.55
        self.rot = 0.0
        self.sweep = 0.0
        self.waves: list = []
        self.next_wave = 0.0
        self.parts = [self._particle(i) for i in range(20)]
        self.bind("<Configure>", self._static)

    @staticmethod
    def _particle(i: int) -> dict:
        return {
            "rf": random.uniform(0.62, 1.6),
            "speed": random.choice([-1, 1]) * random.uniform(0.25, 0.9),
            "a": random.uniform(0, math.tau),
            "flat": random.uniform(0.35, 1.0),
            "tilt": random.uniform(0, math.pi),
            "size": random.uniform(2.0, 4.0),
            "accent": i % 3 == 0,
        }

    @staticmethod
    def _geom(w: float, h: float) -> tuple[float, float, float]:
        radius = min(w, h) * 0.28
        return w / 2, (h - 60) / 2 + 12, radius

    def _static(self, e) -> None:
        self.delete("static")
        w, h = e.width, e.height
        grid = dim(CYAN, 0.07)
        for x in range(0, w, 48):
            self.create_line(x, 0, x, h, fill=grid, tags="static")
        for y in range(0, h, 48):
            self.create_line(0, y, w, y, fill=grid, tags="static")
        cx, cy, r = self._geom(w, h)
        for f in (0.55, 1.0, 1.7):
            self.create_oval(cx - r * f, cy - r * f, cx + r * f, cy + r * f, outline=dim(CYAN, 0.12), tags="static")
        self.tag_lower("static")

    def draw(self, t: float, dt: float, state: str) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        if w < 160 or h < 160:
            return
        style = STATE_STYLE[state]
        k = min(1.0, dt * 5.0)
        self.color = blend(self.color, style["color"], k)
        col = self.color
        accent = MAGENTA if state != "THINKING" else CYAN

        wob = abs(math.sin(t * 11.0) * math.sin(t * 4.7) + 0.5 * math.sin(t * 19.0))
        target = style["amp"] + style["var"] * min(1.0, wob)
        self.amp += (target - self.amp) * min(1.0, dt * 8.0)
        amp = self.amp
        self.spin += (style["spin"] - self.spin) * k
        self.rot += dt * 60.0 * self.spin
        self.sweep = (self.sweep + dt * 90.0 * (0.6 + self.spin)) % 360

        self.delete("dyn")
        cx, cy, R = self._geom(w, h)
        c = self.create_oval

        for i in range(14):
            a = math.radians(self.sweep - i * 2.5)
            f = 1 - i / 14
            self.create_line(cx, cy, cx + math.cos(a) * R * 1.32, cy + math.sin(a) * R * 1.32,
                             fill=dim(col, 0.55 * f * f), width=2 if i == 0 else 1, tags="dyn")

        if t >= self.next_wave:
            self.waves.append((t, style["dir"], col))
            self.next_wave = t + style["wave"]
        alive = []
        for born, direction, wc in self.waves:
            life = (t - born) / 2.4
            if life >= 1.0:
                continue
            alive.append((born, direction, wc))
            p = life if direction > 0 else 1 - life
            r = R * (0.55 + 1.05 * p)
            c(cx - r, cy - r, cx + r, cy + r, outline=dim(wc, (1 - life) ** 1.5 * 0.9), width=2 if life < 0.5 else 1, tags="dyn")
        self.waves = alive

        ring_specs = ((1.30, 3, 3, 50, 0.50, False), (1.20, 1, 36, 4, -1.20, False), (1.08, 2, 5, 30, 1.60, True))
        for rf, width, segs, gap, speed, use_accent in ring_specs:
            r = R * rf
            step = 360.0 / segs
            rc = accent if use_accent else col
            for i in range(segs):
                self.create_arc(cx - r, cy - r, cx + r, cy + r, start=(self.rot * speed + i * step) % 360, extent=step - gap, style="arc", outline=rc, width=width, tags="dyn")

        for phase, wc, wd in ((0.0, col, 2), (1.7, accent, 1)):
            pts = []
            n = 140
            for i in range(n + 1):
                a = i / n * math.tau
                d = (math.sin(a * 5 + t * 4.0 + phase) + 0.6 * math.sin(a * 9 - t * 6.3 + phase) + 0.4 * math.sin(a * 3 + t * 2.3))
                r = R * 0.86 + R * 0.20 * amp * d
                pts += [cx + math.cos(a) * r, cy + math.sin(a) * r]
            self.create_line(*pts, fill=wc, width=wd, smooth=True, tags="dyn")

        for i in range(7):
            rr = R * 0.62 * (1 - i * 0.12) * (1 + 0.06 * amp * math.sin(t * 7 + i))
            c(cx - rr, cy - rr, cx + rr, cy + rr, fill=dim(col, 0.05 + 0.07 * i), outline=dim(col, 0.4) if i == 0 else "", tags="dyn")
        
        fsize = max(11, int(R * 0.12))
        self.create_text(cx, cy - 4, text=state, fill=blend(col, WHITE, 0.6), font=(DISPLAY, fsize, "bold"), tags="dyn")
        self.create_text(cx, cy + R * 0.17, text=style["sub"], fill=dim(col, 0.9), font=(MONO, 8), tags="dyn")

        if h > 420:
            nb = 56
            bw = min(w * 0.7, 720) / nb
            x0 = cx - nb * bw / 2
            yb = h - 24
            for i in range(nb):
                v = abs(math.sin(i * 0.55 + t * 5.0) * math.sin(i * 0.21 - t * 2.7))
                hgt = 3 + (0.15 + amp) * 58 * v
                self.create_rectangle(x0 + i * bw + 1, yb - hgt, x0 + (i + 1) * bw - 1, yb, fill=blend(col, MAGENTA, i / nb * 0.8), outline="", tags="dyn")

        ro = dim(col, 0.7)
        self.create_text(30, 30, anchor="nw", fill=ro, font=(MONO, 8), tags="dyn", justify="left", text=f"SYNC  {97 + 2.5 * math.sin(t):5.1f} %\nFREQ  {432 + 8 * math.sin(t * 1.3):5.1f} Hz")
        self.create_text(w - 30, 30, anchor="ne", fill=ro, font=(MONO, 8), tags="dyn", justify="right", text=f"CORE  {state}\nAMP   {amp * 100:03.0f}")

class DiagCanvas(tk.Canvas):
    def __init__(self, parent) -> None:
        super().__init__(parent, bg=PANEL, highlightthickness=0, width=300, height=300)

    def _bar(self, label: str, value: float, text: str, y: float, w: int) -> None:
        self.create_text(12, y, text=label, anchor="w", fill=DIMTEXT, font=(MONO, 8))
        self.create_text(w - 12, y, text=text, anchor="e", fill=BODYTEXT, font=(MONO, 8, "bold"))
        segs = 24
        x0, x1 = 12, w - 12
        sw = (x1 - x0) / segs
        filled = int(max(0.0, min(100.0, value)) / 100 * segs)
        for i in range(segs):
            c = RED if i / segs > 0.85 else blend(CYAN, MAGENTA, i / segs) if i < filled else dim(CYAN, 0.12)
            self.create_rectangle(x0 + i * sw + 1, y + 8, x0 + (i + 1) * sw - 1, y + 16, fill=c, outline="")

    def draw(self, tel: Telemetry, ctx: Any, t: float) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 100: return
        y = 14
        self._bar("CPU LOAD", tel.cpu, f"{tel.cpu:5.1f} %", y, w); y += 34
        self._bar("MEMORY", tel.mem, f"{tel.mem:5.1f} %", y, w); y += 34
        self._bar("STORAGE", tel.disk, f"{tel.disk:5.1f} %", y, w); y += 34
        self._bar("NET ▼ DOWN", tel.down / 10, f"{tel.down:7.1f} KB/s", y, w); y += 34
        self._bar("NET ▲ UP", tel.up / 10, f"{tel.up:7.1f} KB/s", y, w); y += 36

        if y + 70 < h:
            self.create_text(12, y, text="CPU HISTORY // 60s", anchor="w", fill=DIMTEXT, font=(MONO, 8))
            top, bot = y + 10, y + 62
            self.create_rectangle(12, top, w - 12, bot, outline=dim(CYAN, 0.3))
            hist = list(tel.hist)
            step = (w - 26) / max(1, (len(hist) - 1))
            pts = []
            for i, v in enumerate(hist):
                pts += [13 + i * step, bot - 2 - (bot - top - 4) * v / 100]
            if len(pts) >= 4:
                self.create_line(*pts, fill=CYAN, width=2)
            y += 78

        rows = [
            ("UPTIME", tel.uptime),
            ("THREADS", str(threading.active_count())),
            ("TELEMETRY", "SIMULATED" if tel.simulated else "LIVE // psutil"),
        ]
        for label, val in rows:
            if y + 12 > h: break
            self.create_text(12, y, text=label, anchor="w", fill=DIMTEXT, font=(MONO, 8))
            self.create_text(w - 12, y, text=val, anchor="e", fill=CYAN, font=(MONO, 8, "bold"))
            y += 18

class LinkCanvas(tk.Canvas):
    def __init__(self, parent) -> None:
        super().__init__(parent, bg=PANEL, highlightthickness=0, width=300, height=220)

    def draw(self, info: dict, st: Any, t: float) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 100: return
        status = info.get("status", "ONLINE")
        scol = STATUS_COLORS.get(status, AMBER)
        self.create_text(12, 14, text=f"{PROVIDER_LABEL} UPLINK", anchor="w", fill=DIMTEXT, font=(MONO, 8))
        self.create_text(12, 36, text=f"◉ {status}", anchor="w", fill=scol, font=(MONO, 15, "bold"))

        rows = [
            ("MODEL", MODEL),
            ("LATENCY", f"{info.get('latency', 120)} ms"),
            ("TOKENS USED", f"{info.get('tokens', 0)}"),
            ("MIC ARRAY", "ONLINE" if st.mic_enabled else "MUTED"),
            ("VOICE SYNTH", "ONLINE" if st.voice_enabled else "MUTED"),
            ("CHANNEL", "TLS // SECURED"),
        ]
        y = 66
        for label, val in rows:
            if y + 10 > h - 40: break
            self.create_text(12, y, text=label, anchor="w", fill=DIMTEXT, font=(MONO, 8))
            self.create_text(w - 12, y, text=val, anchor="e", fill=CYAN, font=(MONO, 8, "bold"))
            y += 17

class App:
    def __init__(self, root: tk.Tk, ctx: Any) -> None:
        self.root, self.ctx = root, ctx
        self.t0 = self.last = time.perf_counter()
        self.frame = 0
        self.shown_state = "IDLE"
        self.link_info = {"status": "ONLINE", "latency": 115, "tokens": 320}
        self.telemetry = Telemetry()
        self._next_sample = 0.0
        self._build()

    def _build(self) -> None:
        r = self.root
        r.configure(bg=BG)
        r.title("DESTROYER // Neural Command Core")
        r.geometry("1500x900")
        r.minsize(1150, 720)
        r.grid_columnconfigure(1, weight=1)
        r.grid_rowconfigure(1, weight=1)

        self.header = HeaderCanvas(r)
        self.header.grid(row=0, column=0, columnspan=3, sticky="ew")

        left = tk.Frame(r, bg=BG)
        left.grid(row=1, column=0, sticky="ns", padx=(10, 5), pady=6)
        left.grid_rowconfigure(0, weight=3)
        left.grid_rowconfigure(1, weight=2)
        p1 = Panel(left, "SYSTEM DIAGNOSTICS", CYAN)
        p1.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.diag = DiagCanvas(p1.body)
        self.diag.pack(fill="both", expand=True)
        p2 = Panel(left, "NEURAL LINK // SECURE", MAGENTA)
        p2.grid(row=1, column=0, sticky="nsew")
        self.link = LinkCanvas(p2.body)
        self.link.pack(fill="both", expand=True)

        pc = Panel(r, "CENTRAL CORE // LIVE", MAGENTA)
        pc.grid(row=1, column=1, sticky="nsew", padx=5, pady=6)
        self.core = CoreCanvas(pc.body)
        self.core.pack(fill="both", expand=True)

        right = tk.Frame(r, bg=BG)
        right.grid(row=1, column=2, sticky="ns", padx=(5, 10), pady=6)
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=2)
        pt = Panel(right, "TERMINAL FEED", CYAN)
        pt.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.terminal = TerminalPanel(pt.body)
        self.terminal.pack(fill="both", expand=True)
        pm = Panel(right, "COMMS // TRANSCRIPT", MAGENTA)
        pm.grid(row=1, column=0, sticky="nsew")
        self.chat = ChatPanel(pm.body)
        self.chat.pack(fill="both", expand=True)

        bar = tk.Frame(r, bg=BG)
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        tk.Label(bar, text="MASTER ▸", fg=MAGENTA, bg=BG, font=(MONO, 12, "bold")).pack(side="left", padx=(2, 8))
        self.entry = tk.Entry(bar, font=(MONO, 12), bg="#0a1f33", fg=CYAN, insertbackground=MAGENTA, relief="flat", highlightthickness=1, highlightbackground=dim(CYAN, 0.5), highlightcolor=MAGENTA)
        self.entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send())
        self.entry.focus_set()
        NeonButton(bar, "TRANSMIT", self.send, CYAN).pack(side="left", padx=3)
        self.btn_mic = NeonButton(bar, "MIC: ON", self.toggle_mic, CYAN)
        self.btn_mic.pack(side="left", padx=3)
        self.btn_voice = NeonButton(bar, "VOICE: ON", self.toggle_voice, CYAN)
        self.btn_voice.pack(side="left", padx=3)
        NeonButton(bar, "CLEAR", self.clear_all, MAGENTA, width=9).pack(side="left", padx=3)

    def send(self) -> None:
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.ctx.submit(text)

    def toggle_mic(self) -> None:
        st = self.ctx.state
        st.mic_enabled = not st.mic_enabled
        self.terminal.write(datetime.now().strftime("%H:%M:%S"), "sys", f"Audio intake {'ENGAGED' if st.mic_enabled else 'MUTED'}")

    def toggle_voice(self) -> None:
        st = self.ctx.state
        st.voice_enabled = not st.voice_enabled
        self.terminal.write(datetime.now().strftime("%H:%M:%S"), "sys", f"Voice synthesis {'ENGAGED' if st.voice_enabled else 'MUTED'}")

    def clear_all(self) -> None:
        self.terminal.clear()
        self.chat.clear()
        self.ctx.reset_memory.set()
        self.terminal.write(datetime.now().strftime("%H:%M:%S"), "sys", "Buffers cleared.")

    def start(self) -> None:
        self.terminal.write(datetime.now().strftime("%H:%M:%S"), "sys", f"INITIALIZING ZAYN NEURAL CORE v2050")
        self.terminal.write(datetime.now().strftime("%H:%M:%S"), "info", f"AUTHORIZED OPERATOR ▸ {OPERATOR.upper()}")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._tick()
        self._drain()

    def shutdown(self) -> None:
        self.ctx.stop.set()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _drain(self) -> None:
        try:
            for _ in range(50):
                ev = self.ctx.ui_q.get_nowait()
                if ev[0] == "log":
                    self.terminal.write(ev[1], ev[2], ev[3])
                elif ev[0] == "chat":
                    self.chat.add(ev[1], ev[2])
                elif ev[0] == "link":
                    self.link_info.update(ev[1])
                elif ev[0] == "quit":
                    self.shutdown()
                    return
        except queue.Empty:
            pass
        self.root.after(40, self._drain)

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.1, now - self.last)
        self.last = now
        t = now - self.t0
        state = self.ctx.state.current

        self.core.draw(t, dt, state)
        self.header.draw(t, state, self.core.color)

        self.frame = (self.frame + 1) % 4
        if self.frame == 0:
            self.diag.draw(self.telemetry, self.ctx, t)
            self.link.draw(self.link_info, self.ctx.state, t)

        if now >= self._next_sample:
            self.telemetry.sample()
            self._next_sample = now + 1.0

        self.root.after(33, self._tick)

def create_root() -> tk.Tk:
    return tk.Tk()

def launch(root: tk.Tk, ctx: Any) -> None:
    app = App(root, ctx)
    app.start()
    root.mainloop()