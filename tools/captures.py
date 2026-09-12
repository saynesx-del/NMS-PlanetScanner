"""Photographie l'app publique, telle qu'un joueur la voit, pour illustrer le depot et la page du mod.

Ouvre l'app dans un navigateur pilote (Playwright, dans .venv-build : rien n'est touche a l'ecran), la met
dans un etat interessant, et enregistre chaque espace. Les images vont dans docs/images/.

Usage : .venv-build\\Scripts\\python.exe tools\\captures.py [--port 8790] [--out public/images]
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LARGEUR, HAUTEUR = 1440, 900

# Les souhaits montres a l'ouverture : une planete agreable a vivre, qui donne des resultats partout.
SOUHAITS = [{"key": "biome", "value": "Lush"}, {"key": "has_water", "value": True},
            {"key": "sentinels", "value": "Low"}, {"key": "storms", "value": "None"},
            {"key": "fauna", "value": "Full"}]


def api(port, chemin, corps=None):
    d = json.dumps(corps).encode() if corps is not None else None
    r = urllib.request.Request(f"http://127.0.0.1:{port}{chemin}", data=d,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)


def preparer(port):
    """Une destination en cours, quelques favoris et quelques visites : l'app a l'air vivante."""
    res = api(port, "/api/search", {"criteria": SOUHAITS, "limit": 8})
    planetes = res["results"]
    if not planetes:
        raise SystemExit("aucun resultat : le serveur a-t-il des donnees ?")
    for p in planetes[:3]:
        api(port, "/api/favorite", {"planet_id": p["id"], "on": True})
    for p in planetes[3:6]:
        api(port, "/api/visit", {"planet_id": p["id"], "on": True})
    for p in planetes[:4]:
        api(port, "/api/trip", {"action": "add", "planet_id": p["id"]})
    api(port, "/api/trip", {"action": "current", "planet_id": planetes[0]["id"]})
    print(f"  {res['total']} resultats, {res['perfect']} parfaites | destination : {planetes[0]['name']}")
    return planetes[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="8790")
    ap.add_argument("--out", default=str(ROOT / "docs" / "images"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from playwright.sync_api import sync_playwright

    sortie = Path(args.out)
    sortie.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{args.port}"
    print("--- preparation de l'app")
    preparer(args.port)

    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(viewport={"width": LARGEUR, "height": HAUTEUR}, device_scale_factor=2,
                            locale="fr-FR")
        page.goto(base, wait_until="networkidle")
        # les souhaits sont gardes par le navigateur : on les pose, puis on recharge pour qu'ils s'appliquent
        page.evaluate("(w) => localStorage.setItem('ps.wishes', JSON.stringify(w))", SOUHAITS)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2000)

        def photo(nom, hash_, avant=None):
            page.evaluate("(h) => { location.hash = h; }", hash_)  # l'app change d'espace sans recharger
            page.wait_for_timeout(1800)
            if avant:
                avant()
                page.wait_for_timeout(900)
            chemin = sortie / f"{nom}.png"
            page.screenshot(path=str(chemin))
            print(f"  {chemin.name} ({chemin.stat().st_size / 1024:.0f} Ko)")

        print("--- captures")
        photo("01-explorer", "/explorer")
        photo("02-fiche-planete", "/explorer", avant=lambda: page.locator(".pc").first.click())
        photo("03-itineraire", "/itineraire")
        photo("04-journal", "/journal")
        photo("05-galaxie", "/galaxie")
        photo("06-reglages", "/reglages")
        nav.close()
    print(f"\n{len(list(sortie.glob('*.png')))} images dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
