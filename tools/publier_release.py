"""Publie une version sur GitHub : l'app compilee et les packs de donnees, avec des notes ecrites a partir
des manifestes (les chiffres annonces sont ceux des fichiers envoyes, jamais recopies a la main).

Demande d'etre connecte une fois : .venv-build\\gh\\bin\\gh.exe auth login
Usage : .venv-build\\Scripts\\python.exe tools\\publier_release.py [--tag v1.0] [--essai]
"""

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GH = ROOT / ".venv-build" / "gh" / "bin" / "gh.exe"
DEPOT = "saynesx-del/NMS-PlanetScanner"
PACKS_PAR_DEFAUT = ROOT / "data" / "packs"  # ou tu poses les packs ; --packs pour aller les chercher ailleurs


def nb(n):
    return f"{n:,}".replace(",", " ")  # 1 315 118, a la francaise


def mo(chemin):
    return f"{Path(chemin).stat().st_size / 1e6:.0f} Mo"


def manifeste(chemin):
    with zipfile.ZipFile(chemin) as z:
        return json.loads(z.read("manifeste.json"))


def notes(app_zip, packs, change=None, packs_de=None):
    total_p = sum(m["planetes"] for _c, m in packs)
    total_r = sum(len(m["regions"]) for _c, m in packs)
    jeu = packs[0][1]["version_jeu"] if packs else "?"
    lignes = [
        "Trouve ta planète parfaite dans No Man's Sky sans la chercher à l'aveugle : tu décris ce que tu veux",
        "(biome, couleurs, sentinelles, tempêtes, faune, ressources), l'app te donne l'adresse du portail des",
        "meilleures et te guide de l'une à l'autre, avec une carte posée par-dessus le jeu.",
        "",
    ]
    if change:  # une version qui corrige quelque chose le dit avant de dire quoi telecharger
        lignes += ["## Ce qui change", "", change, ""]
    lignes += [
        "## Ce qu'il faut télécharger",
        "",
        f"1. **`{Path(app_zip).name}`** ({mo(app_zip)}) — l'application. Décompresse, double-clique sur",
        "   `Planet Scanner.exe`. Rien à installer : ni Python, ni dépendance.",
        f"2. **Au moins un pack de données** — les planètes." + (
            f" Ils n'ont pas changé : prends-les sur la [{packs_de}]"
            f"(https://github.com/{DEPOT}/releases/tag/{packs_de})." if packs_de else ""),
        "   Dépose le `.zip` dans **Galaxie → Ajouter un pack**, puis clique sur **Installer**",
        "   (environ une minute et demie pour 260 Mo).",
        "",
        "| Pack | Régions | Planètes | Taille |",
        "|---|---|---|---|",
    ]
    for chemin, m in packs:
        lignes.append(f"| `{Path(chemin).name}` | {len(m['regions'])} | {nb(m['planetes'])} | {mo(chemin)} |")
    lignes += [
        "",
        f"Les {'deux' if len(packs) == 2 else len(packs)} packs ensemble : **{total_r} régions, {nb(total_p)} planètes**."
        if len(packs) > 1 else f"Le pack : **{total_r} régions, {nb(total_p)} planètes**.",
        "",
        "## À savoir",
        "",
        f"- Ces données valent pour la **version {jeu}** du jeu. Le générateur de No Man's Sky peut changer d'une",
        "  mise à jour à l'autre ; un pack fait pour une autre version ne correspondrait plus à ce que tu verrais.",
        "- Les **systèmes violets** ne sont pas inclus : le portail refuse d'y aller tant qu'ils ne sont pas",
        "  débloqués en jeu.",
        "- La **ressource rare** d'une planète n'est pas connue ; les packs donnent la commune et la peu commune.",
        "- Windows 10 ou 11. La fenêtre utilise WebView2, présent d'origine sur Windows 11 et installé avec Edge",
        "  sur Windows 10.",
        "- Tout reste sur ton PC : l'app n'écoute que sur 127.0.0.1 et n'appelle aucun service.",
        "",
        "## Licences",
        "",
        "Le code est sous **MIT**. Les packs de données sont sous **CC BY 4.0** : sers-t'en comme tu veux, cite",
        "la source. No Man's Sky est une marque de Hello Games ; ce projet n'est pas affilié à Hello Games.",
    ]
    return "\n".join(lignes)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1.0")
    ap.add_argument("--titre", default=None)
    ap.add_argument("--app", default=None, help="l'archive de l'app (par defaut : dist/Planet-Scanner.zip)")
    ap.add_argument("--packs", default=None, metavar="DOSSIER", help="ou sont les packs (par defaut : data/packs)")
    ap.add_argument("--change", default=None, help="ce que cette version corrige, en une phrase")
    ap.add_argument("--packs-de", default=None, metavar="TAG",
                    help="ne pas renvoyer les packs : ils restent sur cette version-la (ex. v1.0.1)")
    ap.add_argument("--essai", action="store_true", help="montrer les notes sans rien publier")
    args = ap.parse_args()

    app_zip = Path(args.app) if args.app else ROOT / "dist" / "Planet-Scanner.zip"
    if not app_zip.exists():
        raise SystemExit(f"archive de l'app introuvable : {app_zip} (lance tools/make_exe.py)")
    dossier_packs = Path(args.packs) if args.packs else PACKS_PAR_DEFAUT
    packs = [(c, manifeste(c)) for c in sorted(dossier_packs.glob("planet-scanner-pack-*.zip"))]
    if not packs:
        raise SystemExit(f"aucun pack dans {dossier_packs}")
    corps = notes(app_zip, packs, args.change, args.packs_de)
    titre = args.titre or f"Planet Scanner {args.tag}"

    # Les packs ne repartent pas quand ils n'ont pas change : ils restent sur la version qui les porte.
    envoi = [app_zip] + ([] if args.packs_de else [c for c, _m in packs])
    if args.essai:
        print(corps)
        print(f"\n--- {len(envoi)} fichiers a envoyer ---")
        for c in envoi:
            print(f"  {Path(c).name} ({mo(c)})")
        return 0

    etat = subprocess.run([str(GH), "auth", "status"], capture_output=True, text=True)
    if etat.returncode:
        raise SystemExit(f"{GH} auth login  <- a faire une fois, dans une console")

    fichier_notes = ROOT / "dist" / "notes-release.md"
    fichier_notes.parent.mkdir(parents=True, exist_ok=True)
    fichier_notes.write_text(corps, encoding="utf-8")
    cmd = [str(GH), "release", "create", args.tag, "--repo", DEPOT, "--title", titre,
           "--notes-file", str(fichier_notes)] + [str(c) for c in envoi]
    print("--- envoi (les packs font quelques centaines de Mo, compte plusieurs minutes)")
    r = subprocess.run(cmd, text=True)
    if r.returncode:
        raise SystemExit("la publication a echoue")
    print(f"\npublie : https://github.com/{DEPOT}/releases/tag/{args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
