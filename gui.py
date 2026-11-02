#!/usr/bin/env python3
"""
ForgeModSearch GUI - Interfaccia grafica per separazione mod server-ready.
Zero dipendenze esterne (usa solo tkinter standard library).
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import sys
from pathlib import Path

# Importa logica core
from separate_mods import analyze_modpack, normalize_mod_name
import config


class ForgeModSearchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ForgeModSearch v4.1.0 - Mod Server-Ready Separator")
        self.root.geometry("900x650")
        self.root.minsize(800, 550)

        # Queue per comunicazione thread
        self.log_queue = queue.Queue()
        self.running = False

        self.setup_ui()
        self.poll_log_queue()

    def setup_ui(self):
        # Style
        style = ttk.Style()
        style.theme_use('clam')

        # --- Header ---
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="ForgeModSearch", font=('Segoe UI', 16, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header, text="v4.1.0", font=('Segoe UI', 10), foreground='gray').pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))

        # --- Input Section ---
        input_frame = ttk.LabelFrame(self.root, text="Cartelle", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Input folder
        ttk.Label(input_frame, text="Modpack sorgente:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.input_var, width=60).grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(input_frame, text="Sfoglia", command=self.browse_input).grid(row=0, column=2, padx=5)

        # Output folder
        ttk.Label(input_frame, text="Output server-ready:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_var = tk.StringVar(value="./mods/Server_Ready")
        ttk.Entry(input_frame, textvariable=self.output_var, width=60).grid(row=1, column=1, sticky=tk.EW, padx=5)
        ttk.Button(input_frame, text="Sfoglia", command=self.browse_output).grid(row=1, column=2, padx=5)

        # Compare folder (optional)
        ttk.Label(input_frame, text="Reference (opzionale):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.compare_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.compare_var, width=60).grid(row=2, column=1, sticky=tk.EW, padx=5)
        ttk.Button(input_frame, text="Sfoglia", command=self.browse_compare).grid(row=2, column=2, padx=5)

        input_frame.columnconfigure(1, weight=1)

        # --- Options Section ---
        opt_frame = ttk.LabelFrame(self.root, text="Opzioni", padding=10)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)

        self.api_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Abilita fallback API (Modrinth + CurseForge) per mod UNKNOWN",
                       variable=self.api_var).pack(anchor=tk.W)

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Dry-run (solo analisi, nessuna copia file)",
                       variable=self.dry_run_var).pack(anchor=tk.W)

        # API Key status
        api_status = "✓ Configurata" if config.CURSEFORGE_API_KEY else "✗ Non configurata (solo Modrinth)"
        api_color = "green" if config.CURSEFORGE_API_KEY else "orange"
        self.api_status_label = ttk.Label(opt_frame, text=f"CurseForge API: {api_status}", foreground=api_color)
        self.api_status_label.pack(anchor=tk.W, pady=(5, 0))

        # --- Action Buttons ---
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)

        self.run_btn = ttk.Button(btn_frame, text="▶ Avvia Analisi", command=self.start_analysis, style='Accent.TButton')
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="■ Ferma", command=self.stop_analysis, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Pulisci Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Apri Cartella Output", command=self.open_output_folder).pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(btn_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

        # --- Log Output ---
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # Tag per colorazione
        self.log_text.tag_config('HEADER', foreground='#0066cc', font=('Consolas', 9, 'bold'))
        self.log_text.tag_config('SUCCESS', foreground='#008000')
        self.log_text.tag_config('ERROR', foreground='#cc0000')
        self.log_text.tag_config('WARNING', foreground='#cc8800')
        self.log_text.tag_config('INFO', foreground='#333333')
        self.log_text.tag_config('BOTH', foreground='#0066cc')
        self.log_text.tag_config('CLIENT', foreground='#cc0000')
        self.log_text.tag_config('SERVER', foreground='#008000')
        self.log_text.tag_config('UNKNOWN', foreground='#cc8800')

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def browse_input(self):
        folder = filedialog.askdirectory(title="Seleziona cartella modpack sorgente")
        if folder:
            self.input_var.set(folder)

    def browse_output(self):
        folder = filedialog.askdirectory(title="Seleziona cartella output")
        if folder:
            self.output_var.set(folder)

    def browse_compare(self):
        folder = filedialog.askdirectory(title="Seleziona cartella reference (es. mods-corrected)")
        if folder:
            self.compare_var.set(folder)

    def log(self, message, tag='INFO'):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + '\n', tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def poll_log_queue(self):
        try:
            while True:
                msg, tag = self.log_queue.get_nowait()
                self.log(msg, tag)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_log_queue)

    def start_analysis(self):
        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()
        compare_path = self.compare_var.get().strip() or None

        if not input_path:
            messagebox.showerror("Errore", "Seleziona una cartella modpack sorgente")
            return

        if not Path(input_path).exists():
            messagebox.showerror("Errore", f"Cartella non trovata: {input_path}")
            return

        self.running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start(10)
        self.status_var.set("Analisi in corso...")

        # Thread worker
        self.worker_thread = threading.Thread(
            target=self.run_analysis,
            args=(input_path, output_path, compare_path),
            daemon=True
        )
        self.worker_thread.start()

    def stop_analysis(self):
        self.running = False
        self.status_var.set("Interruzione...")

    def run_analysis(self, input_path, output_path, compare_path):
        try:
            # Redirect print to queue
            import io
            import sys
            from contextlib import redirect_stdout, redirect_stderr

            class QueueWriter:
                def __init__(self, queue, tag):
                    self.queue = queue
                    self.tag = tag
                    self.buffer = ''

                def write(self, s):
                    self.buffer += s
                    lines = self.buffer.split('\n')
                    self.buffer = lines[-1]
                    for line in lines[:-1]:
                        if line.strip():
                            self.queue.put((line, self.tag))

                def flush(self):
                    if self.buffer.strip():
                        self.queue.put((self.buffer, self.tag))
                        self.buffer = ''

            stdout_writer = QueueWriter(self.log_queue, 'INFO')
            stderr_writer = QueueWriter(self.log_queue, 'ERROR')

            with redirect_stdout(stdout_writer), redirect_stderr(stderr_writer):
                analyze_modpack(
                    input_folder=Path(input_path),
                    output_folder=Path(output_path),
                    use_api=self.api_var.get(),
                    compare_folder=Path(compare_path) if compare_path else None,
                    dry_run=self.dry_run_var.get()
                )

            if self.running:
                self.log_queue.put(("\n✅ Analisi completata!", 'SUCCESS'))
                self.root.after(0, lambda: self.status_var.set("Completato"))
            else:
                self.log_queue.put(("\n⏹ Analisi interrotta", 'WARNING'))
                self.root.after(0, lambda: self.status_var.set("Interrotto"))

        except Exception as e:
            self.log_queue.put((f"\n❌ Errore: {e}", 'ERROR'))
            self.root.after(0, lambda: self.status_var.set("Errore"))
        finally:
            self.root.after(0, self.analysis_finished)

    def analysis_finished(self):
        self.running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()

    def open_output_folder(self):
        output_path = self.output_var.get().strip()
        path = Path(output_path)
        if path.exists():
            import subprocess
            subprocess.Popen(f'explorer "{path.absolute()}"')
        else:
            messagebox.showinfo("Info", "Cartella output non esiste ancora. Esegui prima l'analisi.")


def main():
    root = tk.Tk()
    app = ForgeModSearchGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()