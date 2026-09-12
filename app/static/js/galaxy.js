"use strict";
/* Galaxie : les packs de donnees installes, la carte de tes zones (la galaxie vue de dessus, puis ta zone
   region par region) et la liste de toutes tes regions. */

const GX = { perRegion: null, glyphs: "", filter: "", shown: 50, visited: null };
const regionXYZ = (region) => ({ x: parseInt(region.slice(5, 8), 16), z: parseInt(region.slice(2, 5), 16), y: parseInt(region.slice(0, 2), 16) });

async function renderGalaxy() {
  $("view").innerHTML = `<div class="gal"><aside class="g-side scroller" id="gside"></aside><section class="g-main scroller" id="gmain"></section></div>`;
  renderSidePanel();
  renderGalaxyMain();
  try {
    const [res, j] = await Promise.all([
      S.criteria.length ? api("/api/search", { criteria: S.criteria.map((c) => ({ ...c, required: false })), limit: 0, per_region: true }) : null,
      api("/api/journal")]);
    GX.perRegion = res && res.per_region;
    GX.visited = j.visited.length;
  } catch { /* la carte s'affiche sans */ }
  if ($("gmain")) renderGalaxyMain();
}
// Le panneau de gauche de Galaxie.
function renderSidePanel() {
  const box = $("gside");
  if (box) renderPackTiles(box);
}

// La region mise en avant sur la carte, et ce qu'on en dit.
function regionEnAvant() {
  const r = [...S.meta.regions].sort((a, b) => (b.added_at || "").localeCompare(a.added_at || ""))[0];
  return r ? { id: r.id, libelle: "Dernière ajoutée" } : null;
}

