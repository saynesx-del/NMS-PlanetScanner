"""Installe un pack de donnees dans la base de l'app.

Un pack contient des regions deja pretes : couleurs calculees, phrases du jeu, vocabulaire public.
L'installation remplit les colonnes de la base, pour que la recherche, les fiches et le guidage s'en servent
comme du reste.
"""

import json
import zipfile

import vocabulaire as voc

FORMATS_LUS = (1,)
FRANCAIS_VERS_INTERNE = {fr: en for en, fr in voc.RESSOURCES_FR.items()}


class PackInvalide(Exception):
    pass


def _ressource(valeur):
    """Nom francais (ou liste d'alternatives) -> valeur interne, telle que la base la range."""
    if not valeur:
        return None
    noms = valeur if isinstance(valeur, list) else [valeur]
    return "|".join(FRANCAIS_VERS_INTERNE.get(n, n) for n in noms)


def _details(p):
    """Reconstruit le detail que la fiche planete affiche, dans la forme qu'elle attend."""
    d = {"name": p.get("nom"), "has_water": p.get("eau", False)}
    teintes = p.get("teintes") or {}
    if teintes:
        d["palettes"] = {voc.PALETTES_INVERSE.get(nom, nom): {"c": couleurs}
                         for nom, couleurs in teintes.items()}
    meteo = p.get("meteo") or {}
    d["weather"] = {"WeatherType": voc.vers_interne("meteo", meteo.get("type")),
                    "WeatherIntensity": voc.vers_interne("intensite", meteo.get("intensite")),
                    "StormFrequency": voc.vers_interne("tempetes", meteo.get("tempetes"))}
    d["clouds"] = {"Cloudiness": voc.vers_interne("nuages", meteo.get("nuages"))}
    d["hazard"] = {cle: [valeur] for cle, valeur in (("Temperature", meteo.get("temperature")),
                                                     ("Toxicity", meteo.get("toxicite")),
                                                     ("Radiation", meteo.get("radiation")))
                   if valeur is not None}
    d["sentinels"] = voc.vers_interne("sentinelles", p.get("sentinelles"))
    d["flora"] = voc.vers_interne("plantes", p.get("plantes"))
    d["fauna"] = voc.vers_interne("animaux", p.get("animaux"))
    # Les phrases du jeu sont deja ecrites en clair dans le pack : la fiche les affiche telles quelles.
    textes = p.get("textes") or {}
    if textes:
        d["texts"] = {voc.ROLES_INVERSE.get(role, role): phrase for role, phrase in textes.items()}
    if p.get("anneau"):
        c1, c2 = (p["anneau"] + [None, None])[:2]
        d["ring"] = {"has": True, "c1": c1, "c2": c2}
    return d


def _ligne_planete(p, galaxie, rid, ua):
    glyphes = p["glyphes"]
    meteo = p.get("meteo") or {}
    couleurs = p.get("couleurs") or {}
    familles = p.get("familles") or {}
    eau = bool(p.get("eau"))
    return (
        f"{galaxie:02X}{glyphes}", ua, rid, galaxie, int(glyphes[0], 16), glyphes,
        voc.vers_interne("biome", p.get("biome")), None, None, voc.vers_interne("taille", p.get("taille")),
        int(bool(p.get("prime"))), int(bool(p.get("anneaux"))), int(bool(p.get("continents"))),
        p.get("nom"), voc.vers_interne("sentinelles", p.get("sentinelles")),
        voc.vers_interne("meteo", meteo.get("type")), voc.vers_interne("tempetes", meteo.get("tempetes")),
        voc.vers_interne("intensite", meteo.get("intensite")),
        voc.vers_interne("plantes", p.get("plantes")), voc.vers_interne("animaux", p.get("animaux")),
        voc.vers_interne("nuages", meteo.get("nuages")), None, int(bool(p.get("meteo_extreme"))),
        _ressource((p.get("ressources") or {}).get("commune")),
        _ressource((p.get("ressources") or {}).get("peu_commune")),
        _ressource((p.get("ressources") or {}).get("rare")),
        meteo.get("temperature"), meteo.get("toxicite"), meteo.get("radiation"),
        couleurs.get("eau") if eau else None, familles.get("eau") if eau else None,
        couleurs.get("ciel"), familles.get("ciel"),
        couleurs.get("herbe"), familles.get("vegetation"),
        couleurs.get("plantes"), couleurs.get("feuilles"),
        json.dumps(_details(p), ensure_ascii=False), int(eau),
        # La description est deja en clair : la fiche l'affiche directement.
        p.get("description"), None, p.get("lunes_propres") or 0)


