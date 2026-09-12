"""L'overlay de Planet Scanner : l'adresse du portail de ta destination, par-dessus le jeu, et rien de plus.

- Visible tant que No Man's Sky a le focus, cachee avec lui ; le bouton Masquer la range, et ce choix est retenu.
- Elle a l'allure d'une fiche du jeu : bandeau coloré (deplacer, plus petit, plus grand, le nom de la
  destination) et corps sombre (ce qu'est la planete, ses 12 glyphes, les boutons). Les messages arrivent en
  notification sous la carte, comme dans le jeu.
- Tout se pilote a la souris, quand le curseur est libre (menus du jeu, ou jeu en fenetre) : les clics
  n'enlevent jamais le focus au jeu.
Elle parle a l'app locale (app/server.py). Le jeu doit tourner en plein ecran fenetre / sans bordure.
"""

import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Les fichiers livres avec l'app : a cote du code, ou dans le paquet quand elle est compilee.
STATIC = Path(getattr(sys, "_MEIPASS", ROOT / "app")) / "static"
DATA = Path(os.environ.get("PS_DATA_DIR") or ROOT / "data")  # le meme dossier que l'app
API = f"http://127.0.0.1:{os.environ.get('PS_PORT', 8765)}"
STATE_FILE = DATA / "overlay.json"
GLYPH_NAMES = ["Couchant", "Oiseau", "Visage", "Diplo", "Éclipse", "Ballon", "Bateau", "Insecte", "Libellule",
               "Galaxie", "Voxel", "Poisson", "Tente", "Fusée", "Arbre", "Atlas"]
BIOME_FR = {"Lush": "Luxuriante", "Toxic": "Toxique", "Scorched": "Brûlante", "Radioactive": "Radioactive",
            "Frozen": "Gelée", "Barren": "Aride", "Dead": "Morte", "Weird": "Exotique", "Red": "Rouge", "Green": "Verte",
            "Blue": "Bleue", "Swamp": "Marécageuse", "Lava": "Volcanique", "Waterworld": "Océanique",
            "GasGiant": "Géante gazeuse"}
# Les couleurs du jeu : bandeau or des decouvertes, corps presque noir, texte blanc, turquoise des donnees.
C = {"bg": "#07090B", "body": "#07090B", "panel": "#14181C", "line": "#2B3036", "rule": "#3A3F45", "edge": "#07090B",
     "cap": "#B9BEC4", "text": "#F2F2EE", "muted": "#9CA3AB", "accent": "#EBC733", "band": "#EBC733",
     "band_text": "#221B04", "band_sub": "#5A4A0E", "band_light": "#F6DA62", "teal": "#3FB9B3", "teal_dark": "#062625",
     "teal_light": "#7FE0DA"}
# The card's band takes the destination's biome colour (yellow stays for favourites); grey without a destination.
BIOME_BAND = {"Lush": "#7DC25B", "Swamp": "#A3A857", "Toxic": "#E2C93C", "Radioactive": "#B7E23F",
              "Scorched": "#F2913D", "Lava": "#EC5F3B", "Frozen": "#A9D8EA", "Waterworld": "#4DA3DC",
              "Barren": "#DCBC84", "Dead": "#A4ACB5", "Weird": "#C88BE8", "Red": "#F0667A", "Green": "#4FD39A",
              "Blue": "#6F9CF2", "GasGiant": "#E6A3C8"}
IDLE_BAND = "#AEB8C4"
KEY = "#010203"  # transparent colour: the gap between the card and the notification lets the game show through
SCALES = [0.85, 1.0, 1.25, 1.55, 1.9]
# The keys line at the bottom of the card (one line, always).
def spaced(text):
    """Uppercase with wide letter spacing, like the game's titles (Tk has no letter spacing: hair spaces)."""
    return "\u200a".join(text.upper())


