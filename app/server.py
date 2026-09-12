"""Le serveur local de Planet Scanner : il sert la page, repond aux recherches et garde l'itineraire.

Rien ne sort de la machine : il n'ecoute que sur 127.0.0.1 et n'appelle aucun service.
"""

import json
import mimetypes
import os
import sys
import threading
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import packs  # noqa: E402


def _routes_en_plus(path, corps):
    """Aucune route en plus dans cette app."""
    return None


def _au_demarrage(con):
    """Rien de particulier au demarrage."""


HOST, PORT = "127.0.0.1", int(os.environ.get("PS_PORT", 8765))
STATIC = Path(__file__).resolve().parent / "static"
CON = db.connect()


# L'index de recherche se prepare a part, sur sa propre connexion : la page s'ouvre pendant ce temps.
IMPORTER = {"running": False, "last": None, "error": None}


def _importer():
    con = db.connect()
    db.INDEX.load()  # l'index enregistre au dernier lancement : seules les regions arrivees depuis sont relues
    try:
        IMPORTER["running"] = True
        db.refresh_index(con)
        db.meta(con)  # compte les filtres tout de suite, pour qu'aucune requete ne l'attende
        IMPORTER["last"] = time.time()
        IMPORTER["error"] = None
    except Exception as e:
        IMPORTER["error"] = repr(e)
    finally:
        IMPORTER["running"] = False


def start_importer():
    db._options(CON, allow_stale=True)  # les comptes enregistres au dernier lancement : la page s'affiche aussitot
    threading.Thread(target=_importer, daemon=True).start()
    _au_demarrage(CON)
# --- Packs de donnees : des regions toutes pretes, a installer une fois ---------------------------------

PACKS_DIR = db.DATA_DIR / "packs"
PACK = {"running": False, "fichier": None, "fait": 0, "total": 0, "region": None, "erreur": None,
        "installees": 0, "sautees": 0, "fini_le": None}


def packs_disponibles():
    """Les packs poses dans data/packs, avec ce qu'ils annoncent et ce qui est deja installe."""
    if not PACKS_DIR.exists():
        return []
    empreintes = {r[0]: r[1] for r in CON.execute("SELECT id, file_mtime FROM regions")}
    out = []
    for chemin in sorted(PACKS_DIR.glob("*.zip")):
        try:
            m = packs.lire_manifeste(chemin)
        except (packs.PackInvalide, OSError, zipfile.BadZipFile) as e:
            out.append({"fichier": chemin.name, "octets": chemin.stat().st_size, "erreur": str(e)})
            continue
        empreinte = f"pack:{m['version_jeu']}:{m.get('cree_le')}:{m['format']}"
        regions = m.get("regions", [])
        out.append({"fichier": chemin.name, "octets": chemin.stat().st_size, "regions": len(regions),
                    "systemes": m.get("systemes"), "planetes": m.get("planetes"),
                    "version_jeu": m.get("version_jeu"), "cree_le": m.get("cree_le"),
                    "galaxies": m.get("galaxies", []),
                    "installees": sum(empreintes.get(r) == empreinte for r in regions)})
    return out


def _pack_worker(chemin):
    con = db.connect()
    try:
        PACK.update(fait=0, total=0, region=None, installees=0, sautees=0, erreur=None)
        n, saut = packs.installer(con, chemin, avance=lambda i, t, r: PACK.update(fait=i, total=t, region=r))
        PACK.update(installees=n, sautees=saut)
        db.refresh_index(con)
        db.meta(con)
    except Exception as e:
        PACK["erreur"] = str(e)
    finally:
        con.close()
        PACK.update(running=False, fini_le=time.time())


def pack_install(nom):
    if PACK["running"]:
        raise ValueError("Une installation est deja en cours.")
    chemin = PACKS_DIR / os.path.basename(nom or "")
    if chemin.suffix.lower() != ".zip" or not chemin.exists():
        raise ValueError("Pack introuvable.")
    packs.lire_manifeste(chemin)  # refuse tout de suite un fichier qui n'est pas un pack
    PACK.update(running=True, fichier=chemin.name, fini_le=None, erreur=None)
    threading.Thread(target=_pack_worker, args=(chemin,), daemon=True).start()
    return dict(PACK)


