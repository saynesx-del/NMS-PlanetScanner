"use strict";
/* Journal: favourites, planets visited and notes, as souvenirs (big portrait, the game's description, the date,
   the note written on the card). */

const J = { data: null, tab: store.get("journalTab", "favorites"), q: "" };
async function renderJournal() {
  try { J.data = await api("/api/journal"); } catch (e) { $("view").innerHTML = `<div class="journal"><div class="empty">${esc(e.message)}</div></div>`; return; }
  $("view").innerHTML = `<div class="journal scroller" id="journal">
    <div class="pagehead"><div><div class="eyebrow">Carnet de bord</div><h1>Journal</h1><p>Tes favoris, les planètes où tu es allé et tes notes.</p></div>
      <span class="sp"></span><div class="m-input" style="width:280px">${icon("search", 16)}<input id="jq" placeholder="Chercher dans le journal" aria-label="Chercher dans le journal" value="${esc(J.q)}"></div></div>
    <div class="tabs2" role="tablist" id="jtabs"></div><div id="jlist"></div></div>`;
  $("jq").oninput = (e) => { J.q = e.target.value; renderJournalList(); };
  renderJournalList();
}
function renderJournalList() {
  const d = J.data, tabs = [["favorites", "Favoris"], ["visited", "Visitées"], ["notes", "Avec une note"]];
  $("jtabs").innerHTML = tabs.map(([k, l]) => `<button role="tab" class="${J.tab === k ? "on" : ""}" data-tab="${k}" aria-selected="${J.tab === k}">${l}<small>${d[k].length}</small></button>`).join("");
  const q = norm(J.q);
  const list = d[J.tab].filter((p) => !q || norm(`${planetTitle(p)} ${planetKind(p)} ${p.note || ""} ${p.region}`).includes(q));
  const empty = { favorites: "Aucun favori pour l'instant. En jeu, après F9, réponds « oui » (Maj+F9) ; ou clique sur l'étoile d'une planète.",
    visited: "Aucune planète visitée. En jeu, F9 quand tu arrives sur ta destination.", notes: "Aucune note. Ouvre la fiche d'une planète pour en écrire une." }[J.tab];
  $("jlist").innerHTML = !list.length ? `<div class="empty" style="margin-top:18px">${q ? "Rien ne correspond à ta recherche." : empty}</div>`
    : `<div class="jgrid">${list.map((p) => {
      const date = J.tab === "visited" ? `Visitée le ${dateFr(p.visited_at)}` : p.favorite_at ? `Favori depuis le ${dateFr(p.favorite_at)}` : p.visited_at ? `Visitée le ${dateFr(p.visited_at)}` : where(p);
      return `<article class="jc" data-pid="${p.id}">
        <header class="pc-band" style="${bandStyle(p.biome)}"><i class="dia"></i><b>${esc(planetTitle(p))}</b>${p.favorite_at ? `<span style="margin-left:auto">★</span>` : ""}</header>
        <div class="jc-pic" data-open="${esc(p.system_ua)}|${p.idx}">${portrait(p, 112)}</div>
        <div class="jc-t"><div class="d">${esc(planetKind(p))}</div><div class="m">${esc(date)}</div></div>
        ${p.note ? `<div class="note-view" data-edit="${p.id}" title="Modifier la note">${esc(p.note)}</div>` : `<button class="note-add" data-edit="${p.id}">+ Ajouter une note</button>`}
        <footer class="pc-foot"><span class="tags">${p.visited_at && J.tab !== "visited" ? `<span class="tag ok" title="Visitée">✓</span>` : ""}</span>
          <button class="b gold sm" data-go="${p.id}">Y retourner</button><button class="b sm icon" data-open="${esc(p.system_ua)}|${p.idx}" title="Fiche">${icon("eye")}</button>
          <button class="b sm icon${p.favorite_at ? " on" : ""}" data-fav="${p.id}" data-on="${p.favorite_at ? 0 : 1}" title="${p.favorite_at ? "Retirer des favoris" : "Ajouter aux favoris"}">${icon("star")}</button></footer></article>`;
    }).join("")}</div>`;
}
async function journalClick(e) {
  const tab = e.target.closest("[data-tab]");
  if (tab) { J.tab = tab.dataset.tab; store.set("journalTab", J.tab); return renderJournalList(); }
  const edit = e.target.closest("[data-edit]");
  if (edit) {
    const p = Object.values(J.data).flat().find((x) => x.id === edit.dataset.edit);
    const ta = document.createElement("textarea");
    ta.className = "note"; ta.maxLength = 500; ta.value = p.note || ""; ta.placeholder = "« base principale », « œufs rares près du lac »…";
    edit.replaceWith(ta); ta.focus();
    ta.onblur = async () => {
      const v = ta.value.trim();
      if (v !== (p.note || "")) {
        try { await api("/api/note", { planet_id: p.id, note: v }); toast(v ? "Note enregistrée" : "Note effacée"); } catch (err) { toast(err.message, "bad"); }
      }
      renderJournal();
    };
    ta.onkeydown = (k) => { if (k.key === "Enter" && !k.shiftKey) { k.preventDefault(); ta.blur(); } if (k.key === "Escape") { ta.value = p.note || ""; ta.blur(); } };
    return;
  }
  const fav = e.target.closest("[data-fav]");
  if (fav) { await setFavorite(fav.dataset.fav, fav.dataset.on === "1"); return; }
  planetClicks(e);
}
