"use strict";
/* Explorer: describe the planet (a word bar, saved searches and ideas, criteria you can see: biome tiles, colour
   swatches, scales), then the result first (perfect / one short), what limits you, Me guider, and the cards. */

const STAR_METALS = ["Copper", "Cadmium", "Emeril", "Indium", "Quartzite"];
const BIOME_SUBSTANCES = ["Paraffinium", "Dioxite", "Ammonia", "Phosphorus", "Pyrite", "Uranium", "Gold", "Rusted Metal", "Faecium",
  "Sulphurine", "Basalt", "Lithium", "Crystallised Helium"];
const RARE_SUBSTANCES = ["Magnetised Ferrite", "Silver", "Salt", "Sodium", "Cobalt"];
const BIOME_DESC = { Lush: "verte, vivante, climat doux", Toxic: "pluies acides", Scorched: "très chaude", Radioactive: "radiations",
  Frozen: "glace et neige", Barren: "désert, peu de vie", Dead: "sans air ni vie", Weird: "formes étranges", Red: "végétation rouge",
  Green: "végétation vert vif", Blue: "végétation bleue", Swamp: "marais", Lava: "volcans et lave", Waterworld: "presque tout en eau",
  GasGiant: "boule de gaz" };
const ALIASES = {
  "sentinels:Low": "sans sentinelles aucune peu calme tranquille paisible", "sentinels:Aggressive": "hostiles dangereuses",
  "storms:None": "sans tempete aucune calme jamais", "storms:Low": "peu", "sentinels:Default": "moyennes", "storms:Always": "toujours",
  "flora:Full": "beaucoup de plantes vegetation foret", "fauna:Full": "beaucoup d'animaux creatures faune", "flora:Dead": "sans plantes",
  "fauna:Dead": "sans animaux", "intensity:Extreme": "dangereuse hostile extreme", "intensity:Default": "douce clemente",
  "biome:Waterworld": "ocean mer eau", "biome:Lush": "paradis verte temperee jardin", "biome:Frozen": "froid glace neige",
  "biome:Scorched": "chaud chaleur desert", "biome:Weird": "bizarre etrange", "biome:Lava": "volcan lave", "biome:Toxic": "acide poison",
  "biome:Barren": "desert sable", "biome:Dead": "morte sans vie", "biome:Swamp": "marais", "biome:GasGiant": "gaz",
  "has_water:true": "eau mer ocean lac avec", "has_water:false": "sec seche aride sans eau", "prime": "rare speciale",
  "rings": "anneau", "wealth:Wealthy": "riche prospere", "conflict:Low": "calme paisible", "size:Giant": "enorme",
  "resource:Activated": "metal active activee", "min_moons": "lune lunes satellite satellites systeme",
  "own_moon": "lune lunes satellite satellites propre sa autour", "resource:Silver": "argent", "resource:Gold": "or",
  "body:moon": "lune lunes satellite", "body:planet": "planete planetes pas lune",
};
// What the finder, the chips and the "what limits you" line call each wish.
function wishLabel(key, v) {
  switch (key) {
    case "water": return `eau ${v}`;
    case "sky": return `ciel ${v}`;
    case "grass": return `végétation ${v}`;
    case "has_water": return v ? "avec de l'eau" : "sans eau";
    case "prime": return "prime";
    case "rings": return "anneaux";
    case "abandoned": return v ? "abandonné" : "pas abandonné";
    case "pirate": return v ? "pirate" : "pas pirate";
    case "body": return v === "moon" ? "lunes seulement" : "planètes seulement";
    case "resource": return v === "Activated" ? "un métal activé" : resFr(v);
    case "desc": return `« ${gameText(Array.isArray(v) ? v[0] : v) || v} »`;
    case "biome": return lo("biome", v);
    case "size": return `taille ${lo("size", v)}`;
    case "sentinels": return `sentinelles ${lo("sentinels", v)}`;
    case "storms": return `tempêtes : ${lo("storms", v)}`;
    case "intensity": return `météo ${lo("intensity", v)}`;
    case "flora": return { Dead: "sans plantes", Low: "plantes rares", Mid: "plantes moyennes", Full: "plantes abondantes" }[v] || `plantes ${lo("flora", v)}`;
    case "fauna": return { Dead: "sans animaux", Low: "animaux rares", Mid: "animaux moyens", Full: "animaux abondants" }[v] || `animaux ${lo("fauna", v)}`;
    case "star": return `étoile ${lo("star", v)}`;
    case "race": return fr("race", v);
    case "wealth": return `richesse ${lo("wealth", v)}`;
    case "conflict": return `conflit ${lo("conflict", v)}`;
    case "trading": return `économie ${lo("trading", v)}`;
    case "min_moons": return `${v} lune${v > 1 ? "s" : ""} ou plus dans le système`;
    case "own_moon": return v > 1 ? `${v} lunes ou plus autour d'elle` : "sa propre lune";
    default: return String(v);
  }
}
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const SECTIONS = [
  { id: "planete", title: "Planète", icon: "planet", open: true, parts: [
    { type: "body", key: "body", label: "Corps céleste" },
    { type: "tiles", key: "biome", label: "Biome", hint: "plusieurs = l'un ou l'autre" },
    { type: "chips", key: "size", label: "Taille", order: ["Small", "Medium", "Large", "Giant"] }] },
  { id: "couleurs", title: "Couleurs", icon: "drop", open: true, parts: [
    { type: "chips", key: "has_water", label: "Eau", bool: { true: "Avec de l'eau", false: "Sans eau" } },
    { type: "swatches", key: "water", label: "" },
    { type: "swatches", key: "sky", label: "Ciel", hint: "tel qu'on le voit en jeu" },
    { type: "swatches", key: "grass", label: "Végétation" }] },
  { id: "calme", title: "Calme", icon: "shield", open: true, parts: [
    { type: "scale", key: "sentinels", label: "Sentinelles", order: ["Low", "Default", "Aggressive", "Corrupt"],
      short: { Low: "Peu", Default: "Normales", Aggressive: "Agressives", Corrupt: "Corrompues" } },
    { type: "scale", key: "storms", label: "Tempêtes", order: ["None", "Low", "High", "Always"],
      short: { None: "Jamais", Low: "Rares", High: "Fréquentes", Always: "Tout le temps" } },
    { type: "scale", key: "intensity", label: "Météo", order: ["Default", "Extreme"] }] },
  { id: "vie", title: "Vie", icon: "leaf", parts: [
    { type: "scale", key: "flora", label: "Plantes", order: ["Dead", "Low", "Mid", "Full"], short: { Dead: "Aucune", Low: "Rares", Mid: "Moyennes", Full: "Abondantes" } },
    { type: "scale", key: "fauna", label: "Animaux", order: ["Dead", "Low", "Mid", "Full"], short: { Dead: "Aucun", Low: "Rares", Mid: "Moyens", Full: "Abondants" } }] },
  { id: "ressources", title: "Ressources", icon: "gem", note: "Plusieurs cochées = il les faut toutes.", parts: [
    { type: "chips", key: "resource", label: "Métaux de l'étoile", values: ["Activated", ...STAR_METALS.map((m) => `Activated ${m}`), ...STAR_METALS] },
    { type: "chips", key: "resource", label: "Selon le biome", values: BIOME_SUBSTANCES },
    { type: "chips", key: "resource", label: "Rares", values: RARE_SUBSTANCES }] },
  { id: "special", title: "Particularités", icon: "star", parts: [
    { type: "chips", key: "prime", label: "Planète « prime » : terrain et couleurs rares", bool: { true: "Oui" } },
    { type: "chips", key: "rings", label: "Anneaux dans le ciel", bool: { true: "Oui" } },
    { type: "chips", key: "own_moon", label: "Une lune qui tourne autour d'elle", min: [1, 2] }] },
  { id: "systeme", title: "Système", icon: "sun", parts: [
    { type: "chips", key: "star", label: "Couleur de l'étoile", order: ["Yellow", "Red", "Green", "Blue", "Purple"] },
    { type: "chips", key: "race", label: "Espèce qui y vit" },
    { type: "chips", key: "wealth", label: "Richesse", order: ["Wealthy", "Average", "Poor"] },
    { type: "chips", key: "conflict", label: "Niveau de conflit", order: ["Low", "Default", "High"] },
    { type: "chips", key: "trading", label: "Économie" },
    { type: "chips", key: "min_moons", label: "Lunes dans le système", min: [1, 2, 3] },
    { type: "chips", key: "abandoned", label: "Systèmes abandonnés (sans station habitée)", bool: { false: "Les éviter" } },
    { type: "chips", key: "pirate", label: "Systèmes pirates", bool: { false: "Les éviter" } }] },
  { id: "ou", title: "Où chercher", icon: "pin", parts: [{ type: "where" }] },
];
const IDEAS = [
  ["Paradis tranquille", "Luxuriante, de l'eau, peu de sentinelles, jamais de tempête", BAND.Lush,
    [["biome", "Lush"], ["has_water", true], ["sentinels", "Low"], ["storms", "None"], ["flora", "Full"]]],
  ["Monde océan", "Presque tout en eau, sentinelles calmes", BAND.Waterworld, [["biome", "Waterworld"], ["sentinels", "Low"]]],
  ["Planète exotique", "Formes étranges, paysages uniques", BAND.Weird, [["biome", "Weird"]]],
  ["Ciel rose", "Un ciel rose au-dessus de l'eau", "#E89AC4", [["sky", "rose"], ["has_water", true]]],
  ["Base riche en métal", "Métal activé, calme, sans tempête", "#C9CED4", [["resource", "Activated"], ["sentinels", "Low"], ["storms", "None"]]],
  ["Planète prime", "Terrain et couleurs rares, plantes abondantes", "#B7A8FF", [["prime", true], ["flora", "Full"]]],
  ["Chasse aux animaux", "Faune abondante, sentinelles calmes", BAND.Green, [["fauna", "Full"], ["sentinels", "Low"]]],
];

