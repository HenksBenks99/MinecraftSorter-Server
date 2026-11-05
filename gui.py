#!/usr/bin/env python3
"""
ForgeModSearch GUI - interfaccia a passi: Preparazione -> Analisi -> Risultati.
Solo tkinter (zero dipendenze). Usa analyze_modpack() cosi' com'e'.
"""

import ctypes
import json
import os
import queue
import threading
import tkinter as tk
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import config
from separate_mods import analyze_modpack

PREFS = Path.home() / '.forgemodsearch_gui.json'
LIGHT = dict(bg='#f8fafc', card='#ffffff', fg='#0f172a', muted='#64748b', border='#e2e8f0', field='#ffffff', ghost='#f1f5f9')
DARK = dict(bg='#020617', card='#0f172a', fg='#f1f5f9', muted='#94a3b8', border='#1e293b', field='#020617', ghost='#1e293b')
GREEN, GREEN_HOVER = '#059669', '#047857'
CATS = {  # categoria -> (scheda, etichetta riga, colore chiaro, colore scuro)
    'server': ('Server-ready', '✓ Server', '#047857', '#6ee7b7'),
    'client': ('Solo client', '✕ Client', '#be123c', '#fda4af'),
    'unknown': ('Da verificare', '? Verifica', '#b45309', '#fcd34d'),
}
F, FB, FS = ('Segoe UI', 10), ('Segoe UI', 10, 'bold'), ('Segoe UI', 9)


def is_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as k:
            return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 0
    except (ImportError, OSError):
        return False


DARK_MODE = is_dark()
P = DARK if DARK_MODE else LIGHT


def category(r):  # stessa regola con cui l'app conta le statistiche
    return 'server' if r['action'] == 'COPY' else 'client' if r['side'] == 'client' else 'unknown'


def color(cat):
    return CATS[cat][3 if DARK_MODE else 2]


KEY_STATES = {  # stato chiave -> (testo, categoria colore o None = neutro)
    'empty': ('Non inserita', None),
    'checking': ('Verifica in corso…', None),
    'ok': ('Valida e funzionante', 'server'),
    'bad': ('Non valida', 'client'),
    'offline': ('Non verificabile (rete)', 'unknown'),
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


def card(parent, **kw):
    kw = {'padx': 20, 'pady': 18} | kw
    return tk.Frame(parent, bg=P['card'], highlightbackground=P['border'], highlightthickness=1, **kw)


def label(parent, text, font=F, fg=None, bg=None, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg or P['fg'], bg=bg or parent['bg'], **kw)


def button(parent, text, cmd, primary=False):
    bg, fg, hover = (GREEN, 'white', GREEN_HOVER) if primary else (P['ghost'], P['fg'], P['border'])
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=hover, activeforeground=fg, disabledforeground='#a7f3d0',
                  relief='flat', bd=0, padx=16, pady=8, cursor='hand2', font=FB if primary else F)
    b.bind('<Enter>', lambda e: b.config(bg=hover))
    b.bind('<Leave>', lambda e: b.config(bg=bg))
    return b


def entry(parent, **kw):
    return tk.Entry(parent, font=F, bg=P['field'], fg=P['fg'], insertbackground=P['fg'], relief='flat',
                    highlightthickness=1, highlightbackground=P['border'], highlightcolor=GREEN, **kw)


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


