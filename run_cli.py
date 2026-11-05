#!/usr/bin/env python3
"""
Launcher CLI per ForgeModSearch - gestisce argomenti con spazi correttamente.
Uso: python run_cli.py -i "path con spazi" -o "output" [--dry-run]
   O: python run_cli.py  (modalita interattiva)
"""
import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SEPARATE_MODS = SCRIPT_DIR / "separate_mods.py"

def main():
    # Verifica Python
    try:
        subprocess.run([sys.executable, "--version"], capture_output=True, check=True)
    except Exception:
        print("Python non trovato. Usa ForgeModSearch_GUI.exe")
        input("Premi INVIO per uscire...")
        return 1

    if not SEPARATE_MODS.exists():
        print(f"separate_mods.py non trovato in {SCRIPT_DIR}")
        input("Premi INVIO per uscire...")
        return 1

    if len(sys.argv) == 1:
        # Modalita interattiva
        print("ForgeModSearch v4.1.0 - Modalita interattiva")
        print()
        input_path = input("Cartella modpack sorgente: ").strip()
        if not input_path:
            return 0
        output_path = input("Cartella output [./mods/Server_Ready]: ").strip() or "./mods/Server_Ready"
        dry_run = input("Solo dry-run? [s/N]: ").strip().lower() == 's'

        cmd = [sys.executable, str(SEPARATE_MODS), "-i", input_path, "-o", output_path]
        if dry_run:
            cmd.append("--dry-run")

        print(f"Eseguo: {' '.join(cmd)}")
        print()
        result = subprocess.run(cmd)
        try:
            if sys.stdin.isatty():
                input("\nPremi INVIO per uscire...")
        except (EOFError, OSError):
            pass
        return result.returncode
    else:
        # Modalita non-interattiva: passa argomenti direttamente, NON attendere input
        cmd = [sys.executable, str(SEPARATE_MODS)] + sys.argv[1:]
        print(f"Eseguo: {' '.join(cmd)}")
        print()
        result = subprocess.run(cmd)
        return result.returncode

if __name__ == "__main__":
    sys.exit(main())