const has = (key, v) => (Array.isArray(v) ? v.length > 0 && v.every((x) => has(key, x)) : S.criteria.some((c) => c.key === key && c.value === v));
const gid = (c) => (c.key === "resource" ? `resource:${c.value}` : c.key);
function groupWishes(criteria) {
  const out = new Map();
  for (const c of criteria) {
    const id = gid(c);
    if (!out.has(id)) out.set(id, { id, key: c.key, values: [] });
    out.get(id).values.push(c.value);
  }
  return [...out.values()];
}
const groupLabel = (g) => [...new Set(g.values.map((v) => wishLabel(g.key, v)))].join(" ou ");
const sameWishes = (a, b) => a.length === b.length && a.every((c) => b.some((d) => d.key === c.key && JSON.stringify(d.value) === JSON.stringify(c.value)));
function saveWishes() { store.set("wishes", S.criteria); S.limit = 60; }
function toggleWish(key, v) {
  if (Array.isArray(v)) {  // a game description shared by several keys
    if (has(key, v)) S.criteria = S.criteria.filter((c) => !(c.key === key && v.includes(c.value)));
    else for (const x of v) if (!has(key, x)) S.criteria.push({ key, value: x });
  } else if (has(key, v)) S.criteria = S.criteria.filter((c) => !(c.key === key && c.value === v));
  else {
    if (typeof v === "boolean" || key === "body") S.criteria = S.criteria.filter((c) => c.key !== key);  // one or the other
    S.criteria.push({ key, value: v });
  }
  saveWishes();
}
function setWishes(list) { S.criteria = list.map(([key, value]) => ({ key, value })); saveWishes(); }

