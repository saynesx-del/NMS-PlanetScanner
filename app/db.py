"""La base : les regions connues de l'app, et le moteur de recherche (score par defaut, criteres exiges
en filtre)."""

import json
import os
import sqlite3
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
import index as index_mod  # noqa: E402  (the in-memory search index)
import vocabulaire as voc  # noqa: E402  (les mots du jeu, en francais)

IMPORT_VERSION = 4  # bump to re-import every region after a change in how region files are read
DATA_DIR = Path(os.environ.get("PS_DATA_DIR") or ROOT / "data")  # PS_DATA_DIR: test/demo data folder
# Les fichiers livres avec l'app : a cote du code, ou dans le paquet quand elle est compilee.
STATIC = Path(getattr(sys, "_MEIPASS", ROOT / "app")) / "static"
DB_PATH = DATA_DIR / "scanner.db"

GALAXIES = ["Euclid", "Hilbert Dimension", "Calypso", "Hesperius Dimension", "Hyades", "Ickjamatew", "Butterfly",
            "Aptarkaba", "Ontiniangp", "Odiwagiri", "Ogtialabi", "Muhacksonto", "Hitonskyer", "Rerasmutul",
            "Isdoraijung"]


def galaxy_name(g):
    return GALAXIES[g] if g < len(GALAXIES) else f"Galaxie {g + 1}"


# Les couleurs, dites comme un joueur les dirait ("eau rose", "ciel violet").
COLOUR_FAMILIES = ["rouge", "orange", "jaune", "vert", "turquoise", "bleu", "violet", "rose", "marron",
                   "blanc", "gris", "noir"]


# --- Schema & import ------------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
  id TEXT PRIMARY KEY, galaxy INTEGER, region TEXT, added_at TEXT, details INTEGER,
  systems INTEGER, planets INTEGER, file_mtime REAL);
CREATE TABLE IF NOT EXISTS systems (
  ua TEXT PRIMARY KEY, region_id TEXT, galaxy INTEGER, sss INTEGER, star TEXT, race TEXT, conflict TEXT,
  trading TEXT, wealth TEXT, abandoned INTEGER, pirate INTEGER, gas_giant INTEGER, anomaly TEXT,
  planet_count INTEGER, moons INTEGER, glyphs TEXT, booster TEXT, boundary INTEGER);
CREATE TABLE IF NOT EXISTS planets (
  id TEXT PRIMARY KEY, system_ua TEXT, region_id TEXT, galaxy INTEGER, idx INTEGER, glyphs TEXT,
  biome TEXT, subtype TEXT, variant TEXT, size TEXT, prime INTEGER, rings INTEGER, continents INTEGER,
  name TEXT, sentinels TEXT, weather TEXT, storms TEXT, intensity TEXT, flora TEXT, fauna TEXT,
  cloudiness TEXT, rainbow TEXT, extreme INTEGER, common TEXT, uncommon TEXT, rare TEXT,
  temperature REAL, toxicity REAL, radiation REAL,
  water_hex TEXT, water_family TEXT, sky_hex TEXT, sky_family TEXT, grass_hex TEXT, grass_family TEXT,
  plant_hex TEXT, leaf_hex TEXT, details TEXT, has_water INTEGER, desc_key TEXT, class_key TEXT, own_moons INTEGER);
