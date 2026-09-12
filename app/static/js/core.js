"use strict";
/* Planet Scanner - shared pieces: state, server calls, the game's vocabulary, planet cards, glyphs, actions.
   The app's spaces (Explorer, Itinéraire, Journal, Galaxie, Réglages) live in their own files; main.js routes. */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const nf = new Intl.NumberFormat("fr-FR");
const num = (n) => nf.format(n || 0);
const store = {
  get(k, d) { try { const v = localStorage.getItem("ps." + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("ps." + k, JSON.stringify(v)); } catch { /* storage blocked */ } },
};

// ---------- state ----------
const S = {
  meta: null, settings: { purple_access: false, own_glyphs: false },
  trip: { planets: [], current: null, remaining: 0 },
  criteria: store.get("wishes", []),      // [{key, value}]
  strict: store.get("strict", false),      // only planets meeting every wish
  region: store.get("region", ""),
  hideVisited: store.get("hideVisited", false),
  view: store.get("resultsView", "cards"),
  huntOrder: store.get("huntOrder", "score"),
  dbarSmall: store.get("dbarSmall", false),
  saved: [], res: null, limit: 60, askFav: null,
};

/* How the player drives the card laid over the game: with the mouse, so the pages name the card's own
   buttons. Whole sentences rather than single words, because another way of driving the card would not fit
   the same turn of phrase; an extra module loaded after this one can put its own wording here. */
const OVL = {
  kbdVisit: "", kbdSkip: "",                                        // in front of the Itinéraire buttons
  guidage: "Sur la carte : <b>✓&nbsp;J'y suis</b> quand tu y es, <b>Passer</b> pour la suivante.",
  suivante: "à chaque <b>✓&nbsp;J'y suis</b>, la suivante",
  destination: "<b>✓&nbsp;J'y suis</b> quand tu y es et on passe à la suivante",
  faites: "Les planètes visitées ou passées apparaîtront ici, avec Annuler.",
  visitees: "Les planètes où tu es allé apparaîtront ici.",
  favori: "En jeu, clique sur <b>★&nbsp;Favori</b> sur la carte",
  arrivee: "En jeu, <b>✓&nbsp;J'y suis</b> quand tu arrives sur ta destination.",
};

async function api(path, body) {
  const r = await fetch(path, body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
// A notification like the game's: a coloured square and one line.
function toast(msg, kind = "teal", ms = 3200) {
  const t = $("toast");
  t.className = `toast show ${kind}`;
  $("toastIcon").innerHTML = kind === "gold" ? icon("star", 15) : kind === "bad" ? icon("x", 15) : icon("check", 15);
  $("toastText").textContent = msg;
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), ms);
}

// ---------- icons ----------
const ICONS = {
  planet: '<circle cx="12" cy="12" r="6"/><path d="M3 15c3 2 15-3 18-6"/>', drop: '<path d="M12 3c3 4.5 6 7.7 6 11a6 6 0 0 1-12 0c0-3.3 3-6.5 6-11z"/>',
  shield: '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/>', storm: '<path d="M7 15a4 4 0 0 1 .5-8A5.5 5.5 0 0 1 18 8a3.5 3.5 0 0 1 0 7"/><path d="M12 13l-2 4h3l-2 4"/>',
  leaf: '<path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14"/><path d="M5 19l7-7"/>', gem: '<path d="M6 4h12l3 5-9 11L3 9z"/><path d="M3 9h18"/>',
  star: '<path d="M12 3l2.6 5.8 6.4.6-4.8 4.2 1.4 6.3L12 16.8 6.4 19.9l1.4-6.3L3 9.4l6.4-.6z"/>', sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>', search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>',
  down: '<path d="M6 9l6 6 6-6"/>', up: '<path d="M6 15l6-6 6 6"/>', check: '<path d="M5 12l5 5 9-10"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', copy: '<rect x="8" y="8" width="12" height="12"/><path d="M4 16V4h12"/>', mark: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  grid: '<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>', list: '<path d="M9 6h12M9 12h12M9 18h12M4 6h1M4 12h1M4 18h1"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>', undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>', radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6.5-6.5"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  data: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>', back: '<path d="M11 18l-6-6 6-6M5 12h14"/>',
};
const icon = (n, s = 14) => `<svg class="ic" viewBox="0 0 24 24" style="width:${s}px;height:${s}px" aria-hidden="true">${ICONS[n] || ""}</svg>`;

// ---------- the game's vocabulary, in plain French ----------
const FR = {
  biome: { Lush: "Luxuriante", Toxic: "Toxique", Scorched: "Brûlante", Radioactive: "Radioactive", Frozen: "Gelée", Barren: "Aride",
    Dead: "Morte", Weird: "Exotique", Red: "Rouge", Green: "Verte", Blue: "Bleue", Swamp: "Marécageuse", Lava: "Volcanique",
    Waterworld: "Océanique", GasGiant: "Géante gazeuse" },
  size: { Large: "Grande", Medium: "Moyenne", Small: "Petite", Moon: "Lune", Giant: "Géante" },
  star: { Yellow: "Jaune", Green: "Verte", Blue: "Bleue", Red: "Rouge", Purple: "Violette" },
  race: { Traders: "Gek", Warriors: "Vy'keen", Explorers: "Korvax", None: "Aucune", Robots: "Sentinelles", Atlas: "Atlas",
    Diplomats: "Diplomates", Exotics: "Exotiques", Builders: "Autophages" },
  trading: { Mining: "Minière", HighTech: "Haute technologie", Trading: "Commerce", Manufacturing: "Manufacture", Fusion: "Fusion",
    Scientific: "Scientifique", PowerGeneration: "Énergie" },
  wealth: { Poor: "Pauvre", Average: "Moyenne", Wealthy: "Riche", Pirate: "Pirate" },
  conflict: { Low: "Faible", Default: "Moyen", High: "Élevé", Pirate: "Pirate" },
  sentinels: { Low: "Peu présentes", Default: "Normales", Aggressive: "Agressives", Corrupt: "Corrompues" },
  storms: { None: "Jamais", Low: "Rares", High: "Fréquentes", Always: "Permanentes" },
  intensity: { Default: "Supportable", Extreme: "Extrême" },
  flora: { Dead: "Aucune", Low: "Rare", Mid: "Moyenne", Full: "Abondante" },
  fauna: { Dead: "Aucune", Low: "Rare", Mid: "Moyenne", Full: "Abondante" },
  weather: { Clear: "Dégagé", Dust: "Poussière", Humid: "Humide", Snow: "Neige", Toxic: "Toxique", Scorched: "Brûlant",
    Radioactive: "Radioactif", RedWeather: "Rouge", GreenWeather: "Vert", BlueWeather: "Bleu", Swamp: "Marécageux", Lava: "Volcanique",
    Bubble: "Bulles", Weird: "Étrange", Fire: "Feu", ClearCold: "Froid et dégagé", GasGiant: "Géante gazeuse" },
  cloudiness: { CloudyWithClearSpells: "Nuageux avec éclaircies", ClearWithCloudySpells: "Dégagé avec passages nuageux" },
  anomaly: { None: "", BlackHole: "Trou noir", AtlasStation: "Station Atlas", AtlasStationFinal: "Atlas final", MiniStation: "Mini-station",
    BackgroundSwarmHive: "Essaim" },
};
const fr = (key, v) => (FR[key] && FR[key][v] !== undefined ? FR[key][v] : v);
const lo = (key, v) => String(fr(key, v) ?? "").toLowerCase();
const COLOUR_CSS = { rouge: "#D8443C", orange: "#E8893A", jaune: "#E9CF4A", vert: "#5DB45A", turquoise: "#3FB8B0", bleu: "#4A86DE",
  violet: "#8E62D9", rose: "#E07AB5", marron: "#7A5334", blanc: "#EDEFF2", gris: "#8A93A3", noir: "#1A1D24" };
// The band of a planet's card: its biome's colour (the same as the in-game overlay).
const BAND = { Lush: "#7DC25B", Swamp: "#A3A857", Toxic: "#E2C93C", Radioactive: "#B7E23F", Scorched: "#F2913D", Lava: "#EC5F3B",
  Frozen: "#A9D8EA", Waterworld: "#4DA3DC", Barren: "#DCBC84", Dead: "#A4ACB5", Weird: "#C88BE8", Red: "#F0667A", Green: "#4FD39A",
  Blue: "#6F9CF2", GasGiant: "#E6A3C8" };
const STAR_CSS = { Yellow: "#F4C63B", Green: "#65D68A", Blue: "#5AB4FF", Red: "#FF6B5C", Purple: "#B57CFF" };
const shade = (hex, t) => "#" + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * (1 - t)).toString(16).padStart(2, "0")).join("");
const bandColour = (biome) => BAND[biome] || "#AEB8C4";
const bandStyle = (biome) => { const c = bandColour(biome); return `background:${c};color:${shade(c, .84)}`; };
const bandSub = (biome) => shade(bandColour(biome), .56);
const GLYPH_NAMES = ["Couchant", "Oiseau", "Visage", "Diplo", "Éclipse", "Ballon", "Bateau", "Insecte", "Libellule", "Galaxie", "Voxel",
  "Poisson", "Tente", "Fusée", "Arbre", "Atlas"];