def shade(hex_colour, t):
    """The colour darkened towards black by t (0..1): the band's text is a deep shade of the band itself."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(int(v * (1 - t)) for v in (r, g, b))


def api(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read())


GAME_EXE = "nms.exe"
_process_names = {}


def foreground_process():
    """(window, process id) of the window that has the keyboard focus."""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value


def process_name(pid):
    """Executable name of a process ('nms.exe'), cached."""
    if pid in _process_names:
        return _process_names[pid]
    k32, name = ctypes.windll.kernel32, ""
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            name = buf.value.rsplit("\\", 1)[-1].lower()
        k32.CloseHandle(h)
    if len(_process_names) > 256:
        _process_names.clear()
    _process_names[pid] = name
    return name


def load_glyph_font(root):
    """Register the NMS glyph font for this process only (no system install). None when it isn't there, or when
    Planet Scanner's own drawings were chosen (setting own_glyphs)."""
    try:
        if json.loads((DATA / "settings.json").read_text(encoding="utf-8")).get("own_glyphs"):
            return None
    except (OSError, ValueError):
        pass
    try:
        ttf = DATA / "NmsGlyphs.ttf"          # celle que le joueur a posee, si elle est la
        if not ttf.exists() and (STATIC / "NmsGlyphs.ttf").is_file():
            ttf = STATIC / "NmsGlyphs.ttf"    # celle livree avec l'app
        if not ttf.exists():                  # sinon, celle enfermee dans la feuille de style
            css = (STATIC / "nms-glyphs.css").read_text(encoding="utf-8")
            ttf.write_bytes(base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", css).group(1)))
        ctypes.windll.gdi32.AddFontResourceExW(str(ttf), 0x10, 0)  # FR_PRIVATE
        # Le nom de la famille depend de la variante livree (Tight, Mono...) : on prend celle qui est la.
        return next((f for f in tkfont.families(root) if f.startswith("NMS Glyphs")), None)
    except (OSError, AttributeError):
        return None


def load_glyph_drawings():
    try:
        return json.loads((STATIC / "glyphs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Overlay:
    def __init__(self):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        self._prev_fg = ctypes.windll.user32.GetForegroundWindow()  # the player's window, given back at start
        self.root = tk.Tk()
        self.root.title("Planet Scanner - overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.state = self.load_state()
        self._state_stamp = self._stamp()
        self.root.attributes("-alpha", self.state["alpha"])
        families = set(tkfont.families(self.root))
        self.display_family = next((f for f in ("Bahnschrift Light", "Segoe UI Light") if f in families), "Segoe UI")
        self.glyph_family = load_glyph_font(self.root)
        self.drawings = None if self.glyph_family else load_glyph_drawings()
        self.trip, self.meta = None, None
        self.offline = False
        self.visible = self.state.get("visible", True)  # bouton Masquer, retenu
        self.game_active = False      # No Man's Sky a le focus
        self.game_hwnd = None
        self.ask_fav, self.ask_until = None, 0
        self.flash_text, self.flash_until, self.flash_toast = "", 0, None
        self.build()
        self.root.geometry(f"+{self.state['x']}+{self.state['y']}")
        self.root.withdraw()  # shown without activation by apply_visibility(), once there is something to show
        self.root.after(200, self.no_activate)
        self.poll()
        self.load_meta()
        self.root.after(250, self.watch_game)

    # --- persistence ---
    def load_state(self):
        s = {"x": 60, "y": 60, "scale": 1, "alpha": 0.9, "system_open": False, "visible": True}
        try:
            s.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        s["scale"] = min(max(0, s.get("scale", 1)), len(SCALES) - 1)
        return s

    def save_state(self):
        DATA.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state), encoding="utf-8")
        self._state_stamp = self._stamp()

    @staticmethod
    def _stamp():
        try:
            return STATE_FILE.stat().st_mtime_ns
        except OSError:
            return None

    def check_state_file(self):
        """The app's Réglages page writes the same file: apply its changes (size, opacity, band colour, position,
        shown or hidden) within a second."""
        stamp = self._stamp()
        if stamp is None or stamp == getattr(self, "_state_stamp", None):
            return
        self._state_stamp = stamp
        old, new = self.state, self.load_state()
        self.state = new
        if new.get("alpha") != old.get("alpha"):
            self.root.attributes("-alpha", new["alpha"])
        if (new.get("x"), new.get("y")) != (old.get("x"), old.get("y")):
            self.root.geometry(f"+{new['x']}+{new['y']}")
        if new.get("visible", True) != self.visible:
            self.visible = new.get("visible", True)
            self.apply_visibility()
        if new.get("scale") != old.get("scale"):
            self.build()
        self.render()

    # --- window behaviour ---
    def no_activate(self):
        """Clicks on the overlay must not steal the focus from the game."""
        hwnd = self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # WS_EX_NOACTIVATE : les clics arrivent bien aux boutons, mais le jeu garde le focus.
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        self._shown = None
        self.apply_visibility()
        self.root.after(100, self.give_back_focus)

    def give_back_focus(self):
        """Started by a process that had the focus (the launcher, a shell), this hidden window may receive it from
        Windows, and with it the keyboard: hand it back to the window the player was using."""
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != self.hwnd:
            return
        prev = self._prev_fg
        if prev and prev != self.hwnd and user32.IsWindow(prev):
            self.focus_window(prev)

    def start_drag(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def on_drag(self, e):
        if getattr(self, "_drag", None):
            x, y = e.x_root - self._drag[0], e.y_root - self._drag[1]
            self.root.geometry(f"+{x}+{y}")
            self.state.update(x=x, y=y)

    def end_drag(self, _e):
        if getattr(self, "_drag", None):
            self._drag = None
            self.save_state()

    # --- layout ---
    def s(self, px):
        return max(1, int(px * SCALES[self.state["scale"]]))

    def f(self, size, weight="normal"):
        return ("Segoe UI", self.s(size), weight)

    def d(self, size, weight="normal"):
        """The display face (titles, labels): thin and geometric, used in spaced capitals."""
        return (self.display_family, self.s(size), weight)

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.frame = tk.Frame(self.root, bg=KEY)
        self.frame.pack()

        # the card: yellow band + dark body, in a 1 px outline (yellow in mouse mode)
        self.outline = tk.Frame(self.frame, bg=C["edge"], padx=1, pady=1)
        self.outline.pack(anchor="w", fill="x")
        card = tk.Frame(self.outline, bg=C["body"])
        card.pack(fill="x")

        self._band_for = None
        self.head = tk.Frame(card, bg=C["band"], padx=self.s(8), pady=self.s(5))
        self.head.pack(fill="x")
        ctl = tk.Frame(self.head, bg=C["band"])
        ctl.pack(side="left")
        # top left, always: move (drag the grip, or the band) and size; clicking never takes the game's focus
        self.grip = self._chip(ctl, "✥", None)
        self.grip.config(cursor="fleur")
        for text, delta in (("−", -1), ("+", 1)):
            self._chip(ctl, text, lambda d=delta: self.rescale(d))
        k, m = self.s(14), max(2, self.s(3))
        self.diamond = tk.Canvas(self.head, width=k, height=k, bg=C["band"], highlightthickness=0)
        self.diamond.create_polygon(k / 2, m - 1, k - m + 1, k / 2, k / 2, k - m + 1, m - 1, k / 2, fill="",
                                    outline=C["band_text"], width=max(1, self.s(2)))
        self.diamond.pack(side="left", padx=(self.s(9), self.s(7)))
        names = tk.Frame(self.head, bg=C["band"])
        names.pack(side="left")
        self.title = tk.Label(names, text="", fg=C["band_text"], bg=C["band"], font=self.d(14), anchor="w")
        self.title.pack(anchor="w")
        self.tag = tk.Label(names, text="", fg=C["band_sub"], bg=C["band"], font=self.d(7), anchor="w")
        self.tag.pack(anchor="w")
        self.chips = ctl.winfo_children()
        self.band_frames = (self.head, ctl, names)

        self.body = tk.Frame(card, bg=C["body"], padx=self.s(10), pady=self.s(7))
        self.body.pack(fill="x")
        self.desc = tk.Label(self.body, text="", fg=C["text"], bg=C["body"], font=self.f(10), anchor="w")
        self.gframe = tk.Frame(self.body, bg=C["body"])
        self.cells = []
        for i in range(12):
            if self.drawings:
                icon = tk.Canvas(self.gframe, width=self.s(32), height=self.s(32), bg=C["body"], highlightthickness=0)
                icon.drawn = None
            else:
                icon = tk.Label(self.gframe, text="", fg=C["text"], bg=C["body"], font=(self.glyph_family, self.s(22)),
                                width=2, pady=0)
            icon.grid(row=0, column=i, padx=self.s(1))
            self.cells.append(icon)
        self.rule = tk.Frame(self.body, bg=C["rule"], height=1)

        # les boutons, toujours la : le clic ne prend pas le focus au jeu
        self.toolbar = tk.Frame(self.body, bg=C["body"])
        left = tk.Frame(self.toolbar, bg=C["body"])
        left.pack(side="left")
        self.actions = []
        for text, cmd, primary in (("✓ J'y suis", self.visited, True),
                                   ("★ Favori", lambda: self.favorite(self.current_id()), False),
                                   ("Passer", self.skip, False)):
            b = self._button(left, text, cmd, primary)
            b.pack(side="left", padx=(0, self.s(3)))
            self.actions.append(b)
        right = tk.Frame(self.toolbar, bg=C["body"])
        right.pack(side="right")
        for text, cmd in (("◐", self.cycle_alpha), ("Masquer", self.toggle)):
            self._button(right, text, cmd).pack(side="left", padx=(self.s(3), 0))

        # the notification, under the card (the gap is transparent)
        self.toast = tk.Frame(self.frame, bg=C["body"])
        self.toast_icon = tk.Label(self.toast, text="", font=("Segoe UI Symbol", self.s(12)), width=2,
                                   fg=C["band_text"], bg=C["band"])
        self.toast_icon.pack(side="left", fill="y")
        tb = tk.Frame(self.toast, bg=C["body"], padx=self.s(9), pady=self.s(4))
        tb.pack(side="left", fill="both", expand=True)
        self.toast_title = tk.Label(tb, text="", fg=C["band_light"], bg=C["body"], font=self.d(8), anchor="w")
        self.toast_title.pack(anchor="w")
        self.toast_line = tk.Frame(tb, bg=C["body"])
        self.toast_line.pack(anchor="w")
        self._toast_for = None

        # dragging, whenever the cursor is free: from the grip, the band and the body
        for w in (self.head, ctl, self.grip, self.diamond, names, self.title, self.tag, self.body, self.desc,
                  self.gframe, *self.cells):
            w.bind("<ButtonPress-1>", self.start_drag)
            w.bind("<B1-Motion>", self.on_drag)
            w.bind("<ButtonRelease-1>", self.end_drag)
        self._layout = None

    def _chip(self, parent, text, cmd):
        """A small square button on the yellow band."""
        b = tk.Label(parent, text=text, fg=C["band_text"], bg=C["band"], font=self.f(9, "bold"), width=2,
                     highlightthickness=1, highlightbackground=C["band_text"], cursor="hand2")
        b.pack(side="left", padx=(0, self.s(2)))
        if cmd:
            b.bind("<Button-1>", lambda _e: cmd())
        return b

    def set_band(self, colour):
        """Recolour the band (background, its text in deep shades of the same colour)."""
        if colour == self._band_for:
            return
        self._band_for = colour
        text, sub = shade(colour, 0.84), shade(colour, 0.58)
        for w in self.band_frames:
            w.config(bg=colour)
        for w in self.chips:
            w.config(bg=colour, fg=text, highlightbackground=text)
        self.diamond.config(bg=colour)
        self.diamond.itemconfig("all", outline=text)
        self.title.config(bg=colour, fg=text)
        self.tag.config(bg=colour, fg=sub)

    def set_toast(self, toast):
        """toast = (colour, icon, title, detail, keys)."""
        if toast[:4] == self._toast_for:  # les boutons portent des fonctions : on compare ce qui s'affiche
            return
        self._toast_for = toast[:4]
        colour, icon, title, detail, boutons = toast
        band, dark, light = ((C["teal"], C["teal_dark"], C["teal_light"]) if colour == "teal" else
                             (C["band"], C["band_text"], C["band_light"]))
        self.toast_icon.config(text=icon, bg=band, fg=dark)
        self.toast_title.config(text=spaced(title), fg=light)
        for w in self.toast_line.winfo_children():
            w.destroy()
        if detail:
            tk.Label(self.toast_line, text=detail, fg=C["text"], bg=C["body"], font=self.f(9)).pack(side="left")
        for i, (label, cmd) in enumerate(boutons):
            self._button(self.toast_line, label, cmd, primary=(i == 0)).pack(side="left", padx=(self.s(8), 0))

    def _button(self, parent, text, cmd, primary=False):
        b = tk.Label(parent, text=text, fg=C["band_text"] if primary else C["text"],
                     bg=C["accent"] if primary else C["panel"], font=self.f(8, "bold" if primary else "normal"),
                     padx=self.s(7), pady=self.s(2), cursor="hand2")
        b.bind("<Button-1>", lambda _e: cmd())
        return b

    def show_sections(self, wanted):
        """Pack exactly the sections that have something to show, in a fixed order (no empty boxes)."""
        order = [("desc", self.desc, {"fill": "x"}), ("glyphs", self.gframe, {"anchor": "w", "pady": (self.s(5), 0)}),
                 ("toolbar", self.rule, {"fill": "x", "pady": (self.s(7), self.s(6))}),
                 ("toolbar", self.toolbar, {"fill": "x"}),
                 ("toast", self.toast, {"anchor": "w", "fill": "x", "pady": (self.s(6), 0)})]
        key = tuple(name for name, _w, _o in order if name in wanted)
        if key == self._layout:
            return
        self._layout = key
        for _name, w, _o in order:
            w.pack_forget()
        for name, w, opts in order:
            if name in wanted:
                w.pack(**opts)

    # --- data ---
    def current(self):
        if not self.trip:
            return None
        return next((p for p in self.trip["planets"] if p["id"] == self.trip["current"]), None)

    def current_id(self):
        p = self.current()
        return p["id"] if p else None

    def poll(self):
        if getattr(self, "_polling", False):  # previous request still running: don't pile them up
            self.root.after(1000, self.poll)
            return
        self._polling = True

        def work():
            try:
                trip = api("/api/trip")
                self.failures = 0
                self.root.after(0, lambda: self.render(trip, False))
            except OSError:
                # One slow answer is not "app closed": keep the last picture until it fails 3 times in a row.
                self.failures = getattr(self, "failures", 0) + 1
                if self.failures >= 3:
                    self.root.after(0, lambda: self.render(None, True))
            finally:
                self._polling = False
        threading.Thread(target=work, daemon=True).start()
        self.root.after(1000, self.poll)

    def render(self, trip=None, offline=None):
        if trip is not None or offline is not None:
            self.trip, self.offline = trip, bool(offline)
        trip, now = self.trip, time.time()
        p = None if self.offline else self.current()
        hunt = bool(trip and trip.get("mode") == "hunt")
        wanted = {"desc", "toolbar"}

        if p:
            wanted.add("glyphs")
            n = trip["remaining"]
            left = f"{n} restante{'s' if n > 1 else ''}"
            score = f" · {p['score']} %" if hunt and p.get("score") is not None else ""
            self.tag.config(text=spaced(f"{'Guidage' if hunt else 'Voyage'} · {left}{score}"))
            self.title.config(text=spaced(p.get("name") or f"Planète {p['idx']}"))
            kind = BIOME_FR.get(p["biome"], p["biome"])
            self.set_band(C["band"] if self.state.get("band") == "gold" else BIOME_BAND.get(p["biome"], C["band"]))
            desc = self.game_text(p.get("desc_key"), p.get("class_key"))
            self.desc.config(text=f"{desc} · {kind.lower()}" if desc else kind)
            for k, icon in enumerate(self.cells):
                c = p["glyphs"][k]
                if self.drawings:
                    self.draw_glyph(icon, c, C["text"])
                else:
                    icon.config(text=c)
        else:
            self.set_band(IDLE_BAND)
            self.title.config(text=spaced("Planet Scanner"))
            self.tag.config(text=spaced("App fermée" if self.offline else "Aucune destination"))
            self.desc.config(text="Ouvre Planet Scanner" if self.offline else
                             "Choisis une destination dans l'app : « Me guider » ou « Y aller »")
        for b in self.actions:  # sans destination, les boutons d'action n'ont rien a faire
            b.config(state="normal" if p else "disabled", fg=C["muted"] if not p else b.cget("fg"))

        # la notification : question favori, puis message
        if self.ask_fav and now > self.ask_until:
            self.ask_fav = None
        toast = None
        if self.ask_fav:
            toast = ("band", "★", "Planète visitée", "La garder en favori ?",
                     (("★ Oui", lambda: self.favorite(self.ask_fav)), ("Non", self.dismiss_ask)))
        elif now < self.flash_until and self.flash_toast:
            toast = self.flash_toast
        if toast:
            self.set_toast(toast)
            wanted.add("toast")

        self.show_sections(wanted)
        self.has_content = True
        self.apply_visibility()

    def draw_glyph(self, canvas, c, colour):
        """Planet Scanner's own glyph drawing (24x24 strokes) on a cell's canvas; redrawn only when it changes."""
        if canvas.drawn == (c, colour):
            return
        canvas.drawn = (c, colour)
        canvas.delete("all")
        if not c:
            return
        size = self.s(24)
        k, w = size / 24, max(2, self.s(2))
        ox, oy = (int(canvas["width"]) - size) / 2, (int(canvas["height"]) - size) / 2
        for p in self.drawings[int(c, 16)]:
            if "e" in p:
                cx, cy, rx, ry = p["e"]
                canvas.create_oval(ox + (cx - rx) * k, oy + (cy - ry) * k, ox + (cx + rx) * k, oy + (cy + ry) * k,
                                   outline=colour, width=w)
            else:
                pts = p["l"] + ([p["l"][0]] if p.get("z") else [])
                canvas.create_line(*[v for x, y in pts for v in (ox + x * k, oy + y * k)], fill=colour, width=w,
                                   capstyle="round", joinstyle="round")

    # --- actions (also bound to global keys) ---
    def act(self, fn):
        def run():
            try:
                fn()
            except OSError:
                pass
        threading.Thread(target=run, daemon=True).start()

    def visited(self):
        pid = self.current_id()
        if pid:
            self.ask_fav, self.ask_until = pid, time.time() + 10  # the question goes away on its own (= no)
            self.render()
            self.act(lambda: api("/api/visit", {"planet_id": pid, "on": True}))

    def favorite(self, pid):
        if pid:
            self.ask_fav = None
            self.flash("Ajoutée aux favoris ★", 3)
            self.act(lambda: api("/api/favorite", {"planet_id": pid, "on": True}))

    def dismiss_ask(self):
        self.ask_fav = None
        self.render()

    def flash(self, text, seconds=4):
        """A notification under the card for a few seconds: "Title : detail"."""
        title, _sep, detail = text.replace("★", "").strip().partition(" : ")
        favori = "favori" in text.lower()
        self.flash_toast = ("band", "★" if favori else "◆", title.strip(), detail.strip(), ())
        self.flash_text, self.flash_until = text, time.time() + seconds
        self.render()
        self.root.after(int(seconds * 1000) + 50, self.render)

    def skip(self):
        """Next planet without marking this one visited (in a guided hunt, it won't come back)."""
        if not self.trip or not self.current():
            return
        self.ask_fav = None  # moving on: the favourite question was about the previous planet
        if self.trip.get("mode") == "hunt":
            self.act(lambda: api("/api/trip", {"action": "skip"}))
            return
        ids = [p["id"] for p in self.trip["planets"]]
        nxt = ids[(ids.index(self.current_id()) + 1) % len(ids)]
        self.act(lambda: api("/api/trip", {"action": "current", "planet_id": nxt}))

    def toggle(self):
        self.visible = not self.visible
        self.state["visible"] = self.visible
        self.save_state()
        self.apply_visibility()

    def rescale(self, delta):
        self.state["scale"] = min(max(0, self.state["scale"] + delta), len(SCALES) - 1)
        self.save_state()
        self.build()
        self.render()

    def cycle_alpha(self):
        steps = [0.9, 0.75, 0.6, 1.0]
        self.state["alpha"] = steps[(steps.index(self.state["alpha"]) + 1) % len(steps)] \
            if self.state["alpha"] in steps else 0.9
        self.root.attributes("-alpha", self.state["alpha"])
        self.save_state()

    def load_meta(self):
        """The game's texts (planet descriptions) from the app, once; retried while the app isn't there."""
        def work():
            try:
                self.meta = api("/api/meta")
                self.root.after(0, self.render)
            except (OSError, ValueError):
                self.root.after(10000, self.load_meta)
        threading.Thread(target=work, daemon=True).start()

    def game_text(self, key, planet_class=None):
        texts = (self.meta or {}).get("texts", {})
        # Les donnees portent soit une cle de texte, soit la phrase elle-meme (une cle n'a pas d'espace).
        t = texts.get(key) or (key if key and " " in key else None)
        if not t:
            return None
        t = re.sub(r"%[A-Z_]+%", texts.get(planet_class) or "Planète", t)
        return re.sub(r"<[^>]*>", "", t).strip()

    # --- attached to the game: shown only while No Man's Sky has the focus, and only when useful ---
    def watch_game(self):
        hwnd, pid = foreground_process()
        if pid and pid != os.getpid():  # notre propre fenetre ne change pas l'etat
            self.game_active = process_name(pid) == GAME_EXE and not ctypes.windll.user32.IsIconic(hwnd)
            if self.game_active:
                self.game_hwnd = hwnd
        self.apply_visibility()
        self.check_state_file()
        self.root.after(300, self.watch_game)

    def apply_visibility(self):
        """Show without activating (the game keeps the focus), hide with the window manager directly."""
        want = self.visible and self.game_active
        if want == getattr(self, "_shown", None) or not getattr(self, "hwnd", None):
            return
        self._shown = want
        user32 = ctypes.windll.user32
        if want:
            user32.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE
            # back on top of the game: HWND_TOPMOST, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        else:
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE

    @staticmethod
    def focus_window(hwnd):
        """Bring a window to the front even though Windows restricts focus changes (attach to the current
        foreground thread for the call)."""
        user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        me = k32.GetCurrentThreadId()
        attached = fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)

    def run(self):
        self.root.mainloop()


def lancer():
    # Une seule carte a la fois.
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "PlanetScannerOverlay")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        raise SystemExit(0)
    Overlay().run()


if __name__ == "__main__":
    lancer()