CREATE INDEX IF NOT EXISTS planets_region ON planets(region_id);
CREATE INDEX IF NOT EXISTS planets_system ON planets(system_ua);
CREATE INDEX IF NOT EXISTS systems_region ON systems(region_id);
-- Player data: kept apart from the planets, so reloading a region never touches it.
CREATE TABLE IF NOT EXISTS trip (planet_id TEXT PRIMARY KEY, position INTEGER, added_at TEXT);
CREATE TABLE IF NOT EXISTS visited (planet_id TEXT PRIMARY KEY, visited_at TEXT);
CREATE TABLE IF NOT EXISTS favorites (planet_id TEXT PRIMARY KEY, note TEXT, added_at TEXT);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
-- Named searches saved by the player ("Mes recherches").
CREATE TABLE IF NOT EXISTS searches (name TEXT PRIMARY KEY, criteria TEXT, strict INTEGER, saved_at TEXT);
-- The player's notes on planets (favourite or not).
CREATE TABLE IF NOT EXISTS notes (planet_id TEXT PRIMARY KEY, note TEXT, updated_at TEXT);
"""

_lock = threading.RLock()

# Player settings.
SETTINGS_DEFAULT = {"purple_access": False, "own_glyphs": False}
MIGRATIONS = []  # fonctions (con) -> None, appelees a l'ouverture de la base


def load_settings():
    try:
        return SETTINGS_DEFAULT | json.loads((DATA_DIR / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(SETTINGS_DEFAULT)


def save_settings(**changes):
    settings = load_settings() | {k: bool(v) for k, v in changes.items() if k in SETTINGS_DEFAULT}
    (DATA_DIR / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return settings


# Purple systems (and the plain star opening their range) can't be reached until the player has unlocked them:
# the portal then errors and drops you on the nearest planet of another system.
LOCKED_PURPLE_SQL = "s.star != 'Purple' AND s.boundary = 0"


def connect():
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    # WAL: the background importer writes while the app and the overlay keep reading, without waiting.
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    for migration in MIGRATIONS:  # des modules peuvent avoir leurs propres mises a niveau
        migration(con)
    # Columns added after the first release: add them to existing databases, then force a re-import.
    cols = {r["name"] for r in con.execute("PRAGMA table_info(planets)")}
    for col, typ in (("has_water", "INTEGER"), ("desc_key", "TEXT"), ("class_key", "TEXT"), ("own_moons", "INTEGER")):
        if col not in cols:
            con.execute(f"ALTER TABLE planets ADD COLUMN {col} {typ}")
            con.execute("UPDATE regions SET file_mtime = 'reimport'")
    # Notes used to live with the favourites: keep them.
    con.execute("INSERT OR IGNORE INTO notes SELECT planet_id, note, added_at FROM favorites "
                "WHERE note IS NOT NULL AND note != ''")
    con.commit()
    return con


# --- Search ---------------------------------------------------------------------------------------------

# key -> (label, column, table, kind). kind: enum | bool | colour | text | min
FEATURES = {
    "biome": ("Biome", "biome", "p", "enum"),
    "variant": ("Variante", "variant", "p", "enum"),
    "size": ("Taille", "size", "p", "enum"),
    "body": ("Corps celeste", "size", "p", "body"),  # "planet" or "moon"
    "prime": ("Prime", "prime", "p", "bool"),
    "rings": ("Anneaux", "rings", "p", "bool"),
    "continents": ("Continents", "continents", "p", "bool"),
    "has_water": ("Eau", "has_water", "p", "bool"),
    "desc": ("Description du jeu", "desc_key", "p", "enum"),
    "sentinels": ("Sentinelles", "sentinels", "p", "enum"),
    "storms": ("Tempetes", "storms", "p", "enum"),
    "weather": ("Meteo", "weather", "p", "enum"),
    "intensity": ("Meteo extreme", "intensity", "p", "enum"),
    "flora": ("Flore", "flora", "p", "enum"),
    "fauna": ("Faune", "fauna", "p", "enum"),
    "cloudiness": ("Nuages", "cloudiness", "p", "enum"),
    "water": ("Couleur de l'eau", "water_family", "p", "colour"),
    "sky": ("Couleur du ciel", "sky_family", "p", "colour"),
    "grass": ("Couleur de l'herbe", "grass_family", "p", "colour"),
    "resource": ("Ressource", "common|uncommon|rare", "p", "text"),
    "star": ("Etoile", "star", "s", "enum"),
    "race": ("Espece", "race", "s", "enum"),
    "trading": ("Economie", "trading", "s", "enum"),
    "wealth": ("Richesse", "wealth", "s", "enum"),
    "conflict": ("Conflit", "conflict", "s", "enum"),
    "abandoned": ("Systeme abandonne", "abandoned", "s", "bool"),
    "pirate": ("Systeme pirate", "pirate", "s", "bool"),
    "min_planets": ("Planetes (min)", "planet_count", "s", "min"),
    "min_moons": ("Lunes (min)", "moons", "s", "min"),
    "own_moon": ("Sa propre lune", "own_moons", "p", "min"),
}

# Every planet column except the big `details` JSON (a few KB each): searches never need it.
PLANET_COLS = ", ".join(f"p.{c}" for c in (
    "id system_ua region_id galaxy idx glyphs biome subtype variant size prime rings continents name sentinels "
    "weather storms intensity flora fauna cloudiness rainbow extreme common uncommon rare temperature toxicity "
    "radiation water_hex water_family sky_hex sky_family grass_hex grass_family plant_hex leaf_hex has_water desc_key "
    "class_key own_moons").split())
ROW_SQL = f"""
SELECT {PLANET_COLS}, s.star, s.race, s.conflict, s.trading, s.wealth, s.abandoned, s.pirate, s.gas_giant, s.anomaly,
       s.planet_count, s.moons, s.sss, s.boundary, s.glyphs AS system_glyphs, s.booster, r.region, r.galaxy AS g,
       t.position AS trip_position, v.visited_at, f.added_at AS favorite_at, n.note
