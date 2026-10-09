"""The shot list: every cut, camera move and walk, keyed to the dialogue edit (timeline.py).

Where everyone is. The living room (plates LR, the wide with the sofa, and TW, the telly wall): the telly is on its
unit at screen right; Mum's armchair is screen left, facing it; the boy plays on the rug between them. So Mum looks
screen right to the boy and the telly, the boy looks left up to Mum and right to the telly. On the phone Mum faces
right and Dad (in his office, mirrored) faces left, so they look at each other across the cut.

The grammar: wides at true scale in the family's own rooms, where the walking, throwing and smashing happen (pose
drawings swapped on the action, as the drawings are made); close singles for every line, the room soft behind them,
the face acting; inserts on the props that change the story (the screen cracking, the card reader, the cards)."""
import json

import numpy as np

from studio.film import ep
from studio.film.cast import CAST, feet
from studio.film.shots import Marks, card, finish, insert, shot_at as _shot_at, single, world
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt = T.m, T.ls, T.le, T.wt

PLATES = {"LR": "home/family-living-room", "TW": "home/family-living-room-tv-wall",
          "OF": "home/family-office", "CAR": "street/family-car-interior", "HA": "home/family-hallway",
          "SH": "street/electronics-shop-tv-aisle",
          # the telly wall with its screen cracked (TWc), smashed through (TWs), and the telly gone, a projector
          # throwing a picture on the wall where it was (TWp): props.plate_image
          "TWc": "home/family-living-room-tv-wall", "TWs": "home/family-living-room-tv-wall",
          "TWp": "home/family-living-room-tv-wall", "LRs": "home/family-living-room"}
# the plant on the telly unit stands in front of the screen's lower right corner (1x plate px, traced)
PLANT = [(838, 541), (842, 520), (851, 506), (866, 497), (880, 500), (893, 489), (907, 487), (921, 494), (933, 506),
         (941, 512), (941, 640), (900, 640), (876, 600), (858, 586), (840, 573)]
OCCL = {k: {"plant": [PLANT]} for k in ("TW", "TWc", "TWs")}

HEIGHT = {"boy": 1.05, "mum": 1.65, "dad": 1.80}          # metres, standing
DRAW = {w: f"family-{w}:stand" for w in HEIGHT}


def ed_at(who, ppm):
    """a character's eye distance (plate px) where the floor is `ppm` plate px to the metre"""
    d, info = CAST.get(DRAW[who])
    return info["ed"] * HEIGHT[who] * ppm / (feet(DRAW[who])[1] - d.oy)


def at_feet(draw, fx, fy, ed_p, mirror=False):
    """the eye point (plate px) that stands a drawing's feet on (fx, fy); ed_p is this drawing's eye distance"""
    d, info = CAST.get(draw)
    k = ed_p / info["ed"]
    ax, ay = info["anchor"]
    ftx, fty = feet(draw)
    return (fx + (-1 if mirror else 1) * (ax - ftx) * k, fy - (fty - ay) * k)


# the floor's perspective in each set, measured from the plate: plate px to the metre at floor row y is
# k * (y - horizon). Living room: the rug's near and far edges (1.96x wider at y 1095 than at y 830) and the
# sofa (0.85 m, 215 px from its feet at y 805). Telly wall: the 55-inch screen (1.21 m, 372 px) at the back of the
# unit (y 745) and the unit's front (0.55 m, 205 px, feet at y 790).
FLOOR = {"LR": (1.0, 554), "LRs": (1.0, 554), "TW": (1.47, 536)}
for _k in ("TWc", "TWs", "TWp"):
    FLOOR[_k] = FLOOR["TW"]


def ppm_at(plate, y):
    k, h = FLOOR[plate]
    return k * (y - h)


def pose_scale(who, name):
    """a pose's eye distance relative to the standing drawing's (the character is the same size in both): with open
    eyes, their own spacing; a closed-eyed pose has only a guessed eye distance, so it takes the scale of the sheet
    it is drawn on instead (the eye spacing of that sheet's poses with eyes)"""
    cid = f"family-{who}"
    stand = CAST.get(DRAW[who])[1]["ed"]
    d, info = CAST.get(f"{cid}:{name}")
    if d.spec["eyes"]:
        return info["ed"] / stand
    return info["ed"] / _sheet_ed(cid, CAST.spec(cid)["drawings"][name].get("sheet"))