const resFr = (v) => (S.meta && S.meta.substances_fr && S.meta.substances_fr[v]) || v;
function resLabel(v) {
  if (!v) return "";
  const parts = String(v).split("|");
  return parts.length > 1 ? `${parts.map(resFr).join(" ou ")} (selon la planète)` : resFr(v);
}
// A text key of the game ('UI_PARADISE_PLANET') in the game's own words. Data installed from a pack carries
// the sentence itself instead of a key (a key never contains a space): it is already the game's wording.
const gameText = (key, planetClass) => {
  const texts = (S.meta && S.meta.texts) || {};
  const t = key && (texts[key] || (key.includes(" ") ? key : null));
  if (!t) return null;
  const cls = planetClass && texts[planetClass] ? texts[planetClass] : "Planète";
  // Le gabarit du jeu place la classe de la planete la ou il y a un %MOT% (c'est le seul qui apparaisse).
  return t.replace(/%[A-Z_]+%/g, cls).replace(/<[^>]*>/g, "").trim();
};
const planetKind = (p) => gameText(p.desc_key, p.class_key) || fr("biome", p.biome);
const planetTitle = (p) => p.name || `Planète ${p.idx}`;
const sssHex = (n) => (n ?? 0).toString(16).toUpperCase().padStart(3, "0");
const where = (p) => `${p.galaxy_name || ""} ${p.region || ""} · système ${sssHex(p.sss)}`.trim();
const dateFr = (s) => {
  if (!s) return "";
  const [d, t] = s.split(" "); const [, m, dd] = d.split("-");
  return `${+dd} ${["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."][+m - 1]}${t ? ` à ${t}` : ""}`;
};
const feature = (key) => S.meta && S.meta.features.find((f) => f.key === key);
const countOf = (key, v) => { const f = feature(key); const o = f && f.options && f.options.find(([x]) => x === v); return o ? o[1] : 0; };