FROM planets p JOIN systems s ON s.ua = p.system_ua JOIN regions r ON r.id = p.region_id
LEFT JOIN trip t ON t.planet_id = p.id LEFT JOIN visited v ON v.planet_id = p.id
LEFT JOIN favorites f ON f.planet_id = p.id LEFT JOIN notes n ON n.planet_id = p.id
"""


_meta_cache = {"gen": None, "options": None}
META_CACHE = DATA_DIR / "meta_cache.json"


def _options(con, allow_stale=False):
    """Per-value planet counts: from the index when ready (milliseconds), else the counts saved at the last run (the
    app shows them at once), else counted by SQL (tens of seconds, first run only)."""
    if INDEX.ready():
        if _meta_cache["gen"] != INDEX.generation:
            options = INDEX.options(FEATURES, list(voc.RESSOURCES_FR) + ["Activated"])
            _meta_cache.update(gen=INDEX.generation, options=options)
            try:
                tmp = META_CACHE.with_suffix(".tmp")
                tmp.write_text(json.dumps(options, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, META_CACHE)
            except OSError:
                pass
        return _meta_cache["options"]
    if _meta_cache["options"] is None:
        try:
            _meta_cache["options"] = json.loads(META_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if not allow_stale:
                _meta_cache["options"] = _meta_options(con)
    return _meta_cache["options"] or {}


# Les donnees portent deja les phrases du jeu : cette table ne sert qu'a celles qui n'y seraient pas.
def TRADUCTIONS():
    return {}, {}


def meta(con, allow_stale=False):
    """Everything the app's filter panel needs. The per-value counts take seconds over 300k+ planets: they are
    recomputed after each import (by the importer); allow_stale lets a request use the last counts meanwhile."""
    regions = [dict(r) | {"galaxy_name": galaxy_name(r["galaxy"])}
               for r in con.execute("SELECT * FROM regions ORDER BY galaxy, region")]
    options = _options(con, allow_stale)
    features = [{"key": k, "label": v[0], "kind": v[3], "options": options.get(k)} for k, v in FEATURES.items()]
    totals = {"planets": sum(r["planets"] or 0 for r in regions),
              "detailed": sum(r["planets"] or 0 for r in regions if r["details"])}
    texts, names = TRADUCTIONS()
    return {"regions": regions, "features": features, "totals": totals, "substances_fr": voc.RESSOURCES_FR | names, "texts": texts,
            # The NMS glyph font is a personal-use extra, never shipped: the player's own copy, dropped in the
            # data folder, is enough. Without it, Planet Scanner's own drawings are used.
            "glyph_font": any(f.exists() for f in (STATIC / "nms-glyphs.css", STATIC / "NmsGlyphs.ttf",
                                                   DATA_DIR / "NmsGlyphs.ttf")),
            "colour_families": COLOUR_FAMILIES}


def _meta_options(con):
    """How many planets carry each value: shown on every filter button (system values count their planets).
    One grouped query per filter; planet values without joining the systems (365 000 planets: ~30 s before)."""
    options = {}
    for key, (label, col, tbl, kind) in FEATURES.items():
        if kind not in ("enum", "colour", "bool", "min", "body"):
            continue
        if tbl == "p":
            rows = con.execute(f"SELECT {col} AS v, COUNT(*) AS n FROM planets GROUP BY {col}").fetchall()
        else:  # a system value, counted once per planet of the system
            rows = con.execute(f"SELECT s.{col} AS v, SUM(s.planet_count) AS n FROM systems s GROUP BY s.{col}").fetchall()
        counts = [(r["v"], r["n"] or 0) for r in rows if r["v"] is not None]
        if kind in ("enum", "colour"):
            options[key] = sorted(([v, n] for v, n in counts), key=lambda x: -x[1])
        elif kind == "bool":
            options[key] = [[True, sum(n for v, n in counts if v == 1)], [False, sum(n for v, n in counts if v == 0)]]
        elif kind == "min":  # planets with at least 1, 2, 3, 4
            options[key] = [[k, sum(n for v, n in counts if v >= k)] for k in (1, 2, 3, 4)]
        else:  # body: planets / moons
            options[key] = [["planet", sum(n for v, n in counts if v != "Moon")],
                            ["moon", sum(n for v, n in counts if v == "Moon")]]
    # resources: one pass over the distinct (common, uncommon, rare) combinations
    names = list(voc.RESSOURCES_FR) + ["Activated"]
    totals = dict.fromkeys(names, 0)
    for r in con.execute("SELECT common, uncommon, rare, COUNT(*) AS n FROM planets GROUP BY common, uncommon, rare"):
        text = "|".join(x for x in (r["common"], r["uncommon"], r["rare"]) if x)
        for name in names:
            if name in text:  # same rule as the search: "Copper" also matches "Activated Copper"
                totals[name] += r["n"]
    options["resource"] = [[n, totals[n]] for n in names]
    return options


def _match_group(row, group):
    """A group is every criterion of one kind ('biome: Lush' + 'biome: Weird' = either)."""
    results = [_match(row, {"key": group["key"], "value": v}) for v in group["values"]]
    if any(results):
        return True
    return None if all(r is None for r in results) else False


def _match(row, crit):
    key, value = crit["key"], crit.get("value")
    label, col, tbl, kind = FEATURES[key]
    if kind == "text":
        q = str(value or "").lower()
        return any(q and q in str(row[c] or "").lower() for c in col.split("|"))
    if key == "water" and row["has_water"] == 0:
        return False  # "eau bleue" on a planet without water is a miss, not an unknown
    v = row[col]
    if v is None:
        return None  # inconnu (planete sans details)
    if kind == "bool":
        return bool(v) == bool(value if value is not None else True)
    if kind == "min":
        return v >= int(value or 0)
    if kind == "body":
        return (v == "Moon") == (value == "moon")
    return str(v) == str(value)


def _group_sql(group):
    """SQL twin of _match_group: 1 when the row matches one of the group's values, else 0 (unknown = 0)."""
    label, col, tbl, kind = FEATURES[group["key"]]
    parts, args = [], []
    for value in group["values"]:
        if kind == "text":
            q = str(value or "").lower()
            if not q:
                continue
            parts.append("(" + " OR ".join(f"instr(lower(coalesce({tbl}.{c}, '')), ?) > 0" for c in col.split("|")) + ")")
            args += [q] * len(col.split("|"))
        elif kind == "bool":
            parts.append(f"(({tbl}.{col} != 0) = ?)")
            args.append(int(bool(value if value is not None else True)))
        elif kind == "min":
            parts.append(f"({tbl}.{col} >= ?)")
            args.append(int(value or 0))
        elif kind == "body":
            parts.append(f"({tbl}.{col} {'=' if value == 'moon' else '!='} 'Moon')")
        else:
            parts.append(f"({tbl}.{col} = ?)")
            args.append(str(value))
    if not parts:
        return "0", []
    expr = " OR ".join(parts)
    if group["key"] == "water":
        expr = f"coalesce(p.has_water, 1) != 0 AND ({expr})"  # colour of a dry planet's (absent) water: a miss
    return f"coalesce(({expr}), 0)", args


