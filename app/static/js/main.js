"use strict";
/* La coquille : la navigation entre les cinq espaces, la ligne d'etat en haut, la barre de destination en bas
   (la carte de l'overlay, posee dans la page) et le premier lancement. */

// Les pages sont appelees par leur nom au moment du clic, pas par une reference figee ici.
const VIEWS = {
  explorer: () => renderExplorer(), itineraire: () => renderItinerary(), journal: () => renderJournal(),
  galaxie: () => renderGalaxy(), reglages: () => renderSettings(),
};
const CLICKS = {
  itineraire: (e) => itineraryClick(e), journal: (e) => journalClick(e), galaxie: (e) => galaxyClick(e),
  reglages: (e) => settingsClick(e),
};
const currentView = () => { const h = location.hash.replace(/^#\/?/, "").split("/")[0]; return h in VIEWS ? h : "explorer"; };
function route() {
  const v = currentView();
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.view === v));
  closeSheet();
  $("view").onclick = null;  // the first-launch page's own handler
  VIEWS[v]();
}
function refreshView() {
  const v = currentView();
  if (v === "explorer") { if ($("res")) runSearch(); else route(); }
  else if (v === "itineraire") renderItinerary();
  else if (v === "journal") renderJournal();
  else if (v === "galaxie") { renderSidePanel(); renderGalaxyMain(); }
  if (SHEET) reloadSheet();
}
$("view").addEventListener("click", (e) => { const f = CLICKS[currentView()]; if (f) f(e); });

// ---------- premier lancement : trois etapes ----------
function renderFirst() {
  $("view").innerHTML = `<div class="first-wrap"><div class="first">
    <div class="eyebrow" style="text-align:center">Bienvenue</div><h1>Trouve ta planète parfaite</h1>
    <p>Des régions entières déjà explorées : biomes, couleurs, sentinelles, ressources. Tu décris ce que tu veux, l'app te donne l'adresse du portail.</p>
    <div class="fsteps">
      <div class="fstep now"><div class="n">1</div><h4>Télécharger un pack</h4><p>Chaque pack couvre une partie de la galaxie. Un fichier .zip, rien à installer.</p></div>
      <div class="fstep"><div class="n">2</div><h4>L'ajouter ici</h4><p>Dépose le fichier dans Galaxie, puis clique sur Installer.</p>
        <a class="b gold sm" href="#/galaxie">Ajouter un pack</a></div>
      <div class="fstep"><div class="n">3</div><h4>Décrire ta planète</h4><p>Choisis un point de départ, puis ajuste.</p></div></div>
    <div class="ideas">${IDEAS.slice(0, 6).map(([t, d, c], i) => `<button class="idea" data-first-idea="${i}"><div class="pc-band" style="background:${c};color:${shade(c, .84)}"><i class="dia"></i><b>${esc(t)}</b></div><p>${esc(d)}</p></button>`).join("")}</div>
    <p class="hint" style="text-align:center;margin-top:14px">Les modèles s'appliqueront dès qu'un pack sera installé.</p></div></div>`;
  $("view").onclick = (e) => {
    const idea = e.target.closest("[data-first-idea]");
    if (idea) { setWishes(IDEAS[+idea.dataset.firstIdea][3]); toast("Modèle choisi : il s'appliquera dès le premier pack"); }
  };
}

// ---------- la ligne d'etat, en haut a droite ----------
function renderStatus() {
  const n = S.meta.regions.length;
  $("status").innerHTML = `<span class="led on"></span><span><b>${num(n)}</b> région${n > 1 ? "s" : ""} · ${num(S.meta.totals.planets)} planètes</span>`;
}
$("status").addEventListener("click", (e) => { if (!e.target.closest("button")) location.hash = "#/galaxie"; });

