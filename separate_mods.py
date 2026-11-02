#!/usr/bin/env python3
"""
ForgeModSearch - Mod Separation Tool v4.0.0
Usa metadati interni dei jar + override map per classificare correttamente le mod.
Entry point principale - usa mod_parser.py + config.py
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from mod_parser import ModMetadataParser
import config


def get_final_side(jar_path: Path, metadata: dict) -> str:
    """
    Combina il risultato del parser con la mappa di override.
    Priorità assoluta: se in SERVER_SIDE_FORCE_INCLUDE, va sempre al server (both).
    """
    mod_name_lower = jar_path.stem.lower()

    # 1. Controllo override forzato verso il server
    if any(keyword in mod_name_lower for keyword in config.SERVER_SIDE_FORCE_INCLUDE):
        print(f"    [INFO] Override: {jar_path.name} forzato a SERVER (libreria API necessaria)")
        return 'both'  # 'both' garantisce la copia nel server

    # 2. Se il parser ha identificato 'client', rispetta
    if metadata['side'] == 'client':
        return 'client'

    # 3. Rispetta il parsing dinamico altrimenti
    return metadata['side']


def main():
    parser = argparse.ArgumentParser(description='Separazione intelligente mod server-side')
    parser.add_argument('--input', type=Path, default=Path('./mods/mods-corrected'))
    parser.add_argument('--output', type=Path, default=Path('./mods/Server_Ready'))
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Errore: Cartella di input {args.input} non trovata.")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Analisi mod in: {args.input}")
    print(f"Destinazione server: {args.output}")

    # Statistiche
    stats = {'server': 0, 'client': 0, 'unknown': 0}

    # Processamento
    for jar_path in args.input.glob("*.jar"):
        # 1. Analisi Metadati Interni
        metadata = ModMetadataParser.get_jar_metadata(jar_path)

        # 2. Applica logica di override
        final_side = get_final_side(jar_path, metadata)

        # 3. Decisione
        if final_side in ['both', 'server']:
            shutil.copy2(jar_path, args.output / jar_path.name)
            stats['server'] += 1
            print(f"[SERVER] {jar_path.name}")
        elif final_side == 'client':
            stats['client'] += 1
            print(f"[CLIENT] {jar_path.name}")
        else:
            stats['unknown'] += 1
            print(f"[UNKNOWN] {jar_path.name}")

    print("\n--- ANALISI COMPLETATA ---")
    print(f"Mod Server-Ready copiate: {stats['server']}")
    print(f"Mod Client-Only ignorate: {stats['client']}")
    print(f"Mod da verificare: {stats['unknown']}")


if __name__ == '__main__':
    main()