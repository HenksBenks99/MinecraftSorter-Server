# ForgeModSearch - Mod Separation Tool

<div align="center">

## 🔍 Identifica e separa mod Client-Only dalle mod Server-Ready per Minecraft modpacks

**ForgeModSearch v4.0.0** - Parsing statico metadati JAR + override server-side

</div>

---

## 🎯 Caratteristiche Principali

- ✅ **Analisi Statica Veloce**: Legge `fabric.mod.json`, `mods.toml`, `neoforge.mods.toml` dai file `.jar`
- ✅ **Campo `side` Ufficiale**: Usa la chiave `side` di Forge/NeoForge (non `displayTest` deprecato)
- ✅ **Override Server-Side**: Librerie/API critiche forzate lato server (`jei`, `ferritecore`, `kotlinforforge`, `journeymap`, `connector`, ...)
- ✅ **Zero Dipendenze Esterne**: Funziona **completamente offline** (Python 3.11+ nativo)
- ✅ **API Key Opzionale**: CurseForge solo come fallback per mod `UNKNOWN` (via env var)
- ✅ **Sicuro**: Nessuna API key hardcoded - `.gitignore` protegge `config.py`

---

## 📦 Requisiti

- **Python 3.11+** (usa `tomllib` nativo)
- **Python 3.8-3.10**: `pip install tomli`

```bash
# Verifica versione
python --version
```

---

## 🚀 Uso Rapido

```bash
# Analizza mod in mods-corrected, copia server-ready in Server_Ready
python separate_mods.py --input ./mods/mods-corrected --output ./mods/Server_Ready

# Dry-run (solo analisi, nessuna copia)
python separate_mods.py --input ./mods/mods-corrected --output ./mods/Server_Ready --dry-run
```

**Output esempio:**
```
Analisi mod in: mods\mods-corrected
Destinazione server: mods\Server_Ready
[SERVER] jei-1.20.1-forge-15.20.0.112.jar
[INFO] Override: jei-1.20.1-forge-15.20.0.112.jar forzato a SERVER (libreria API necessaria)
[SERVER] create-1.20.1-6.0.8.jar
[CLIENT] sodium-1.20.1.jar
...
--- ANALISI COMPLETATA ---
Mod Server-Ready copiate: 209
Mod Client-Only ignorate: 12
Mod da verificare: 0
```

## 🪟 Interfaccia Grafica

```bash
python gui.py
```

Scegli la cartella delle mod e la destinazione, poi premi **Analizza modpack**. Opzioni:

- **Solo anteprima**: analizza senza copiare nessun file
- **Opzioni avanzate**: controllo online delle mod sconosciute, **chiave API CurseForge** (con indicatore di stato) e cartella di confronto

## 🖥️ Creazione Eseguibili (.exe)

