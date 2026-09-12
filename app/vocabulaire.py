"""Le vocabulaire public des packs : les mots de l'app d'un cote, les valeurs internes de l'autre.

Un seul endroit pour les deux sens, pour que le fabricant de packs (tools/make_pack.py) et le lecteur de packs
(app/packs.py) ne puissent pas se contredire.
"""

import re
import unicodedata

# Champ public -> {valeur interne: mot affiche}. Les identifiants ecrits dans les packs sont les mots
# sans accent ni espace (voir slug) : "peu-presentes", "geante-gazeuse".
FR = {
    "biome": {"Lush": "Luxuriante", "Toxic": "Toxique", "Scorched": "Brûlante", "Radioactive": "Radioactive",
              "Frozen": "Gelée", "Barren": "Aride", "Dead": "Morte", "Weird": "Exotique", "Red": "Rouge",
              "Green": "Verte", "Blue": "Bleue", "Swamp": "Marécageuse", "Lava": "Volcanique",
              "Waterworld": "Océanique", "GasGiant": "Géante gazeuse"},
    "taille": {"Large": "Grande", "Medium": "Moyenne", "Small": "Petite", "Moon": "Lune", "Giant": "Géante"},
    "etoile": {"Yellow": "Jaune", "Green": "Verte", "Blue": "Bleue", "Red": "Rouge"},
    "espece": {"Traders": "Gek", "Warriors": "Vy'keen", "Explorers": "Korvax", "None": "Aucune",
               "Robots": "Sentinelles", "Atlas": "Atlas", "Diplomats": "Diplomates", "Exotics": "Exotiques",
               "Builders": "Autophages"},
    "economie": {"Mining": "Minière", "HighTech": "Haute technologie", "Trading": "Commerce",
                 "Manufacturing": "Manufacture", "Fusion": "Fusion", "Scientific": "Scientifique",
                 "PowerGeneration": "Énergie"},
    "richesse": {"Poor": "Pauvre", "Average": "Moyenne", "Wealthy": "Riche", "Pirate": "Pirate"},
    "conflit": {"Low": "Faible", "Default": "Moyen", "High": "Élevé", "Pirate": "Pirate"},
    "sentinelles": {"Low": "Peu présentes", "Default": "Normales", "Aggressive": "Agressives",
                    "Corrupt": "Corrompues"},
    "tempetes": {"None": "Jamais", "Low": "Rares", "High": "Fréquentes", "Always": "Permanentes"},
    "intensite": {"Default": "Supportable", "Extreme": "Extrême"},
    "plantes": {"Dead": "Aucune", "Low": "Rare", "Mid": "Moyenne", "Full": "Abondante"},
    "animaux": {"Dead": "Aucun", "Low": "Rare", "Mid": "Moyen", "Full": "Abondant"},
    "meteo": {"Clear": "Dégagé", "Dust": "Poussière", "Humid": "Humide", "Snow": "Neige", "Toxic": "Toxique",
              "Scorched": "Brûlant", "Radioactive": "Radioactif", "RedWeather": "Rouge", "GreenWeather": "Vert",
              "BlueWeather": "Bleu", "Swamp": "Marécageux", "Lava": "Volcanique", "Bubble": "Bulles",
              "Weird": "Étrange", "Fire": "Feu", "ClearCold": "Froid et dégagé", "GasGiant": "Géante gazeuse"},
    "nuages": {"CloudyWithClearSpells": "Nuageux avec éclaircies",
               "ClearWithCloudySpells": "Dégagé avec passages nuageux"},
    "anomalie": {"None": "", "BlackHole": "Trou noir", "AtlasStation": "Station Atlas",
                 "AtlasStationFinal": "Atlas final", "MiniStation": "Mini-station", "BackgroundSwarmHive": "Essaim"},
}

