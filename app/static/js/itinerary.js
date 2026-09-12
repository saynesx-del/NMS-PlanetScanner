"use strict";
/* Itinéraire: the one queue the overlay follows. It comes either from a search (guided hunt: always the best
   remaining match) or from planets added by hand. The destination in large, where you are, what comes next,
   and what is already done (with Annuler: a wrong F9 is one click away from being undone). */

function renderItinerary() {
  const t = S.trip, hunt = t.mode === "hunt" && t.hunt;
  const cur = t.planets.find((p) => p.id === t.current);
  const G = hunt ? groupWishes(t.hunt.criteria).length : 0;
  const head = hunt
    ? `<div class="pagehead"><div><div class="eyebrow teal">Guidage automatique · ${esc(t.hunt.label.length > 60 ? "ta recherche" : `« ${t.hunt.label} »`)}</div><h1>Itinéraire</h1>
        <p>L'overlay affiche la destination par-dessus le jeu. Coche « j'y suis » quand tu y es, ou passe-la : visitées et passées ne reviennent plus, et les régions ajoutées ensuite rejoignent le guidage.</p></div>
        <span class="sp"></span><button class="b ghost sm" id="editHunt">Modifier la recherche</button><button class="b ghost sm" id="stopHunt">Arrêter le guidage</button></div>`
    : `<div class="pagehead"><div><div class="eyebrow">Liste à la main</div><h1>Itinéraire</h1>
        <p>Les planètes ajoutées avec + ou Y aller, dans ton ordre. L'overlay affiche la destination ; <b>F9</b> quand tu y es et on passe à la suivante.</p></div>
        <span class="sp"></span>${t.planets.some((p) => p.visited_at) ? `<button class="b ghost sm" id="clearVisited">Retirer les visitées</button>` : ""}
        ${t.planets.length ? `<button class="b ghost sm" id="clearAll">Tout vider</button>` : ""}</div>`;
  const hero = cur ? `<div class="hero"><div class="hero-band" style="${bandStyle(cur.biome)}"><i class="dia"></i><b>${esc(planetTitle(cur))}</b><small>Destination actuelle</small></div>
      <div class="hero-body">${portrait(cur, 128)}<div style="min-width:0"><div class="desc">${esc(planetKind(cur))}${hunt && cur.score != null ? ` · ${cur.score}&nbsp;%` : ""}</div>
        <div class="meta">${esc(where(cur))} · étoile ${esc(lo("star", cur.star))}${cur.rings ? " · anneaux" : ""}${cur.own_moons > 0 ? ` · ${cur.own_moons > 1 ? `${cur.own_moons} lunes` : "sa lune"}` : ""}</div>
        <div class="hero-glyphs">${glyphCells(cur.glyphs, 30, true)}</div></div>
        <div class="hero-act"><button class="b gold" data-visit="${cur.id}"><kbd>F9</kbd>J'y suis</button><button class="b" id="skipCur"><kbd>F10</kbd>Passer</button>
          <button class="b ghost" data-copy="${cur.glyphs}">${icon("copy")}Copier les glyphes</button><button class="b ghost" data-open="${esc(cur.system_ua)}|${cur.idx}">${icon("eye")}Voir la fiche</button></div></div></div>`
    : `<div class="empty" style="margin-top:20px">${hunt ? "<b>Plus aucune planète ne correspond.</b> Ajoute d'autres régions (Galaxie), ou relance un guidage moins exigeant."
      : "<b>Ton itinéraire est vide.</b> Dans Explorer, clique sur « Y aller » ou + sur une planète, ou lance « Me guider »."}</div>`;
  let prog = "";
  if (hunt) {
    const done = t.done || 0, skip = t.skipped || 0, left = t.remaining || 0, total = done + skip + left;
    const cells = Math.min(40, total);
    const k = total ? cells / total : 0;
    const nd = Math.round(done * k), ns = Math.round(skip * k);
    prog = total ? `<div class="prog"><div class="lbl"><span><b>${num(done)}</b> visitée${done > 1 ? "s" : ""}</span><span><b>${num(skip)}</b> passée${skip > 1 ? "s" : ""}</span>
        <span><b>${num(left)}</b> restante${left > 1 ? "s" : ""}${cur ? ", dont celle-ci" : ""}</span></div>
      <div class="bar">${Array.from({ length: cells }, (_, i) => `<i class="${i < nd ? "done" : i < nd + ns ? "skip" : i === nd + ns && cur ? "cur" : ""}"></i>`).join("")}</div></div>` : "";
  } else if (t.planets.length) {
    const v = t.planets.filter((p) => p.visited_at).length;
    prog = `<div class="prog"><div class="lbl"><span><b>${v}</b> visitée${v > 1 ? "s" : ""}</span><span><b>${t.planets.length - v}</b> à visiter</span></div>
      <div class="bar">${t.planets.map((p) => `<i class="${p.visited_at ? "done" : p.id === t.current ? "cur" : ""}"></i>`).join("")}</div></div>`;
  }
  const rest = hunt ? t.planets.filter((p) => p.id !== t.current) : t.planets;
  const queue = rest.length ? `<div class="h5">${hunt ? "Ensuite" : "La liste"}</div>${rest.map((p, i) => {
    const pos = hunt ? i + 2 : i + 1, isCur = p.id === t.current;
    const act = hunt ? `<button class="b sm" data-current="${p.id}">Y aller</button>`
      : `${isCur ? "" : `<button class="b sm" data-current="${p.id}">Y aller</button>`}<button class="b sm icon" data-move="${p.id}" data-d="-1" title="Monter">${icon("up")}</button>
         <button class="b sm icon" data-move="${p.id}" data-d="1" title="Descendre">${icon("down")}</button><button class="b sm icon" data-remove="${p.id}" title="Retirer">${icon("x")}</button>`;
    return `<div class="qrow${isCur ? " cur" : ""}${p.visited_at ? " visited" : ""}" data-open="${esc(p.system_ua)}|${p.idx}"><span class="pos">${p.visited_at ? "✓" : pos}</span>${portrait(p, 42)}
      <div style="min-width:0"><b>${esc(planetTitle(p))}</b><span class="sub">${esc(planetKind(p))}${p.rings ? " · anneaux" : ""}${p.own_moons > 0 ? ` · ${p.own_moons > 1 ? `${p.own_moons} lunes` : "sa lune"}` : ""}</span></div>
      <span class="sc">${hunt && p.score != null ? `${p.score}&nbsp;%` : ""}</span><span class="where">${esc(where(p))}</span><span class="act">${act}</span></div>`;
  }).join("")}${hunt && t.remaining > t.planets.length ? `<p class="hint">+ ${num(t.remaining - t.planets.length)} autres dans la file.</p>` : ""}` : "";
  // right column
  let side;
  if (hunt) {
    const hist = t.history || [];
    side = `<div class="h5" style="margin-top:0">Ce que suit le guidage</div>
      <div class="side-card"><div class="row between"><span class="caps" style="font-size:11px">${esc(t.hunt.label.length > 40 ? "Ta recherche" : t.hunt.label)}</span><button class="link" id="editHunt2">Changer</button></div>
        <div class="t">${t.hunt.min_score >= 100 ? "Parfaites seulement" : "Les parfaites, puis à un critère près"} · ${t.hunt.order === "system" ? "système par système" : "les meilleures d'abord"}</div>
        <div class="mini-chips">${groupWishes(t.hunt.criteria).map((g) => `<span>${esc(cap(groupLabel(g)))}</span>`).join("")}</div></div>
      <div class="h5">Déjà faites · ${hist.length}</div>
      ${hist.length ? hist.map((p) => `<div class="done-row"><span class="${p.skipped ? "skip" : "ok"}">${icon(p.skipped ? "x" : "check")}</span>${portrait(p, 32)}
        <div style="min-width:0"><b>${esc(planetTitle(p))}</b><small>${p.skipped ? "Passée" : `Visitée à ${esc((p.visited_at || "").slice(11, 16))}`}${p.favorite_at ? " · ★ favori" : ""}</small></div>
        <button class="b ghost sm icon" data-undo="${p.id}" data-skipped="${p.skipped ? 1 : 0}" title="Annuler : la remettre dans la file">${icon("undo")}</button></div>`).join("")
        : `<p class="hint">Les planètes visitées (F9) ou passées (F10) apparaîtront ici, avec Annuler.</p>`}`;
  } else {
    const visited = t.planets.filter((p) => p.visited_at);
    side = `<div class="h5" style="margin-top:0">Visitées · ${visited.length}</div>
      ${visited.length ? visited.map((p) => `<div class="done-row"><span class="ok">${icon("check")}</span>${portrait(p, 32)}<div style="min-width:0"><b>${esc(planetTitle(p))}</b>
        <small>Le ${esc(dateFr(p.visited_at))}${p.favorite_at ? " · ★ favori" : ""}</small></div>
        <button class="b ghost sm icon" data-undo="${p.id}" data-skipped="0" title="Annuler la visite">${icon("undo")}</button></div>`).join("")
        : `<p class="hint">Les planètes où tu es allé (F9) apparaîtront ici.</p>`}
      <div class="h5">Guidage automatique</div><div class="side-card"><div class="t">Laisse l'app choisir la prochaine planète</div>
        <p class="hint" style="margin-top:0">Dans Explorer, décris ta planète puis « Me guider » : l'overlay affiche toujours la meilleure qui reste.</p>
        <a class="b sm" href="#/explorer" style="margin-top:10px">Aller dans Explorer</a></div>`;
  }
  $("view").innerHTML = `<div class="itin"><section class="it-main scroller">${head}${hero}${prog}${queue}</section><aside class="it-side scroller">${side}</aside></div>`;
}
async function itineraryClick(e) {
  const t = e.target;
  const visit = t.closest("[data-visit]");
  if (visit) { e.stopPropagation(); return setVisited(visit.dataset.visit, true); }
  if (t.closest("#skipCur")) return skipCurrent();
  const copy = t.closest("[data-copy]");
  if (copy) { e.stopPropagation(); return copyGlyphs(copy.dataset.copy); }
  if (t.closest("#stopHunt")) return stopHunt();
  if (t.closest("#editHunt") || t.closest("#editHunt2")) {
    S.criteria = S.trip.hunt.criteria.map((c) => ({ key: c.key, value: c.value }));
    S.strict = S.trip.hunt.min_score >= 100; store.set("strict", S.strict); saveWishes();
    location.hash = "#/explorer"; return;
  }
  const current = t.closest("[data-current]");
  if (current) {
    e.stopPropagation();
    if (S.trip.mode === "hunt") { await api("/api/trip", { action: "current", planet_id: current.dataset.current }); }
    else await api("/api/trip", { action: "current", planet_id: current.dataset.current });
    await loadTrip(); return renderItinerary();
  }
  const move = t.closest("[data-move]");
  if (move) { e.stopPropagation(); await api("/api/trip", { action: "move", planet_id: move.dataset.move, delta: +move.dataset.d }); await loadTrip(); return renderItinerary(); }
  const remove = t.closest("[data-remove]");
  if (remove) { e.stopPropagation(); await api("/api/trip", { action: "remove", planet_id: remove.dataset.remove }); await loadTrip(); return renderItinerary(); }
  const undo = t.closest("[data-undo]");
  if (undo) {
    e.stopPropagation();
    if (undo.dataset.skipped === "1") await api("/api/trip", { action: "unskip", planet_id: undo.dataset.undo });
    else await api("/api/visit", { planet_id: undo.dataset.undo, on: false });
    toast("Remise dans la file"); await loadTrip(); return renderItinerary();
  }
  if (t.closest("#clearVisited")) { await api("/api/trip", { action: "clear_visited" }); await loadTrip(); return renderItinerary(); }
  if (t.closest("#clearAll")) { if (confirm("Vider tout l'itinéraire ?")) { await api("/api/trip", { action: "clear" }); await loadTrip(); renderItinerary(); } return; }
  planetClicks(e);
}
