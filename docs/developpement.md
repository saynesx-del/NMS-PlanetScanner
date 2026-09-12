# Travailler sur Planet Scanner

Ce dépôt est l'application complète : elle lit des packs de données et n'a besoin de rien d'autre.

## Lancer l'app depuis le code

```
python -m venv .venv
.venv\Scripts\pip install pywebview
.venv\Scripts\pythonw.exe "Planet Scanner.pyw"
```

L'app ouvre sa fenêtre, sert la page sur `127.0.0.1` et garde tout dans `data/`. Pour la voir dans un
navigateur pendant qu'on la modifie : `.venv\Scripts\python.exe app\server.py`.

Deux copies posées dans deux dossiers sont deux apps différentes : chacune retient son port dans
`data/port.txt`, garde son verrou et sa carte. Elles ne se prennent pas l'une pour l'autre.

## Ce qu'il y a dans le code

- `Planet Scanner.pyw` — le lanceur : la fenêtre, le serveur local et la carte posée par-dessus le jeu.
- `app/server.py` — le serveur (127.0.0.1 uniquement, aucun appel sortant) et ses routes.
- `app/db.py` — la base SQLite, la recherche par planète et la recherche par système.
- `app/index.py` — l'index en mémoire : un octet par critère et par planète, pour classer plus d'un million
  de planètes en quelques millisecondes.
- `app/packs.py` — l'installation d'un pack ; `app/vocabulaire.py` — les mots publics des packs.
- `app/static/` — l'interface ; `overlay/overlay.py` — la carte par-dessus le jeu (tkinter, à la souris).

## Compiler l'exécutable

```
python -m venv .venv-build
.venv-build\Scripts\pip install pyinstaller pywebview
.venv-build\Scripts\python.exe tools\make_exe.py
```

Produit `dist/Planet Scanner/` et l'archive `dist/Planet-Scanner.zip`. PyInstaller vit dans son
environnement à lui, pour ne pas peser sur celui de l'app.

## Publier une version

```
.venv-build\gh\bin\gh.exe auth login          (une fois)
.venv-build\Scripts\python.exe tools\publier_release.py --tag v1.1 --essai
```

`--essai` montre les notes sans rien envoyer. Les chiffres annoncés sont lus dans les manifestes des packs,
jamais recopiés à la main. `--packs DOSSIER` va chercher les packs ailleurs, `--packs-de TAG` les laisse sur
une version précédente quand ils n'ont pas changé, et `--change "…"` écrit ce que la version corrige.

## Refaire les captures du README

Avec l'app lancée et des packs installés :

```
.venv-build\Scripts\pip install playwright && .venv-build\Scripts\playwright install chromium
.venv-build\Scripts\python.exe tools\captures.py --port 8765
```

Les six images vont dans `docs/images/`, celles que montre le README.
