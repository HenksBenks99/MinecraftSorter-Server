#!/usr/bin/env python3
"""
ForgeModSearch GUI - "Server Mod Utilities". Riproduce al pixel UI/*.png:
pagina principale (scuro/chiaro) + modali Advanced Settings, Manual Override, Mod Analysis Report.
Solo tkinter: i widget sono disegnati su Canvas (angoli arrotondati), la finestra non ha cornice di sistema.
Usa analyze_modpack() cosi' com'e'.
"""

import ctypes
import json
import os
import queue
import shutil
import threading
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
import webbrowser
from contextlib import redirect_stdout
from pathlib import Path
from tkinter import filedialog, messagebox

import config
from separate_mods import analyze_modpack, normalize_mod_name

PREFS = Path.home() / '.forgemodsearch_gui.json'
W, H = 1289, 688  # dimensioni di Main_Page.png
# Colori letti dai pixel di Design_System.png / Main_Page*.png / Modal_*.png.
DARK = dict(bg='#1b2024', field='#14191d', ghost='#272c31', fg='#e1e2e2', title='#ffffff', fg_on='#e1e2e2', blue='#2b7fff', main='#1062ea',
            green='#22ef32', red='#e93636', close='#cd1515', orange='#e98136', line='#272c31')
LIGHT = dict(bg='#f3f3f3', field='#ffffff', ghost='#e8e8e8', fg='#000000', title='#000000', fg_on='#ffffff', blue='#1062ea', main='#1062ea',
             green='#21c82f', red='#cd1515', close='#cd1515', orange='#cd6215', line='#e8e8e8')
CATS = {  # categoria -> (scheda, etichetta riga, chiave colore)
    'server': ('Server-ready', '✓ Server', 'green'),
    'client': ('Client only', '✕ Client', 'red'),
    'unknown': ('To verify', '? Verify', 'orange'),
}
NAMES = {'input': 'Mod Folder', 'output': 'Server Pack Folder', 'compare': 'Compare Folder'}
OVERRIDE_BELOW = 60  # le mod con confidenza sotto questa soglia finiscono nell'override manuale

DARK_MODE, P, FN = False, LIGHT, {}


def is_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as k:
            return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 0
    except (ImportError, OSError):
        return False


def set_theme(dark):
    global DARK_MODE, P
    DARK_MODE, P = dark, DARK if dark else LIGHT


def init_fonts():
    """Tipografia del design system (px): Display 32 bold / 24, Text 16, Small 12. Le famiglie 'Variable' hanno un nome per ogni peso."""
    D, T, S = 'Segoe UI Variable Display', 'Segoe UI Variable Text', 'Segoe UI Variable Small'

    def f(fam, px, bold=False):
        return tkfont.Font(family=fam, size=-px, weight='bold' if bold else 'normal')
    FN.update(h1=f(D, 32, True), h2=f(D + ' Semib', 24), t24=f(D, 24), body=f(S + ' Light', 16), hint=f(S + ' Light', 16), bold=f(D, 16, True), semi=f(T + ' Semibold', 16),
              sub=f(S + ' Light', 16), small=f(S + ' Light', 12), report=f(S + ' Light', 12), icon=f('Segoe Fluent Icons', 20))


# ---------- logica (invariata, testata in test_gui.py) ----------
def category(r):  # stessa regola con cui l'app conta le statistiche
    return 'server' if r['action'] == 'COPY' else 'client' if r['side'] == 'client' else 'unknown'


def confidence(r):
    """shortcut: il backend non ha un punteggio, lo stimo dalla fonte della decisione; sostituire se arriva un punteggio reale."""
    if r['side'] == 'unknown':
        return 50
    return {'OVERRIDE': 100, 'FABRIC-ONLY': 95, 'BLACKLIST': 90, 'PARSER': 90, 'MODRINTH': 80, 'CURSEFORGE': 70}.get(r['reason'].split(':')[0], 50)


def jars(folder):
    return sorted(f.name for f in Path(folder).glob('*.jar'))


def _names(names):
    return '\n'.join(f'  - {n}' for n in names) or '  (none)'


def diff_report(a, b):
    """Confronto per nome file tra due cartelle. shortcut: niente versioni/contenuto JAR, aggiungerli se serve."""
    A, B = jars(a), jars(b)
    bar = '=' * 78
    return (f'{bar}\nMOD DIFFERENCE REPORT\nCompares the .jar file names of two folders\n{bar}\n\n'
            f'SUMMARY\n{"-" * 40}\nFolder 1: {a}\nFolder 2: {b}\n\nFolder 1 mods: {len(A)}\nFolder 2 mods: {len(B)}\n'
            f'Same mods (exact match): {len(set(A) & set(B))}\n\n'
            f'Unique to Folder 1 ({len(set(A) - set(B))} mods):\n{_names(sorted(set(A) - set(B)))}\n\n'
            f'Unique to Folder 2 ({len(set(B) - set(A))} mods):\n{_names(sorted(set(B) - set(A)))}\n\n{bar}\nEND OF REPORT\n{bar}')


