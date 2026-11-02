#!/usr/bin/env python3
"""
ForgeModSearch - Mod Separation Tool v4.1.0
Parsing statico metadati JAR + override map + fallback API opzionale.
Funziona su QUALSIASI modpack Minecraft Forge/NeoForge/Fabric.
"""

import os
import sys
import shutil
import argparse
import json
from pathlib import Path
from mod_parser import ModMetadataParser
import config


def normalize_mod_name(name: str) -> str:
    """Normalizza nome mod per matching: lowercase, _ -> -, rimuovi versioni."""
    import re
    name = name.lower()
    name = name.replace('_', '-')
    # Rimuovi pattern versione: -1.20.1, -1.2.3, +build.123, -mc1.20, -forge, -fabric, -neoforge
    name = re.sub(r'-\d+\.\d+\.\d+.*', '', name)
    name = re.sub(r'-\d+\.\d+.*', '', name)
    name = re.sub(r'\+.*', '', name)
    name = re.sub(r'-(forge|fabric|neoforge|mc\d+).*', '', name)
    name = re.sub(r'[^a-z0-9\-]', '', name)
    return name.strip('-')


def get_final_side(jar_path: Path, metadata: dict) -> tuple[str, str]:
    """
    Combina parser + override map + blacklist.
    Returns: (side, reason)
    """
    mod_name_raw = jar_path.stem
    mod_name_norm = normalize_mod_name(mod_name_raw)

    # 1. Override forzato server-side (librerie/API critiche) - PRIORITÀ ASSOLUTA
    for keyword in config.SERVER_SIDE_FORCE_INCLUDE:
        if keyword in mod_name_norm:
            return 'both', f'OVERRIDE: {keyword} (libreria/API necessaria al server)'

    # 2. Blacklist client-only - match su nome normalizzato
    for keyword in config.CLIENT_ONLY_BLACKLIST:
        if keyword in mod_name_norm:
            # Eccezione: se contiene parola "server-safe"
            exception = any(exc in mod_name_norm for exc in config.CLIENT_WORDS_IN_SERVER_MODS)
            if not exception:
                return 'client', f'BLACKLIST: {keyword} (mod client-only nota)'

    # 3. Parser ha identificato client-only
    if metadata['side'] == 'client':
        return 'client', f'PARSER: side=client ({metadata["type"]})'

    # 4. Parser ha identificato server/both
    if metadata['side'] in ('server', 'both'):
        return metadata['side'], f'PARSER: side={metadata["side"]} ({metadata["type"]})'

    # 5. Unknown - servirà fallback API se abilitato
    return 'unknown', f'PARSER: side=unknown ({metadata["type"]})'