class App:
    def __init__(self, root):
        self.root = root
        root.title('ForgeModSearch')
        root.geometry('1000x820')
        root.minsize(780, 640)
        root.configure(bg=P['bg'])

        self.q = queue.Queue()
        self.data, self.cat, self.total, self.done = None, 'all', 0, 0
        self.paths = {k: tk.StringVar() for k in ('input', 'output', 'compare')}
        self.paths['output'].set('./mods/Server_Ready')
        self.api, self.dry = tk.BooleanVar(), tk.BooleanVar()
        self.key, self.key_state, self.key_lbl, self.key_timer = tk.StringVar(value=ENV_KEY), 'empty', None, None
        self.load_prefs()
        config.CURSEFORGE_API_KEY = self.key.get().strip()  # l'app legge la chiave da config a ogni chiamata
        if config.CURSEFORGE_API_KEY:
            self.key_state = 'checking'
            root.after(300, self.check_key)
        self.apply_style()

        head = tk.Frame(root, bg=P['bg'])
        head.pack(fill='x', padx=28, pady=(24, 0))
        label(head, 'ForgeModSearch', ('Segoe UI', 22, 'bold')).pack(anchor='w')
        label(head, 'Separa le mod che servono al server da quelle solo client.', fg=P['muted']).pack(anchor='w')
        self.body = tk.Frame(root, bg=P['bg'])
        self.body.pack(fill='both', expand=True, padx=28, pady=(14, 24))
        self.show(self.setup)
        self.poll()

    # ---------- preferenze e stile ----------
    def load_prefs(self):
        try:
            d = json.loads(PREFS.read_text(encoding='utf-8'))
            for k, v in self.paths.items():
                v.set(d.get(k, v.get()))
            self.api.set(d.get('api', False))
            self.key.set(d.get('cf_key') or self.key.get())
        except (OSError, ValueError):
            pass

    def save_prefs(self):
        key = self.key.get().strip()
        try:  # la chiave presa dalla variabile d'ambiente non viene copiata nel file
            PREFS.write_text(json.dumps({k: v.get() for k, v in self.paths.items()} | {'api': self.api.get(), 'cf_key': '' if key == ENV_KEY else key}), encoding='utf-8')
        except OSError:
            pass

    def apply_style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('Treeview', rowheight=30, background=P['card'], fieldbackground=P['card'], foreground=P['fg'], borderwidth=0, font=F,
                    bordercolor=P['card'], lightcolor=P['card'], darkcolor=P['card'])
        s.configure('Treeview.Heading', background=P['ghost'], foreground=P['muted'], font=FB, relief='flat', padding=6)
        s.map('Treeview', background=[('selected', P['border'])], foreground=[('selected', P['fg'])])
        s.map('Treeview.Heading', background=[('active', P['ghost'])])
        s.configure('G.Horizontal.TProgressbar', troughcolor=P['border'], background=GREEN, thickness=10, borderwidth=0)
        s.configure('Vertical.TScrollbar', background=P['ghost'], troughcolor=P['card'], bordercolor=P['card'], arrowcolor=P['muted'])

    def show(self, screen):
        for w in self.body.winfo_children():
            w.destroy()
        screen()

    # ---------- schermata 1: preparazione ----------
    def field(self, parent, title, hint, key):
        label(parent, title, FB).pack(anchor='w', pady=(14, 0))
        row = tk.Frame(parent, bg=P['card'])
        row.pack(fill='x', pady=(4, 0))
        entry(row, textvariable=self.paths[key]).pack(side='left', fill='x', expand=True, ipady=6)
        button(row, 'Scegli…', lambda: self.browse(key)).pack(side='left', padx=(8, 0))
        label(parent, hint, FS, P['muted']).pack(anchor='w', pady=(3, 0))

    def check(self, parent, var, title, hint):
        tk.Checkbutton(parent, text=title, variable=var, font=FB, bg=P['card'], fg=P['fg'], activebackground=P['card'], activeforeground=P['fg'],
                       selectcolor=P['field'], bd=0, highlightthickness=0, cursor='hand2').pack(anchor='w', pady=(14, 0))
        label(parent, hint, FS, P['muted']).pack(anchor='w', padx=(24, 0))

    def setup(self):
        c = card(self.body)
        c.pack(fill='x')
        self.field(c, '1.  Cartella delle mod', 'La cartella con i file .jar del tuo modpack.', 'input')
        self.field(c, '2.  Dove salvare le mod per il server', 'Qui verranno copiate le mod server-ready.', 'output')
        self.check(c, self.dry, 'Solo anteprima', 'Analizza e mostra i risultati senza copiare nessun file.')

        toggle = label(c, '▸  Opzioni avanzate', FB, cursor='hand2')
        toggle.pack(anchor='w', pady=(18, 0))
        adv = tk.Frame(c, bg=P['card'])
        self.check(adv, self.api, 'Controlla online le mod sconosciute', 'Usa Modrinth e, se la chiave qui sotto è valida, anche CurseForge. Più lento.')
        self.key_field(adv)
        self.field(adv, 'Cartella di confronto (facoltativa)', "Una cartella già corretta: serve a misurare la precisione dell'analisi.", 'compare')

        def flip(_):
            opening = not adv.winfo_ismapped()
            adv.pack(fill='x', after=toggle) if opening else adv.pack_forget()
            toggle.config(text=('▾' if opening else '▸') + '  Opzioni avanzate')
        toggle.bind('<Button-1>', flip)
        button(c, '▶  Analizza modpack', self.start, primary=True).pack(fill='x', pady=(20, 0), ipady=4)

    def key_field(self, parent):
        label(parent, 'Chiave API CurseForge (facoltativa)', FB).pack(anchor='w', pady=(14, 0))
        row = tk.Frame(parent, bg=P['card'])
        row.pack(fill='x', pady=(4, 0))
        e = entry(row, textvariable=self.key, show='•')
        e.pack(side='left', fill='x', expand=True, ipady=6)
        e.bind('<KeyRelease>', self.key_typed)
        show = label(row, 'Mostra', fg=P['muted'], cursor='hand2')
        show.pack(side='left', padx=10)
        show.bind('<Button-1>', lambda _: (e.config(show='' if e['show'] else '•'), show.config(text='Mostra' if e['show'] else 'Nascondi')))
        button(row, 'Verifica', self.check_key).pack(side='left')
        self.key_lbl = label(row, '', FB, width=24, anchor='w')
        self.key_lbl.pack(side='left', padx=(12, 0))
        label(parent, 'Serve solo per il controllo online. Si ottiene gratis su console.curseforge.com. '
              'Viene salvata solo su questo PC, nel tuo profilo utente.', FS, P['muted']).pack(anchor='w', pady=(3, 0))
        self.paint_key()

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
        if self.key_lbl is not None and self.key_lbl.winfo_exists():
            text, cat = KEY_STATES[self.key_state]
            self.key_lbl.config(text='●  ' + text, fg=color(cat) if cat else P['muted'])

    def browse(self, key):
        folder = filedialog.askdirectory(title='Scegli una cartella')
        if folder:
            self.paths[key].set(os.path.normpath(folder))

    # ---------- schermata 2: analisi ----------
    def progress_screen(self):
        c = card(self.body, pady=40)
        c.pack(fill='x')
        label(c, 'Analisi in corso…', ('Segoe UI', 14, 'bold')).pack()
        self.plabel = label(c, 'Preparazione', fg=P['muted'])
        self.plabel.pack(pady=(4, 20))
        self.bar = ttk.Progressbar(c, style='G.Horizontal.TProgressbar', length=420, maximum=1)
        self.bar.pack()

    def start(self):
        inp, out, cmp_ = (self.paths[k].get().strip() for k in ('input', 'output', 'compare'))
        err = None
        if not inp or not Path(inp).is_dir():  # Path('') sarebbe la cartella corrente
            err = 'Scegli la cartella che contiene le mod.'
        elif not any(Path(inp).glob('*.jar')):
            err = 'Nella cartella scelta non ci sono file .jar.'
        elif not out:
            err = 'Scegli la cartella di destinazione.'
        elif cmp_ and not Path(cmp_).is_dir():
            err = 'La cartella di confronto non esiste. Svuota il campo oppure scegline una valida.'
        if err:
            return messagebox.showwarning('Controlla i dati', err)
        self.save_prefs()
        self.total = self.done = 0
        self.show(self.progress_screen)
        args = dict(input_folder=Path(inp), output_folder=Path(out), use_api=self.api.get(),
                    compare_folder=Path(cmp_) if cmp_ else None, dry_run=self.dry.get())
        threading.Thread(target=self.work, args=(args,), daemon=True).start()

    def work(self, args):
        try:
            with redirect_stdout(LineWriter(self.q)):
                self.q.put(('done', analyze_modpack(**args)))
        except (Exception, SystemExit) as e:  # l'app chiama sys.exit su errori di input
            self.q.put(('error', str(e) or 'Errore sconosciuto'))

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == 'line' and data.startswith('Trovate'):
                    self.total = int(data.split()[1])
                    self.bar.config(maximum=max(self.total, 1))
                elif kind == 'line' and data.startswith('  ['):  # una riga per mod (solo cosmetico)
                    self.done += 1
                    self.bar.config(value=self.done)
                    self.plabel.config(text=f'{self.done} di {self.total} mod')
                elif kind == 'key':
                    if data[0] == self.key.get().strip():  # scarta risposte per una chiave già modificata
                        self.set_key_state(data[1])
                elif kind == 'done':
                    self.data, self.cat = data, 'all'
                    self.show(self.results)
                elif kind == 'error':
                    self.show(self.setup)
                    messagebox.showerror('Analisi non riuscita', data)
        except (queue.Empty, tk.TclError):  # TclError: schermata cambiata mentre arrivavano righe
            pass
        self.root.after(100, self.poll)

    # ---------- schermata 3: risultati ----------
    def results(self):
        st = self.data['stats']
        c = card(self.body)
        c.pack(fill='x')
        title = tk.Frame(c, bg=P['card'])
        title.pack(anchor='w')
        label(title, f"{st['server']} mod pronte per il server", ('Segoe UI', 15, 'bold')).pack(side='left')
        label(title, f"  su {st['total']}", ('Segoe UI', 15), P['muted']).pack(side='left')
        msg = 'Anteprima: nessun file è stato copiato.' if self.dry.get() else f"Copiate in {self.paths['output'].get()}"
        ref = st['matched_ref'] + st['missed_ref']
        if self.paths['compare'].get().strip() and ref:
            msg += f"  ·  Precisione rispetto al riferimento: {st['matched_ref'] / ref:.0%}"
        label(c, msg, fg=P['muted']).pack(anchor='w', pady=(4, 12))
        row = tk.Frame(c, bg=P['card'])
        row.pack(anchor='w')
        if not self.dry.get():
            button(row, 'Apri cartella', self.open_output, primary=True).pack(side='left', padx=(0, 8))
        button(row, 'Nuova analisi', lambda: self.show(self.setup)).pack(side='left')

        grid = tk.Frame(self.body, bg=P['bg'])
        grid.pack(fill='x', pady=12)
        self.tiles = {}
        for i, (k, name, n, fg) in enumerate([('all', 'Tutte', st['total'], P['fg'])] + [(k, v[0], st[k], color(k)) for k, v in CATS.items()]):
            grid.columnconfigure(i, weight=1, uniform='t')
            t = tk.Frame(grid, bg=P['card'], highlightthickness=2, padx=14, pady=10, cursor='hand2')
            t.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 8, 0))
            for w in (label(t, str(n), ('Segoe UI', 20, 'bold')), label(t, name, fg=fg if k != 'all' else P['muted'])):
                w.pack(anchor='w')
                w.bind('<Button-1>', lambda e, k=k: self.set_cat(k))
            t.bind('<Button-1>', lambda e, k=k: self.set_cat(k))
            self.tiles[k] = t

        box = card(self.body, padx=0, pady=0)
        box.pack(fill='both', expand=True)
        bar = tk.Frame(box, bg=P['card'])
        bar.pack(fill='x', padx=12, pady=12)
        label(bar, 'Cerca', fg=P['muted']).pack(side='left', padx=(0, 8))
        self.search = entry(bar)
        self.search.pack(side='left', fill='x', expand=True, ipady=6)
        self.search.bind('<KeyRelease>', lambda e: self.refresh())
        inner = tk.Frame(box, bg=P['card'])
        inner.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(inner, columns=('esito', 'mod', 'motivo'), show='headings', selectmode='browse')
        for col, text, w in (('esito', 'Esito', 110), ('mod', 'Mod', 360), ('motivo', 'Motivo', 380)):
            self.tree.heading(col, text=text, anchor='w')
            self.tree.column(col, width=w, anchor='w', stretch=col != 'esito')
        for k in CATS:
            self.tree.tag_configure(k, foreground=color(k))
        sb = ttk.Scrollbar(inner, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.set_cat('all')

    def set_cat(self, cat):
        self.cat = cat
        for k, t in self.tiles.items():
            t.config(highlightbackground=GREEN if k == cat else P['border'], highlightcolor=GREEN)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        text = self.search.get().strip().lower()
        for r in self.data['results']:
            cat = category(r)
            if self.cat in ('all', cat) and text in (r['file'] + ' ' + r['reason']).lower():
                self.tree.insert('', 'end', values=(CATS[cat][1], r['file'], r['reason']), tags=(cat,))

    def open_output(self):
        p = Path(self.paths['output'].get().strip())
        if p.is_dir():
            os.startfile(p.resolve())
        else:
            messagebox.showinfo('Cartella non trovata', 'La cartella di destinazione non esiste.')


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # testo nitido su schermi HiDPI
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
