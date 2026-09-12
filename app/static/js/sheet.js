"use strict";
/* The planet sheet: a panel over the page (the list underneath stays where it was). The planet as the game shows
   it, its real colours, its portal address, every body of its system, and the player's own journal. */

let SHEET = null;  // {system, idx}
async function openSheet(ua, idx) {
  let system;
  try { system = await api(`/api/system/${ua}`); } catch (e) { return toast(e.message, "bad"); }
  SHEET = { system, idx };
  renderSheet();
  $("drawer").hidden = false; $("scrim").hidden = false;
  $("drawer").scrollTop = 0;
}
function closeSheet() {
  SHEET = null; $("drawer").hidden = true; $("scrim").hidden = true; $("drawer").innerHTML = "";
}
async function reloadSheet() {
  if (!SHEET) return;
  try { SHEET.system = await api(`/api/system/${SHEET.system.ua}`); } catch { return; }
  renderSheet();
}
function renderSheet() {
  const s = SHEET.system, p = s.planets.find((x) => x.idx === SHEET.idx) || s.planets[0];
  const d = p.details || {}, pal = d.palettes || {}, w = d.weather || {}, tx = d.texts || {};
  const inRes = S.res && S.res.results.find((r) => r.id === p.id);
  const colours = [["Eau", p.has_water === 0 ? null : p.water_hex], ["Ciel", p.sky_hex], ["Coucher", pal.SkySunset && pal.SkySunset.c[0]],
    ["Nuit", pal.SkyNight && pal.SkyNight.c[0]], ["Herbe", p.grass_hex || (pal.Grass && pal.Grass.c[0])], ["Plantes", p.plant_hex || (pal.Plant && pal.Plant.c[0])],
    ["Feuilles", p.leaf_hex || (pal.Leaf && pal.Leaf.c[0])], ["Roche", pal.Rock && pal.Rock.c[0]]].filter(([, h]) => h);
  const temp = d.hazard && d.hazard.Temperature ? `${Math.round(d.hazard.Temperature[0])} °C` : "";
  const special = [p.prime && "prime", p.rings && "anneaux", p.own_moons > 0 && (p.own_moons > 1 ? `${p.own_moons} lunes autour d'elle` : "sa propre lune"),
    p.has_water === 0 && "sans eau"].filter(Boolean).join(" · ");
  const kv = p.details ? `<dl class="kv">
      <dt>Météo</dt><dd>${esc(gameText(tx.Weather) || fr("weather", w.WeatherType) || "?")}${w.WeatherIntensity === "Extreme" ? " · extrême" : ""}${temp ? ` · ${temp}` : ""}</dd>
      <dt>Tempêtes</dt><dd>${esc(fr("storms", w.StormFrequency) || "?")}</dd>
      <dt>Sentinelles</dt><dd>${esc(gameText(tx.Sentinels) || fr("sentinels", d.sentinels) || "?")}</dd>
      <dt>Plantes</dt><dd>${esc(gameText(tx.Flora) || fr("flora", d.flora) || "?")}</dd>
      <dt>Animaux</dt><dd>${esc(gameText(tx.Fauna) || fr("fauna", d.fauna) || "?")}</dd>
      <dt>Ressources</dt><dd>${esc([p.common, p.uncommon, p.rare].filter(Boolean).map(resLabel).join(" · ") || "inconnues")}</dd>
      ${special ? `<dt>Particularités</dt><dd>${esc(special)}</dd>` : ""}</dl>`
    : `<p class="muted">Les détails de cette planète (couleurs, météo, ressources) ne sont pas dans les données.</p>`;
  const bodies = s.planets.map((q) => `<button class="${q.idx === p.idx ? "on" : ""}" data-body-idx="${q.idx}">${portrait(q, 50)}<span>${esc(planetTitle(q))}</span>
    <small>${q.size === "Moon" ? "lune" : esc(lo("biome", q.biome))}</small></button>`).join("");
  const sysMeta = [fr("race", s.race), `économie ${lo("trading", s.trading)}`, `richesse ${lo("wealth", s.wealth)}`, `conflit ${lo("conflict", s.conflict)}`,
    fr("anomaly", s.anomaly)].filter(Boolean).join(" · ");
  $("drawer").innerHTML = `
    <div class="dr-band" style="${bandStyle(p.biome)}"><i class="dia"></i><div style="min-width:0"><b>${esc(planetTitle(p))}</b>
      <small style="color:${bandSub(p.biome)}">${esc(planetKind(p))} · ${esc(lo("size", p.size))} · ${esc(lo("biome", p.biome))}</small></div>
      ${inRes && S.criteria.length ? `<span class="pc-score" style="margin-left:auto">${inRes.score}&nbsp;%</span>` : `<span style="margin-left:auto"></span>`}
      <button class="x" id="sheetClose" title="Fermer (Échap)" aria-label="Fermer">&times;</button></div>
    <div class="dr-body">
      <div class="dr-hero">${portrait(p, 176)}${kv}</div>
      ${colours.length ? `<div class="dr-h">Couleurs vues en jeu</div><div class="palrow">${colours.map(([l, h]) => `<div><i style="background:${h}"></i>${l}</div>`).join("")}</div>` : ""}
      <div class="dr-h">Adresse du portail<span class="sp"></span><button class="b sm" data-copy="${p.glyphs}">${icon("copy")}Copier</button>
        <button class="b sm" data-trip="${p.id}"${p.trip_position != null ? " disabled" : ""}>${icon("plus")}${p.trip_position != null ? "Dans l'itinéraire" : "Itinéraire"}</button>
        <button class="b gold sm" data-go="${p.id}">Y aller</button></div>
      <div class="addr">${glyphCells(p.glyphs, 28)}</div>
      <div class="dr-h">Système ${sssHex(s.sss)} · étoile ${esc(lo("star", s.star))}<span class="sp"></span><span class="meta">${esc(sysMeta)}</span></div>
      ${s.star === "Purple" ? `<p class="hint" style="color:#C3A6FF">Système violet : le portail n'y va qu'une fois les systèmes violets débloqués en jeu.</p>` : ""}
      <div class="sysstrip">${bodies}</div>
      <div class="dr-h">Mon journal</div>
      <div class="row"><button class="b sm${p.favorite_at ? " on" : ""}" data-fav="${p.id}" data-on="${p.favorite_at ? 0 : 1}">${icon("star")}${p.favorite_at ? "Favori" : "Ajouter aux favoris"}</button>
        <button class="b sm${p.visited_at ? " on" : ""}" data-visit="${p.id}" data-on="${p.visited_at ? 0 : 1}">${icon("check")}${p.visited_at ? `Visitée le ${esc(dateFr(p.visited_at))}` : "Déjà visitée"}</button></div>
      <textarea class="note" id="sheetNote" maxlength="500" placeholder="Ajoute une note : « base principale », « œufs rares près du lac »…">${esc(p.note || "")}</textarea>
    </div>`;
  const note = $("sheetNote");
  note.onblur = async () => {
    const v = note.value.trim();
    if (v === (p.note || "")) return;
    try { await api("/api/note", { planet_id: p.id, note: v }); p.note = v || null; toast(v ? "Note enregistrée" : "Note effacée"); refreshView(); }
    catch (e) { toast(e.message, "bad"); }
  };
}
$("drawer").addEventListener("click", async (e) => {
  const t = e.target;
  if (t.closest("#sheetClose")) return closeSheet();
  const body = t.closest("[data-body-idx]");
  if (body) { SHEET.idx = +body.dataset.bodyIdx; renderSheet(); return; }
  const copy = t.closest("[data-copy]");
  if (copy) return copyGlyphs(copy.dataset.copy);
  const visit = t.closest("[data-visit]");
  if (visit) { await setVisited(visit.dataset.visit, visit.dataset.on === "1"); return reloadSheet(); }
  const go = t.closest("[data-go]"), trip = t.closest("[data-trip]"), fav = t.closest("[data-fav]");
  if (go) { await goTo(go.dataset.go); return reloadSheet(); }
  if (trip) { await addToTrip(trip.dataset.trip); return reloadSheet(); }
  if (fav) { await setFavorite(fav.dataset.fav, fav.dataset.on === "1"); return reloadSheet(); }
});
$("scrim").addEventListener("click", closeSheet);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && SHEET && !e.target.matches("textarea")) closeSheet();
});