function renderGalaxyMain() {
  const box = $("gmain");
  if (!box) return;
  const regions = S.meta.regions;
  const avant = regionEnAvant() || {};
  const here = regions.some((r) => r.id === avant.id) ? avant.id : null;
  const recent = [...regions].sort((a, b) => (b.added_at || "").localeCompare(a.added_at || ""));
  const centerId = here || (recent[0] || {}).id;
  const center = regions.find((r) => r.id === centerId);
  const galaxies = new Set(regions.map((r) => r.galaxy_name));
  const per = GX.perRegion || {};
  let maps = "";
  if (center) {
    const gal = center.id.split("_")[0], inGal = regions.filter((r) => r.id.startsWith(gal + "_")).map((r) => ({ ...r, ...regionXYZ(r.region) }));
    const zones = [];
    for (const r of inGal) {
      const z = zones.find((q) => Math.abs(q.x - r.x) < 64 && Math.abs(q.z - r.z) < 64);
      if (z) { z.n++; z.gold ||= !!per[r.id]; } else zones.push({ x: r.x, z: r.z, n: 1, gold: !!per[r.id] });
    }
    const c = regionXYZ(center.region), G = 250, gx = (v) => 12 + v / 4096 * (G - 24);
    const disc = `<svg width="${G}" height="${G}" viewBox="0 0 ${G} ${G}" role="img" aria-label="Tes zones dans la galaxie">
      <circle cx="${G / 2}" cy="${G / 2}" r="${G / 2 - 10}" fill="#0A0D12" stroke="#222932"/><circle cx="${G / 2}" cy="${G / 2}" r="${G / 5}" fill="none" stroke="#1B2129"/>
      <circle cx="${G / 2}" cy="${G / 2}" r="4" fill="#EEF1F4" opacity=".7"/>
      ${zones.map((z) => `<circle cx="${gx(z.x)}" cy="${gx(z.z)}" r="${3 + Math.sqrt(z.n) * 1.1}" fill="${z.gold ? "#EBC733" : "#3FB9B3"}" fill-opacity=".85"><title>${z.n} région${z.n > 1 ? "s" : ""}</title></circle>`).join("")}
      <circle cx="${gx(c.x)}" cy="${gx(c.z)}" r="13" fill="none" stroke="#EEF1F4" stroke-width="1.2"/></svg>`;
    const N = 13, C = 26, half = (N - 1) / 2, cols = new Map();
    for (const r of inGal) {
      const dx = r.x - c.x, dz = r.z - c.z;
      if (Math.abs(dx) > half || Math.abs(dz) > half) continue;
      const k = `${dx},${dz}`, o = cols.get(k) || { n: 0, perfect: 0, near: false, best: null };
      o.n++; o.perfect += per[r.id] || 0;
      if (Math.abs(r.y - c.y) <= 1) o.near = true;
      if (!o.best || (per[r.id] || 0) > (per[o.best.id] || 0) || r.y === c.y) o.best = r;
      cols.set(k, o);
    }
    let cells = "";
    for (let i = -half; i <= half; i++) for (let j = -half; j <= half; j++) {
      const o = cols.get(`${i},${j}`), X = (i + half) * C, Y = (j + half) * C;
      const adj = Math.abs(i) <= 1 && Math.abs(j) <= 1 && (i || j);
      const fill = o ? (o.perfect ? "#EBC733" : "#3FB9B3") : "#0D1015";
      const tip = o ? `${o.n} région${o.n > 1 ? "s" : ""} ici${o.perfect ? ` · ${o.perfect} parfaite${o.perfect > 1 ? "s" : ""}` : ""} · clic : chercher ici` : "Inconnue";
      cells += `<rect class="${o ? "cell" : ""}" data-region="${o ? o.best.id : ""}" x="${X + 1}" y="${Y + 1}" width="${C - 2}" height="${C - 2}" fill="${fill}"
        fill-opacity="${o ? Math.min(1, .35 + o.n * .2) : 1}" stroke="${adj && !(o && o.near) ? "#3FB9B3" : "#1A2029"}" stroke-dasharray="${adj && !(o && o.near) ? "3 2" : "0"}"><title>${tip}</title></rect>`;
    }
    const zoneCount = [...cols.values()].reduce((a, o) => a + o.n, 0);
    const grid = `<svg width="${N * C}" height="${N * C}" viewBox="0 0 ${N * C} ${N * C}" role="img" aria-label="Ta zone vue de dessus">${cells}
      <rect x="${half * C + 1}" y="${half * C + 1}" width="${C - 2}" height="${C - 2}" fill="none" stroke="#EEF1F4" stroke-width="2" pointer-events="none"/>
      <g transform="translate(${half * C + C / 2},${half * C + C / 2}) rotate(45)" pointer-events="none"><rect x="-4" y="-4" width="8" height="8" fill="#EEF1F4"/></g></svg>`;
    maps = `<div class="maps">
      <div class="mapbox"><div class="hd">${esc(center.galaxy_name)} · tes ${zones.length} zone${zones.length > 1 ? "s" : ""}</div>${disc}
        <div class="legend"><span><i style="background:#3FB9B3"></i>Connue</span>${S.criteria.length ? `<span><i style="background:#EBC733"></i>Parfaites pour ta recherche</span>` : ""}<span><i style="border:1px solid #EEF1F4"></i>${esc(avant.libelle || "")}</span></div></div>
      <div class="mapbox"><div class="hd">Ta zone · vue de dessus<span class="sp"></span><span class="meta">${zoneCount} région${zoneCount > 1 ? "s" : ""} ici</span></div>
        <div style="display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap">${grid}<div class="legend" style="flex-direction:column;gap:9px;margin-top:10px;font-size:12px">
          <span><i style="background:#3FB9B3"></i>Connue (plus clair : plusieurs étages)</span>${S.criteria.length ? `<span><i style="background:#EBC733"></i>Contient une planète parfaite</span>` : ""}
          <span><i style="border:1px dashed #3FB9B3"></i>Voisine inconnue</span><span><i style="background:#EEF1F4;transform:rotate(45deg);width:8px;height:8px"></i>${esc(avant.libelle || "")}</span>
          <span style="margin-top:6px;color:var(--ink-2)">Clic sur une case : chercher dans cette région.</span></div></div></div></div>`;
  }
  const q = norm(GX.filter);
  const rows = recent.filter((r) => !q || norm(`${r.region} ${r.galaxy_name}`).includes(q));
  box.innerHTML = `<div class="pagehead"><div><div class="eyebrow teal">Ta cartographie</div><h1>Galaxie</h1></div><span class="sp"></span>
      <div class="stats"><div><b>${num(regions.length)}</b><span>Régions</span></div><div><b>${num(S.meta.totals.planets)}</b><span>Planètes</span></div>
        <div><b>${galaxies.size}</b><span>Galaxie${galaxies.size > 1 ? "s" : ""}</span></div>${GX.visited != null ? `<div><b>${GX.visited}</b><span>Visitées</span></div>` : ""}</div></div>
    ${maps}
    <div class="h5">Régions<span class="sp"></span><div class="m-input" style="width:240px;padding:0 10px">${icon("search", 14)}<input id="gfilter" placeholder="Filtrer : 0799, Euclid…" value="${esc(GX.filter)}" aria-label="Filtrer les régions" style="padding:6px 0;font-size:12.5px"></div></div>
    <div class="tablewrap"><table class="rows"><thead><tr><th>Région</th><th>Galaxie</th><th>Systèmes</th><th>Planètes</th>${S.criteria.length ? "<th>Parfaites</th>" : ""}<th>Ajoutée</th><th></th></tr></thead>
      <tbody>${rows.slice(0, GX.shown).map((r) => `<tr class="${r.id === here ? "here" : ""}"><td class="mono">${r.region}${r.id === here ? " ◆" : ""}</td><td>${esc(r.galaxy_name)}</td>
        <td>${num(r.systems)}</td><td>${num(r.planets)}</td>${S.criteria.length ? `<td class="${per[r.id] ? "gold" : ""}">${per[r.id] || "—"}</td>` : ""}<td>${esc(dateFr(r.added_at))}</td>
        <td><button class="b sm" data-search-region="${r.id}">Chercher ici</button></td></tr>`).join("")}</tbody></table></div>
    ${rows.length > GX.shown ? `<button class="b more" id="gmore">Afficher plus (${num(rows.length - GX.shown)})</button>` : ""}`;
  $("gfilter").oninput = (e) => { GX.filter = e.target.value; GX.shown = 50; const pos = e.target.selectionStart; renderGalaxyMain(); const f = $("gfilter"); f.focus(); f.setSelectionRange(pos, pos); };
}
// --- Packs de donnees : des regions toutes pretes, a installer une fois ---------------------------------
const PK = { envoi: null, attendue: false };
const mo = (o) => (o >= 1e9 ? `${(o / 1e9).toFixed(2)} Go` : `${Math.round(o / 1e6)} Mo`);

