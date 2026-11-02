# Changelog

Tutti i cambiamenti importanti per questo progetto sono documentati in questo file.

## [4.0.0] - 2026-11-02

### Refactor Completo (Breaking: nuovo entry point)

- **Nuovo entry point**: `separate_mods.py` (~70 linee) - sostituisce `forge_mod_separation.py` (45KB, 1050+ linee)
- **Rimosso codice duplicato/morto**: 13 file eliminati (`forge_mod_separation.py`, `forge_mod_separation_refactored.py`, `testapicurse.py`, `curseforge_checker.py`, `compare_mods.py`, `config.example.py`, 8 file `test_*.py`)
- **API key CurseForge**: Ora **solo** da variabile d'ambiente `CURSEFORGE_API_KEY` (rimossa da `config.py` e codice)
- **Override map centralizzata**: `SERVER_SIDE_FORCE_INCLUDE` in `config.py` con commenti per ogni mod
- **Architettura pulita**: `mod_parser.py` (parsing statico) + `config.py` (config) + `separate_mods.py` (logica)
- **Funziona offline**: Zero dipendenze esterne, parsing deterministico
- **Rimosso**: `lib/` (package vuoto), `cf_cache.json`, `__pycache__/`

### Sicurezza
- **Nessuna API key nel codice** - se era nella history Git, **revocala e rigenerala** su curseforge.com
- `.gitignore` protegge: `config.py`, `cf_cache.json`, `*.env`, `mods/`, `*.jar`

---

## [4.1.1] - 2026-10-30

### Sicurezza
- **Rimossa l'API key CurseForge hardcoded** da `forge_mod_separation.py` (era presente nel codice versionato)
- La chiave ora viene letta da:
  1. variabile d'ambiente `CURSEFORGE_API_KEY`
  2. `config.py` locale (escluso da `.gitignore`)
- `test_api_modrinth_curseforge.py` e `testapicurse.py` aggiornati per usare la variabile d'ambiente invece di un valore nel codice

> ⚠️ **Azione richiesta**: la chiave resta nella cronologia Git dei commit precedenti. Va **revocata e rigenerata** dalla dashboard CurseForge.

---

## [4.1.0] - 2026-10-30

### Aggiunti
- **`mod_parser.py`**: nuovo parser che legge la chiave ufficiale `side` dentro `[[mods]]` (Forge/NeoForge) e `environment` (Fabric), restituendo `client` / `server` / `both` / `unknown`
- **`forge_mod_separation_refactored.py`**: riscrittura della logica di separazione basata sui metadati interni dei jar
- **Mappa `SERVER_SIDE_FORCE_INCLUDE`**: override espliciti per librerie/API necessarie al server (`kotlinforforge`, `jei`, `ferritecore`, `connector`, `polymorph`, `searchables`, `journeymap`, `tconjei`, `appleskin`, ecc.)
- **`.gitignore`**: aggiunti `mods/`, `*.jar`, `*.jar.disabled`, `Server Mod/`, `Server_Ready/` e i report generati

### Corretto
- **Causa dei falsi positivi**: la logica precedente leggeva `displayTest`, che NON indica il lato della mod. `displayTest` controlla solo il match client/server in multiplayer; la chiave corretta è `side` in `[[mods]]`
- **Librerie di dipendenza**: `kotlinforforge` e simili vengono forzate lato server, evitando crash del tipo `requires kotlinforforge X or above`
- **`.gitignore`**: rimossa la regola `lib/`, che avrebbe escluso il package sorgente del progetto

### Rimosso
- **419 jar tracciati** (~906 MB) sotto `mods/`: i jar delle mod non devono essere versionati

---

## [3.5.0] - 2026-10-23

### Aggiunti
- **Fallback automatico su CurseForge API**: Quando Modrinth non trova una mod (404), il fallback su CurseForge è automatico
- **Nuova funzione `search_curseforge()`**: Cerca mod su CurseForge API con parametri corretti
- **Nuova funzione `classify_curseforge()`**: Classifica mod basandosi sulle categorie CurseForge
- **File di configurazione `config.example.py`**: Template per configurazioni personalizzate
- **File `.gitignore` aggiornato**: Esclude `config.py`, `cf_cache.json`, `*.env`, `*.cache`
- **File `README.md` aggiornato**: Istruzioni complete su come configurare le API