# La page, l'overlay (chaque seconde) et le guidage arrivent en meme temps : une seule connexion SQLite
# partagee par plusieurs fils peut se bloquer, donc la base est servie un appel a la fois.
DB_LOCK = threading.RLock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/meta":
            # At start-up the importer counts the filters: wait for it without holding the database lock.
            deadline = time.time() + 30
            while db._meta_cache["options"] is None and time.time() < deadline:
                time.sleep(0.2)
        if path.startswith("/api/"):
            with DB_LOCK:
                return self._get(path)
        return self._get(path)

    def do_POST(self):
        if unquote(urlparse(self.path).path) == "/api/packs/upload":
            return self._upload_pack()
        with DB_LOCK:
            return self._post()

    def _upload_pack(self):
        """Recoit un pack envoye depuis la page et l'ecrit dans data/packs, par morceaux."""
        nom = os.path.basename(unquote(parse_qs(urlparse(self.path).query).get("nom", [""])[0]))
        if not nom.lower().endswith(".zip"):
            return self._json({"error": "Un pack est un fichier .zip."}, 400)
        PACKS_DIR.mkdir(parents=True, exist_ok=True)
        reste = int(self.headers.get("Content-Length") or 0)
        tmp = PACKS_DIR / (nom + ".partiel")
        try:
            with open(tmp, "wb") as sortie:
                while reste > 0:
                    bloc = self.rfile.read(min(1 << 20, reste))
                    if not bloc:
                        raise OSError("Envoi interrompu.")
                    sortie.write(bloc)
                    reste -= len(bloc)
            packs.lire_manifeste(tmp)  # on verifie avant de le garder
            os.replace(tmp, PACKS_DIR / nom)
        except (OSError, ValueError, zipfile.BadZipFile, packs.PackInvalide) as e:
            tmp.unlink(missing_ok=True)
            return self._json({"error": str(e)}, 400)
        with DB_LOCK:
            return self._json({"fichier": nom, "disponibles": packs_disponibles()})

    def _get(self, path):
        if path == "/api/meta":
            return self._json(db.meta(CON, allow_stale=True))
        if path.startswith("/api/system/"):
            s = db.system(CON, path.rsplit("/", 1)[1])
            return self._json(s) if s else self._json({"error": "Systeme inconnu"}, 404)
        if path == "/api/packs":
            return self._json({"dossier": str(PACKS_DIR), "disponibles": packs_disponibles(),
                               "etat": dict(PACK)})
        if path == "/api/settings":
            return self._json(db.load_settings())
        if path == "/api/trip":
            return self._json(db.trip(CON))
        if path == "/api/searches":
            return self._json(db.saved_searches(CON))
        if path == "/api/favorites":
            return self._json(db.favorites(CON))
        if path == "/api/journal":
            return self._json(db.journal(CON))
        if path == "/api/overlay":
            return self._json(overlay_settings())
        if path == "/api/duplicates":
            return self._json(db.duplicate_report(CON))
        reponse = _routes_en_plus(path, self._body)
        if reponse is not None:
            return self._json(*reponse)
        self._static(path)

    def _post(self):
        path = urlparse(self.path).path
        if path == "/api/search":
            q = self._body()
            return self._json(db.search(CON, q.get("criteria", []), q.get("region"), q.get("limit", 200),
                                        q.get("offset", 0), bool(q.get("hide_visited")),
                                        insight=bool(q.get("insight")), per_region=bool(q.get("per_region"))))
        if path == "/api/trip":
            q = self._body()
            action, pid = q.get("action"), q.get("planet_id")
            try:
                if action == "add":
                    added = db.trip_add(CON, pid)
                    return self._json(db.trip(CON) | {"added": added})
                if action == "remove":
                    db.trip_remove(CON, pid)
                elif action == "move":
                    db.trip_move(CON, pid, int(q.get("delta", 0)))
                elif action == "current":
                    if db.get_state(CON, "mode") == "hunt":
                        db.set_state(CON, "hunt_current", pid)
                        db.set_state(CON, "glyph_step", 0)
                    else:
                        db.trip_set_current(CON, pid)
                elif action == "skip":
                    db.hunt_skip(CON)
                elif action == "unskip":
                    db.hunt_unskip(CON, pid)
                elif action == "hunt_start":
                    db.hunt_start(CON, q.get("criteria", []), q.get("region"), q.get("min_score", 75),
                                  q.get("order", "score"), q.get("label", ""))
                elif action == "hunt_stop":
                    db.hunt_stop(CON)
                elif action == "step":
                    db.set_state(CON, "glyph_step", max(0, min(12, int(q.get("step", 0)))))
                elif action == "clear_visited":
                    db.trip_clear(CON, only_visited=True)
                elif action == "clear":
                    db.trip_clear(CON, only_visited=False)
                else:
                    return self._json({"error": "Action inconnue"}, 400)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json(db.trip(CON))
        if path == "/api/visit":
            q = self._body()
            db.set_visited(CON, q["planet_id"], bool(q.get("on", True)))
            return self._json(db.trip(CON))
        if path == "/api/favorite":
            q = self._body()
            db.set_favorite(CON, q["planet_id"], bool(q.get("on", True)), q.get("note"))
            return self._json({"ok": True})
        if path == "/api/settings":
            return self._json(db.save_settings(**self._body()))
        if path == "/api/note":
            q = self._body()
            db.set_note(CON, q["planet_id"], q.get("note"))
            return self._json({"ok": True})
        if path == "/api/overlay":
            return self._json(overlay_settings(self._body()))
        if path == "/api/packs":
            q = self._body()
            try:
                if q.get("action") == "installer":
                    pack_install(q.get("fichier"))
                elif q.get("action") == "supprimer":
                    chemin = PACKS_DIR / os.path.basename(q.get("fichier") or "")
                    if chemin.suffix.lower() == ".zip" and chemin.exists():
                        chemin.unlink()
                else:
                    return self._json({"error": "Action inconnue"}, 400)
            except (ValueError, OSError, packs.PackInvalide) as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"disponibles": packs_disponibles(), "etat": dict(PACK)})
        if path == "/api/searches":
            q = self._body()
            try:
                if q.get("action") == "delete":
                    db.delete_search(CON, q.get("name"))
                    return self._json({"searches": db.saved_searches(CON)})
                existed = db.save_search(CON, q.get("name"), q.get("criteria", []), q.get("strict"))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"replaced": existed, "searches": db.saved_searches(CON)})
        reponse = _routes_en_plus(path, self._body)
        if reponse is not None:
            return self._json(*reponse)
        self._json({"error": "Introuvable"}, 404)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        f = (STATIC / path.lstrip("/")).resolve()
        if STATIC not in f.parents or not f.is_file():
            return self._json({"error": "Introuvable"}, 404)
        body = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
                         + ("; charset=utf-8" if f.suffix in (".html", ".js", ".css") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


OVERLAY_STATE = db.DATA_DIR / "overlay.json"
OVERLAY_DEFAULT = {"x": 60, "y": 60, "scale": 1, "alpha": 0.9, "visible": True, "band": "biome"}


def overlay_settings(changes=None):
    """The overlay's own settings file (size, opacity, band colour, position): the overlay picks up changes within a
    second, so the app's Réglages page can drive it."""
    try:
        state = OVERLAY_DEFAULT | json.loads(OVERLAY_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = dict(OVERLAY_DEFAULT)
    if changes:
        if "scale" in changes:
            state["scale"] = max(0, min(4, int(changes["scale"])))
        if "alpha" in changes:
            state["alpha"] = round(max(0.3, min(1.0, float(changes["alpha"]))), 2)
        if changes.get("band") in ("biome", "gold"):
            state["band"] = changes["band"]
        if "visible" in changes:
            state["visible"] = bool(changes["visible"])
        if changes.get("reset_position"):
            state["x"], state["y"] = 60, 60
        tmp = OVERLAY_STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, OVERLAY_STATE)
    return state


def start():
    """Sert l'app dans un fil de fond (utilise par la fenetre Planet Scanner). None si le port est pris."""
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        return None
    start_importer()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"L'app tourne deja sur http://{HOST}:{PORT}")
        if "--no-browser" not in sys.argv:
            webbrowser.open(f"http://{HOST}:{PORT}")
        return
    start_importer()
    print(f"Planet Scanner : http://{HOST}:{PORT}")
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