// ---------- planet pictures and glyphs ----------
function portrait(p, size) {
  try { return `<img class="por" src="${PlanetArt.render(p, size)}" width="${size}" height="${size}" alt="">`; }
  catch { return `<span class="por" style="display:inline-block;width:${size}px;height:${size}px;border-radius:50%;background:${bandColour(p.biome)}"></span>`; }
}
let GLYPHS = null;  // Planet Scanner's own drawings (glyphs.json); the NMS font when present and chosen
const useDrawings = () => !!GLYPHS && (S.settings.own_glyphs || !(S.meta && S.meta.glyph_font));
function glyph(c, size = 26) {
  if (useDrawings()) {
    const g = GLYPHS[parseInt(c, 16)] || [];
    return `<svg class="gl" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${g.map((p) => p.e
      ? `<ellipse cx="${p.e[0]}" cy="${p.e[1]}" rx="${p.e[2]}" ry="${p.e[3]}"/>`
      : `<${p.z ? "polygon" : "polyline"} points="${p.l.map((q) => q.join(",")).join(" ")}"/>`).join("")}</svg>`;
  }
  return `<span class="gfont" style="font-size:${Math.round(size * 1.05)}px" aria-hidden="true">${esc(c)}</span>`;
}
const glyphCells = (code, size = 26, names = false) => [...(code || "")].map((c) =>
  `<span class="gc" title="${GLYPH_NAMES[parseInt(c, 16)]}">${glyph(c, size)}<small>${c}</small>${names ? `<em>${GLYPH_NAMES[parseInt(c, 16)]}</em>` : ""}</span>`).join("");