def _sheet_ed(cid, sheet):
    """the eye distance (sheet px) the character has on a sheet: the median over that sheet's eyed full poses"""
    sp = CAST.spec(cid)["drawings"]
    eds = [CAST.get(f"{cid}:{n}")[1]["ed"] for n, d in sp.items()
           if d.get("sheet") == sheet and d.get("head_frac", 0) < 0.6 and CAST.get(f"{cid}:{n}")[0].spec["eyes"]]
    return float(np.median(eds))


def actor(who, name, fx, fy, ppm, mirror=False, **opt):
    """a world-shot actor stood on the floor at (fx, fy); opt["path"] as feet [(t, x, y)] is turned into eye points.
    ppm: plate px to the metre, or the plate's key to take it from the floor's perspective at fy"""
    draw = f"family-{who}:{name}"
    if isinstance(ppm, str):
        ppm = ppm_at(ppm, fy)
    ed_p = ed_at(who, ppm) * pose_scale(who, name)
    if "path" in opt:
        opt["path"] = [(t, *at_feet(draw, x, y, ed_p, mirror)) for t, x, y in opt["path"]]
    if "cycle" in opt:
        opt["cycle"] = ([f"family-{who}:{n}" for n in opt["cycle"][0]], opt["cycle"][1])
    if "rest" in opt:
        opt["rest"] = f"family-{who}:{opt['rest']}"
    return (who, draw, at_feet(draw, fx, fy, ed_p, mirror), ed_p, mirror, opt)


# gaze towards characters who are out of frame, in close singles: (screen x -1..1, y + down, head turn)
EYES = {
    "mum": dict(boy=(0.75, 0.25, 0.25), tv=(0.95, 0.0, 0.35), dad=(0.7, 0.02, 0.22), shop=(0.0, 0.0, 0.0)),
    "boy": dict(mum=(-0.85, -0.2, -0.3), tv=(0.9, -0.05, 0.32), dad=(-0.7, -0.25, -0.25)),
    "dad": dict(mum=(-0.75, 0.02, -0.25), boy=(0.7, 0.3, 0.25), shop=(0.8, 0.0, 0.3), tv=(0.8, -0.05, 0.3)),
}


def close(t, who, name, bg, ed=118.0, eye=None, push=(1.0, 1.05), mirror=False, drift=0.7, **kw):
    """a close single: the room soft behind (plate, cx, cy, zoom, blur), the drawing's body running off the frame"""
    eye = eye or ((1140, 430) if mirror else (800, 430))
    return single(t, who, f"family-{who}:{name}", bg, None, ed=ed, eye=eye, push=push, drift=drift, mirror=mirror,
                  **kw)


def medium(t, plate, who, name, fx, fy, ed=112.0, eye=(800, 420), push=(1.0, 1.04), blur=4.0, mirror=False,
           drift=0.6, extra=(), **kw):
    """a single shot in the set at true scale: the character stood at (fx, fy) on the plate's floor, the camera
    framing their eyes at screen `eye` with a screen eye distance `ed` (so the set behind is exactly as big as it
    should be), the set out of focus behind; `extra` actors share the shot"""
    a = actor(who, name, fx, fy, plate, mirror)
    (ex, ey), ed_p = a[2], a[3]
    from studio.paths import BACKGROUNDS
    import cv2
    W1 = cv2.imread(str(BACKGROUNDS / f"{PLATES[plate]}.png")).shape[1] if plate in PLATES else 941
    z = ed / (1920 / W1 * ed_p)
    sc = 1920 / W1 * z
    c0 = (ex - (eye[0] - 960) / sc, ey - (eye[1] - 540) / sc, z)
    k = push[1] / push[0]
    c1 = (c0[0] + (ex - c0[0]) * (1 - 1 / k), c0[1] + (ey - c0[1]) * (1 - 1 / k), z * k)
    return world(t, plate, c0, cam1=c1, drift=drift, blur=blur, layers=[("actors", [a, *extra])], **kw)


