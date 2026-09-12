"""Planet Scanner : une fenetre, et rien d'autre a l'ecran.

Un double-clic (ou le raccourci "Planet Scanner") ouvre l'app dans sa propre fenetre. Derriere elle, sans
console :
  - le serveur local de l'app (le code de app/server.py, dans ce meme processus),
  - l'overlay, visible seulement quand No Man's Sky a le focus.
Fermer la fenetre arrete tout, sauf si le jeu tourne encore : l'overlay reste jusqu'a ce qu'il se ferme.
La rouvrir pendant qu'elle tourne ouvre simplement une nouvelle fenetre sur l'app en cours.
"""

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

# Assemblee en un seul fichier executable, l'app vit a cote de lui ; sinon, a cote de ce script.
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
os.environ.setdefault("PS_DATA_DIR", str(ROOT / "data"))
sys.path.insert(0, str(ROOT / "app"))
VENV = ROOT / ".venv" / "Scripts"
OVERLAY = ROOT / "overlay" / "overlay.py"
NO_WINDOW = 0x08000000


def game_running():
    """No Man's Sky est-il ouvert ? (pour laisser l'overlay en place quand on ferme la fenetre)"""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq NMS.exe", "/NH"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout
    return "NMS.exe" in out


def stop_processes(marker):
    """Stop every Python process whose command line contains `marker` (an overlay left running by an earlier
    session would otherwise keep the new one out: the overlay allows a single instance)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                   creationflags=NO_WINDOW, timeout=30)


def main():
    kernel32 = ctypes.windll.kernel32
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    # Its own taskbar button with its own icon (else Windows groups it with Python and shows Python's icon).
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PlanetScanner.App")
    import server  # noqa: E402  (ouvre la base)
    # Une seule app par port : deux fenetres sur le meme port partagent le meme serveur.
    kernel32.CreateMutexW(None, False, f"PlanetScannerApp:{server.PORT}")
    first = kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS : une fenetre fait deja tourner l'app
    icone = server.STATIC / "icon.ico"
    httpd = server.start() if first else None
    overlay = None
    if first and OVERLAY.exists():
        # A fresh overlay with the current code (an old one would keep the single-instance slot); it shows up
        # over the game only, and never takes the focus.
        stop_processes(r"overlay\overlay.py")
        overlay = subprocess.Popen([str(VENV / "pythonw.exe"), str(OVERLAY)], cwd=ROOT,
                                   creationflags=NO_WINDOW)

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
