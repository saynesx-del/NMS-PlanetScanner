"""In-memory search index: every planet as one byte per criterion, so a search scores a million planets in a few
milliseconds (SQLite needed 4 s). Same rules, same counts and same order as the SQL search in db.py.

Layout: one segment per region (a byte per planet and column, plus a sort key); the global index is the segments
put together in the SQL order (prime first, then glyphs, then galaxy). Only (re)imported regions are re-read from
the database; the segments are saved in data/index.bin so the app starts without re-reading 1.2 million planets.

A criterion becomes a mask: the column's bytes translated to 0/1 per planet, read as one big integer. OR, AND and
+ then work on every planet at once, each planet's score staying in its own byte (fewer than 255 criteria groups).
"""

import array
import bisect
import collections
import os
import pickle
import threading

VERSION = 1
# Planet and system columns, as named in db.FEATURES (plus boundary, for the purple systems).
ENUM = ["biome", "variant", "size", "desc_key", "sentinels", "storms", "weather", "intensity", "flora", "fauna",
        "cloudiness", "water_family", "sky_family", "grass_family", "star", "race", "trading", "wealth", "conflict"]
BOOL = ["prime", "rings", "continents", "has_water", "abandoned", "pirate", "boundary"]
MIN = ["own_moons", "moons", "planet_count"]
WIDE = {"variant", "desc_key", "combo", "region"}  # may exceed 255 values: stored as two bytes (hi, lo)
SEGMENT_SQL = """
SELECT p.glyphs, p.galaxy, p.prime, p.rings, p.continents, p.has_water, p.own_moons, p.biome, p.variant, p.size,
       p.desc_key, p.sentinels, p.storms, p.weather, p.intensity, p.flora, p.fauna, p.cloudiness, p.water_family,
       p.sky_family, p.grass_family, p.common, p.uncommon, p.rare, s.star, s.race, s.trading, s.wealth, s.conflict,
       s.abandoned, s.pirate, s.boundary, s.moons, s.planet_count
FROM planets p JOIN systems s ON s.ua = p.system_ua WHERE p.region_id = ?"""
GLYPH_BITS = (1 << 48) - 1


def byte_columns():
    out = []
    for c in ENUM + BOOL + MIN + ["combo", "region"]:
        out += [c + "_hi", c + "_lo"] if c in WIDE else [c]
    return out


def sort_key(prime, glyphs, galaxy):
    """The SQL order (prime DESC, glyphs, galaxy) as one integer: prime first, then the 12 glyphs, then the galaxy."""
    return ((0 if prime else 1) << 56) | (int(glyphs, 16) << 8) | int(galaxy)


def planet_id(key):
    return f"{key & 0xFF:02X}{(key >> 8) & GLYPH_BITS:012X}"