def ecu(t, who, name, bg, eye=(900, 400), push=(1.0, 1.06), drift=0.6, size=None, **kw):
    """a big close-up on an expression head (a head-and-shoulders drawing): sized so its shoulders run off the
    bottom of the frame"""
    draw = f"family-{who}:{name}"
    d, info = CAST.get(draw)
    bottom = d.oy + d.size(1.0)[1] / d.S
    ed = (OH_LAYOUT + 24 - eye[1]) * info["ed"] / (bottom - info["anchor"][1])
    return single(t, who, draw, bg, None, ed=ed, eye=eye, push=push, drift=drift, **kw)


OH_LAYOUT = 1080


# the backgrounds of the singles: where each one is (plate, cx, cy, zoom, blur)
MUM_BG = ("LR", 300, 600, 2.0, 5.0)              # Mum in her armchair: the window and the lamp behind her
BOY_BG = ("LR", 640, 760, 2.2, 5.0)              # the boy on the rug: the sofa behind him
TV_BG = {"TW": ("TW", 640, 430, 1.9, 4.5), "TWc": ("TWc", 640, 430, 1.9, 4.5), "TWs": ("TWs", 640, 430, 1.9, 4.5)}

# the telly wall, wide: the boy in the foreground at screen left, the telly at right
PPM_NEAR = None                                   # px to the metre where the boy stands to throw (below)
WIDE = (470, 560, 1.0)

# the throws: the hand that lets go (plate px) and where it lands on the screen (uv on the screen, 0..1)
THROW = {1: dict(t0=m("throw1"), t1=m("smash1"), toy="car", hit=(0.42, 0.44)),
         2: dict(t0=m("throw2"), t1=m("smash2"), toy="ball", hit=(0.52, 0.5))}

BOY_X, BOY_Y = 240, 790                          # the boy's feet when throwing
PPM_NEAR = ppm_at("TW", BOY_Y)
T_SNEAK = m("cut_sneak")

