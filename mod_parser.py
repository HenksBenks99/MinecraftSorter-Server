import zipfile
import tomllib
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

class ModMetadataParser:
    """Parser robusto per estrarre metadati da jar di Forge/NeoForge/Fabric."""

    @staticmethod
    def get_jar_metadata(jar_path: Path) -> Dict[str, Any]:
        """
        Analizza un jar per estrarre metadati.
        Ritorna un dizionario con {type: 'forge'|'fabric'|'unknown', side: 'client'|'server'|'both'|'unknown', name: <jar_name>}
        """
        metadata = {'type': 'unknown', 'side': 'unknown', 'name': jar_path.name}

        try:
            with zipfile.ZipFile(jar_path, 'r') as z:
                namelist = z.namelist()

                # 1. Prova a identificare come Forge/NeoForge
                toml_files = [n for n in namelist if n.startswith('META-INF/') and (n.endswith('mods.toml') or n.endswith('neoforge.mods.toml'))]
                if toml_files:
                    metadata['type'] = 'forge'
                    toml_path = toml_files[0]
                    try:
                        with z.open(toml_path) as f:
                            content = f.read().decode('utf-8')
                            toml_data = tomllib.loads(content)
                            metadata['side'] = ModMetadataParser._parse_forge_side(toml_data)
                    except Exception as e:
                        print(f"    [DEBUG] Errore parsing TOML in {jar_path.name}: {e}")

                # 2. Prova a identificare come Fabric (se non Forge)
                elif 'fabric.mod.json' in namelist:
                    metadata['type'] = 'fabric'
                    try:
                        with z.open('fabric.mod.json') as f:
                            data = json.load(f)
                            env = data.get('environment', 'both')
                            # environment "*" = both
                            if env == '*':
                                env = 'both'
                            # Se environment non specificato, controlla entrypoints
                            if env == 'both' or env == 'unknown':
                                entrypoints = data.get('entrypoints', {})
                                has_client = 'client' in entrypoints
                                has_main = 'main' in entrypoints
                                if has_client and has_main:
                                    env = 'both'
                                elif has_client:
                                    env = 'client'
                                elif has_main:
                                    env = 'server'
                            metadata['side'] = env
                            # Rileva dipendenze Fabric - se richiede fabricloader/fabric-api, NON gira su Forge
                            depends = data.get('depends', {})
                            if 'fabricloader' in depends or 'fabric-api' in depends:
                                metadata['fabric_only'] = True
                    except Exception as e:
                        print(f"    [DEBUG] Errore parsing Fabric JSON in {jar_path.name}: {e}")
        except Exception as e:
            print(f"    [DEBUG] Errore nel parsing del file: {jar_path.name} -> {e}")

        return metadata

    @staticmethod
    def _parse_forge_side(toml_data: Dict) -> str:
        """
        Estrae il lato di una mod Forge dal TOML.
        La chiave ufficiale è 'side' all'interno del blocco [[mods]].
        Se 'side' è assente, di default (Forge) è 'both'.
        """
        mod_list = toml_data.get('mods', [])
        if not mod_list:
            # Supporto per formati diversi (es. 'mod' al posto di 'mods')
            mod_list = [toml_data.get('mod', {})]

        for mod in mod_list:
            if isinstance(mod, dict):
                # 1. Controlla la chiave 'side' (ufficiale)
                side = str(mod.get('side', '')).lower()
                if side in ('client', 'server'):
                    return side
                elif side == 'both':
                    return 'both'

                # 2. Fallback: Controlla 'displayTest' (meno comune)
                display_test = str(mod.get('displayTest', '')).lower()
                if display_test in ('client', 'server'):
                    return display_test
                elif display_test == 'both':
                    return 'both'

        # 3. Se nessuno specifica 'side', ma il parsing ha trovato [[mods]],
        #    assumiamo 'both' (comportamento predefinito di Forge)
        if mod_list:
            return 'both'

        return 'unknown'

# --- ESEMPIO DI UTILIZZO ---
if __name__ == "__main__":
    test_file = Path("mods/mods-corrected/jei-1.20.1-forge-15.20.0.112.jar")
    if test_file.exists():
        print(ModMetadataParser.get_jar_metadata(test_file))