class Index:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.dicts = {c: {} for c in ENUM + ["combo", "region"]}  # value -> code (1..), shared by all segments
        self.segments = {}  # region id -> (stamp, {column: bytes}, keys array)
        self.state = None   # the assembled index, replaced in one assignment (searches keep the one they started with)
        self.generation = 0
        self._masks = collections.OrderedDict()
        self._mask_lock = threading.Lock()  # the cache only (a rebuild holds self.lock for seconds)

    # ----- building -----
    def _code(self, col, value):
        if value is None:
            return 0
        d = self.dicts[col]
        code = d.get(value)
        if code is None:
            code = d[value] = len(d) + 1
            if code > 0xFFFF or (col not in WIDE and code > 0xFF):
                raise OverflowError(f"too many values in {col}")
        return code

    def _segment(self, con, rid):
        """One region's planets as byte columns (read column by column: several times faster than row by row)."""
        cur = con.cursor()
        cur.row_factory = None
        rows = cur.execute(SEGMENT_SQL, (rid,)).fetchall()
        region_code = self._code("region", rid)
        n = len(rows)
        cols = {}
        if not n:
            return {c: b"" for c in byte_columns()}, array.array("Q")
        (glyphs, galaxy, prime, rings, continents, has_water, own_moons, biome, variant, size, desc_key, sentinels,
         storms, weather, intensity, flora, fauna, cloudiness, water_family, sky_family, grass_family, common,
         uncommon, rare, star, race, trading, wealth, conflict, abandoned, pirate, boundary, moons,
         planet_count) = zip(*rows)
        keys = array.array("Q", [((0 if p else 1) << 56) | (int(g, 16) << 8) | int(gx)
                                 for g, gx, p in zip(glyphs, galaxy, prime)])
        enum_values = {"biome": biome, "variant": variant, "size": size, "desc_key": desc_key,
                       "sentinels": sentinels, "storms": storms, "weather": weather, "intensity": intensity,
                       "flora": flora, "fauna": fauna, "cloudiness": cloudiness, "water_family": water_family,
                       "sky_family": sky_family, "grass_family": grass_family, "star": star, "race": race,
                       "trading": trading, "wealth": wealth, "conflict": conflict}
        for c, values in enum_values.items():
            codes = [self._code(c, None if v is None else str(v)) for v in values]
            if c in WIDE:
                cols[c + "_hi"] = bytes(code >> 8 for code in codes)
                cols[c + "_lo"] = bytes(code & 0xFF for code in codes)
            else:
                cols[c] = bytes(codes)
        for c, values in (("prime", prime), ("rings", rings), ("continents", continents), ("has_water", has_water),
                          ("abandoned", abandoned), ("pirate", pirate), ("boundary", boundary)):
            cols[c] = bytes(0 if v is None else 2 if v else 1 for v in values)
        for c, values in (("own_moons", own_moons), ("moons", moons), ("planet_count", planet_count)):
            cols[c] = bytes(0 if v is None else min(int(v), 254) + 1 for v in values)
        combos = [self._code("combo", t) for t in zip(common, uncommon, rare)]
        cols["combo_hi"] = bytes(code >> 8 for code in combos)
        cols["combo_lo"] = bytes(code & 0xFF for code in combos)
        cols["region_hi"] = bytes([region_code >> 8]) * n
        cols["region_lo"] = bytes([region_code & 0xFF]) * n
        return cols, keys

    def update(self, con, regions):
        """Bring the index in line with the database. regions: {region id: stamp (file_mtime)}.
        Returns True when something changed (then the index is re-assembled and saved)."""
        with self.lock:
            changed = False
            for rid in list(self.segments):
                if rid not in regions:
                    del self.segments[rid]
                    changed = True
            for rid, stamp in regions.items():
                have = self.segments.get(rid)
                if have is None or have[0] != stamp:
                    cols, keys = self._segment(con, rid)
                    self.segments[rid] = (stamp, cols, keys)
                    changed = True
            if changed or self.state is None:
                self._assemble()
            if changed:
                self.save()
            return changed

    def _assemble(self):
        rids = sorted(self.segments)
        keys = array.array("Q")
        for rid in rids:
            keys.extend(self.segments[rid][2])
        n = len(keys)
        perm = sorted(range(n), key=keys.__getitem__)
        cols = {}
        for c in byte_columns():
            joined = b"".join(self.segments[rid][1][c] for rid in rids)
            cols[c] = bytes(map(joined.__getitem__, perm))
        state = {"n": n, "cols": cols, "keys": array.array("Q", map(keys.__getitem__, perm)),
                 "dicts": {c: dict(d) for c, d in self.dicts.items()},
                 "one": int.from_bytes(b"\x01" * n, "big") if n else 0,
                 "regions": {rid: s[0] for rid, s in self.segments.items()}}
        with self._mask_lock:
            self._masks.clear()
        self.state = state
        self.generation += 1

    # ----- saving -----
    def save(self):
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"version": VERSION, "dicts": self.dicts, "segments": self.segments}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, self.path)

    def load(self):
        """The segments saved last time (then update() only re-reads regions imported since)."""
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
        except (OSError, EOFError, pickle.UnpicklingError, ValueError):
            return False
        if data.get("version") != VERSION:
            return False
        with self.lock:
            self.dicts, self.segments = data["dicts"], data["segments"]
        return True

    # ----- searching -----
    def ready(self):
        return self.state is not None

    def _mask(self, st, col, codes):
        """Planets whose column holds one of these codes: 1 in their byte, else 0."""
        codes = frozenset(codes)
        ck = (id(st), col, codes)
        with self._mask_lock:
            m = self._masks.get(ck)
            if m is not None:
                self._masks.move_to_end(ck)
                return m
        cols = st["cols"]
        if col in WIDE:
            m = 0
            by_hi = collections.defaultdict(set)
            for c in codes:
                by_hi[c >> 8].add(c & 0xFF)
            for hi, los in by_hi.items():
                t_hi, t_lo = bytearray(256), bytearray(256)
                t_hi[hi] = 1
                for lo in los:
                    t_lo[lo] = 1
                m |= (int.from_bytes(cols[col + "_hi"].translate(t_hi), "big")
                      & int.from_bytes(cols[col + "_lo"].translate(t_lo), "big"))
        else:
            t = bytearray(256)
            for c in codes:
                t[c] = 1
            m = int.from_bytes(cols[col].translate(t), "big")
        with self._mask_lock:
            self._masks[ck] = m
            while len(self._masks) > 24:
                self._masks.popitem(last=False)
        return m

    def group_mask(self, st, group, features):
        """The SQL's _group_sql, as a mask: the planet matches one of the group's values (unknown = no)."""
        label, col, tbl, kind = features[group["key"]]
        m = 0
        for value in group["values"]:
            if kind == "text":
                q = str(value or "").lower()
                if not q:
                    continue
                codes = {code for combo, code in st["dicts"]["combo"].items()
                         if any(q in str(x or "").lower() for x in combo)}
                if codes:
                    m |= self._mask(st, "combo", codes)
            elif kind == "bool":
                m |= self._mask(st, col, {2 if bool(value if value is not None else True) else 1})
            elif kind == "min":
                k = int(value or 0)
                m |= self._mask(st, col, range(max(1, k + 1), 256))
            elif kind == "body":
                moon = st["dicts"]["size"].get("Moon")
                codes = {moon} if value == "moon" else set(st["dicts"]["size"].values()) - {moon}
                codes.discard(None)
                if codes:
                    m |= self._mask(st, "size", codes)
            else:
                code = st["dicts"][col].get(str(value))
                if code:
                    m |= self._mask(st, col, {code})
        if group["key"] == "water":
            m &= self._mask(st, "has_water", {0, 2})  # colour of a dry planet's (absent) water: a miss
        return m

    def position(self, st, pid):
        """Row of a planet id in the index, or None."""
        keys = st["keys"]
        galaxy, glyphs = int(pid[:2], 16), int(pid[2:], 16)
        for prime in (1, 0):
            k = ((0 if prime else 1) << 56) | (glyphs << 8) | galaxy
            i = bisect.bisect_left(keys, k)
            if i < len(keys) and keys[i] == k:
                return i
        return None

    def _filters(self, st, region, exclude_ids, locked_purple):
        """Region, purple systems still locked, planets to leave out: one mask (None = keep everything)."""
        n, one = st["n"], st["one"]
        keep = None
        if region:
            code = st["dicts"]["region"].get(region)
            keep = self._mask(st, "region", {code}) if code else 0
        if locked_purple:
            star_purple = st["dicts"]["star"].get("Purple")
            ok = self._mask(st, "boundary", {1})
            if star_purple:
                ok &= one ^ self._mask(st, "star", {star_purple})
            keep = ok if keep is None else keep & ok
        if exclude_ids:
            gone = bytearray(n)
            for pid in exclude_ids:
                i = self.position(st, pid)
                if i is not None:
                    gone[i] = 1
            not_gone = one ^ int.from_bytes(gone, "big")
            keep = not_gone if keep is None else keep & not_gone
        return keep

    def _levels(self, st, masks, keep):
        score = st["one"]
        for m in masks:
            score += m
        if keep is not None:
            score &= keep * 0xFF
        return score.to_bytes(st["n"], "big")  # a planet's byte: its hits + 1 (0 = filtered out)

    def rank(self, groups, features, region=None, exclude_ids=(), locked_purple=True, min_score=0, want=200):
        """(total, perfect, near, [(planet id, hits), ...]) with the SQL's filters and order."""
        st = self.state
        g = len(groups)
        masks = [self.group_mask(st, grp, features) for grp in groups]
        keep = self._filters(st, region, exclude_ids, locked_purple)
        for grp, m in zip(groups, masks):
            if grp["required"]:
                keep = m if keep is None else keep & m
        levels = self._levels(st, masks, keep)
        low = 1
        if groups and not all(grp["required"] for grp in groups):
            low = 2
        if groups and min_score:
            h = next((h for h in range(g + 1) if round(100 * h / g) >= min_score), g + 1)
            low = max(low, h + 1)
        total = sum(levels.count(level) for level in range(low, g + 2))
        perfect = levels.count(g + 1) if g + 1 >= low else 0
        near = levels.count(g) if g >= low and g >= 1 else 0
        found = []
        keys = st["keys"]
        for level in range(g + 1, low - 1, -1):
            i = levels.find(level)
            while i != -1 and len(found) < want:
                found.append((planet_id(keys[i]), level - 1))
                i = levels.find(level, i + 1)
            if len(found) >= want:
                break
        return total, perfect, near, found

    def limits(self, groups, features, region=None, exclude_ids=(), locked_purple=True):
        """For each group: how many planets would be perfect without it ("what limits you"). Computed as if no group
        were required: perfect now + those missing only this group."""
        st = self.state
        g = len(groups)
        masks = [self.group_mask(st, grp, features) for grp in groups]
        levels = self._levels(st, masks, self._filters(st, region, exclude_ids, locked_purple))
        perfect = levels.count(g + 1)
        t = bytearray(256)
        t[g] = 1  # hits = g - 1: exactly one group missing
        near = int.from_bytes(levels.translate(t), "big")
        near_n = near.bit_count()
        return [perfect + near_n - (near & m).bit_count() for m in masks]

    def per_region(self, groups, features, region=None, exclude_ids=(), locked_purple=True, cap=200000):
        """{region id: perfect planets} for the map (None when the search is too broad to be useful)."""
        st = self.state
        g = len(groups)
        if not g:
            return None
        masks = [self.group_mask(st, grp, features) for grp in groups]
        levels = self._levels(st, masks, self._filters(st, region, exclude_ids, locked_purple))
        if levels.count(g + 1) > cap:
            return None
        hi, lo = st["cols"]["region_hi"], st["cols"]["region_lo"]
        by_code = collections.Counter()
        i = levels.find(g + 1)
        while i != -1:
            by_code[hi[i] << 8 | lo[i]] += 1
            i = levels.find(g + 1, i + 1)
        names = {code: rid for rid, code in st["dicts"]["region"].items()}
        return {names[c]: k for c, k in by_code.items() if c in names}

    def options(self, features, resource_names):
        """How many planets carry each value (the filter buttons' counts), straight from the index."""
        st = self.state
        cols = st["cols"]
        counts = {}
        for c in ENUM:
            if c in WIDE:
                cnt = collections.Counter(zip(cols[c + "_hi"], cols[c + "_lo"]))
                by_code = {hi << 8 | lo: n for (hi, lo), n in cnt.items()}
            else:
                cnt = collections.Counter(cols[c])
                by_code = dict(cnt)
            counts[c] = {v: by_code.get(code, 0) for v, code in st["dicts"][c].items()}
        out = {}
        for key, (label, col, tbl, kind) in features.items():
            if kind in ("enum", "colour"):
                out[key] = sorted(([v, n] for v, n in counts.get(col, {}).items() if n), key=lambda x: -x[1])
            elif kind == "bool":
                cnt = collections.Counter(cols[col])
                out[key] = [[True, cnt.get(2, 0)], [False, cnt.get(1, 0)]]
            elif kind == "min":
                cnt = collections.Counter(cols[col])
                out[key] = [[k, sum(n for code, n in cnt.items() if code >= k + 1)] for k in (1, 2, 3, 4)]
            elif kind == "body":
                sizes = counts.get("size", {})
                out[key] = [["planet", sum(n for v, n in sizes.items() if v != "Moon")], ["moon", sizes.get("Moon", 0)]]
        combo_counts = collections.Counter(zip(cols["combo_hi"], cols["combo_lo"]))
        totals = dict.fromkeys(resource_names, 0)
        for combo, code in st["dicts"]["combo"].items():
            nplanets = combo_counts.get((code >> 8, code & 0xFF), 0)
            if not nplanets:
                continue
            text = "|".join(x for x in combo if x)
            for name in resource_names:
                if name in text:  # same rule as the search: "Copper" also matches "Activated Copper"
                    totals[name] += nplanets
        out["resource"] = [[name, totals[name]] for name in resource_names]
        return out