def _ligne_systeme(s, galaxie, rid):
    glyphes = s["glyphes"]
    ua = f"{glyphes[1:4]}{galaxie:02X}{glyphes[4:]}"
    return ua, (
        ua, rid, galaxie, int(glyphes[1:4], 16), voc.vers_interne("etoile", s.get("etoile")),
        voc.vers_interne("espece", s.get("espece")), voc.vers_interne("conflit", s.get("conflit")),
        voc.vers_interne("economie", s.get("economie")), voc.vers_interne("richesse", s.get("richesse")),
        int(bool(s.get("abandonne"))), int(bool(s.get("pirate"))), 0,
        voc.vers_interne("anomalie", s.get("anomalie")), len(s.get("planetes") or ()),
        s.get("lunes") or 0, glyphes, None, 0)


def lire_manifeste(chemin):
    """Ce que le pack annonce, sans rien installer : de quoi l'afficher avant de se decider."""
    with zipfile.ZipFile(chemin) as z:
        try:
            m = json.loads(z.read("manifeste.json"))
        except KeyError:
            raise PackInvalide("Ce fichier n'est pas un pack Planet Scanner (manifeste absent).")
    if m.get("format") not in FORMATS_LUS:
        raise PackInvalide(f"Pack au format {m.get('format')} : cette version de l'app lit le format "
                           f"{', '.join(map(str, FORMATS_LUS))}.")
    return m


def installer(con, chemin, avance=None, deja=None):
    """Installe les regions du pack. `avance(fait, total, region)` est appele au fil de l'eau.
    Rend (regions installees, regions deja presentes)."""
    m = lire_manifeste(chemin)
    empreinte = f"pack:{m['version_jeu']}:{m.get('cree_le')}:{m['format']}"
    connues = deja if deja is not None else {r[0]: r[1] for r in con.execute(
        "SELECT id, file_mtime FROM regions")}
    installees, sautees = 0, 0
    with zipfile.ZipFile(chemin) as z:
        entrees = [n for n in z.namelist() if n.startswith("regions/") and n.endswith(".json")]
        for i, nom in enumerate(sorted(entrees), 1):
            rid = nom.split("/")[1][:-5]
            if connues.get(rid) == empreinte:
                sautees += 1
                if avance:
                    avance(i, len(entrees), rid)
                continue
            region = json.loads(z.read(nom))
            galaxie = region["galaxie"]
            with con:
                con.execute("DELETE FROM planets WHERE region_id=?", (rid,))
                con.execute("DELETE FROM systems WHERE region_id=?", (rid,))
                planetes = 0
                for s in region["systemes"]:
                    ua, ligne = _ligne_systeme(s, galaxie, rid)
                    con.execute("INSERT OR REPLACE INTO systems VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                ligne)
                    con.executemany(
                        "INSERT OR REPLACE INTO planets VALUES (" + ",".join("?" * 42) + ")",
                        [_ligne_planete(p, galaxie, rid, ua) for p in s.get("planetes") or ()])
                    planetes += len(s.get("planetes") or ())
                con.execute("INSERT OR REPLACE INTO regions VALUES (?,?,?,?,?,?,?,?)", (
                    rid, galaxie, region["region"], m.get("cree_le"), 1, len(region["systemes"]), planetes,
                    empreinte))
            installees += 1
            if avance:
                avance(i, len(entrees), rid)
    return installees, sautees