Per creare eseguibili standalone per CLI e GUI (richiede [PyInstaller](https://pyinstaller.org/)):

1. **Installa PyInstaller**:
   ```bash
pip install pyinstaller
```

2. **Costruisci l'eseguibile CLI**:
   ```bash
pyinstaller --onefile --console --name ForgeModSearch_CLI separate_mods.py
```
   Trova l'eseguibile in `dist/ForgeModSearch_CLI.exe`.

3. **Costruisci l'eseguibile GUI** (usa `gui.py`):
   ```bash
pyinstaller --onefile --windowed --name ForgeModSearch_GUI gui.py
```
   Trova l'eseguibile in `dist/ForgeModSearch_GUI.exe`.

> **Nota**: Gli eseguibili includono tutte le dipendenze. Assicurati che `gui.py` e `separate_mods.py` siano aggiornati prima di costruire.

---

## ⚙️ Configurazione API (Opzionale)

### CurseForge API - Solo per fallback mod UNKNOWN

1. Vai su [https://console.curseforge.com/api](https://console.curseforge.com/#/api-keys)
2. Crea una **Personal Access Token**
3. Imposta come variabile d'ambiente (più sicuro):

```powershell
# Windows (PowerShell - persistente)
[Environment]::SetEnvironmentVariable("CURSEFORGE_API_KEY", "tua_chiave", "User")

# Windows (CMD - sessione corrente)
set CURSEFORGE_API_KEY=tua_chiave

# Linux/Mac
export CURSEFORGE_API_KEY=tua_chiave
```

In alternativa, nella GUI (**Opzioni avanzate**) puoi incollare la chiave nel campo dedicato: viene verificata subito (indicatore: non inserita / valida / non valida) e salvata **solo sul tuo PC**, in `~/.forgemodsearch_gui.json`, mai nel repository.

> **Nota**: Il programma funziona **senza API key**. La key serve solo come fallback online per mod non classificate staticamente (`UNKNOWN`). Con l'override map attuale, `UNKNOWN` = 0.

---

## 📂 Struttura Progetto

```
MinecraftSorter-Server/
├── .gitignore              # Protegge config.py, cache, mods/
├── CHANGELOG.md            # Storico versioni
├── config.py               # Config centralizzata (API key SOLO env var)
├── gui.py                  # Interfaccia grafica (tkinter)
├── mod_parser.py           # Parser metadati JAR (Forge/Fabric)
├── README.md               # Questo file
├── run_cli.py / run_cli.bat # Launcher CLI (gestisce percorsi con spazi)
├── separate_mods.py        # Entry point principale (CLI)
├── MODRINTH_INTEGRATION.md # Doc API Modrinth (storico)
└── mods/                   # Tue mod (non versionate)
    ├── mods-corrected/     # Input: modpack da analizzare
    └── Server_Ready/       # Output: mod server-side pronte
```

---

## 🔄 Come Funziona

### 1. Parsing Metadati Interni (Priorità 1)
Lo script legge **solo file dentro al `.jar`**:
- **Forge/NeoForge**: `META-INF/mods.toml` / `META-INF/neoforge.mods.toml` → campo `side`
- **Fabric**: `fabric.mod.json` → campo `environment` + `entrypoints`

### 2. Override Map (Priorità 2 - Forza Server)
Da `config.py` - `SERVER_SIDE_FORCE_INCLUDE`:
| Mod | Motivo |
|-----|--------|
| `jei` | API integrazione item lato server |
| `ferritecore` | Ottimizzazione memoria fondamentale |
| `journeymap` | Fornisce dati API al server |
| `kotlinforforge` | Libreria necessaria a mod server-side |
| `connector` | Bridge Fabric→Forge |
| `tconjei`, `appleskin`, `searchables`, `polymorph` | API/integrazioni server |

### 3. Decisione Finale
| Risultato Parser | Override | Azione |
|------------------|----------|--------|
| `server` / `both` | - | ✅ Copia in `Server_Ready/` |
| `client` | No | ❌ Ignora (client-only) |
| `client` | Sì | ✅ Forza `both` → Copia |
| `unknown` | - | ⚠️ Segnala da verificare |

---

## 🛡️ Sicurezza

### File MAI da committare (già in `.gitignore`):
- `config.py` - Config locale (può contenere override custom)
- `cf_cache.json` - Cache runtime API
- `*.env` - Variabili d'ambiente
- `mods/` - File `.jar` (binari grandi)

### Best Practice:
1. **API key solo in env var** - Mai in `config.py` né nel codice
2. **Non versionare `mods/`** - Usa `.gitignore` (già configurato)
3. **Rigenera key se esposta** - Su curseforge.com → API settings

---

## 📜 Changelog Principale

| Versione | Cambiamenti |
|----------|-------------|
| **v4.0.0** | Refactor completo: rimosso `forge_mod_separation.py` (45KB duplicato), nuovo `separate_mods.py` minimal, API key solo env var, override map centralizzata |
| **v3.5.0** | Integrazione Modrinth API prioritaria, fallback CurseForge automatico |
| **v3.2.0** | Parsing `displayTest` + whitelist BOTH |
| **v1.0.0** | Prima versione - parsing base TOML |

Vedi [CHANGELOG.md](CHANGELOG.md) per dettagli.

---

## 🐛 Debug / Verifica

```bash
# Test parser singolo file
python -c "from mod_parser import ModMetadataParser; from pathlib import Path; print(ModMetadataParser.get_jar_metadata(Path('mods/mods-corrected/tua_mod.jar')))"

# Verifica override attivi
python -c "import config; print('Override:', config.SERVER_SIDE_FORCE_INCLUDE)"
```

---

## 🤝 Contribuire

1. Fork → branch → PR
2. Mantieni `separate_mods.py` sotto 100 linee
3. Nuove override in `config.py` → `SERVER_SIDE_FORCE_INCLUDE` con commento motivo

---

## 📞 Contatti

- **GitHub**: [HenksBenks99](https://github.com/HenksBenks99)
- **Repo**: https://github.com/HenksBenks99/mod-server-sorter

---

<div align="center">

**Made with ❤️ by Henks**

</div>