def _groups(criteria):
    groups = {}
    for c in criteria:
        if c.get("key") not in FEATURES:
            continue
        # Same kind = either one (two biomes), except resources: "copper + silver" means both.
        gk = f"resource:{c.get('value')}" if c["key"] == "resource" else c["key"]
        g = groups.setdefault(gk, {"id": gk, "key": c["key"], "values": [], "required": False})
        g["values"].append(c.get("value"))
        g["required"] = g["required"] or bool(c.get("required"))
    return list(groups.values())


# The in-memory index (app/index.py) answers searches in milliseconds; until it is ready (first seconds after a
# start), the SQL search below answers instead, with the same results.
INDEX = index_mod.Index(DATA_DIR / "index.bin")


def refresh_index(con):
    """Bring the index in line with the imported regions (only changed regions are re-read)."""
    regions = {r["id"]: r["file_mtime"] for r in con.execute("SELECT id, file_mtime FROM regions")}
    return INDEX.update(con, regions)


def rows_by_id(con, ids):
    rows = {}
    ids = list(ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in con.execute(ROW_SQL + f" WHERE p.id IN ({','.join('?' * len(part))})", part):
            rows[r["id"]] = r
    return rows


def _materialise(con, found, groups):
    """Full rows for (planet id, hits) pairs, in that order (a planet gone from the database since the index was
    built is skipped)."""
    rows = rows_by_id(con, [pid for pid, _h in found])
    out = []
    for pid, hits in found:
        row = rows.get(pid)
        if row is None:
            continue
        d = dict(row)
        d.pop("details", None)
        out.append(d | {"score": round(100 * hits / len(groups)) if groups else 0,
                        "hits": [g["id"] for g in groups if _match_group(row, g)],
                        "galaxy_name": galaxy_name(d["galaxy"])})
    return out


def _visited_ids(con):
    return [r[0] for r in con.execute("SELECT planet_id FROM visited")]


def search(con, criteria, region=None, limit=200, offset=0, hide_visited=False, min_score=0, purple=None,
           insight=False, per_region=False):
    """Planets ranked by the share of criteria groups they match (then prime first, then glyphs).
    insight: for each group, the perfect planets there would be without it ("what limits you").
    per_region: perfect planets per region (the map)."""
    if not INDEX.ready():
        return _search_sql(con, criteria, region, limit, offset, hide_visited, min_score, purple)
    groups = _groups(criteria)
    unlocked = load_settings()["purple_access"] if purple is None else purple
    exclude = _visited_ids(con) if hide_visited else ()
    total, perfect, near, found = INDEX.rank(groups, FEATURES, region, exclude, locked_purple=not unlocked,
                                             min_score=min_score, want=int(offset) + int(limit))
    out = {"total": total, "perfect": perfect if groups else total, "near": near if len(groups) > 1 else 0,
           "groups": len(groups), "results": _materialise(con, found[int(offset):], groups)}
    if insight and len(groups) > 1:
        without = INDEX.limits(groups, FEATURES, region, exclude, locked_purple=not unlocked)
        out["limits"] = sorted(({"id": g["id"], "key": g["key"], "values": g["values"], "perfect": n}
                                for g, n in zip(groups, without)), key=lambda x: -x["perfect"])
    if per_region:
        out["per_region"] = INDEX.per_region(groups, FEATURES, None, exclude, locked_purple=not unlocked)
    return out


def _search_sql(con, criteria, region=None, limit=200, offset=0, hide_visited=False, min_score=0, purple=None):
    """The same search inside SQLite (4 s over a million planets): used until the index is ready, and to check it."""
    groups = _groups(criteria)
    # Inner query: every column + the hit count, with the plain filters. Outer query: filters on the hit count.
    hit_parts, hit_args, inner, inner_args = [], [], [], []
    for g in groups:
        e, a = _group_sql(g)
        hit_parts.append(e)
        hit_args += a
        if g["required"]:
            inner.append(f"{e} = 1")
            inner_args += a
    if region:
        inner.append("p.region_id = ?")
        inner_args.append(region)
    if hide_visited:
        inner.append("v.planet_id IS NULL")
    if not (load_settings()["purple_access"] if purple is None else purple):
        inner.append(LOCKED_PURPLE_SQL)
    outer, outer_args = [], []
    if groups and not all(g["required"] for g in groups):
        outer.append("hits > 0")
    if groups and min_score:
        # score = round(100 * hits / n) >= min_score  <=>  hits >= the smallest count that rounds up to it
        outer.append("hits >= ?")
        outer_args.append(next((h for h in range(len(groups) + 1) if round(100 * h / len(groups)) >= min_score),
                               len(groups) + 1))
    sql = ROW_SQL.replace("SELECT ", f"SELECT ({' + '.join(hit_parts) or '0'}) AS hits, ", 1)
    if inner:
        sql += " WHERE " + " AND ".join(inner)
    sql = f"SELECT * FROM ({sql})" + (" WHERE " + " AND ".join(outer) if outer else "")
    args = hit_args + inner_args + outer_args
    total, perfect, near = con.execute(f"SELECT COUNT(*), SUM(hits = ?), SUM(hits = ?) FROM ({sql})",
                                       [len(groups), len(groups) - 1] + args).fetchone()
    perfect, near = perfect or 0, near or 0
    rows = con.execute(f"{sql} ORDER BY hits DESC, prime DESC, glyphs LIMIT ? OFFSET ?",
                       args + [int(limit), int(offset)]).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d.pop("details", None)
        score = round(100 * d.pop("hits") / len(groups)) if groups else 0
        out.append(d | {"score": score, "hits": [g["id"] for g in groups if _match_group(row, g)],
                        "galaxy_name": galaxy_name(d["galaxy"])})
    return {"total": total, "perfect": perfect if groups else total, "near": near if len(groups) > 1 else 0,
            "groups": len(groups), "results": out}


def system(con, ua):
    s = con.execute("SELECT * FROM systems WHERE ua=?", (ua,)).fetchone()
    if not s:
        return None
    planets = []
    for p in con.execute("SELECT p.*, t.position AS trip_position, v.visited_at, f.added_at AS favorite_at, n.note "
                         "FROM planets p LEFT JOIN trip t ON t.planet_id = p.id "
                         "LEFT JOIN visited v ON v.planet_id = p.id LEFT JOIN favorites f ON f.planet_id = p.id "
                         "LEFT JOIN notes n ON n.planet_id = p.id WHERE p.system_ua=? ORDER BY p.idx", (ua,)):
        d = dict(p)
        d["details"] = json.loads(d["details"]) if d["details"] else None
        planets.append(d)
    return dict(s) | {"galaxy_name": galaxy_name(s["galaxy"]), "planets": planets}


# --- Itineraire, visitees, favoris (partages par l'app et la fenetre de l'overlay) ----------------------

import time as _time  # noqa: E402


def _now():
    return _time.strftime("%Y-%m-%d %H:%M")


def get_state(con, key, default=None):
    r = con.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def set_state(con, key, value):
    with _lock, con:
        con.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value)))


