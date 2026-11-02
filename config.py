#!/usr/bin/env python3
"""
Configuration file for ForgeModSearch
=====================================

⚠️  IMPORTANT: Questo file contiene configurazioni!
⚠️  API key CurseForge va SOLO in variabile d'ambiente CURSEFORGE_API_KEY
⚠️  NON commitare mai API key su GitHub!
"""

import os

# ============================================================================
# MODRINTH API (PRIORITARIA)
# ============================================================================
MODRINTH_BASE_URL = "https://api.modrinth.com/v2/project"
MODRINTH_HEADERS = {
    'User-Agent': 'ForgeModSearch/4.0.0 (Riccardo.Contatto.GitHub)',
}

# ============================================================================
# CURSEFORGE API (FALLBACK AUTOMATICO) - SOLO DA ENV VAR
# ============================================================================
CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY", "").strip()

CURSEFORGE_BASE_URL = "https://api.curseforge.com/v1"
CURSEFORGE_GAME_ID = 432  # Minecraft
CURSEFORGE_MODS_ENDPOINT = "/mods/search"
CURSEFORGE_CLASS_ID = 6  # Solo Mods

# Categorie CurseForge (Minecraft gameId: 432)
CURSEFORGE_CATEGORIES = {
    421: "API and Library",
    414: "Player Transport",
    423: "Map and Information",
    424: "Cosmetic",
    436: "Food",
    6814: "Optimization/Performance",
    425: "Utility / Miscellaneous",
}

# Categorie che identificano mod strettamente Client-Only
STRICT_CLIENT_CATEGORIES = {
    423,  # Map and Information (Minimappe)
    6814,  # Optimization / Performance (Shaders, Sodium, Embeddium)
}

# ============================================================================
# WHITELIST MOD NOTE CHE SONO BOTH (anche se client_side=required)
# ============================================================================
BOTH_WHITELIST = {
    "jei", "rei", "emi", "jade", "entity_model_features",
    "entity_texture_features", "fallingleaves", "helditemtooltips",
    "holdmyitems", "mouse-tweaks", "presencefootsteps",
    "soundphysicsremastered", "sounds", "immerse-ui", "betterpingdisplay",
    "inventorytweaks", "mousewheelie", "controlling", "ferritecore",
    "distant-horizons", "dynamicfps", "tconjei", "searchables",
    "stackrefill", "fabric-api", "architectury", "balm",
    "cloth-config", "modmenu", "kotlinforforge", "geckolib",
    "polytone", "yet-another-config-lib-v3", "puzzleslib",
    "let-s-do", "handcrafted", "cristellib", "mdm",
    "resourcefullib", "moonlight", "octolib", "obscure-api",
    "player-animation-lib-forge", "playeranimatorapi",
    "tinkersinnovation", "mimimod", "tinkerbettercombat",
    "tinkersjewelry", "tinkersdelight", "create-tinkers-compat",
    "create-ore-excavation", "create-struct-arise", "create-questing",
    "create-connected", "create-deco", "create-numismatics",
    "create-addition", "tconstruct", "mantle", "l2library",
    "ldlib", "decorative-blocks", "delightful", "does-it-tick",
    "dynamic-trees", "dynamic-trees-plus", "immersive-weathering",
    "iter-rpg",
}

# ============================================================================
# BLACKLIST E WHITELIST PER CLASSIFICAZIONE STATICA
# ============================================================================
LIBRARY_DEPENDENCIES = {
    "kotlinforforge", "geckolib", "polytone", "modmenu",
}

CLIENT_ONLY_BLACKLIST = {
    "sodium", "rubidium", "iris", "embeddium", "embed", "ophiurei",
    "oculus", "turbo", "turbo-api", "optifine",
    "journeymap", "xaerominimap", "xaeroworldmap",
    "appleskin", "inventorytweaks", "mousewheelie", "controlling",
    "ferritecore", "jei", "rei", "emi", "waystones",
    "animatica", "cameraoverhaul", "distant-horizons", "dynamic-fps",
    "enhanced-boss-bars", "entity-model-features", "entity-texture-features",
    "fallingleaves", "flerovium", "held-item-tooltips", "holdmyitems",
    "modelfix", "mouse-tweaks", "polytone", "presence-footsteps",
    "sodium-dynamic-lights", "sodium-options-api", "sound-physics-remastered",
    "sounds", "immerse-ui", "jade", "amendments", "better-advancements",
    "better-ping-display",
    "betteradvancements", "betterpingdisplay", "distanthorizons", "dynamicfps",
    "enhancedbossbars", "entitymodelfeatures", "entitytexturefeatures",
    "fallingleaves", "flerovium", "helditemtooltips", "holdmyitems",
    "immediatelyfast", "immersiveui", "modelfix", "mousetweaks",
    "presencefootsteps", "polytone", "sodiumdynamiclights", "sodiumoptionsapi",
    "soundphysicsremastered", "sounds",
    # Aggiunte per modpack Fantasy RP - mod client-only note
    "asyncparticles", "blur", "continuity", "enhancedvisuals", "entityculling",
    "ambientsounds", "animaticareforged", "betteradvancements", "betterpingdisplay",
    "cameraoverhaul", "distanthorizons", "dynamicfps", "embeddium", "entitymodelfeatures",
    "entitytexturefeatures", "fallingleaves", "flerovium", "helditemtooltips", "holdmyitems",
    "immediatelyfast", "immersiveui", "modelfix", "mousetweaks", "oculus",
    "presencefootsteps", "polytone", "shieldoverhaul", "sodiumdynamiclights",
    "sodiumoptionsapi", "soundphysicsremastered",
}

CLIENT_WORDS_IN_SERVER_MODS = {
    "balm", "architectury", "cloth-config", "modmenu",
}

# ============================================================================
# OVERRIDE FORZATO SERVER-SIDE (per mod_parser.py)
# ============================================================================
SERVER_SIDE_FORCE_INCLUDE = {
    "jei", "ferritecore", "tconjei", "appleskin",
    "refined-storage-jei", "searchables", "polymorph",
    "journeymap", "kotlinforforge", "connector",
}

# ============================================================================
# CACHE
# ============================================================================
CACHE_FILE = "cf_cache.json"