### Corretto
- **Header Authorization CurseForge**: Cambiato da `Authorization: Bearer` a `x-api-key`
- **Parametri URL CurseForge**: Aggiunti `classId=6`, `sortField`, `sortOrder`, `pageSize`
- **Parsing dei dati CurseForge**: Estrazione corretta di `title`, `slug`, `version`, `categories`
- **Categorie client-only**: Aggiunte categorie 423, 6814, 421, 414
- **Variabile `CURSEFORGE_CLASS_ID`**: Corretto errore `name 'CURSEFORGE_CLASS_ID' is not defined`

### Testati
- **API Modrinth**: Funzionante (testato)
- **API CurseForge**: Funzionante (testato con testapicurse.py)
- **Fallback automatico**: Attivo e funzionante
- **Classificazione Journeymap**: CLIENT_ONLY su CurseForge (categoria 423)
- **Classificazione Architectury**: BOTH su CurseForge (categoria API and Library)

---

## [3.4.0] - 2026-10-23

### Aggiunti
- **`BOTH_WHITELIST`**: Lista di mod note classificate come BOTH anche se `client_side=required`
- **Funzione `classify_curseforge()`**: Classifica mod basandosi sulle categorie CurseForge

### Corretto
- **Parsing dati Modrinth**: Usato `mod_data.get('title', '')` invece di `mod_data.get('name', '')`
- **Parsing dati Modrinth**: Usato `mod_data.get('versions', [])[0]` invece di `mod_data.get('latestVersion', '')`
- **Report**: Mostrato "Modrinth Title" invece di "Modrinth Name"

---

## [3.3.0] - 2026-10-22

### Corretto
- **API Modrinth**: Usa i campi corretti `title` e `versions` invece di `name` e `latestVersion`
- **Parsing dati Modrinth**: Ora restituisce correttamente name, slug, version
- **Report**: Mostra "Modrinth Title" invece di "Modrinth Name"

---

## [3.2.0] - 2026-10-22

### Migliorato
- **Parsing dati Modrinth**: Ora estrae correttamente name, slug, version
- **Threshold di fiducia**: Aumentato da 0.85 a 0.90 per evitare falsi positivi
- **Logica di classificazione**: Più robusta per displayTest="both"
- **Funzione `update_cache()`**: Separata per migliorare la cache

### Corretto
- **Nomi dei file**: Le mod vengono copiate nella cartella "Server Mod" con il nome originale (con estensione .jar)

---

## [3.1.0] - 2026-10-22

### Corretto
- **Nomi dei file**: Le mod vengono copiate nella cartella "Server Mod" con il nome originale (con estensione .jar)

---

## [3.0.0] - 2026-10-22

### Migrato
- **Rimossa CurseForge**: Ora solo Modrinth API + classificazione statica

### Ristrutturato
- **Flusso semplificato**: Funzione `analyze_mod()` unifica il processo
- **Timeout API aumentato**: Da 5 a 10 secondi
- **Gestione errori più robusta**

---

## [2.5.0] - 2026-10-21

### Aggiunto
- **Integrazione API Modrinth come priorità**
- **Gestione cache locale** (`cf_cache.json`)
- **CurseForge ora è fallback** invece che principale

---

## [2.1.0] - 2026-10-20

### Aggiunto
- **Analisi statica** (lettura dei file .toml/.json)
- **Blacklist** per classificazione rapida

---

## [1.2.0] - 2026-10-22

### Aggiunto
- **Analisi statica** (lettura dei file .toml/.json)
- **Blacklist** per classificazione rapida

---

## [1.0.0] - 2026-10-19

### Rilascio iniziale
- **Analisi statica**
- **Classificazione basata su nome**
- **Blacklist/Whitelist**

---

<div align="center">

**ForgeModSearch - Made with ❤️ by Riccardo**

</div>