# Les familles de teintes, en mots ordinaires.
PALETTES = {"Grass": "herbe", "GrassAlt": "herbe-variante", "Plant": "plantes", "Leaf": "feuilles",
            "Wood": "bois", "Rock": "roche", "Stone": "pierre", "Sand": "sable", "Dirt": "terre",
            "Snow": "neige", "Crystal": "cristal", "Cave": "grottes", "Cloud": "nuages",
            "Water": "eau", "WaterNear": "eau-rivage", "DeepWaterBioLum": "eau-profonde-lumineuse",
            "Sky": "ciel", "SkyHorizon": "ciel-horizon", "SkyFog": "brume", "SkyHeightFog": "brume-altitude",
            "SkySunset": "ciel-couchant", "SkyNight": "ciel-nuit", "PlanetRing": "anneau"}

# Les ressources, telles que le jeu francais les nomme.
RESSOURCES_FR = {
    "Copper": "Cuivre", "Cadmium": "Cadmium", "Emeril": "Émeril", "Indium": "Indium", "Quartzite": "Quartzite",
    "Activated Copper": "Cuivre activé", "Activated Cadmium": "Cadmium activé", "Activated Emeril": "Émeril activé",
    "Activated Indium": "Indium activé", "Activated Quartzite": "Quartzite activée",
    "Paraffinium": "Paraffinium", "Dioxite": "Dioxite", "Ammonia": "Ammoniac", "Gold": "Or", "Phosphorus": "Phosphore",
    "Pyrite": "Pyrite", "Uranium": "Uranium", "Rusted Metal": "Métal rouillé", "Faecium": "Faecium",
    "Basalt": "Basalte", "Sulphurine": "Sulphurine", "Lithium": "Lithium", "Crystallised Helium": "Hélium cristallisé",
    "Magnetised Ferrite": "Ferrite magnétisée", "Silver": "Argent", "Salt": "Sel", "Sodium": "Sodium",
    "Cobalt": "Cobalt",
}

# Les phrases du jeu que la fiche affiche, par role.
ROLES_TEXTES = {"Weather": "meteo", "Sentinels": "sentinelles", "Flora": "plantes", "Fauna": "animaux",
                "Resources": "ressources"}

# Le champ public correspondant a chaque colonne de la base, pour les deux sens.
CHAMPS = {"biome": "biome", "size": "taille", "star": "etoile", "race": "espece", "trading": "economie",
          "wealth": "richesse", "conflict": "conflit", "sentinels": "sentinelles", "storms": "tempetes",
          "intensity": "intensite", "flora": "plantes", "fauna": "animaux", "weather": "meteo",
          "cloudiness": "nuages", "anomaly": "anomalie"}


def slug(texte):
    """Le mot affiche ramene a un identifiant simple : 'Peu présentes' -> 'peu-presentes'."""
    s = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def vers_public(champ, valeur):
    """Valeur interne -> identifiant public. Rend None quand la valeur est INCONNUE, et "" quand elle est
    connue mais ne s'affiche pas (l'absence d'anomalie, par exemple) : l'appelant doit pouvoir distinguer
    les deux, sinon une valeur vide passerait pour une nouveaute a signaler."""
    if valeur is None or valeur == "":
        return ""
    libelle = FR.get(champ, {}).get(valeur)
    return slug(libelle) if libelle is not None else None


def vers_interne(champ, identifiant):
    """Identifiant public -> valeur interne, l'inverse exact de vers_public."""
    if identifiant is None or identifiant == "":
        return None
    return _INVERSES.get(champ, {}).get(identifiant)


def dictionnaire():
    """Ce qu'un pack embarque : identifiant public -> mot affiche, par champ."""
    out = {champ: {slug(v): v for v in table.values() if v} for champ, table in FR.items()}
    out["corps"] = {"planete": "Planète", "lune": "Lune"}
    return out


def _construire_inverses():
    out = {}
    for champ, table in FR.items():
        inverse = {}
        for interne, libelle in table.items():
            cle = slug(libelle)
            # Deux valeurs internes peuvent porter le meme mot (Pirate en richesse et en conflit) : la
            # premiere gagne, ce qui suffit puisque le champ est connu.
            if cle and cle not in inverse:
                inverse[cle] = interne
        out[champ] = inverse
    return out


_INVERSES = _construire_inverses()
PALETTES_INVERSE = {public: interne for interne, public in PALETTES.items()}
ROLES_INVERSE = {public: interne for interne, public in ROLES_TEXTES.items()}