def trip(con):
    """What the overlay and the dock navigate: the hand-made itinerary, or the guided hunt."""
    if get_state(con, "mode") == "hunt" and get_state(con, "hunt"):
        return hunt_trip(con)
    return manual_trip(con)


def manual_trip(con):
    """Planets to visit, in order, with where the player is in the list and in the glyph entry."""
    rows = [dict(r) | {"galaxy_name": galaxy_name(r["galaxy"])} for r in con.execute(
        ROW_SQL + " WHERE p.id IN (SELECT planet_id FROM trip) ORDER BY t.position")]
    for r in rows:
        r.pop("details", None)
    current = get_state(con, "trip_current")
    ids = [r["id"] for r in rows]
    if current not in ids:
        current = next((r["id"] for r in rows if not r["visited_at"]), ids[0] if ids else None)
    return {"mode": "trip", "planets": rows, "current": current, "step": get_state(con, "glyph_step", 0),
            "remaining": sum(1 for r in rows if not r["visited_at"])}


# --- Guided hunt: the next planet is always the best remaining match of a saved search -----------------

def hunt_start(con, criteria, region=None, min_score=75, order="score", label=""):
    set_state(con, "hunt", {"criteria": criteria, "region": region, "min_score": int(min_score),
                            "order": order, "label": label, "started_at": _now()})
    set_state(con, "hunt_skipped", [])
    set_state(con, "hunt_current", None)
    set_state(con, "hunt_done", 0)
    set_state(con, "glyph_step", 0)
    set_state(con, "mode", "hunt")