def try_api_fallback(jar_path: Path) -> tuple[str, str] | None:
    """
    Tenta fallback API (Modrinth -> CurseForge) per mod UNKNOWN.
    Returns: (side, reason) o None se non abilitato/fallito.
    """
    if not config.CURSEFORGE_API_KEY:
        return None

    # Estrae slug pulito dal nome file
    name = jar_path.stem
    name = name.lower()
    # Rimuovi pattern versione comuni
    import re
    name = re.sub(r'-\d+\.\d+\.\d+.*', '', name)
    name = re.sub(r'-(forge|fabric|neoforge|mc\d+).*', '', name)
    name = re.sub(r'[^a-z0-9\-]', '', name).strip('-')

    if not name:
        return None

    # Prova Modrinth prima (no key needed)
    try:
        import urllib.request
        import urllib.parse

        url = f"{config.MODRINTH_BASE_URL}/{name}"
        req = urllib.request.Request(url, headers=config.MODRINTH_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        client_side = data.get('client_side', '')
        server_side = data.get('server_side', '')

        # Whitelist BOTH
        if name in config.BOTH_WHITELIST:
            return 'both', f'MODRINTH: whitelist BOTH ({name})'

        if client_side == 'unsupported' and server_side in ('required', 'optional'):
            return 'server', f'MODRINTH: server_side={server_side}, client_side=unsupported'
        if client_side in ('required', 'optional') and server_side == 'unsupported':
            return 'client', f'MODRINTH: client_side={client_side}, server_side=unsupported'
        if client_side != 'unsupported' and server_side != 'unsupported':
            return 'both', f'MODRINTH: both sides supported'

    except Exception:
        pass

    # Fallback CurseForge
    try:
        params = urllib.parse.urlencode({
            'gameId': config.CURSEFORGE_GAME_ID,
            'classId': config.CURSEFORGE_CLASS_ID,
            'searchFilter': name,
            'pageSize': 5,
            'sortField': 2,
            'sortOrder': 'desc',
        })
        url = f"{config.CURSEFORGE_BASE_URL}/mods/search?{params}"
        headers = {
            'Accept': 'application/json',
            'x-api-key': config.CURSEFORGE_API_KEY,
            'User-Agent': 'ForgeModSearch/4.1.0',
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        mods = data.get('data', [])
        if not mods:
            return None

        # Match migliore
        matched = mods[0]
        clean_input = name.replace('-', '')
        for m in mods:
            if clean_input in m.get('slug', '').replace('-', ''):
                matched = m
                break

        cat_ids = [c.get('id') for c in matched.get('categories', [])]

        # Categorie client-only strette
        is_client = any(cid in config.STRICT_CLIENT_CATEGORIES for cid in cat_ids)
        if 421 in cat_ids or 414 in cat_ids:  # API/Library o Transport
            is_client = False

        if is_client:
            return 'client', f'CURSEFORGE: categorie client-only {[config.CURSEFORGE_CATEGORIES.get(c, c) for c in cat_ids]}'
        else:
            return 'both', f'CURSEFORGE: server-ready {[config.CURSEFORGE_CATEGORIES.get(c, c) for c in cat_ids]}'

    except Exception:
        pass

    return None


def analyze_modpack(input_folder: Path, output_folder: Path, use_api: bool, compare_folder: Path | None, dry_run: bool) -> dict:
    """Analizza un modpack completo."""

    print(f"\n{'='*60}")
    print(f"  ForgeModSearch v4.1.0 - Modpack Separator")
    print(f"{'='*60}")
    print(f"  Input:      {input_folder}")
    print(f"  Output:     {output_folder}")
    print(f"  API Fallback: {'ON' if use_api else 'OFF (solo statico)'}")
    print(f"  Dry-run:    {'SÌ' if dry_run else 'NO'}")
    if compare_folder:
        print(f"  Compare:    {compare_folder}")
    print(f"{'='*60}\n")

    if not input_folder.exists():
        print(f"ERRORE: Cartella input non trovata: {input_folder}")
        sys.exit(1)

    if not dry_run:
        output_folder.mkdir(parents=True, exist_ok=True)

    # Carica reference per confronto
    reference_mods = set()
    if compare_folder and compare_folder.exists():
        reference_mods = {f.name for f in compare_folder.glob("*.jar")}

    # Statistiche
    stats = {
        'total': 0, 'server': 0, 'client': 0, 'unknown': 0,
        'api_used': 0, 'matched_ref': 0, 'missed_ref': 0, 'extra_ref': 0
    }

    results = []

    jar_files = sorted(input_folder.glob("*.jar"))
    print(f"Trovate {len(jar_files)} mod da analizzare...\n")

    for jar_path in jar_files:
        stats['total'] += 1

        # 1. Parsing statico
        metadata = ModMetadataParser.get_jar_metadata(jar_path)
        side, reason = get_final_side(jar_path, metadata)

        # 2. Fallback API se UNKNOWN e abilitato
        if side == 'unknown' and use_api:
            api_result = try_api_fallback(jar_path)
            if api_result:
                side, reason = api_result
                stats['api_used'] += 1

        # 3. Decisione
        in_reference = jar_path.name in reference_mods
        action = 'COPY' if side in ('both', 'server') else 'SKIP'

        result = {
            'file': jar_path.name,
            'side': side,
            'reason': reason,
            'action': action,
            'in_reference': in_reference,
            'parser_type': metadata['type'],
        }
        results.append(result)

        # Output per mod
        status_tag = f"[{side.upper()}]"
        ref_tag = " ✓" if in_reference else " ✗" if action == 'COPY' else ""
        print(f"  {status_tag:12} {jar_path.name:<60} {reason}{ref_tag}")

        if action == 'COPY':
            stats['server'] += 1
            if not dry_run:
                shutil.copy2(jar_path, output_folder / jar_path.name)
        elif side == 'client':
            stats['client'] += 1
        else:
            stats['unknown'] += 1

    # Confronta con reference
    if compare_folder:
        copied_names = {r['file'] for r in results if r['action'] == 'COPY'}
        stats['matched_ref'] = len(copied_names & reference_mods)
        stats['missed_ref'] = len(reference_mods - copied_names)
        stats['extra_ref'] = len(copied_names - reference_mods)

    # Report finale
    print(f"\n{'='*60}")
    print(f"  RISULTATO FINALE")
    print(f"{'='*60}")
    print(f"  Mod totali analizzate:    {stats['total']}")
    print(f"  → Server-Ready (copiate): {stats['server']}")
    print(f"  → Client-Only (scartate): {stats['client']}")
    print(f"  → Unknown (da verificare): {stats['unknown']}")
    if use_api:
        print(f"  → Risolte via API:        {stats['api_used']}")

    if compare_folder:
        print(f"\n  CONFRONTO vs {compare_folder.name}:")
        print(f"  ✓ Corrette (match):        {stats['matched_ref']}/{len(reference_mods)}")
        print(f"  ✗ Mancanti (false negative): {stats['missed_ref']}")
        for r in results:
            if r['in_reference'] and r['action'] == 'SKIP':
                print(f"      - {r['file']} ({r['reason']})")
        print(f"  ⚠ Extra (false positive):  {stats['extra_ref']}")
        for r in results:
            if not r['in_reference'] and r['action'] == 'COPY':
                print(f"      + {r['file']} ({r['reason']})")

        accuracy = stats['matched_ref'] / len(reference_mods) * 100 if reference_mods else 0
        print(f"\n  Accuracy: {accuracy:.1f}%")

    # Salva report JSON
    report_path = output_folder / 'separation_report.json'
    if not dry_run:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({'stats': stats, 'results': results}, f, indent=2, ensure_ascii=False)
        print(f"\n  Report JSON: {report_path}")

    return {'stats': stats, 'results': results}


def main():
    parser = argparse.ArgumentParser(
        description='Separa mod Server-Ready da Client-Only per qualsiasi modpack Minecraft',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Base: analizza modpack e copia server-ready
  python separate_mods.py -i "E:/MinecraftCurse/Instances/MyPack/mods" -o "./mods/Server_Ready"

  # Con fallback API per mod UNKNOWN (richiede CURSEFORGE_API_KEY)
  python separate_mods.py -i ./mods -o ./out --api

  # Dry-run + confronto con reference noto
  python separate_mods.py -i ./mods -o ./out --compare ./mods/mods-corrected --dry-run

  # Solo analisi, nessuna copia
  python separate_mods.py -i ./mods --list-only
        """
    )
    parser.add_argument('-i', '--input', type=Path, required=True,
                       help='Cartella modpack sorgente (con file .jar)')
    parser.add_argument('-o', '--output', type=Path, default=Path('./mods/Server_Ready'),
                       help='Cartella destinazione mod server-ready')
    parser.add_argument('--api', action='store_true',
                       help='Abilita fallback API (Modrinth + CurseForge) per mod UNKNOWN')
    parser.add_argument('--compare', type=Path, metavar='REF_FOLDER',
                       help='Cartella reference (es. mods-corrected) per calcolo accuracy')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo analisi, nessuna copia file')
    parser.add_argument('--list-only', action='store_true',
                       help='Solo lista classificazione, nessuna copia né report')
    args = parser.parse_args()

    if args.list_only:
        args.dry_run = True
        args.output = Path('./tmp_dummy')
        args.api = False

    analyze_modpack(
        input_folder=args.input,
        output_folder=args.output,
        use_api=args.api,
        compare_folder=args.compare,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()