def list_report(folder):
    """Elenco mod + conflitti = piu' file dello stesso mod (es. due versioni). Ritorna (testo, dati per il JSON)."""
    names, groups = jars(folder), {}
    for n in names:
        groups.setdefault(normalize_mod_name(Path(n).stem), []).append(n)
    conflicts = {k: v for k, v in groups.items() if k and len(v) > 1}
    bar = '=' * 78
    text = (f'{bar}\nMOD LIST\n{bar}\n\nFolder: {folder}\nTotal mods: {len(names)}\n\n{_names(names)}\n\n'
            f'POSSIBLE CONFLICTS - same mod, several files ({len(conflicts)}):\n'
            + ('\n'.join(f'  - {k}: {", ".join(v)}' for k, v in conflicts.items()) or '  (none)') + f'\n\n{bar}\nEND OF LIST\n{bar}')
    return text, {'folder': str(folder), 'total': len(names), 'mods': names, 'conflicts': conflicts}


def apply_manual(data, files, src, out, dry):
    """Promuove a server le mod 'unknown' scelte a mano: le copia e riallinea statistiche e report JSON."""
    st = data['stats']
    for r in data['results']:
        if r['file'] in files and r['side'] == 'unknown':
            r.update(side='server', action='COPY', reason='MANUAL: selected by user')
            st['unknown'] -= 1
            st['server'] += 1
            if not dry:
                shutil.copy2(src / r['file'], out / r['file'])
    if not dry:
        (out / 'separation_report.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


KEY_STATES = {  # stato chiave -> (testo, colore o None = neutro)
    'empty': ('Not set', None),
    'checking': ('Verification in progress', 'orange'),
    'ok': ('Valid and working', 'green'),
    'bad': ('Not valid', 'red'),
    'offline': ('Cannot verify (network)', 'orange'),
}
ENV_KEY = config.CURSEFORGE_API_KEY


def probe(key):
    """Verifica la chiave con una GET leggera. Solo 401/403 = non valida: un problema di rete non accusa la chiave."""
    req = urllib.request.Request(f'{config.CURSEFORGE_BASE_URL}/games/{config.CURSEFORGE_GAME_ID}',
                                 headers={'x-api-key': key, 'Accept': 'application/json', 'User-Agent': 'ForgeModSearch'})
    try:
        urllib.request.urlopen(req, timeout=10).close()
        return 'ok'
    except urllib.error.HTTPError as e:
        return 'bad' if e.code in (401, 403) else 'offline'
    except OSError:
        return 'offline'


class LineWriter:
    """Inoltra a una queue ogni riga stampata da analyze_modpack."""

    def __init__(self, q):
        self.q, self.buf = q, ''

    def write(self, s):
        *lines, self.buf = (self.buf + s).split('\n')
        for line in lines:
            self.q.put(('line', line))

    def flush(self):
        pass


# ---------- disegno ----------
def mix(a, b, t):
    ca, cb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def rrect(c, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def text(c, x, base, s, font, fill, anchor='w', **kw):
    """Testo posizionato per BASELINE (come nel design): anchor w/e/c = lato orizzontale."""
    return c.create_text(x, base + font.metrics('descent'), text=s, font=font, fill=fill, anchor={'w': 'sw', 'e': 'se', 'c': 's'}[anchor], **kw)


def win_api(win, w, h, taskbar=False):
    """Angoli arrotondati (raggio 12) e, per la finestra principale, icona nella taskbar nonostante l'assenza di cornice."""
    try:
        u = ctypes.windll.user32
        hwnd = u.GetAncestor(win.winfo_id(), 2)
        u.SetWindowRgn(hwnd, ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, 24, 24), True)
        if taskbar:
            u.SetWindowLongW(hwnd, -20, (u.GetWindowLongW(hwnd, -20) & ~0x80) | 0x40000)
            win.withdraw()
            win.after(10, win.deiconify)
    except (AttributeError, OSError):
        pass


def draggable(win, canvas):
    pos = {}
    canvas.bind('<ButtonPress-1>', lambda e: pos.update(x=e.x_root - win.winfo_x(), y=e.y_root - win.winfo_y()), add='+')
    canvas.bind('<B1-Motion>', lambda e: win.geometry(f'+{e.x_root - pos["x"]}+{e.y_root - pos["y"]}'), add='+')


# ---------- widget Canvas ----------
class Btn(tk.Canvas):
    """Pulsante arrotondato (raggio 8). kind: ghost | main | blue | red | close."""

    def __init__(self, parent, label, cmd, w, h=44, kind='ghost', font=None):
        super().__init__(parent, width=w, height=h, bg=parent['bg'], highlightthickness=0, takefocus=1, cursor='hand2')
        self.cmd, self.w, self.h = cmd, w, h
        self.base = P['ghost' if kind == 'ghost' else kind]
        self.hover = mix(self.base, '#ffffff' if DARK_MODE else '#000000', .1)
        self.shape = rrect(self, 0, 0, w, h, 8, fill=self.base, outline=self.base)
        self.create_text(w / 2, h / 2 - 1, text=label, font=font or FN['bold'], fill=P['fg'] if kind == 'ghost' else P['fg_on'])
        self.bind('<Enter>', lambda e: self.itemconfig(self.shape, fill=self.hover))
        self.bind('<Leave>', lambda e: self.itemconfig(self.shape, fill=self.base))
        self.bind('<ButtonRelease-1>', lambda e: 0 <= e.x <= w and 0 <= e.y <= h and cmd())
        self.bind('<Return>', lambda e: cmd())
        self.bind('<space>', lambda e: cmd())
        self.bind('<FocusIn>', lambda e: self.itemconfig(self.shape, outline=P['fg'], width=2))
        self.bind('<FocusOut>', lambda e: self.itemconfig(self.shape, outline=self.base, width=1))


class Field(tk.Canvas):
    """Campo di testo arrotondato, piu' scuro dello sfondo, senza bordo."""

    def __init__(self, parent, var, w, h=53, show=''):
        super().__init__(parent, width=w, height=h, bg=parent['bg'], highlightthickness=0)
        self.shape = rrect(self, 0, 0, w, h, 8, fill=P['field'], outline=P['field'])
        self.entry = tk.Entry(self, textvariable=var, font=FN['body'], bg=P['field'], fg=P['fg'], insertbackground=P['fg'], relief='flat', bd=0,
                              highlightthickness=0, show=show)
        self.create_window(15, h / 2 - 1, window=self.entry, anchor='w', width=w - 30)
        self.entry.bind('<FocusIn>', lambda e: self.itemconfig(self.shape, outline=P['blue'], width=2))
        self.entry.bind('<FocusOut>', lambda e: self.itemconfig(self.shape, outline=P['field'], width=1))


class Check(tk.Canvas):
    """Casella 16/20 px con etichetta e nota in corsivo-light, come nel design."""

    def __init__(self, parent, var, label, hint, w, size=16, cmd=None):
        super().__init__(parent, width=w, height=size + 14, bg=parent['bg'], highlightthickness=0, takefocus=1, cursor='hand2')
        self.var, self.cmd = var, cmd
        lx = size + 13
        self.box = rrect(self, 1, 1, size, size, 4, fill=P['field'], outline=P['line'])
        self.tick = self.create_line(4, 9, 7, 12, 13, 5, width=2, fill='#f0f5fd', state='hidden', capstyle='round', joinstyle='round')
        text(self, lx, 15, label, FN['body'], P['fg'])
        text(self, lx + FN['body'].measure(label) + 14, 13, hint, FN['small'], P['fg'])
        for ev in ('<Button-1>', '<space>'):
            self.bind(ev, self.flip)
        self.bind('<FocusIn>', lambda e: self.itemconfig(self.box, width=2, outline=P['blue']))
        self.bind('<FocusOut>', lambda e: self.paint())
        self.trace = var.trace_add('write', lambda *a: self.winfo_exists() and self.paint())
        self.bind('<Destroy>', lambda e: e.widget is self and var.trace_remove('write', self.trace))
        self.paint()

    def paint(self):
        on = self.var.get()
        self.itemconfig(self.box, fill=P['main'] if on else P['field'], outline=P['blue'] if on else P['line'], width=1)
        self.itemconfig(self.tick, state='normal' if on else 'hidden')

    def flip(self, e=None):
        self.focus_set()
        self.var.set(not self.var.get())
        self.cmd and self.cmd()


class Circle(tk.Canvas):
    """Pulsanti rotondi 34 px dell'intestazione: kind = wrench | theme | min | close."""

    def __init__(self, parent, kind, cmd):
        super().__init__(parent, width=34, height=34, bg=parent['bg'], highlightthickness=0, takefocus=1, cursor='hand2')
        base = {'min': P['orange'], 'close': P['red']}.get(kind, P['ghost'])
        self.disc = self.create_oval(0, 0, 33, 33, fill=base, outline=base)
        fg = P['fg']
        if kind == 'min':
            self.create_line(10, 17, 24, 17, width=2, fill=fg)
        elif kind == 'close':
            self.create_line(10, 10, 24, 24, width=2, fill=fg)
            self.create_line(10, 24, 24, 10, width=2, fill=fg)
        else:  # glifi Segoe Fluent Icons: Repair (chiave inglese), QuietHours (luna), Brightness (sole)
            self.create_text(17, 17, text={'wrench': '', 'theme': '' if DARK_MODE else ''}[kind], font=FN['icon'], fill=fg)
        hover = mix(base, '#ffffff' if DARK_MODE else '#000000', .12)
        self.bind('<Enter>', lambda e: self.itemconfig(self.disc, fill=hover, outline=hover))
        self.bind('<Leave>', lambda e: self.itemconfig(self.disc, fill=base, outline=base))
        self.bind('<ButtonRelease-1>', lambda e: 0 <= e.x <= 34 and 0 <= e.y <= 34 and cmd())
        self.bind('<Return>', lambda e: cmd())
        self.bind('<space>', lambda e: cmd())
        self.bind('<FocusIn>', lambda e: self.itemconfig(self.disc, outline=fg, width=2))
        self.bind('<FocusOut>', lambda e: self.itemconfig(self.disc, outline=base, width=1))


class VScroll(tk.Canvas):
    """Barra di scorrimento 8 px: frecce quadrate alle estremita' e cursore arrotondato (Modal_Text_Box.png)."""

    def __init__(self, parent, h, command):
        super().__init__(parent, width=8, height=h, bg=P['field'], highlightthickness=0)
        self.h, self.cmd, self.first, self.last, self.drag = h, command, 0.0, 1.0, None
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<B1-Motion>', self.motion)
        self.paint()

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self.paint()

    def paint(self):
        self.delete('all')
        span = self.h - 18
        for y, up in ((0, True), (self.h - 8, False)):
            rrect(self, 0, y, 8, y + 8, 2, fill=P['ghost'])
            self.create_polygon((1.5, y + 5.5, 6.5, y + 5.5, 4, y + 2.5) if up else (1.5, y + 2.5, 6.5, y + 2.5, 4, y + 5.5), fill=P['fg'], outline='')
        rrect(self, 0, 9 + self.first * span, 8, 9 + self.last * span, 3, fill=P['ghost'])

    def press(self, e):
        span = self.h - 18
        if e.y < 8:
            self.cmd('scroll', -1, 'units')
        elif e.y > self.h - 8:
            self.cmd('scroll', 1, 'units')
        elif 9 + self.first * span <= e.y <= 9 + self.last * span:
            self.drag = (e.y, self.first)
        else:
            self.cmd('moveto', max(0, (e.y - 9) / span - (self.last - self.first) / 2))

    def motion(self, e):
        if self.drag:
            self.cmd('moveto', max(0, self.drag[1] + (e.y - self.drag[0]) / (self.h - 18)))


class ListView(tk.Canvas):
    """Elenco a righe disegnate (header fisso). check=True: casella 20 px per riga (Manual Override). Misure da Modal_Manual_Override.png."""

    def __init__(self, parent, w, h, cols, rows, check=False, row_h=29):
        super().__init__(parent, width=w, height=h, bg=parent['bg'], highlightthickness=0, takefocus=1)
        self.w, self.h, self.cols, self.rows, self.check, self.rh = w, h, cols, rows, check, row_h
        self.sel, self.cur, self.off = set(), 0, 0.0
        self.max = max(0, 46 + len(rows) * row_h - h + 4)  # px scorrevoli
        self.sb = VScroll(self, h, self.yview) if self.max else None
        self.bind('<MouseWheel>', lambda e: self.yview('scroll', -1 if e.delta > 0 else 1, 'units'))
        self.bind('<Button-1>', self.click)
        self.bind('<space>', lambda e: self.toggle(self.cur))
        self.bind('<Up>', lambda e: self.move(-1))
        self.bind('<Down>', lambda e: self.move(1))
        for ev in ('<FocusIn>', '<FocusOut>'):
            self.bind(ev, lambda e: self.paint())
        self.paint()

    def paint(self):
        self.delete('all')
        rrect(self, 0, 0, self.w, self.h, 8, fill=P['field'], outline=P['field'])
        for i, row in enumerate(self.rows):
            top = 46 + i * self.rh - self.off
            if top < 0 or top > self.h:
                continue
            x0 = 52 if self.check else 17
            if self.check:
                on = i in self.sel
                rrect(self, 16, top, 36, top + 20, 5, fill=P['main'] if on else P['ghost'], outline=P['blue'] if self.focus_get() is self and i == self.cur else P['main'] if on else P['ghost'], width=2)
                if on:
                    self.create_line(21, top + 10, 25, top + 14, 31, top + 6, width=2, fill='#f0f5fd', capstyle='round', joinstyle='round')
            for (title, x, anc, fk), val in zip(self.cols, row[0]):
                text(self, x0 if x is None else x, top + 16, val, FN[fk if fk != 'cell' else 'body'], row[1] if x is None and row[1] else P['fg'], anc)
        rrect(self, 0, 0, self.w, 36, 8, fill=P['field'], outline=P['field'])
        self.create_rectangle(0, 20, self.w, 38, fill=P['field'], outline=P['field'])
        for title, x, anc, _ in self.cols:
            text(self, 17 if x is None else x, 33, title, FN['semi'], P['title'], anc)
        if self.sb:  # delete('all') ha tolto la finestra della barra: la ricreo sopra il resto
            self.create_window(self.w - 8, 0, window=self.sb, anchor='nw')

    def yview(self, *a):
        span = self.max or 1
        if a[0] == 'moveto':
            self.off = min(self.max, max(0, float(a[1]) * (self.max + self.h)))
        else:
            self.off = min(self.max, max(0, self.off + int(a[1]) * self.rh))
        self.sb and self.sb.set(self.off / (self.max + self.h), (self.off + self.h) / (self.max + self.h))
        self.paint()

    def row_at(self, y):
        i = int((y + self.off - 46) // self.rh)
        return i if 0 <= i < len(self.rows) and y > 36 else None

    def click(self, e):
        self.focus_set()
        i = self.row_at(e.y)
        if i is not None:
            self.cur = i
            self.toggle(i)

    def toggle(self, i):
        if self.check:
            self.sel.symmetric_difference_update({i})
        self.paint()

    def move(self, d):
        self.cur = min(len(self.rows) - 1, max(0, self.cur + d))
        top = 46 + self.cur * self.rh
        if top - self.off < 40 or top - self.off > self.h - 30:
            self.off = min(self.max, max(0, top - 46))
            self.sb and self.sb.set(self.off / (self.max + self.h), (self.off + self.h) / (self.max + self.h))
        self.paint()


# ---------- applicazione ----------
class App:
    def __init__(self, root):
        self.root = root
        root.title('Server Mod Utilities')
        root.overrideredirect(True)
        init_fonts()
        self.q = queue.Queue()
        self.data, self.cat, self.total, self.done, self.args, self.h = None, 'all', 0, 0, None, H
        self.paths = {k: tk.StringVar() for k in ('input', 'output', 'compare')}
        self.paths['output'].set('./mods/Server_Ready')
        self.api, self.dry, self.override = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        self.key, self.key_state, self.key_ui, self.key_timer = tk.StringVar(value=ENV_KEY), 'empty', None, None
        self.dark = is_dark()  # preferenza di sistema, sovrascritta dalla scelta salvata
        self.load_prefs()
        set_theme(self.dark)
        config.CURSEFORGE_API_KEY = self.key.get().strip()  # l'app legge la chiave da config a ogni chiamata
        if config.CURSEFORGE_API_KEY:
            self.key_state = 'checking'
            root.after(300, self.check_key)
        self.screen = self.setup
        self.cv = None
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f'{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 2)}')
        self.build()
        root.update_idletasks()
        win_api(root, W, H, taskbar=True)
        root.bind('<Map>', self.on_map)
        self.poll()

    # ---------- preferenze, tema, finestra ----------
    def load_prefs(self):
        try:
            d = json.loads(PREFS.read_text(encoding='utf-8'))
            for k, v in self.paths.items():
                v.set(d.get(k, v.get()))
            self.api.set(d.get('api', False))
            self.override.set(d.get('override', False))
            self.dark = d.get('dark', self.dark)
            self.key.set(d.get('cf_key') or self.key.get())
        except (OSError, ValueError):
            pass

    def save_prefs(self):
        key = self.key.get().strip()
        try:  # la chiave presa dalla variabile d'ambiente non viene copiata nel file
            PREFS.write_text(json.dumps({k: v.get() for k, v in self.paths.items()} | {
                'api': self.api.get(), 'override': self.override.get(), 'dark': self.dark, 'cf_key': '' if key == ENV_KEY else key}), encoding='utf-8')
        except OSError:
            pass

    def toggle_theme(self):
        if self.screen == self.progress_screen:  # ricostruire ora perderebbe la barra di avanzamento
            return
        self.dark = not self.dark
        set_theme(self.dark)
        self.save_prefs()
        self.build()

    def minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()

    def on_map(self, e):  # al ripristino da icona rimetto la finestra senza cornice
        if e.widget is self.root and not self.root.overrideredirect():
            self.root.after(10, lambda: (self.root.overrideredirect(True), win_api(self.root, W, self.h, taskbar=True)))

    def resize(self, h):
        if h != self.h:
            self.h = h
            self.root.geometry(f'{W}x{h}')
            self.root.update_idletasks()
            win_api(self.root, W, h)

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=P['bg'])
        self.cv = tk.Canvas(self.root, width=W, height=self.h, bg=P['bg'], highlightthickness=0)
        self.cv.pack(fill='both', expand=True)
        draggable(self.root, self.cv)
        self.show(self.screen)

    def show(self, screen):
        self.screen = screen
        self.resize(H if screen != self.results else 860)
        for w in self.cv.winfo_children():
            w.destroy()
        self.cv.delete('all')
        self.cv.configure(height=self.h)
        cv = self.cv
        text(cv, 64, 75, 'Server Mod Utilities', FN['h1'], P['title'])
        text(cv, 64, 112, 'Welcome to the Ultimate toolbox for managing your modpacks!', FN['h2'], P['title'])
        text(cv, 64, 139, 'Use the buttons below to manage your mods. You can compare folders, list mods or split server-ready mods.', FN['sub'], P['fg'])
        for x, kind, cmd in ((1071, 'wrench', self.settings), (1111, 'theme', self.toggle_theme), (1151, 'min', self.minimize), (1191, 'close', self.root.destroy)):
            cv.create_window(x, 39, window=Circle(cv, kind, cmd), anchor='nw')
        screen()

    # ---------- pagina principale ----------
    def setup(self):
        cv = self.cv
        for k, (key, title, hint) in enumerate((('input', 'Mod Folder', 'Select the folder with .jar files of your modpack.'),
                                                ('output', 'Server Pack Folder', 'Select the folder where to save your server-ready modpack'),
                                                ('compare', 'Compare Folders', '(Optional) Select the folder you want to compare with.'))):
            y = 130 * k
            text(cv, 64, 185 + y, title, FN['t24'], P['title'])
            text(cv, 64, 213 + y, hint, FN['hint'], P['fg'])
            cv.create_window(64, 221 + y, window=Field(cv, self.paths[key], 1056), anchor='nw')
            cv.create_window(1131, 226 + y, window=Btn(cv, 'Find...', lambda k=key: self.browse(k), 94), anchor='nw')
        cv.create_window(63, 560, window=Check(cv, self.api, 'Check mod online', '(Uses Modrinth or CurseForge API. Slower)', 420, cmd=self.save_prefs), anchor='nw')
        cv.create_window(807, 560, window=Check(cv, self.dry, 'Preview Only', '(Generate an analysis file without copying your mods)', 417), anchor='nw')
        for x, label, cmd, w, kind in ((665, 'Scan Mod Differences', self.scan, 201, 'ghost'), (874, 'Generate Mod List', self.mod_list, 190, 'ghost'),
                                       (1072, 'Start Analysis', self.start, 153, 'main')):
            cv.create_window(x, 604, window=Btn(cv, label, cmd, w, kind=kind), anchor='nw')

    def browse(self, key):
        folder = filedialog.askdirectory(title='Choose a folder')
        if folder:
            self.paths[key].set(os.path.normpath(folder))

    def dir_of(self, key):
        p = self.paths[key].get().strip()
        if p and Path(p).is_dir():  # Path('') sarebbe la cartella corrente
            return Path(p)
        messagebox.showwarning('Check your input', f'Choose a valid {NAMES[key]}.')

    def scan(self):
        a, b = self.dir_of('input'), self.dir_of('compare')
        if a and b:
            self.report_modal('Mod Analysis Report', diff_report(a, b))

    def mod_list(self):
        a = self.dir_of('input')
        if a:
            text_, data = list_report(a)
            self.report_modal('Mod List', text_, data)

    # ---------- modali ----------
    def modal(self, title, w, h):
        t = tk.Toplevel(self.root, bg=P['bg'])
        t.overrideredirect(True)
        r = self.root
        t.geometry(f'{w}x{h}+{r.winfo_x() + (r.winfo_width() - w) // 2}+{r.winfo_y() + (r.winfo_height() - h) // 2}')
        t.bind('<Escape>', lambda e: t.destroy())
        cv = tk.Canvas(t, width=w, height=h, bg=P['bg'], highlightthickness=0)
        cv.pack()
        draggable(t, cv)
        text(cv, 16, 51, title, FN['h1'], P['title'])
        t.update_idletasks()
        win_api(t, w, h)
        t.wait_visibility()
        t.grab_set()
        t.focus_force()
        return t, cv

    def report_modal(self, title, body, data=None):
        """Testo scorrevole (Modal_Text_Box.png). Con `data` il salvataggio puo' essere anche .json."""
        t, cv = self.modal(title, 804, 536)

        def copy():
            t.clipboard_clear()
            t.clipboard_append(body)

        def save():
            path = filedialog.asksaveasfilename(parent=t, defaultextension='.txt', filetypes=[('Text', '*.txt')] + ([('JSON', '*.json')] if data else []))
            if path:
                try:
                    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) if data and path.endswith('.json') else body, encoding='utf-8')
                except OSError as e:
                    messagebox.showerror('Cannot save', str(e), parent=t)

        rrect(cv, 16, 67, 787, 466, 8, fill=P['field'], outline=P['field'])
        txt = tk.Text(cv, wrap='word', font=FN['report'], bg=P['field'], fg=P['fg'], relief='flat', bd=0, padx=14, pady=10, highlightthickness=0,
                      insertbackground=P['fg'], selectbackground=P['ghost'], selectforeground=P['fg'])
        sb = VScroll(cv, 400, txt.yview)
        txt.configure(yscrollcommand=sb.set)
        cv.create_window(20, 71, window=txt, anchor='nw', width=756, height=392)
        cv.create_window(779, 67, window=sb, anchor='nw')
        txt.insert('1.0', body)
        txt.config(state='disabled')  # sola lettura, ma selezionabile e copiabile
        for x, label, cmd, w, kind in ((312, 'Copy to clipboard', copy, 186, 'ghost'), (514, 'Save report', save, 137, 'blue'),
                                       (668, '✕  Close', t.destroy, 120, 'close')):
            cv.create_window(x, 476, window=Btn(cv, label, cmd, w, kind=kind), anchor='nw')

    def settings(self):
        t, cv = self.modal('Advanced Settings', 804, 365)
        text(cv, 17, 92, 'CurseForge API (Optional)', FN['t24'], P['title'])
        text(cv, 17, 120, 'Paste here your API Key. (Saved only on this PC)', FN['hint'], P['fg'])
        field = Field(cv, self.key, 282, show='*')
        field.entry.bind('<KeyRelease>', self.key_typed)
        cv.create_window(16, 128, window=field, anchor='nw')

        def paste():
            try:
                self.key.set(t.clipboard_get().strip())
            except tk.TclError:  # appunti vuoti o non testuali
                return
            self.check_key()

        cv.create_window(309, 133, window=Btn(cv, 'Paste', paste, 88), anchor='nw')
        cv.create_window(408, 133, window=Btn(cv, 'Retry', self.check_key, 88, kind='blue'), anchor='nw')
        dot = cv.create_oval(523, 152, 531, 160, outline='')
        label = text(cv, 537, 161, '', FN['body'], P['fg'])
        self.key_ui = (cv, dot, label)
        self.paint_key()
        link = text(cv, 17, 202, 'Get API ↗', FN['body'], P['blue'])
        cv.tag_bind(link, '<Button-1>', lambda e: webbrowser.open('https://console.curseforge.com'))
        cv.tag_bind(link, '<Enter>', lambda e: cv.config(cursor='hand2'))
        cv.tag_bind(link, '<Leave>', lambda e: cv.config(cursor=''))
        cv.create_window(15, 237, window=Check(cv, self.api, 'Check for Unknown Mods online', '(Uses Modrinth or CurseForge API. Slower)', 700, cmd=self.save_prefs), anchor='nw')
        cv.create_window(15, 268, window=Check(cv, self.override, 'Manual Override Unknown Mods', '(Gives you a list of potential conflicting mods you can select manually)', 760, cmd=self.save_prefs), anchor='nw')
        cv.create_window(668, 305, window=Btn(cv, '✕  Close', t.destroy, 120, kind='close'), anchor='nw')

    def override_dialog(self):
        cands = [r for r in self.data['results'] if r['side'] == 'unknown' and confidence(r) < OVERRIDE_BELOW]
        if not cands:
            return
        t, cv = self.modal('Manual Mod Filtering Override', 804, 582)
        text(cv, 17, 80, 'Mods below the confidence threshold will display here. Select only the ones you want to be copied in your', FN['body'], P['fg'])
        text(cv, 17, 101, 'Server Pack', FN['body'], P['fg'])
        rows = [((r['file'], f'{confidence(r)}%', r['parser_type'].title()), None) for r in cands]
        lv = ListView(cv, 772, 400, [('Modname', None, 'w', 'body'), ('Confidence', 548, 'c', 'bold'), ('ModType', 755, 'e', 'body')], rows, check=True)
        cv.create_window(16, 113, window=lv, anchor='nw')

        def confirm():
            if lv.sel:
                try:
                    apply_manual(self.data, {cands[i]['file'] for i in lv.sel}, self.args['input_folder'], self.args['output_folder'], self.args['dry_run'])
                except OSError as e:
                    messagebox.showerror('Copy failed', str(e), parent=t)
                    return
                self.show(self.results)
            t.destroy()

        def all_(on):
            lv.sel = set(range(len(rows))) if on else set()
            lv.paint()

        for x, label, cmd, w, kind in ((270, 'Select All', lambda: all_(True), 120, 'ghost'), (407, 'Deselect All', lambda: all_(False), 138, 'ghost'),
                                       (562, 'Confirm', confirm, 111, 'blue'), (690, 'Cancel', t.destroy, 98, 'red')):
            cv.create_window(x, 522, window=Btn(cv, label, cmd, w, kind=kind), anchor='nw')
        lv.focus_set()

    # ---------- chiave API ----------
    def key_typed(self, _):  # verifica automatica 0,7 s dopo l'ultimo tasto
        self.set_key_state('empty' if not self.key.get().strip() else 'checking')
        if self.key_timer:
            self.root.after_cancel(self.key_timer)
        self.key_timer = self.root.after(700, self.check_key)

    def check_key(self):
        key = self.key.get().strip()
        config.CURSEFORGE_API_KEY = key
        self.save_prefs()
        self.set_key_state('checking' if key else 'empty')
        if key:
            threading.Thread(target=lambda: self.q.put(('key', (key, probe(key)))), daemon=True).start()

    def set_key_state(self, state):
        self.key_state = state
        self.paint_key()

    def paint_key(self):
        if self.key_ui and self.key_ui[0].winfo_exists():
            cv, dot, label = self.key_ui
            msg, col = KEY_STATES[self.key_state]
            color = P[col] if col else P['fg']
            cv.itemconfig(dot, fill=color)
            cv.itemconfig(label, text=msg, fill=color)

    # ---------- analisi ----------
    def progress_screen(self):
        cv = self.cv
        text(cv, 644, 330, 'Analysis in progress…', FN['h2'], P['title'], 'c')
        self.plabel = text(cv, 644, 366, 'Preparing', FN['body'], P['fg'], 'c')
        rrect(cv, 394, 400, 894, 410, 5, fill=P['ghost'], outline=P['ghost'])
        self.fill = rrect(cv, 394, 400, 400, 410, 5, fill=P['main'], outline=P['main'])

    def start(self):
        inp, out, cmp_ = (self.paths[k].get().strip() for k in ('input', 'output', 'compare'))
        err = None
        if not inp or not Path(inp).is_dir():
            err = 'Choose the folder that contains your mods.'
        elif not any(Path(inp).glob('*.jar')):
            err = 'There are no .jar files in the chosen folder.'
        elif not out:
            err = 'Choose the Server Pack folder.'
        elif cmp_ and not Path(cmp_).is_dir():
            err = 'The compare folder does not exist. Clear the field or choose a valid one.'
        if err:
            return messagebox.showwarning('Check your input', err)
        self.save_prefs()
        self.total = self.done = 0
        self.args = dict(input_folder=Path(inp), output_folder=Path(out), use_api=self.api.get(),
                         compare_folder=Path(cmp_) if cmp_ else None, dry_run=self.dry.get())
        self.show(self.progress_screen)
        threading.Thread(target=self.work, args=(self.args,), daemon=True).start()

    def work(self, args):
        try:
            with redirect_stdout(LineWriter(self.q)):
                self.q.put(('done', analyze_modpack(**args)))
        except (Exception, SystemExit) as e:  # l'app chiama sys.exit su errori di input
            self.q.put(('error', str(e) or 'Unknown error'))

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == 'line' and data.startswith('Trovate'):
                    self.total = int(data.split()[1])
                elif kind == 'line' and data.startswith('  ['):  # una riga per mod (solo cosmetico)
                    self.done += 1
                    self.cv.coords(self.fill, *self.fill_pts(self.done / max(self.total, 1)))
                    self.cv.itemconfig(self.plabel, text=f'{self.done} of {self.total} mods')
                elif kind == 'key':
                    if data[0] == self.key.get().strip():  # scarta risposte per una chiave già modificata
                        self.set_key_state(data[1])
                elif kind == 'done':
                    self.data, self.cat = data, 'all'
                    self.show(self.results)
                    if self.override.get():
                        self.root.after(100, self.override_dialog)
                elif kind == 'error':
                    self.show(self.setup)
                    messagebox.showerror('Analysis failed', data)
        except (queue.Empty, tk.TclError):  # TclError: schermata cambiata mentre arrivavano righe
            pass
        self.root.after(100, self.poll)

    @staticmethod
    def fill_pts(f):  # stessi punti di rrect() per la barra 394..894 x 400..410 riempita al `f`
        x1, r = 394 + max(12, 500 * f), 5
        return [394 + r, 400, x1 - r, 400, x1, 400, x1, 400 + r, x1, 410 - r, x1, 410, x1 - r, 410, 394 + r, 410, 394, 410, 394, 410 - r, 394, 400 + r, 394, 400]

    # ---------- risultati ----------
    def results(self):
        cv, st = self.cv, self.data['stats']
        text(cv, 64, 200, f"{st['server']} mods ready for the server", FN['t24'], P['title'])
        text(cv, 64 + FN['t24'].measure(f"{st['server']} mods ready for the server") + 12, 200, f"of {st['total']}", FN['t24'], P['fg'])
        msg = 'Preview: no file was copied.' if self.dry.get() else f"Copied to {self.paths['output'].get()}"
        ref = st['matched_ref'] + st['missed_ref']
        if self.paths['compare'].get().strip() and ref:
            msg += f"  ·  Accuracy vs reference: {st['matched_ref'] / ref:.0%}"
        text(cv, 64, 228, msg, FN['hint'], P['fg'])
        x = 1225 - 153
        cv.create_window(x, 176, window=Btn(cv, 'New analysis', lambda: self.show(self.setup), 153), anchor='nw')
        if not self.dry.get():
            cv.create_window(x - 169, 176, window=Btn(cv, 'Open folder', self.open_output, 161, kind='main'), anchor='nw')
        self.tiles = {}
        for i, (k, name, n, col) in enumerate([('all', 'All', st['total'], 'fg')] + [(k, v[0], st[k], v[2]) for k, v in CATS.items()]):
            t = tk.Canvas(cv, width=254, height=76, bg=P['bg'], highlightthickness=0, cursor='hand2')
            t.bind('<Button-1>', lambda e, k=k: self.set_cat(k))
            t.shape = rrect(t, 1, 1, 253, 75, 8, fill=P['field'], outline=P['field'], width=2)
            text(t, 17, 40, str(n), FN['h2'], P['title'])
            text(t, 17, 63, name, FN['body'], P[col])
            cv.create_window(64 + i * 267, 258, window=t, anchor='nw')
            self.tiles[k] = t
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *a: self.refresh())
        cv.create_window(64, 354, window=Field(cv, self.search, 1161, h=45), anchor='nw')
        self.box, self.rows_cv = cv, None
        self.set_cat(self.cat)

    def set_cat(self, cat):
        self.cat = cat
        for k, t in self.tiles.items():
            t.itemconfig(t.shape, outline=P['blue'] if k == cat else P['field'])
        self.refresh()

    def refresh(self):
        needle = self.search.get().strip().lower()
        rows = [((CATS[category(r)][1], r['file'], r['reason']), P[CATS[category(r)][2]]) for r in self.data['results']
                if self.cat in ('all', category(r)) and needle in (r['file'] + ' ' + r['reason']).lower()]
        if self.rows_cv:
            self.rows_cv.destroy()
        self.rows_cv = ListView(self.cv, 1161, 400, [('Result', None, 'w', 'body'), ('Mod', 150, 'w', 'body'), ('Reason', 560, 'w', 'body')], rows)
        self.cv.create_window(64, 415, window=self.rows_cv, anchor='nw')

    def open_output(self):
        p = Path(self.paths['output'].get().strip())
        if p.is_dir():
            os.startfile(p.resolve())
        else:
            messagebox.showinfo('Folder not found', 'The Server Pack folder does not exist.')


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 px del design = 1 px reale
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