def hunt_stop(con):
    set_state(con, "mode", "trip")
    set_state(con, "glyph_step", 0)


_hunt_cache = {"key": None, "value": None, "total": 0}
HUNT_KEEP = 20000  # candidates kept in order (the count stays exact beyond it)


def hunt_candidates(con, hunt):
    """Unvisited, unskipped matches at or above the minimum score, in the order they will be served.
    Cached until the hunt, the visits, the skipped list or the known regions change (the overlay polls
    every second)."""
    skipped_list = get_state(con, "hunt_skipped", [])
    v = con.execute("SELECT COUNT(*) AS n, MAX(visited_at) AS m FROM visited").fetchone()
    regions = con.execute("SELECT GROUP_CONCAT(id || file_mtime) AS s FROM regions").fetchone()["s"]
    key = json.dumps([hunt, skipped_list, v["n"], v["m"], regions, load_settings()["purple_access"],
                      INDEX.generation], sort_keys=True)
    if _hunt_cache["key"] == key:
        return _hunt_cache["value"]
    skipped = set(skipped_list)
    if INDEX.ready():
        groups = _groups(hunt["criteria"])
        total, _p, _n, found = INDEX.rank(groups, FEATURES, hunt.get("region"), set(_visited_ids(con)) | skipped,
                                          locked_purple=not load_settings()["purple_access"],
                                          min_score=hunt["min_score"], want=HUNT_KEEP)
        cands = [{"id": pid, "score": round(100 * h / len(groups)) if groups else 0, "hits_n": h,
                  "system_ua": pid[3:6] + pid[:2] + pid[6:], "idx": int(pid[2], 16)} for pid, h in found]
        cands = [c for c in cands if c["score"] >= hunt["min_score"]]
        _hunt_cache["total"] = total if len(found) >= HUNT_KEEP else len(cands)
    else:
        res = search(con, hunt["criteria"], hunt.get("region"), limit=10 ** 6, hide_visited=True,
                     min_score=hunt["min_score"])["results"]
        cands = [r for r in res if r["score"] >= hunt["min_score"] and r["id"] not in skipped]
        _hunt_cache["total"] = len(cands)
    if hunt.get("order") == "system":
        # Finish a system before taking the portal again: systems ranked by their best planet.
        best = {}
        for r in cands:
            best[r["system_ua"]] = max(best.get(r["system_ua"], 0), r["score"])
        cands.sort(key=lambda r: (-best[r["system_ua"]], r["system_ua"], -r["score"], r["idx"]))
    _hunt_cache.update(key=key, value=cands)
    return cands