// ---------- options of a part, with their planet counts ----------
function partOptions(part) {
  if (part.bool) return Object.keys(part.bool).map((k) => [k === "true", countOf(part.key, k === "true")]);
  if (part.values) return part.values.map((v) => [v, countOf("resource", v)]).filter(([, n]) => n > 0);
  if (part.min) return part.min.map((v) => [v, countOf(part.key, v)]).filter(([, n]) => n > 0);
  const f = feature(part.key);
  let opts = (f && f.options) || [];
  if (part.order) opts = [...opts].filter(([v]) => part.order.includes(v)).sort((a, b) => part.order.indexOf(a[0]) - part.order.indexOf(b[0]));
  return opts.filter(([v, n]) => n > 0 && fr(part.key, v) !== "" && !String(v).startsWith("?"));
}
const optData = (key, v) => `data-k="${key}" data-v="${esc(JSON.stringify(v))}"`;
function optLabel(part, v) {
  if (part.bool) return part.bool[String(v)];
  if (part.key === "resource") return v === "Activated" ? "N'importe quel métal activé" : resFr(v);
  if (part.min) return `Au moins ${v}`;
  return fr(part.key, v);
}
function renderPart(part) {
  if (part.type === "where") return renderWhere();
  const label = part.label === "" ? "" : `<div class="lab"><span>${esc(part.label)}</span>${part.hint ? `<small>${esc(part.hint)}</small>` : ""}</div>`;
  if (part.type === "body") {
    const cur = (S.criteria.find((c) => c.key === "body") || {}).value || null;
    return label + `<div class="seg">${[["planet", "Planètes"], ["moon", "Lunes"], [null, "Les deux"]].map(([v, l]) =>
      `<button class="${cur === v ? "on" : ""}" data-body="${v ?? ""}" title="${v ? num(countOf("body", v)) + " corps" : "Planètes et lunes"}">${l}</button>`).join("")}</div>`;
  }
  const opts = partOptions(part);
  if (!opts.length) return "";
  if (part.type === "tiles") {
    return label + `<div class="tiles">${opts.map(([v, n]) => `<button class="tile${has(part.key, v) ? " on" : ""}" ${optData(part.key, v)} title="${esc(fr("biome", v))} : ${esc(BIOME_DESC[v] || "")}">
      <span class="t"><i style="background:${bandColour(v)}"></i><span>${esc(fr("biome", v))}</span></span><small>${num(n)}</small></button>`).join("")}</div>`;
  }
  if (part.type === "swatches") {
    const counts = new Map(opts);
    const fams = (S.meta.colour_families || Object.keys(COLOUR_CSS));
    return label + `<div class="sws">${fams.map((f) => `<button class="swc${has(part.key, f) ? " on" : ""}" ${optData(part.key, f)}
      style="background:${COLOUR_CSS[f] || "#888"}" title="${esc(wishLabel(part.key, f))} · ${num(counts.get(f) || 0)} planètes"${counts.get(f) ? "" : " disabled"}></button>`).join("")}</div>`;
  }
  if (part.type === "scale") {
    return label + `<div class="seg">${opts.map(([v, n]) => `<button class="${has(part.key, v) ? "on" : ""}" ${optData(part.key, v)} title="${esc(fr(part.key, v))} · ${num(n)} planètes">${esc((part.short || {})[v] || fr(part.key, v))}</button>`).join("")}</div>`;
  }
  return label + `<div class="chips-w">${opts.map(([v, n]) => {
    const dot = part.key === "star" ? `<span class="dot" style="background:${STAR_CSS[v] || "#888"}"></span>` : "";
    return `<button class="chipt${has(part.key, v) ? " on" : ""}" ${optData(part.key, v)}>${dot}${esc(optLabel(part, v))}<small>${num(n)}</small></button>`;
  }).join("")}</div>`;
}
function renderWhere() {
  const regions = S.meta.regions;
  const byGalaxy = {};
  for (const r of regions) (byGalaxy[r.galaxy_name] = byGalaxy[r.galaxy_name] || []).push(r);
  const avant = regionEnAvant() || {}, here = avant.id || null;
  const hereKnown = here && regions.some((r) => r.id === here);
  return `<div class="lab"><span>Régions</span><small>${regions.length} connues</small></div>
    <select class="sel" id="scope" style="width:100%"><option value="">Toutes mes régions</option>
      ${hereKnown ? `<option value="${here}"${S.region === here ? " selected" : ""}>${esc(avant.libelle)} (${esc(here.split("_")[1])})</option>` : ""}
      ${Object.entries(byGalaxy).map(([g, rs]) => `<optgroup label="${esc(g)}">${rs.map((r) => `<option value="${r.id}"${S.region === r.id ? " selected" : ""}>Région ${r.region}</option>`).join("")}</optgroup>`).join("")}
    </select>
    <p class="hint">Les planètes des systèmes violets ${S.settings.purple_access ? "sont incluses" : "sont cachées tant que tu ne les as pas débloqués"} (Réglages).</p>`;
}
function sectionActive(sec) {
  return S.criteria.filter((c) => sec.parts.some((p) => p.key === c.key && (!p.values || p.values.includes(c.value))));
}
function sectionOpen(sec) {
  const open = store.get("openSections2", {});
  return sec.id in open ? open[sec.id] : !!sec.open || sectionActive(sec).length > 0;
}
function sectionSummary(sec, active) {
  if (sec.id === "ou") return S.region ? `Région ${esc(S.region.split("_")[1])}` : "Toutes tes régions";
  if (!active.length) return { ressources: "Aucune exigence", systeme: "Tous les systèmes" }[sec.id] || "Pas de préférence";
  return `<b>${esc([...new Set(active.map((c) => cap(wishLabel(c.key, c.value))))].join(" · "))}</b>`;
}

// ---------- the criteria column ----------
function renderCriteria() {
  const box = $("crit");
  if (!box) return;
  const scroll = box.scrollTop;
  const saved = S.saved.find((x) => sameWishes(x.criteria, S.criteria));
  box.innerHTML = `
    <div class="row between"><span class="caps" style="font-size:12.5px">Ma planète idéale</span>${S.criteria.length ? `<button class="link" id="clearAll">Tout effacer</button>` : ""}</div>
    <div class="m-input" style="margin-top:14px">${icon("search", 16)}<input id="finder" autocomplete="off" placeholder="Décris-la : eau bleue, calme, cuivre…" aria-label="Décris ta planète"></div>
    <div class="finds" id="finds" hidden></div>
    <div class="row" style="margin-top:8px">
      <div class="menu-wrap"><button class="m-select" id="menuBtn" aria-haspopup="true" aria-expanded="false"><i class="dia" style="color:var(--gold);width:8px;height:8px"></i>
        <span class="grow">${saved ? `${esc(saved.name)} <small>· ${saved.criteria.length} critères</small>` : `Mes recherches et modèles`}</span>${icon("down")}</button>
        <div class="menu scroller" id="menu" hidden></div></div>
      <button class="b icon" id="saveOpen" title="Enregistrer cette recherche"${S.criteria.length ? "" : " disabled"}>${icon("mark")}</button></div>
    <form class="saveform" id="saveForm" hidden><input id="saveName" maxlength="60" placeholder="Nom : Base cuivre calme" value="${esc(saved ? saved.name : "")}" aria-label="Nom de la recherche">
      <button class="b gold sm">Enregistrer</button><button type="button" class="b ghost sm" id="saveCancel">Annuler</button></form>
    ${SECTIONS.map((sec) => {
      const active = sectionActive(sec), open = sectionOpen(sec);
      return `<div class="sec${open ? " open" : ""}" data-sec="${sec.id}"><button class="sec-h" data-toggle="${sec.id}" aria-expanded="${open}">${icon(sec.icon)}${esc(sec.title)}
        ${active.length ? `<span class="n">${active.length}</span>` : ""}<span class="chev">${icon("down")}</span></button>
        ${open ? `<div class="sec-body">${sec.note ? `<p class="hint">${esc(sec.note)}</p>` : ""}${sec.parts.map(renderPart).join("")}</div>`
          : `<div class="sec-sum">${sectionSummary(sec, active)}</div>`}</div>`;
    }).join("")}`;
  box.scrollTop = scroll;
  wireCriteria();
}
function wireCriteria() {
  const box = $("crit");
  box.onclick = (e) => {
    const t = e.target;
    const opt = t.closest("[data-k]");
    if (opt && !opt.disabled) { toggleWish(opt.dataset.k, JSON.parse(opt.dataset.v)); return wishesChanged(); }
    const body = t.closest("[data-body]");
    if (body) {
      S.criteria = S.criteria.filter((c) => c.key !== "body");
      if (body.dataset.body) S.criteria.push({ key: "body", value: body.dataset.body });
      saveWishes(); return wishesChanged();
    }
    const tog = t.closest("[data-toggle]");
    if (tog) {
      const open = store.get("openSections2", {}), sec = SECTIONS.find((s) => s.id === tog.dataset.toggle);
      open[sec.id] = !sectionOpen(sec); store.set("openSections2", open); return renderCriteria();
    }
    if (t.id === "clearAll") { S.criteria = []; saveWishes(); return wishesChanged(); }
    if (t.closest("#menuBtn")) return toggleMenu();
    if (t.closest("#saveOpen")) { $("saveForm").hidden = false; $("saveName").focus(); return; }
    if (t.id === "saveCancel") { $("saveForm").hidden = true; return; }
  };
  $("saveForm").onsubmit = async (e) => {
    e.preventDefault();
    const name = $("saveName").value.trim();
    try {
      const r = await api("/api/searches", { name, criteria: S.criteria, strict: S.strict });
      S.saved = r.searches; toast(r.replaced ? `Recherche « ${name} » mise à jour` : `Recherche « ${name} » enregistrée`, "gold");
      renderCriteria();
    } catch (err) { toast(err.message, "bad"); }
  };
  const finder = $("finder");
  finder.oninput = finderInput;
  finder.onkeydown = (e) => {
    if (e.key === "Enter") { const first = $("finds").querySelector("[data-k]"); if (first) first.click(); }
    if (e.key === "Escape") { finder.value = ""; finderInput(); }
  };
  const scope = $("scope");
  if (scope) scope.onchange = () => { S.region = scope.value; store.set("region", S.region); wishesChanged(); };
}
function toggleMenu(force) {
  const menu = $("menu"), open = force ?? menu.hidden;
  menu.hidden = !open; $("menuBtn").setAttribute("aria-expanded", String(open));
  if (!open) return;
  menu.innerHTML = `<h4>Mes recherches</h4>${S.saved.length ? S.saved.map((x, i) => `<div class="mi"><button class="load" data-load="${i}">${esc(x.name)} <small>· ${x.criteria.length} critères${x.strict ? " · parfaites" : ""}</small></button>
      <button class="x" data-del="${i}" title="Supprimer ${esc(x.name)}" aria-label="Supprimer ${esc(x.name)}">&times;</button></div>`).join("")
      : `<div class="empty-m">Choisis des critères puis ${icon("mark", 12)} pour garder ta recherche.</div>`}
    <h4>Modèles</h4>${IDEAS.map(([name, desc], i) => `<div class="mi"><button class="load" data-idea="${i}">${esc(name)} <small>· ${esc(desc)}</small></button></div>`).join("")}`;
  menu.onclick = async (e) => {
    e.stopPropagation();
    const load = e.target.closest("[data-load]"), idea = e.target.closest("[data-idea]"), del = e.target.closest("[data-del]");
    if (load) {
      const x = S.saved[+load.dataset.load];
      S.criteria = x.criteria.map((c) => ({ key: c.key, value: c.value })); S.strict = x.strict; store.set("strict", S.strict);
      saveWishes(); toggleMenu(false); wishesChanged(); toast(`Recherche « ${x.name} » chargée`);
    } else if (idea) {
      const [name, , , wishes] = IDEAS[+idea.dataset.idea];
      setWishes(wishes); toggleMenu(false); wishesChanged(); toast(`Modèle « ${name} » : ajuste les critères comme tu veux`);
    } else if (del) {
      const x = S.saved[+del.dataset.del];
      if (!confirm(`Supprimer la recherche « ${x.name} » ?`)) return;
      S.saved = (await api("/api/searches", { action: "delete", name: x.name })).searches;
      toggleMenu(true); toast(`Recherche « ${x.name} » supprimée`);
    }
  };
}
document.addEventListener("click", (e) => { const m = $("menu"); if (m && !m.hidden && !e.target.closest(".menu-wrap")) toggleMenu(false); });

// ---------- the word bar: any word gives the matching criteria ----------
const STOP = new Set(["de", "la", "le", "les", "des", "du", "un", "une", "avec", "et", "en", "au", "aux", "d", "l", "a", "je", "veux", "planete", "planetes"]);
const NEG = new Set(["pas", "sans", "aucun", "aucune", "aucuns", "jamais", "zero", "no", "non"]);
const words = (s) => norm(s).split(/[^a-z0-9]+/).filter((w) => w.length > 1 && !STOP.has(w)).map((w) => (NEG.has(w) ? "sans" : w));
function allOptions() {
  const out = [];
  const desc = feature("desc"), byText = new Map();
  for (const [k, cnt] of (desc && desc.options) || []) {
    const text = gameText(k);
    if (!text) continue;
    const o = byText.get(text) || { keys: [], cnt: 0 };
    o.keys.push(k); o.cnt += cnt; byText.set(text, o);
  }
  for (const [text, o] of byText) out.push({ key: "desc", v: o.keys, cnt: o.cnt, text: words(`description ${text}`).join(" ") });
  for (const sec of SECTIONS) for (const part of sec.parts) {
    if (part.type === "where") continue;
    const opts = part.type === "body" ? [["planet", countOf("body", "planet")], ["moon", countOf("body", "moon")]]
      : part.type === "swatches" ? (S.meta.colour_families || []).map((f) => [f, countOf(part.key, f)]).filter(([, n]) => n) : partOptions(part);
    for (const [v, cnt] of opts) {
      const txt = `${part.label || ""} ${wishLabel(part.key, v)} ${v} ${ALIASES[`${part.key}:${v}`] || ""} ${ALIASES[part.key] || ""} ${part.key === "biome" ? BIOME_DESC[v] || "" : ""}`;
      out.push({ key: part.key, v, cnt, text: words(txt).join(" ") });
    }
  }
  return out;
}
function finderInput() {
  const q = words($("finder").value), box = $("finds");
  if (!q.length) { box.hidden = true; box.innerHTML = ""; return; }
  const point = (w, tw) => (tw.includes(w) ? 2 : tw.some((t) => t.startsWith(w) || (t.length >= 4 && w.startsWith(t) && w.length - t.length <= 2)) ? 1 : 0);
  const hits = allOptions().map((o) => { const tw = o.text.split(" "); return { ...o, score: q.reduce((a, w) => a + point(w, tw), 0) }; })
    .filter((o) => o.score > 0).sort((a, b) => b.score - a.score || b.cnt - a.cnt).slice(0, 10);
  box.hidden = false;
  box.innerHTML = hits.length ? hits.map((o) => {
    const mark = ["water", "sky", "grass"].includes(o.key) ? `<span class="dot" style="background:${COLOUR_CSS[o.v] || "#888"};border-radius:2px"></span>` : "";
    return `<button class="chipt${has(o.key, o.v) ? " on" : ""}" ${optData(o.key, o.v)}>${mark}${esc(cap(wishLabel(o.key, o.v)))}<small>${num(o.cnt)}</small></button>`;
  }).join("") : `<span class="hint">Aucun critère ne correspond. Essaie un autre mot, ou ouvre les catégories ci-dessous.</span>`;
  box.onclick = (e) => {
    const o = e.target.closest("[data-k]");
    if (!o) return;
    e.stopPropagation();
    toggleWish(o.dataset.k, JSON.parse(o.dataset.v));
    const keep = $("finder").value;
    wishesChanged();
    $("finder").value = keep; finderInput(); $("finder").focus();
  };
}

