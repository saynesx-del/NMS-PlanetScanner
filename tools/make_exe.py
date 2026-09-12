"""Fait de Planet Scanner un executable autonome : le joueur n'installe rien, ni Python ni dependance.

Produit dist/Planet Scanner/ : "Planet Scanner.exe", ses bibliotheques dans _internal, le README et le dossier
ou deposer les packs, puis l'archive a distribuer. PyInstaller vit dans .venv-build, a part de l'app.

Usage : .venv-build\\Scripts\\python.exe tools\\make_exe.py [--out DOSSIER]
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_PY = ROOT / ".venv-build" / "Scripts" / "python.exe"
NOM = "Planet Scanner"


def octets(chemin):
    return sum(f.stat().st_size for f in Path(chemin).rglob("*") if f.is_file())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    args = ap.parse_args()
    if not BUILD_PY.exists():
        raise SystemExit("Environnement de compilation absent : python -m venv .venv-build puis "
                         ".venv-build\\Scripts\\pip install pyinstaller pywebview")

    travail = Path(args.out)
    chantier = travail / "chantier"
    if chantier.exists():
        shutil.rmtree(chantier)
    chantier.mkdir(parents=True, exist_ok=True)
    # PyInstaller veut un point d'entree sans espace ni extension .pyw : une copie du lanceur, hors du depot.
    lanceur = chantier / "lanceur.py"
    shutil.copy2(ROOT / f"{NOM}.pyw", lanceur)

    print("--- compilation (quelques minutes la premiere fois)")
    t0 = time.time()
    cmd = [
        str(BUILD_PY), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", NOM,
        "--icon", str(ROOT / "app" / "static" / "icon.ico"),
        "--paths", str(ROOT / "app"), "--paths", str(ROOT / "overlay"),
        "--add-data", f"{ROOT / 'app' / 'static'}{';'}static",
        "--distpath", str(chantier / "dist"), "--workpath", str(chantier / "work"),
        "--specpath", str(chantier),
        "--exclude-module", "unittest", "--exclude-module", "pydoc",
        "--exclude-module", "pdb", "--exclude-module", "doctest",
    ]
    for module in ("server", "db", "index", "packs", "vocabulaire", "overlay"):
        cmd += ["--hidden-import", module]
    cmd.append(str(lanceur))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-4000:])
        print(r.stderr[-4000:])
        raise SystemExit("la compilation a echoue")
    print(f"    compile en {time.time() - t0:.0f} s")

    # Le dossier a distribuer : l'app, le README, et l'endroit ou deposer les packs
    final = travail / NOM
    if final.exists():
        shutil.rmtree(final)
    shutil.move(str(chantier / "dist" / NOM), str(final))
    for nom in ("README.md", "LICENSE", "LICENSE-DONNEES.md"):
        if (ROOT / nom).exists():
            shutil.copy2(ROOT / nom, final / nom)
    # Les captures illustrent la page du depot, pas l'archive : le README livre les laisse de cote plutot
    # que de montrer des images absentes.
    lisezmoi = final / "README.md"
    lisezmoi.write_text(re.sub(r"<!-- captures -->.*?<!-- /captures -->\n", "",
                               lisezmoi.read_text(encoding="utf-8"), flags=re.S), encoding="utf-8")
    (final / "data" / "packs").mkdir(parents=True, exist_ok=True)
    (final / "data" / "packs" / "LISEZ-MOI.txt").write_text(
        "Depose ici les packs de donnees (.zip), puis installe-les depuis Galaxie dans l'app.\n",
        encoding="utf-8")
    shutil.rmtree(chantier, ignore_errors=True)

    # L'archive, faite tout de suite : rien de ce que l'app cree en tournant n'y entre
    archive = Path(shutil.make_archive(str(travail / NOM.replace(" ", "-")), "zip", root_dir=travail,
                                       base_dir=NOM))
    exe = final / f"{NOM}.exe"
    print(f"\n{exe}")
    print(f"    executable {exe.stat().st_size / 1e6:.1f} Mo | dossier complet {octets(final) / 1e6:.0f} Mo")
    print(f"    {sum(1 for f in final.rglob('*') if f.is_file())} fichiers")
    print(f"    a distribuer : {archive.name} ({archive.stat().st_size / 1e6:.0f} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