def hunt_trip(con):
    hunt = get_state(con, "hunt")
    cands = hunt_candidates(con, hunt)
    ids = [r["id"] for r in cands]
    current = get_state(con, "hunt_current")
    if current not in ids:
        current = ids[0] if ids else None
    shown = cands[:30]
    if current and current not in [r["id"] for r in shown]:
        shown = [next(r for r in cands if r["id"] == current)] + shown[:29]
    if shown and "glyphs" not in shown[0]:  # index candidates: full rows for the planets shown only
        shown = _materialise(con, [(r["id"], r["hits_n"]) for r in shown], _groups(hunt["criteria"]))
    return {"mode": "hunt", "hunt": hunt, "planets": shown, "current": current, "history": hunt_history(con, hunt),
            "step": get_state(con, "glyph_step", 0), "remaining": max(len(cands), _hunt_cache.get("total") or 0),
            "done": get_state(con, "hunt_done", 0), "skipped": len(get_state(con, "hunt_skipped", []))}


def hunt_history(con, hunt, limit=40):
    """Planets left behind during this hunt, newest first: visited (with the time) or skipped."""
    visited = [(r["planet_id"], r["visited_at"]) for r in con.execute(
        "SELECT planet_id, visited_at FROM visited WHERE visited_at >= ? ORDER BY visited_at DESC",
        (hunt.get("started_at") or "",))]
    skipped = list(reversed(get_state(con, "hunt_skipped", [])))
    ids = [pid for pid, _t in visited] + [pid for pid in skipped if pid not in {v for v, _t in visited}]
    ids = ids[:limit]
    rows = rows_by_id(con, ids)
    when = dict(visited)
    out = []
    for pid in ids:
        r = rows.get(pid)
        if r is None:
            continue
        d = dict(r)
        d.pop("details", None)
        out.append(d | {"galaxy_name": galaxy_name(d["galaxy"]), "skipped": pid not in when})
    return out


def hunt_unskip(con, planet_id):
    set_state(con, "hunt_skipped", [p for p in get_state(con, "hunt_skipped", []) if p != planet_id])


def _hunt_advance(con, leaving_id, cands_before):
    """After leaving a planet (visited or skipped), serve the one that followed it in the ranking."""
    ids = [r["id"] for r in cands_before]
    nxt = None
    if leaving_id in ids:
        rest = ids[ids.index(leaving_id) + 1:]
        nxt = rest[0] if rest else None
    set_state(con, "hunt_current", nxt)
    set_state(con, "glyph_step", 0)


def hunt_skip(con):
    t = hunt_trip(con)
    if not t["current"]:
        return
    cands = hunt_candidates(con, t["hunt"])
    set_state(con, "hunt_skipped", get_state(con, "hunt_skipped", []) + [t["current"]])
    _hunt_advance(con, t["current"], cands)


def trip_add(con, planet_id):
    """Add once: a planet already in the itinerary is left where it is (no duplicates)."""
    if not con.execute("SELECT 1 FROM planets WHERE id=?", (planet_id,)).fetchone():
        raise ValueError("Planete inconnue")
    with _lock, con:
        if con.execute("SELECT 1 FROM trip WHERE planet_id=?", (planet_id,)).fetchone():
            return False
        pos = (con.execute("SELECT MAX(position) AS m FROM trip").fetchone()["m"] or 0) + 1
        con.execute("INSERT INTO trip VALUES (?,?,?)", (planet_id, pos, _now()))
    return True


def trip_remove(con, planet_id):
    with _lock, con:
        con.execute("DELETE FROM trip WHERE planet_id=?", (planet_id,))


def trip_move(con, planet_id, delta):
    ids = [r["planet_id"] for r in con.execute("SELECT planet_id FROM trip ORDER BY position")]
    if planet_id not in ids:
        return
    i = ids.index(planet_id)
    j = max(0, min(len(ids) - 1, i + delta))
    ids.insert(j, ids.pop(i))
    with _lock, con:
        for pos, pid in enumerate(ids, 1):
            con.execute("UPDATE trip SET position=? WHERE planet_id=?", (pos, pid))


def trip_clear(con, only_visited=True):
    with _lock, con:
        if only_visited:
            con.execute("DELETE FROM trip WHERE planet_id IN (SELECT planet_id FROM visited)")
        else:
            con.execute("DELETE FROM trip")


def trip_set_current(con, planet_id):
    set_state(con, "trip_current", planet_id)
    set_state(con, "glyph_step", 0)