// ---------- results ----------
let searchTimer = null, searchSeq = 0;
function wishesChanged() { renderCriteria(); clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 90); }
function renderExplorer() {
  if (!S.meta.regions.length) return renderFirst();
  $("view").innerHTML = `<div class="exp"><aside class="crit scroller" id="crit" aria-label="Critères"></aside><section class="res scroller" id="res"></section></div>`;
  renderCriteria();
  $("res").addEventListener("click", resultsClick);
  runSearch();
}
async function runSearch() {
  const seq = ++searchSeq;
  const body = { criteria: S.criteria.map((c) => ({ ...c, required: S.strict })), region: S.region || null, limit: S.limit,
    hide_visited: !!S.hideVisited, insight: true };
  let res;
  try { res = await api("/api/search", body); } catch (e) { toast(e.message, "bad"); return; }
  if (seq !== searchSeq) return;  // a newer search is on its way
  S.res = res;
  renderResults();
}
function renderResults() {
  const box = $("res"), res = S.res;
  if (!box || !res) return;
  const groups = groupWishes(S.criteria), G = groups.length;
  const scope = S.region ? `dans la région ${S.region.split("_")[1]}` : `dans tes ${S.meta.regions.length} régions`;
  const head = !G
    ? `<div class="r-head"><div class="bignum plain"><b>${num(res.total)}</b><div><span class="l">Planètes accessibles</span><span class="s">${scope} · décris ta planète à gauche : elles se classent au fur et à mesure</span></div></div></div>`
    : `<div class="r-head"><div class="bignum"><b>${num(res.perfect)}</b><div><span class="l">${res.perfect > 1 ? "Planètes parfaites" : "Planète parfaite"}</span><span class="s">${scope}</span></div></div>
        ${G > 1 && !S.strict ? `<span class="vsep"></span><div class="bignum second"><b>${num(res.near)}</b><div><span class="l">À un critère près</span><span class="s">classées juste après</span></div></div>` : ""}
        <div class="seg" role="group" aria-label="Quelles planètes montrer"><button data-strict="1" class="${S.strict ? "on" : ""}">Parfaites seulement</button><button data-strict="0" class="${S.strict ? "" : "on"}">Les plus proches d'abord</button></div></div>`;
  const lim = (res.limits || [])[0];
  const gain = lim ? lim.perfect - res.perfect : 0;
  const chips = new Map();
  for (const c of S.criteria) { const label = wishLabel(c.key, c.value), id = `${c.key}|${label}`; if (!chips.has(id)) chips.set(id, { c, label }); }
  const chipsHtml = chips.size ? `<div class="chips"><span class="k">Tu cherches</span>${[...chips.entries()].map(([id, { c, label }]) => {
    const sw = ["water", "sky", "grass"].includes(c.key) ? `<i style="background:${COLOUR_CSS[c.value] || "#888"}"></i>` : "";
    const isLim = lim && gain > 0 && gid(c) === lim.id;
    return `<span class="chip${isLim ? " lim" : ""}">${sw}${esc(cap(label))}<button data-rm="${esc(id)}" aria-label="Retirer ${esc(label)}">&times;</button></span>`;
  }).join("")}</div>` : "";
  let insight = "";
  if (lim && gain > 0) {
    const name = groupLabel(groups.find((g) => g.id === lim.id));
    const next = (res.limits || []).slice(1, 4).filter((x) => x.perfect > res.perfect)
      .map((x) => `${groupLabel(groups.find((g) => g.id === x.id))} (${num(x.perfect)} sans lui)`).join(" · ");
    insight = `<div class="insight">${icon("bulb", 20)}<div class="txt"><b>${res.perfect ? "Le critère qui te coûte le plus" : "Aucune planète parfaite. Le critère qui bloque le plus"} : « ${esc(name)} ».</b>
      Sans lui, <b>${num(lim.perfect)}</b> planète${lim.perfect > 1 ? "s" : ""} parfaite${lim.perfect > 1 ? "s" : ""}${res.perfect ? ` au lieu de ${num(res.perfect)}` : ""}.
      ${next ? `<small>Ensuite : ${esc(next)}</small>` : ""}</div><button class="b sm" data-drop="${esc(lim.id)}">Retirer « ${esc(name)} »</button></div>`;
  }
  const hunting = S.trip.mode === "hunt" && S.trip.hunt && sameWishes(S.trip.hunt.criteria.map((c) => ({ key: c.key, value: c.value })), S.criteria);
  let cta = "";
  if (G && hunting) {
    cta = `<div class="cta running"><span class="led on"></span><span class="txt"><b>Guidage en cours avec cette recherche</b> · ${num(S.trip.remaining)} planète${S.trip.remaining > 1 ? "s" : ""} dans la file · ${num(S.trip.done || 0)} visitée${(S.trip.done || 0) > 1 ? "s" : ""}. ${OVL.guidage}</span>
      <a class="b sm" href="#/itineraire">Voir l'itinéraire</a><button class="b ghost sm" id="stopHunt">Arrêter</button></div>`;
  } else if (G && res.total) {
    const n = S.strict || G < 2 ? res.perfect : res.perfect + res.near;
    cta = `<div class="cta"><button class="b gold" id="startHunt"${n ? "" : " disabled"}><i class="dia fill" style="width:8px;height:8px"></i>Me guider · ${num(n)} planète${n > 1 ? "s" : ""}</button>
      <span class="txt">${S.strict || G < 2 ? "Les parfaites" : "Les parfaites, puis celles à un critère près"}. L'overlay affiche la meilleure ; ${OVL.suivante}.${S.trip.mode === "hunt" ? " Remplace le guidage en cours." : ""}</span>
      <div class="seg" role="group" aria-label="Ordre du guidage"><button data-order="score" class="${S.huntOrder === "score" ? "on" : ""}">Les meilleures d'abord</button><button data-order="system" class="${S.huntOrder === "system" ? "on" : ""}">Système par système</button></div></div>`;
  }
  const current = S.trip.current;
  const results = res.results.map((r) => {
    const hits = new Set(r.hits || []);
    const missing = groups.filter((g) => !hits.has(g.id));
    return { r, missing: missing.map((g) => g.id), missText: missing.map(groupLabel).join(", ") };
  });
  const list = !results.length
    ? `<div class="empty">${S.strict && G ? "Aucune planète n'est parfaite. Choisis « Les plus proches d'abord » pour voir celles qui s'en approchent, ou retire un critère."
      : "Aucune planète ne correspond. Retire un critère, ou ajoute d'autres régions (Galaxie)."}</div>`
    : S.view === "list" ? resultsTable(results, current)
    : `<div class="cards">${results.map(({ r, missing, missText }) => card(r, { current: r.id === current, missing, missText: G ? missText : "" })).join("")}</div>`;
  box.innerHTML = `${head}${chipsHtml}${insight}${cta}
    <div class="r-tools"><span class="t">Résultats<small>${G ? (S.strict ? `${num(res.total)} parfaites` : `${num(res.perfect)} parfaites, puis les plus proches`) : `${num(res.total)} planètes`}</small></span><span class="sp"></span>
      <button class="chipt${S.hideVisited ? " on" : ""}" id="hideVisited">Cacher les visitées</button>
      <div class="viewtog" role="group" aria-label="Affichage"><button data-view="cards" class="${S.view === "cards" ? "on" : ""}" title="Cartes">${icon("grid")}</button><button data-view="list" class="${S.view === "list" ? "on" : ""}" title="Liste">${icon("list")}</button></div></div>
    ${list}${res.total > res.results.length ? `<button class="b more" id="more">Afficher plus</button>` : ""}`;
}
function resultsTable(results, current) {
  const sw = (hex, fam) => fam ? `<span class="sw" style="background:${hex}"></span>${esc(fam)}` : "—";
  return `<div class="tablewrap"><table class="rows"><thead><tr><th></th><th>Planète</th><th>Score</th><th>Eau</th><th>Ciel</th><th>Végétation</th><th>Sentinelles</th><th>Tempêtes</th><th>Où</th><th></th></tr></thead><tbody>
    ${results.map(({ r, missText }) => `<tr class="click" data-open="${esc(r.system_ua)}|${r.idx}" title="${esc(missText ? "Il manque : " + missText : "")}">
      <td>${portrait(r, 34)}</td><td><b>${esc(planetTitle(r))}</b>${r.id === current ? ` <span class="tag ok">Destination</span>` : ""}<br><span class="muted">${esc(planetKind(r))}</span></td>
      <td class="gold">${S.criteria.length ? `${r.score} %` : ""}</td><td>${r.has_water === 0 ? "sans eau" : sw(r.water_hex, r.water_family)}</td><td>${sw(r.sky_hex, r.sky_family)}</td><td>${sw(r.grass_hex, r.grass_family)}</td>
      <td>${esc(lo("sentinels", r.sentinels) || "?")}</td><td>${esc(lo("storms", r.storms) || "?")}</td><td>${esc(r.region)}</td>
      <td><button class="b gold sm" data-go="${r.id}">Y aller</button></td></tr>`).join("")}</tbody></table></div>`;
}
function resultsClick(e) {
  const t = e.target;
  const strict = t.closest("[data-strict]");
  if (strict) { S.strict = strict.dataset.strict === "1"; store.set("strict", S.strict); S.limit = 60; return runSearch(); }
  const order = t.closest("[data-order]");
  if (order) { S.huntOrder = order.dataset.order; store.set("huntOrder", S.huntOrder); return renderResults(); }
  const view = t.closest("[data-view]");
  if (view) { S.view = view.dataset.view; store.set("resultsView", S.view); return renderResults(); }
  const rm = t.closest("[data-rm]");
  if (rm) { S.criteria = S.criteria.filter((c) => `${c.key}|${wishLabel(c.key, c.value)}` !== rm.dataset.rm); saveWishes(); return wishesChanged(); }
  const drop = t.closest("[data-drop]");
  if (drop) { S.criteria = S.criteria.filter((c) => gid(c) !== drop.dataset.drop); saveWishes(); toast("Critère retiré"); return wishesChanged(); }
  if (t.closest("#hideVisited")) { S.hideVisited = !S.hideVisited; store.set("hideVisited", S.hideVisited); S.limit = 60; return runSearch(); }
  if (t.closest("#more")) { S.limit += 60; return runSearch(); }
  if (t.closest("#startHunt")) return startHunt();
  if (t.closest("#stopHunt")) return stopHunt();
  planetClicks(e);
}
async function startHunt() {
  const groups = groupWishes(S.criteria), G = groups.length;
  if (!G) return;
  const saved = S.saved.find((x) => sameWishes(x.criteria, S.criteria));
  const label = saved ? saved.name : groups.map(groupLabel).join(" · ");
  const min = S.strict || G < 2 ? 100 : Math.floor(100 * (G - 1) / G);
  try {
    S.trip = await api("/api/trip", { action: "hunt_start", criteria: S.criteria.map((c) => ({ ...c, required: S.strict })),
      region: S.region || null, min_score: min, order: S.huntOrder, label });
  } catch (e) { return toast(e.message, "bad"); }
  S.dbarSmall = false; store.set("dbarSmall", false);
  toast(S.trip.current ? `Guidage lancé : ${num(S.trip.remaining)} planètes. Les glyphes de la première sont dans l'overlay.`
    : "Aucune planète assez proche : retire un critère ou ajoute d'autres régions", S.trip.current ? "gold" : "bad", 4500);
  await loadTrip(); renderResults();
}
async function stopHunt() {
  S.trip = await api("/api/trip", { action: "hunt_stop" });
  toast("Guidage arrêté");
  await loadTrip(); refreshView();
}
