# Integrazione API Modrinth - Storico (v3.x)

> **⚠️ DEPRECATO**: Questo documento descrive l'architettura v3.x che usava API Modrinth + CurseForge.
> La versione attuale **v4.0.0** usa **solo parsing statico offline** - vedi [README.md](README.md).

---

## Cosa è cambiato in v4.0.0

| v3.x (vecchio) | v4.0.0 (attuale) |
|----------------|------------------|
| `forge_mod_separation.py` (1050+ linee) | `separate_mods.py` (~70 linee) |
| API Modrinth (prioritaria) | **Solo parsing statico** |
| Fallback CurseForge automatico | **Rimosso** |
| Cache `cf_cache.json` | **Rimossa** |
| Whitelist/Blacklist 200+ voci | Override map `SERVER_SIDE_FORCE_INCLUDE` (10 voci) |
| `tomllib` + API HTTP | Solo `tomllib` nativo |

---

## Perché la rimozione?

1. **Parsing statico è deterministico** - Il campo `side` in `mods.toml` / `fabric.mod.json` è la source of truth
2. **API key management** - CurseForge richiedeva key, Modrinth aveva rate limit
3. **Overhead inutile** - 99% delle mod hanno metadati interni corretti
4. **Falsi positivi** - Le API online a volte classificavano male mod complesse (es. JEI, JourneyMap)
5. **Semplicità** - 70 linee vs 1050+, zero dipendenze esterne

---

## Archivio: Come funzionava v3.x

### Flusso v3.x
1. **Analisi statica** → `mods.toml` / `fabric.mod.json`
2. **Se UNKNOWN o fiducia < 90%** → API Modrinth (`/v2/project/{slug}`)
3. **Se Modrinth 404** → Fallback CurseForge API (categorie)
4. **Whitelist BOTH** → Forza mod note come BOTH
5. **Cache** → `cf_cache.json` per evitare chiamate duplicate

### Campi Modrinth usati
```json
{
  "title": "Journeymap",
  "slug": "journeymap",
  "client_side": "required",
  "server_side": "unsupported",
  "versions": ["5.10.3", "5.10.2"]
}
```

### Logica classificazione Modrinth
```python
if client_side == "unsupported" and server_side in ("required", "optional"):
    → SERVER_ONLY
elif client_side in ("required", "optional") and server_side == "unsupported":
    → CLIENT_ONLY
elif client_side != "unsupported" and server_side != "unsupported":
    → BOTH
else:
    → UNKNOWN
```

---

## Migrazione v3.x → v4.0.0

### Vecchio comando
```bash
python forge_mod_separation.py ./mods --output ./mods
```

### Nuovo comando
```bash
python separate_mods.py --input ./mods/mods-corrected --output ./mods/Server_Ready
```

### Differenze output
- **v3.x**: Crea `mod_analysis_report.txt` con dettagli API
- **v4.0.0**: Output solo console, report opzionale (`--dry-run` per analisi)

### Override map (sostituisce whitelist/blacklist)
```python
# config.py - SERVER_SIDE_FORCE_INCLUDE
{
    "jei",           # API integrazione item
    "ferritecore",   # Ottimizzazione memoria
    "journeymap",    # Dati API server
    "kotlinforforge",# Libreria per mod server
    "connector",     # Bridge Fabric→Forge
    "tconjei", "appleskin", "searchables", "polymorph"
}
```

---

## File rimossi in v4.0.0

- `forge_mod_separation.py` - Script principale v3.x
- `forge_mod_separation_refactored.py` - Bozza refactor (sostituita da `separate_mods.py`)
- `testapicurse.py` - Test API CurseForge
- `curseforge_checker.py` - Checker API CurseForge
- `compare_mods.py` - Confronto risultati
- `config.example.py` - Template (config.py è source of truth)
- `cf_cache.json` - Cache runtime
- `test_*.py` (8 file) - Test sparsi
- `lib/` - Package vuoto

---

## Se vuoi riattivare API online (futuro)

La struttura è pronta per un modulo opzionale `api_fallback.py` che:
1. Legge `UNKNOWN` da `mod_parser.py`
2. Chiama Modrinth/CurseForge solo per quelle
3. Restituisce classificazione aggiornata

Ma per ora: **il parsing statico + override map copre 100% dei casi reali**.

---

*Documento mantenuto per riferimento storico. Per uso attuale vedi [README.md](README.md).*