async function loadPacks() {
  try { S.packs = await api("/api/packs"); } catch { S.packs = S.packs || { disponibles: [], etat: {} }; }
}
function packTile(k) {
  if (k.erreur) return `<div class="stile"><div class="hd">${icon("data")}${esc(k.fichier)}</div><p class="err">${esc(k.erreur)}</p>
    <button class="b ghost sm" data-pack-delete="${esc(k.fichier)}">Retirer le fichier</button></div>`;
  const fini = k.installees >= k.regions;
  return `<div class="stile"><div class="hd">${icon("data")}${esc(k.fichier)}</div>
    <p>${num(k.planetes)} planètes · ${num(k.regions)} régions · ${mo(k.octets)}<br>
      <span class="meta">Jeu ${esc(k.version_jeu || "?")} · pack du ${esc(k.cree_le || "?")}</span></p>
    ${fini ? `<span class="tag ok">✓ Installé</span>` : k.installees ? `<p class="hint">${num(k.installees)} région${k.installees > 1 ? "s" : ""} déjà installée${k.installees > 1 ? "s" : ""}.</p>` : ""}
    <div class="row" style="margin-top:10px"><button class="b ${fini ? "" : "teal"} sm" data-pack-install="${esc(k.fichier)}">${fini ? "Réinstaller" : "Installer"}</button>
      <button class="b ghost sm" data-pack-delete="${esc(k.fichier)}" style="margin-left:auto" title="Efface le fichier .zip ; les régions déjà installées restent">Retirer le fichier</button></div></div>`;
}
// Les clics du panneau de gauche.
async function panneauClick(e) {
  const t = e.target;
  if (t.closest("#packPick")) { $("packFile").click(); return true; }
  const inst = t.closest("[data-pack-install]");
  if (inst) {
    try { S.packs = await api("/api/packs", { action: "installer", fichier: inst.dataset.packInstall }); }
    catch (err) { toast(err.message, "bad"); return true; }
    renderSidePanel();
    packPoll();
    return true;
  }
  const del = t.closest("[data-pack-delete]");
  if (del) {
    try { S.packs = await api("/api/packs", { action: "supprimer", fichier: del.dataset.packDelete }); }
    catch (err) { toast(err.message, "bad"); return true; }
    toast("Fichier retiré. Les régions déjà installées restent.", "teal", 5000);
    renderSidePanel();
    return true;
  }
  return false;
}