def set_visited(con, planet_id, on=True):
    """Mark a planet visited; if it was the current itinerary target, move on to the next one (glyph 1)."""
    if get_state(con, "mode") == "hunt" and get_state(con, "hunt"):
        t = hunt_trip(con)
        cands = hunt_candidates(con, t["hunt"]) if on and t["current"] == planet_id else None
        undo = not on and con.execute("SELECT 1 FROM visited WHERE planet_id=? AND visited_at >= ?",
                                      (planet_id, t["hunt"].get("started_at") or "")).fetchone()
        with _lock, con:
            if on:
                con.execute("INSERT OR REPLACE INTO visited VALUES (?,?)", (planet_id, _now()))
            else:
                con.execute("DELETE FROM visited WHERE planet_id=?", (planet_id,))
        if undo:  # "Annuler" on a planet visited during this hunt: it comes back in the queue
            set_state(con, "hunt_done", max(0, get_state(con, "hunt_done", 0) - 1))
        if cands is not None:
            set_state(con, "hunt_done", get_state(con, "hunt_done", 0) + 1)
            _hunt_advance(con, planet_id, cands)
        return
    was_current = trip(con)["current"] == planet_id  # before the visit changes which planet comes first
    with _lock, con:
        if on:
            con.execute("INSERT OR REPLACE INTO visited VALUES (?,?)", (planet_id, _now()))
        else:
            con.execute("DELETE FROM visited WHERE planet_id=?", (planet_id,))
    if on and was_current:
        t = trip(con)
        ids = [p["id"] for p in t["planets"]]
        after = ids[ids.index(planet_id) + 1:] + ids[:ids.index(planet_id)] if planet_id in ids else ids
        nxt = next((pid for pid in after if not next(p for p in t["planets"] if p["id"] == pid)["visited_at"]), None)
        trip_set_current(con, nxt)


def set_favorite(con, planet_id, on=True, note=None):
    with _lock, con:
        if on:
            old = con.execute("SELECT added_at FROM favorites WHERE planet_id=?", (planet_id,)).fetchone()
            con.execute("INSERT OR REPLACE INTO favorites VALUES (?,?,?)",
                        (planet_id, None, old["added_at"] if old else _now()))
        else:
            con.execute("DELETE FROM favorites WHERE planet_id=?", (planet_id,))
    if note is not None:
        set_note(con, planet_id, note)


def saved_searches(con):
    return [{"name": r["name"], "criteria": json.loads(r["criteria"]), "strict": bool(r["strict"]), "saved_at": r["saved_at"]}
            for r in con.execute("SELECT * FROM searches ORDER BY saved_at DESC")]


def save_search(con, name, criteria, strict):
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("Donne un nom a ta recherche.")
    if not criteria:
        raise ValueError("Choisis au moins un critere avant d'enregistrer.")
    clean = [{"key": c["key"], "value": c["value"]} for c in criteria if c.get("key") in FEATURES]
    with _lock, con:
        existed = con.execute("SELECT 1 FROM searches WHERE name=?", (name,)).fetchone() is not None
        con.execute("INSERT OR REPLACE INTO searches VALUES (?,?,?,?)",
                    (name, json.dumps(clean, ensure_ascii=False), int(bool(strict)), _now()))
    return existed


def delete_search(con, name):
    with _lock, con:
        con.execute("DELETE FROM searches WHERE name=?", (name,))


def set_note(con, planet_id, note):
    note = (note or "").strip()[:500]
    with _lock, con:
        if note:
            con.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?)", (planet_id, note, _now()))
        else:
            con.execute("DELETE FROM notes WHERE planet_id=?", (planet_id,))


def _listed(con, where, order):
    rows = [dict(r) | {"galaxy_name": galaxy_name(r["galaxy"])} for r in con.execute(
        ROW_SQL + f" WHERE p.id IN ({where}) ORDER BY {order}")]
    for r in rows:
        r.pop("details", None)
    return rows


def journal(con):
    """Favourites, visited planets and planets with a note (the Journal page)."""
    return {"favorites": favorites(con),
            "visited": _listed(con, "SELECT planet_id FROM visited", "v.visited_at DESC"),
            "notes": _listed(con, "SELECT planet_id FROM notes", "n.note IS NULL, p.name")}


def favorites(con):
    rows = [dict(r) | {"galaxy_name": galaxy_name(r["galaxy"])} for r in con.execute(
        ROW_SQL + " WHERE p.id IN (SELECT planet_id FROM favorites) ORDER BY f.added_at DESC")]
    for r in rows:
        r.pop("details", None)
    return rows


def duplicate_report(con):
    """Sanity check: every planet must appear once (same galaxy + glyphs), every system once."""
    dup_planets = con.execute("SELECT galaxy, glyphs, COUNT(*) n FROM planets GROUP BY galaxy, glyphs HAVING n > 1").fetchall()
    dup_systems = con.execute("SELECT ua, COUNT(*) n FROM systems GROUP BY ua HAVING n > 1").fetchall()
    return {"planets": [dict(r) for r in dup_planets], "systems": [dict(r) for r in dup_systems]}