// ---------- one planet, as the game's card ----------
function tags(p) {
  const t = [];
  if (p.prime) t.push(`<span class="tag prime">Prime</span>`);
  if (p.rings) t.push(`<span class="tag">Anneaux</span>`);
  if (p.own_moons > 0) t.push(`<span class="tag">${p.own_moons > 1 ? `${p.own_moons} lunes` : "Sa lune"}</span>`);
  if (p.star === "Purple") t.push(`<span class="tag violet" title="Accessible une fois les systèmes violets débloqués en jeu">Violet</span>`);
  if (p.abandoned) t.push(`<span class="tag bad">Abandonné</span>`);
  if (p.pirate) t.push(`<span class="tag bad">Pirate</span>`);
  if (p.visited_at) t.push(`<span class="tag ok">✓ Visitée</span>`);
  return t.join("");
}
const lifeText = (p) => (p.flora === "Full" && p.fauna === "Full" ? "Faune et flore abondantes"
  : `Plantes : ${lo("flora", p.flora) || "?"} · animaux : ${lo("fauna", p.fauna) || "?"}`);
// opts: missing (wish ids not met), missText, current, score
function card(p, opts = {}) {
  const miss = new Set(opts.missing || []);
  const col = (label, fam, hex, key) => `<span class="${miss.has(key) ? "no" : ""}"><i style="background:${hex || "#555"}"></i>${label} ${esc(fam || "?")}</span>`;
  const colours = [
    p.has_water === 0 ? `<span class="${miss.has("has_water") || miss.has("water") ? "no" : ""}">Sans eau</span>` : p.water_family ? col("Eau", p.water_family, p.water_hex, "water") : "",
    p.sky_family ? col("Ciel", p.sky_family, p.sky_hex, "sky") : "",
    p.grass_family ? col("Vég.", p.grass_family, p.grass_hex, "grass") : ""].join("");
  const fact = (ic, text, keys) => `<li class="${keys.some((k) => miss.has(k)) ? "no" : ""}">${icon(ic)}${esc(text)}</li>`;
  const res = [p.common, p.uncommon, p.rare].filter(Boolean).map(resLabel).join(" · ");
  const facts = p.sentinels ? [
    fact("shield", `Sentinelles ${lo("sentinels", p.sentinels)}`, ["sentinels"]),
    fact("storm", p.storms === "None" ? "Jamais de tempête" : `Tempêtes ${lo("storms", p.storms)}${p.intensity === "Extreme" ? " · météo extrême" : ""}`, ["storms", "intensity"]),
    fact("leaf", lifeText(p), ["flora", "fauna"]),
    res ? fact("gem", res, [...miss].filter((m) => m.startsWith("resource:"))) : ""].join("") : `<li>${icon("info")}Détails absents</li>`;
  const score = opts.score ?? p.score;
  const showScore = S.criteria.length && score != null;
  return `<article class="pc${p.visited_at && !opts.current ? " visited" : ""}" data-open="${esc(p.system_ua)}|${p.idx}">
    <header class="pc-band" style="${bandStyle(p.biome)}"><i class="dia"></i><b>${esc(planetTitle(p))}</b>
      ${opts.current ? `<span class="pc-flag">Destination</span>` : ""}${showScore ? `<span class="pc-score" style="${score === 100 ? "" : "opacity:.8"}">${score}&nbsp;%</span>` : ""}</header>
    <div class="pc-body">${portrait(p, 78)}<div style="min-width:0"><div class="pc-desc">${esc(planetKind(p))}</div>
      <div class="pc-meta">${esc(lo("size", p.size))} · ${esc(where(p))}</div><div class="pc-cols">${colours}</div></div></div>
    <ul class="pc-facts">${facts}</ul>
    ${opts.missText ? `<div class="pc-miss">Il manque : <b>${esc(opts.missText)}</b></div>` : ""}
    <footer class="pc-foot"><div class="tags">${tags(p)}</div>
      <button class="b gold sm" data-go="${p.id}" title="Devient la destination de l'overlay">Y aller</button>
      <button class="b sm icon" data-trip="${p.id}" title="${p.trip_position != null ? "Déjà dans l'itinéraire" : "Ajouter à l'itinéraire"}"${p.trip_position != null ? " disabled" : ""}>${icon("plus")}</button>
      <button class="b sm icon${p.favorite_at ? " on" : ""}" data-fav="${p.id}" data-on="${p.favorite_at ? 0 : 1}" title="${p.favorite_at ? "Retirer des favoris" : "Ajouter aux favoris"}">${icon("star")}</button>
    </footer></article>`;
}

