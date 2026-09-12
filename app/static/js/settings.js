"use strict";
/* Réglages : chaque réglage au même endroit, avec une phrase qui dit ce qu'il fait. Ceux de l'overlay
   (taille, opacité, couleur du bandeau, position) se voient sur un aperçu et s'appliquent en une seconde. */

const SET = { overlay: null, accessible: null, section: "recherche" };
const NAV_REGLAGES = [["recherche", "search", "Recherche"], ["overlay", "eye", "Overlay"],
  ["glyphes", "grid", "Glyphes"], ["donnees", "data", "Données"], ["apropos", "info", "À propos"]];

async function renderSettings() {
  try {
    [SET.overlay, SET.accessible] = await Promise.all([api("/api/overlay"), api("/api/search", { criteria: [], limit: 0, purple: false }).then((r) => r.total)]);
  } catch { /* la page s'affiche sans */ }
  const nav = NAV_REGLAGES;
  const tog = (id, on, disabled) => `<button class="tog" id="${id}" aria-pressed="${!!on}"${disabled ? " disabled" : ""}></button>`;
  // Combien de planètes le portail refuse d'atteindre : s'il n'y en a aucune, le réglage n'a pas lieu d'être.
  const hidden = SET.accessible != null ? S.meta.totals.planets - SET.accessible : 0;
  const o = SET.overlay || { scale: 1, alpha: .9, band: "biome" };
  const cur = S.trip.planets.find((p) => p.id === S.trip.current);
  const pv = cur || { name: "Planet Scanner", biome: null, glyphs: "", desc_key: null };
  const band = o.band === "gold" ? "#EBC733" : cur ? bandColour(cur.biome) : "#AEB8C4";
  $("view").innerHTML = `<div class="set"><nav class="s-nav" id="snav">${nav.map(([k, i, l]) => `<a href="#/reglages" data-sec="${k}" class="${SET.section === k ? "on" : ""}">${icon(i)}${l}</a>`).join("")}</nav>
    <section class="s-main scroller" id="smain">
      <div class="s-sec" id="sec-recherche"><h2>Recherche</h2>
        ${hidden > 0 || S.settings.purple_access ? `<div class="s-row"><div><div class="t">J'ai débloqué les systèmes violets</div><div class="h">Sans ça, le portail refuse d'y aller et t'envoie ailleurs${hidden > 0 && !S.settings.purple_access ? ` : leurs ${num(hidden)} planètes restent cachées des résultats` : ""}.</div></div><div class="ctl">${tog("setPurple", S.settings.purple_access)}</div></div>` : ""}
        <div class="s-row"><div><div class="t">Cacher les planètes où je suis déjà allé</div><div class="h">Dans les résultats d'Explorer. Le guidage, lui, les saute toujours.</div></div><div class="ctl">${tog("setHide", S.hideVisited)}</div></div></div>
      <div class="s-sec" id="sec-overlay"><h2>Overlay</h2>
        <div class="ov-prev"><div class="ovc" style="opacity:${o.alpha}"><div class="hb" style="background:${band};color:${shade(band, .84)}"><span class="chip2">✥</span><span class="chip2">−</span><span class="chip2">+</span>
          <i class="dia" style="width:7px;height:7px;margin:0 4px"></i><div><b>${esc(planetTitle(pv))}</b><small style="color:${shade(band, .56)}">${cur ? (S.trip.mode === "hunt" ? `Guidage · ${S.trip.remaining} restantes` : "Voyage") : "Aucune destination"}</small></div></div>
          <div class="bd"><div class="d">${cur ? esc(planetKind(cur)) : "Choisis une destination dans l'app"}</div>${cur ? `<div class="gl">${[...cur.glyphs].map((c) => glyph(c, 20)).join("")}</div>` : ""}
          <div class="ks">${(cur ? ["J'y suis", "Passer", "Masquer"] : ["Masquer"]).map((l) => `<span class="kc">${l}</span>`).join("")}</div></div></div>
          <div class="ov-note">Aperçu. Chaque réglage change aussi l'overlay par-dessus le jeu, en une seconde.</div></div>
        <div class="s-row"><div><div class="t">Taille</div><div class="h">Les boutons − et + de l'overlay font la même chose.</div></div><div class="ctl"><button class="b sm icon" data-scale="-1" aria-label="Plus petit">−</button>
          <span style="font-size:13px;min-width:70px;text-align:center">${o.scale + 1} sur 5</span><button class="b sm icon" data-scale="1" aria-label="Plus grand">+</button></div></div>
        <div class="s-row"><div><div class="t">Opacité</div></div><div class="ctl" style="gap:12px"><input type="range" id="setAlpha" min="30" max="100" step="5" value="${Math.round(o.alpha * 100)}" aria-label="Opacité"><span style="font-size:13px;min-width:44px" id="alphaVal">${Math.round(o.alpha * 100)} %</span></div></div>
        <div class="s-row"><div><div class="t">Couleur du bandeau</div><div class="h">Celle du biome de la destination, ou toujours l'or des découvertes.</div></div><div class="ctl"><div class="seg" style="min-width:220px">
          <button data-band="biome" class="${o.band !== "gold" ? "on" : ""}">Couleur du biome</button><button data-band="gold" class="${o.band === "gold" ? "on" : ""}">Or</button></div></div></div>
        <div class="s-row"><div><div class="t">Position</div><div class="h">Tu peux aussi le tirer par ✥, directement sur la carte.</div></div><div class="ctl"><button class="b sm" id="ovReset">Replacer en haut à gauche</button></div></div>
        <div class="lab" style="margin-top:18px"><span>Par-dessus le jeu</span></div>
        <p class="hint" id="ovAide">L'overlay affiche ta destination et son adresse par-dessus le jeu, et se pilote à la souris : déplace-le par la poignée, change sa taille avec − et +.
          Coche « j'y suis » depuis l'app ou depuis la carte elle-même. Le jeu doit tourner en plein écran fenêtré.</p></div>
      <div class="s-sec" id="sec-glyphes"><h2>Glyphes</h2>
        <div class="s-row"><div><div class="t">Dessin des glyphes</div><div class="h">La police du jeu (usage personnel, si elle est installée) ou les dessins de Planet Scanner.</div></div>
          <div class="ctl"><div class="seg" style="min-width:250px"><button data-glyphs="font" class="${useDrawings() ? "" : "on"}"${S.meta.glyph_font ? "" : " disabled"}>Police du jeu</button><button data-glyphs="own" class="${useDrawings() ? "on" : ""}">Dessins</button></div></div></div>
        <div class="addr" style="margin-top:12px">${glyphCells("0123456789ABCDEF", 26, true)}</div></div>
      <div class="s-sec" id="sec-donnees"><h2>Données</h2>
        <div class="s-row"><div><div class="t">Ta base</div><div class="h">${num(S.meta.totals.planets)} planètes dans ${num(S.meta.regions.length)} régions, sur ce PC.</div></div><div class="ctl"></div></div></div>
      <div class="s-sec" id="sec-apropos"><h2>À propos</h2>
        <div class="s-row"><div><div class="t">Planet Scanner</div><div class="h">Trouve ta planète parfaite dans No Man's Sky. Gratuit, pour usage personnel.
          Les glyphes de la police du jeu restent la propriété de Hello Games.</div></div><div class="ctl"></div></div></div>
    </section></div>`;
  const sm = $("smain");
  sm.onscroll = () => {
    const secs = nav.map(([k]) => [k, $(`sec-${k}`)]).filter(([, el]) => el);
    const top = sm.getBoundingClientRect().top + 60;
    let current = secs[0][0];
    for (const [k, el] of secs) if (el.getBoundingClientRect().top <= top) current = k;
    if (current !== SET.section) { SET.section = current; document.querySelectorAll("#snav a").forEach((a) => a.classList.toggle("on", a.dataset.sec === current)); }
  };
  if (SET.section !== nav[0][0]) $(`sec-${SET.section}`)?.scrollIntoView();
  $("setAlpha").oninput = (e) => { $("alphaVal").textContent = `${e.target.value} %`; document.querySelector(".ovc").style.opacity = e.target.value / 100; };
  $("setAlpha").onchange = (e) => overlaySet({ alpha: e.target.value / 100 });
}
async function overlaySet(changes) {
  try { SET.overlay = await api("/api/overlay", changes); } catch (e) { return toast(e.message, "bad"); }
  renderSettings();
}
async function reglageSet(changes, msg) {
  try { S.settings = await api("/api/settings", changes); if (msg) toast(msg(S.settings)); } catch (err) { toast(err.message, "bad"); }
  renderSettings();
}
async function settingsClick(e) {
  const t = e.target;
  const sec = t.closest("[data-sec]");
  if (sec) { e.preventDefault(); SET.section = sec.dataset.sec; $(`sec-${sec.dataset.sec}`).scrollIntoView({ behavior: "smooth" }); return; }
  if (t.closest("#setPurple")) {
    await reglageSet({ purple_access: !S.settings.purple_access }, (s) => (s.purple_access ? "Les systèmes violets sont inclus" : "Systèmes violets exclus : le portail ne peut pas y aller"));
    return loadTrip();
  }
  if (t.closest("#setHide")) { S.hideVisited = !S.hideVisited; store.set("hideVisited", S.hideVisited); return renderSettings(); }
  const g = t.closest("[data-glyphs]");
  if (g && !g.disabled) return reglageSet({ own_glyphs: g.dataset.glyphs === "own" }, () => "Glyphes changés (l'overlay suivra à son prochain lancement)");
  const scale = t.closest("[data-scale]");
  if (scale) return overlaySet({ scale: Math.max(0, Math.min(4, (SET.overlay || { scale: 1 }).scale + +scale.dataset.scale)) });
  const band = t.closest("[data-band]");
  if (band) return overlaySet({ band: band.dataset.band });
  if (t.closest("#ovReset")) return overlaySet({ reset_position: true });
}