SHOTS = finish([
    # ---------------------------------------------------------------- 1. five minutes of peace
    world(0.0, "LR", (470, 600, 1.0), cams=[(0.0, (470, 590, 1.0)), (m("cut_vroom"), (480, 610, 1.08))], drift=0.4,
          layers=[("actors", [actor("mum", "armchair", 160, 850, "LR"), actor("boy", "play", 590, 880, "LR")])]),
    world(m("cut_vroom"), "TW", (560, 640, 2.4), cam1=(600, 640, 2.5), drift=0.3, layers=[("props", "vroom")]),
    medium(m("cut_mum1"), "LR", "mum", "hips", 260, 880, ed=145, eye=(800, 400), push=(1.0, 1.05)),
    ecu(m("cut_look"), "boy", "smile", BOY_BG, eye=(1000, 470), push=(1.0, 1.03)),
    ecu(m("cut_narrow"), "mum", "angry", MUM_BG, eye=(860, 420), push=(1.0, 1.12)),
    # the telly wall: the boy winds up (the car in his raised hand), lets go, and the screen goes
    world(m("cut_wind1"), "TW", WIDE, drift=0.0,
          layers=[("actors", [actor("boy", "wind", BOY_X, BOY_Y, PPM_NEAR, show=(0, m("throw1"))),
                              actor("boy", "throw", BOY_X + 25, BOY_Y, PPM_NEAR, show=(m("throw1"), 1e9))]),
                  ("props", "held_car"), ("props", "flight1")]),
    world(m("smash1"), "TW", WIDE, drift=0.0,
          layers=[("props", "screen1"), ("occl", "plant"),
                  ("actors", [actor("boy", "throw", BOY_X + 25, BOY_Y, PPM_NEAR)]), ("props", "impact1")]),
    world(m("cut_crack1"), "TW", (700, 420, 2.3), cam1=(700, 425, 2.6), drift=0.2, ease="out",
          layers=[("props", "screen1"), ("occl", "plant"), ("props", "falling1")]),
    medium(m("cut_shock1"), "LR", "mum", "shock", 330, 880, ed=100, eye=(860, 380), push=(1.0, 1.1), drift=0.3),
    world(m("cut_point1"), "TWc", (560, 520, 1.1), cam1=(560, 520, 1.15), drift=0.4,
          layers=[("occl", "plant"), ("actors", [actor("boy", "point", 290, 770, "TWc")]), ("props", "fallen_car")]),
    ecu(m("cut_boy1"), "boy", "smile", TV_BG["TWc"], eye=(900, 470), push=(1.0, 1.06)),
    medium(m("cut_mum2"), "LR", "mum", "crossed", 300, 880, ed=145, eye=(820, 400)),
    # ---------------------------------------------------------------- 2. the call
    close(m("cut_office"), "dad", "phone", ("OF", 260, 330, 1.7, 4.0), ed=104, mirror=True, eye=(1130, 420)),
    medium(m("cut_mumph1"), "TWc", "mum", "phone", 250, 760, ed=135, eye=(760, 420), push=(1.0, 1.02)),
    close(m("cut_dad2"), "dad", "phone", ("OF", 260, 330, 1.7, 4.0), ed=110, mirror=True, eye=(1130, 420)),
    medium(m("cut_mumph2"), "TWc", "mum", "phone", 250, 760, ed=135, eye=(760, 420), push=(1.0, 1.04)),
    world(m("cut_pointing"), "TWc", (560, 520, 1.1), cam1=(560, 520, 1.12), drift=0.3,
          layers=[("occl", "plant"), ("actors", [actor("boy", "point", 290, 770, "TWc")]), ("props", "fallen_car")]),
    ecu(m("cut_dad3"), "dad", "angry", ("OF", 260, 330, 1.7, 4.0), eye=(1020, 400), push=(1.0, 1.08)),
    # ---------------------------------------------------------------- 3. the expensive way home
    ecu(m("cut_car"), "dad", "angry", ("CAR", 330, 300, 1.25, 3.5), eye=(900, 380), push=(1.0, 1.04),
        props=["wheel"]),
    world(m("cut_shop"), "SH", (262, 560, 1.0), cam1=(262, 566, 1.04), drift=0.35,
          layers=[("actors", [actor("dad", "walk1", 40, 712, 150,
                                    path=[(m("cut_shop") - 0.2, 40, 712), (ls("L012") + 0.1, 330, 712)],
                                    cycle=(["walk1", "walk2", "walk3", "walk4"], 4.2), bob=3.0, linear=True,
                                    rest="stand")])]),
    ecu(m("cut_dad4"), "dad", "deadpan", ("SH", 380, 470, 1.9, 4.0), eye=(860, 400)),
    insert(m("cut_reader"), "reader"),
    world(m("cut_hall"), "HA", (258, 425, 1.0), cam1=(258, 432, 1.03), drift=0.3,
          layers=[("actors", [actor("dad", "carry", -120, 560, 150,
                                    path=[(m("cut_hall"), -120, 560), (m("cut_install") - 0.05, 470, 560)],
                                    cycle=(["carry"], 2.4), bob=4.0, linear=True)])]),
    world(m("cut_install"), "TW", (520, 520, 1.04), cam1=(520, 516, 1.08), drift=0.3,
          layers=[("props", "sparkle"), ("occl", "plant"), ("actors", [actor("dad", "install", 540, 790, "TW")])]),
    world(m("cut_ban"), "LR", (470, 610, 1.0), cam1=(500, 610, 1.03), drift=0.3,
          layers=[("actors", [actor("mum", "toys", 60, 845, "LR",
                                    path=[(m("cut_ban"), 60, 845), (le("L015") + 0.3, 720, 845)],
                                    cycle=(["toys"], 2.6), bob=4.0, linear=True)])]),
    medium(m("cut_sulk"), "LR", "boy", "grump", 520, 900, ed=118, eye=(960, 400), push=(1.0, 1.1), drift=0.3),
    # ---------------------------------------------------------------- 4. two weeks later
    insert(m("card_weeks"), "card_weeks"),
    world(m("cut_dad5"), "TW", (500, 405, 1.0), cam1=(500, 400, 1.04), drift=0.3,
          layers=[("occl", "plant"), ("actors", [actor("dad", "shrug", 330, 770, "TW")]), ("props", "toy_box")]),
    medium(m("cut_mum5"), "LR", "mum", "tired", 330, 880, ed=110, eye=(900, 400), push=(1.0, 1.04)),
    insert(m("card_minutes"), "card_minutes"),
    world(T_SNEAK, "TW", WIDE, drift=0.0,
          layers=[("actors", [actor("boy", "walk1", -90, BOY_Y, PPM_NEAR,
                                    path=[(T_SNEAK, -90, BOY_Y), (T_SNEAK + 1.25, BOY_X, BOY_Y)],
                                    cycle=(["walk1", "walk2", "walk3"], 6.0), bob=6.0, rest="sneak")])]),
    world(m("cut_wind2"), "TW", WIDE, drift=0.0,
          layers=[("actors", [actor("boy", "wind", BOY_X, BOY_Y, PPM_NEAR, show=(0, m("throw2"))),
                              actor("boy", "throw", BOY_X + 25, BOY_Y, PPM_NEAR, show=(m("throw2"), 1e9))]),
                  ("props", "flight2")]),
    world(m("smash2"), "TW", WIDE, drift=0.0,
          layers=[("props", "screen2"), ("occl", "plant"),
                  ("actors", [actor("boy", "throw", BOY_X + 25, BOY_Y, PPM_NEAR)]), ("props", "impact2")]),
    world(m("cut_crack2"), "TW", (705, 415, 2.0), cam1=(705, 420, 2.3), drift=0.2, ease="out",
          layers=[("props", "screen2"), ("occl", "plant"), ("props", "falling2")]),
    world(m("cut_run"), "TWs", (470, 455, 1.0), drift=0.5,
          layers=[("occl", "plant"),
                  ("actors", [actor("boy", "point", 640, 790, "TWs"),
                              actor("dad", "panic", 420, 735, "TWs",
                                    path=[(m("cut_run"), -150, 735), (m("cut_run") + 0.3, 420, 735)]),
                              actor("mum", "shock", 170, 780, "TWs",
                                    path=[(m("cut_run") + 0.08, -200, 780), (m("cut_run") + 0.4, 170, 780)])])]),
    ecu(m("cut_dad6"), "dad", "angry", TV_BG["TWs"], eye=(820, 400), push=(1.0, 1.12)),
    ecu(m("cut_boy2"), "boy", "smile", TV_BG["TWs"], eye=(940, 470), push=(1.0, 1.1)),
    medium(m("cut_mum6"), "TWs", "mum", "crossed", 260, 760, ed=145, eye=(820, 400)),
    # ---------------------------------------------------------------- 5. the solution
    world(m("cut_sofa"), "LRs", (470, 590, 1.0), cam1=(500, 600, 1.06), drift=0.3,
          layers=[("actors", [actor("dad", "sofa", 400, 812, "LRs"), actor("mum", "tired", 690, 860, "LRs")])]),
    ecu(m("cut_dad7"), "dad", "worried", TV_BG["TWs"], eye=(1040, 400)),
    ecu(m("cut_mum7"), "mum", "cross", TV_BG["TWs"], eye=(860, 410), push=(1.0, 1.08)),
    ecu(m("cut_dad8"), "dad", "deadpan", TV_BG["TWs"], eye=(1040, 400)),
    world(m("cut_proj"), "TWp", (520, 300, 1.0), cams=[(m("cut_proj"), (520, 300, 1.0)),
                                                       (m("cut_proj") + 1.6, (520, 560, 1.0))], drift=0.2,
          layers=[("props", "projection"), ("actors", [actor("boy", "sit", 470, 790, "TWp")])]),
    ecu(m("cut_boy3"), "boy", "smile", ("TWp", 560, 420, 1.9, 5.0), eye=(960, 460), push=(1.0, 1.1)),
    card(m("cut_black"), "black"),
    card(m("cut_title"), "title"),
    card(m("cut_post"), "black"),
], TL["total"])

TITLE = (("BROKEN TELE", "BEBAS", 220, None, 14, 330, (255, 255, 255)),)
TAGLINE = (("BOY PARENT PROBLEMS", "BEBAS", 70, None, 8, 610, (236, 236, 236)),)
CAPTIONS = []
WHIPS = []


def shot_at(t):
    return _shot_at(SHOTS, t)