// ---------- actions shared by every page ----------
async function loadTrip() {
  try { S.trip = await api("/api/trip"); } catch { /* server restarting */ }
  if (typeof renderDbar === "function") renderDbar();
  const b = $("tripBadge"), n = S.trip.remaining || 0;
  b.hidden = !n; b.textContent = n > 99 ? "99+" : n;
}
async function goTo(id) {
  try {
    await api("/api/trip", { action: "add", planet_id: id });
    S.trip = await api("/api/trip", { action: "current", planet_id: id });
    S.dbarSmall = false; store.set("dbarSmall", false);
    toast("Nouvelle destination : ses glyphes sont dans l'overlay et en bas de la page");
  } catch (e) { toast(e.message, "bad"); }
  await loadTrip(); refreshView();
}
async function addToTrip(id) {
  try {
    const t = await api("/api/trip", { action: "add", planet_id: id });
    toast(t.added === false ? "Déjà dans ton itinéraire" : S.trip.mode === "hunt"
      ? "Ajoutée à ta liste (elle servira quand tu arrêteras le guidage)" : "Ajoutée à ton itinéraire");
  } catch (e) { toast(e.message, "bad"); }
  await loadTrip(); refreshView();
}
async function setFavorite(id, on) {
  try { await api("/api/favorite", { planet_id: id, on }); toast(on ? "Ajoutée aux favoris" : "Retirée des favoris", "gold"); }
  catch (e) { toast(e.message, "bad"); }
  if (S.askFav === id) S.askFav = null;
  renderDbar(); refreshView();
}
async function setVisited(id, on) {
  try { S.trip = await api("/api/visit", { planet_id: id, on }); } catch (e) { toast(e.message, "bad"); return; }
  S.askFav = on ? id : null;
  await loadTrip(); refreshView();
}
async function skipCurrent() {
  if (S.trip.mode === "hunt") S.trip = await api("/api/trip", { action: "skip" });
  else {
    const ids = S.trip.planets.map((p) => p.id), i = ids.indexOf(S.trip.current);
    if (ids.length) S.trip = await api("/api/trip", { action: "current", planet_id: ids[(i + 1) % ids.length] });
  }
  await loadTrip(); refreshView();
}
function copyGlyphs(code) {
  navigator.clipboard?.writeText(code).then(() => toast(`Glyphes copiés : ${code}`), () => toast(code));
}
// Clicks shared by every list of planets: Y aller, + itinéraire, favori, open the sheet.
function planetClicks(e) {
  const b = e.target.closest("[data-go],[data-trip],[data-fav],[data-open]");
  if (!b) return;
  if (b.dataset.go) { e.stopPropagation(); goTo(b.dataset.go); }
  else if (b.dataset.trip) { e.stopPropagation(); addToTrip(b.dataset.trip); }
  else if (b.dataset.fav) { e.stopPropagation(); setFavorite(b.dataset.fav, b.dataset.on === "1"); }
  else if (b.dataset.open) { const [ua, idx] = b.dataset.open.split("|"); openSheet(ua, +idx); }
}