function renderPackTiles(box) {
  if (S.packs === undefined) {  // premier affichage : on demande la liste, puis on se redessine
    S.packs = null;
    loadPacks().then(() => { renderSidePanel(); packPoll(); });
  }
  const p = S.packs || {}, e = p.etat || {}, liste = p.disponibles || [];
  const pct = e.total ? Math.round(100 * e.fait / e.total) : 0;
  box.innerHTML = `<div class="h5" style="margin-top:0">Packs de données</div>
    <div class="stile drop" id="packDrop"><div class="hd">${icon("plus")}Ajouter un pack</div>
      <p>Un pack rassemble des régions déjà explorées, avec leurs planètes, leurs couleurs et leurs ressources. Dépose le fichier <b>.zip</b> ici, ou choisis-le.</p>
      <input type="file" id="packFile" accept=".zip" hidden>
      ${PK.envoi != null ? `<div class="pbar"><i style="width:${PK.envoi}%"></i></div><p style="margin:8px 0 0">Copie du pack · ${PK.envoi} %</p>`
      : `<button class="b teal sm" id="packPick">Choisir un pack</button>`}</div>
    ${e.running ? `<div class="stile"><div class="hd">${icon("radar")}Installation</div><p>${esc(e.fichier || "")} · région ${num(e.fait)} sur ${num(e.total)}</p>
        <div class="pbar"><i style="width:${pct}%"></i></div><p class="hint" style="margin:8px 0 0">Quelques minutes. Tu peux chercher pendant ce temps.</p></div>` : ""}
    ${e.erreur ? `<div class="stile"><div class="hd">${icon("info")}Échec</div><p class="err">${esc(e.erreur)}</p></div>` : ""}
    ${liste.map(packTile).join("")}
    ${liste.length ? "" : `<p class="hint">Aucun pack ici pour l'instant. Chaque pack couvre une partie de la galaxie : télécharge celui de la zone qui t'intéresse, puis dépose-le ci-dessus.</p>`}`;
  const input = $("packFile");
  if (input) input.onchange = (ev) => { const f = ev.target.files[0]; if (f) uploadPack(f); };
  const zone = $("packDrop");
  if (zone) {
    zone.ondragover = (ev) => { ev.preventDefault(); zone.classList.add("over"); };
    zone.ondragleave = () => zone.classList.remove("over");
    zone.ondrop = (ev) => { ev.preventDefault(); zone.classList.remove("over"); const f = ev.dataTransfer.files[0]; if (f) uploadPack(f); };
  }
}
function uploadPack(file) {
  if (!/\.zip$/i.test(file.name)) return toast("Un pack est un fichier .zip", "bad");
  PK.envoi = 0;
  renderSidePanel();
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/packs/upload?nom=${encodeURIComponent(file.name)}`);
  xhr.upload.onprogress = (ev) => { if (ev.lengthComputable) { PK.envoi = Math.round(100 * ev.loaded / ev.total); renderSidePanel(); } };
  xhr.onload = async () => {
    PK.envoi = null;
    if (xhr.status >= 400) { toast((JSON.parse(xhr.responseText || "{}").error) || "Pack refusé", "bad"); return renderSidePanel(); }
    await loadPacks();
    renderSidePanel();
    toast(`${file.name} prêt : clique sur Installer`, "teal", 5000);
  };
  xhr.onerror = () => { PK.envoi = null; toast("Copie interrompue", "bad"); renderSidePanel(); };
  xhr.send(file);
}
async function packPoll() {
  if (!$("gside")) return;
  await loadPacks();
  const e = (S.packs || {}).etat || {};
  renderSidePanel();
  if (e.running) { PK.attendue = true; return void setTimeout(packPoll, 1000); }
  if (PK.attendue) {
    PK.attendue = false;
    if (e.erreur) toast(e.erreur, "bad", 6000);
    else toast(`${num(e.installees)} région${e.installees > 1 ? "s" : ""} installée${e.installees > 1 ? "s" : ""}`, "teal", 5000);
    await reloadMeta();
  }
}
async function galaxyClick(e) {
  const t = e.target;
  if (await panneauClick(e)) return;
  if (t.closest("#gmore")) { GX.shown += 100; return renderGalaxyMain(); }
  const reg = t.closest("[data-search-region],[data-region]");
  const id = reg && (reg.dataset.searchRegion || reg.dataset.region);
  if (id) { S.region = id; store.set("region", id); location.hash = "#/explorer"; toast(`Recherche dans la région ${id.split("_")[1]}`); }
}