// ---------- destination bar ----------
function renderDbar() {
  const bar = $("dbar"), t = S.trip, p = t.planets.find((x) => x.id === t.current);
  const ask = S.askFav;
  if (!p && !ask) { bar.hidden = true; return; }
  bar.hidden = false;
  bar.classList.toggle("small", !!S.dbarSmall && !ask);
  if (!p) {
    bar.innerHTML = `<div class="dband" style="${bandStyle(null)}"><i class="dia"></i><div><b>${t.mode === "hunt" ? "Guidage terminé" : "Itinéraire terminé"}</b><small style="color:${bandSub(null)}">${t.mode === "hunt" ? "Plus aucune planète ne correspond" : "Toutes les planètes sont visitées"}</small></div></div>
      <div class="dglyphs"></div>${askHtml()}`;
    return;
  }
  const i = t.planets.indexOf(p) + 1;
  const sub = t.mode === "hunt" ? `Guidage · ${num(t.remaining)} restante${t.remaining > 1 ? "s" : ""}${p.score != null ? ` · ${p.score} %` : ""}` : `Itinéraire · ${i} sur ${t.planets.length}`;
  bar.innerHTML = `<button class="dband" id="dbarOpen" style="${bandStyle(p.biome)}" title="Voir la fiche"><i class="dia"></i><div style="min-width:0"><b>${esc(planetTitle(p))}</b><small style="color:${bandSub(p.biome)}">${esc(sub)}</small></div></button>
    <div class="dglyphs">${glyphCells(p.glyphs, 26)}</div>
    ${ask ? askHtml() : `<div class="dkeys"><button class="kc" id="dbarVisit">J'y suis</button><button class="kc" id="dbarSkip">Passer</button>
      <button class="b ghost sm icon" id="dbarCopy" title="Copier les glyphes">${icon("copy")}</button>
      <button class="b ghost sm icon" id="dbarSize" title="${S.dbarSmall ? "Agrandir" : "Réduire"}">${icon(S.dbarSmall ? "up" : "down")}</button></div>`}`;
}
function askHtml() {
  return S.askFav ? `<div class="dask">${icon("star", 16)}<span>Planète visitée. La garder en favori ?</span>
    <button class="b gold sm" id="askYes">Oui</button><button class="b sm" id="askNo">Non</button></div>` : "";
}
$("dbar").addEventListener("click", async (e) => {
  const t = e.target, p = S.trip.planets.find((x) => x.id === S.trip.current);
  if (t.closest("#askYes")) return setFavorite(S.askFav, true);
  if (t.closest("#askNo")) { S.askFav = null; return renderDbar(); }
  if (!p) return;
  if (t.closest("#dbarVisit")) return setVisited(p.id, true);
  if (t.closest("#dbarSkip")) return skipCurrent();
  if (t.closest("#dbarCopy")) return copyGlyphs(p.glyphs);
  if (t.closest("#dbarSize")) { S.dbarSmall = !S.dbarSmall; store.set("dbarSmall", S.dbarSmall); return renderDbar(); }
  if (t.closest("#dbarOpen")) return openSheet(p.system_ua, p.idx);
});

// ---------- ce que l'app sait des regions ----------
async function reloadMeta() {
  const first = !S.meta.regions.length;
  S.meta = await api("/api/meta");
  renderStatus();
  if (first && S.meta.regions.length) { location.hash = "#/explorer"; route(); return; }
  refreshView();
}

(async function init() {
  try { S.settings = await api("/api/settings"); } catch { /* valeurs par defaut */ }
  try { GLYPHS = await (await fetch("glyphs.json")).json(); } catch { /* la police est utilisee */ }
  S.meta = await api("/api/meta");
  try { S.saved = await api("/api/searches"); } catch { S.saved = []; }
  const keys = new Set(S.meta.features.map((f) => f.key));
  S.criteria = S.criteria.filter((c) => keys.has(c.key));  // des souhaits enregistres peuvent nommer un critere retire
  window.addEventListener("hashchange", route);
  await loadTrip();
  renderStatus();
  route();
  setInterval(loadTrip, 1500);
})();
