"""Planet Scanner : une fenetre, et rien d'autre a l'ecran.

Un double-clic (ou le raccourci "Planet Scanner") ouvre l'app dans sa propre fenetre. Derriere elle, sans
console :
  - le serveur local de l'app (le code de app/server.py, dans ce meme processus),
  - l'overlay, visible seulement quand No Man's Sky a le focus.
Fermer la fenetre arrete tout, sauf si le jeu tourne encore : l'overlay reste jusqu'a ce qu'il se ferme.
La rouvrir pendant qu'elle tourne ouvre simplement une nouvelle fenetre sur l'app en cours.
"""

import ctypes
import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# Assemblee en un seul fichier executable, l'app vit a cote de lui ; sinon, a cote de ce script.
GELE = getattr(sys, "frozen", False)  # assemblee en un seul executable
ROOT = Path(sys.executable).parent if GELE else Path(__file__).resolve().parent
os.environ.setdefault("PS_DATA_DIR", str(ROOT / "data"))
sys.path.insert(0, str(ROOT / "app"))
VENV = ROOT / ".venv" / "Scripts"
OVERLAY = ROOT / "overlay" / "overlay.py"
NO_WINDOW = 0x08000000
# Une app, c'est son dossier : deux copies posees a deux endroits sont deux apps, avec chacune ses donnees,
# son serveur, sa carte et son bouton dans la barre des taches. Sans ce nom, la seconde ouvrirait sa fenetre
# sur le serveur de la premiere et montrerait les planetes de l'autre.
INSTALL = hashlib.sha1(str(ROOT).lower().encode("utf-8")).hexdigest()[:8]
PORT_RETENU = Path(os.environ["PS_DATA_DIR"]) / "port.txt"


def game_running():
    """No Man's Sky est-il ouvert ? (pour laisser l'overlay en place quand on ferme la fenetre)"""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq NMS.exe", "/NH"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout
    return "NMS.exe" in out


def libre(port):
    """Personne n'ecoute sur ce port."""
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def choisir_port(deja_ouverte):
    """Le port de cette app. Elle garde le sien dans son dossier de donnees et le reprend a chaque fois :
    la page se souvient de tes envies par port, en changer les oublierait. S'il est pris par autre chose,
    elle prend le suivant de libre."""
    try:
        retenu = int(PORT_RETENU.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        retenu = 0
    if deja_ouverte and retenu:
        return retenu  # une autre fenetre de cette meme app : on rejoint son serveur
    prefere = retenu or int(os.environ.get("PS_PORT", 8765))
    return next((p for p in range(prefere, prefere + 20) if libre(p)), prefere)


def stop_overlay():
    """Arrete une carte laissee par une session precedente de cette app : sans ca, elle garderait la place
    (une seule a la fois) et le joueur verrait l'ancienne. Une carte ouverte par une autre app installee
    ailleurs ne nous regarde pas : on la laisse tranquille."""
    ici = str(ROOT).replace("'", "''")
    # $PID : la recherche porte ces mots dans sa propre ligne de commande ; sans ca, elle se trouve
    # elle-meme, s'arrete au milieu de sa liste, et une carte survit.
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and "
          f"$_.CommandLine.Contains('{ici}') and "
          "($_.CommandLine -like '*--overlay*' -or $_.CommandLine -like '*overlay*overlay.py*') } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                   creationflags=NO_WINDOW, timeout=30)


def main():
    if "--overlay" in sys.argv:  # le meme programme, ouvert en carte par-dessus le jeu
        import overlay
        return overlay.lancer()
    kernel32 = ctypes.windll.kernel32
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    # Its own taskbar button with its own icon (else Windows groups it with Python and shows Python's icon),
    # and one button per app: two copies installed side by side are not the same program.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"PlanetScanner.App.{INSTALL}")
    # Une seule app par installation : deux fenetres de la meme app partagent son serveur ; une app posee
    # dans un autre dossier garde le sien.
    kernel32.CreateMutexW(None, False, f"PlanetScannerApp:{INSTALL}")
    first = kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS : une fenetre fait deja tourner l'app
    os.environ["PS_PORT"] = str(choisir_port(not first))  # avant d'ouvrir le serveur, et l'overlay en herite
    import server  # noqa: E402  (ouvre la base)
    if first and not PORT_RETENU.exists():
        PORT_RETENU.write_text(str(server.PORT), encoding="utf-8")  # le port de cette app, une fois pour toutes
    icone = server.STATIC / "icon.ico"
    httpd = server.start() if first else None
    overlay = None
    if first and (GELE or OVERLAY.exists()):
        # A fresh overlay with the current code (an old one would keep the single-instance slot); it shows up
        # over the game only, and never takes the focus.
        stop_overlay()
        lancement = ([sys.executable, "--overlay"] if GELE
                     else [str(VENV / "pythonw.exe"), str(OVERLAY)])
        overlay = subprocess.Popen(lancement, cwd=ROOT, creationflags=NO_WINDOW)

    import webview  # noqa: E402
    webview.create_window("Planet Scanner", f"http://127.0.0.1:{server.PORT}/", width=1440, height=920,
                          min_size=(1000, 640), background_color="#07090C", text_select=True,
                          minimized="--minimized" in sys.argv)  # (restart during a game session: stay out of the way)
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(Path(os.environ["PS_DATA_DIR"]) / "webview"),
                  icon=str(icone) if icone.exists() else None)

    if not first:
        return
    # Window closed: keep the overlay (and the app it talks to) while the game still runs.
    while game_running():
        time.sleep(5)
    if overlay is not None:
        # The venv's pythonw starts the real interpreter as a child: stop the whole tree.
        subprocess.run(["taskkill", "/PID", str(overlay.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
    if httpd is not None:
        httpd.shutdown()


if __name__ == "__main__":
    main()
