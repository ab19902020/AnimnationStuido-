"""The shot list: every cut, camera move and walk, keyed to the dialogue edit (timeline.py).

Where everyone is. The living room (plates LR, the wide with the sofa, and TW, the telly wall): the telly is on its
unit at screen right; Mum's armchair is screen left, facing it; the boy plays on the rug between them. So Mum looks
screen right to the boy and the telly, the boy looks left up to Mum and right to the telly. On the phone Mum faces
right and Dad (in his office, mirrored) faces left, so they look at each other across the cut.

The grammar: wides at true scale in the family's own rooms, where the walking, throwing and smashing happen (pose
drawings swapped on the action, as the drawings are made); close singles for every line, the room soft behind them,
the face acting; inserts on the props that change the story (the screen cracking, the card reader, the cards)."""
import json

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
          "TWp": "home/family-living-room-tv-wall"}
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


def actor(who, name, fx, fy, ppm, mirror=False, **opt):
    """a world-shot actor stood on the floor at (fx, fy); opt["path"] as feet [(t, x, y)] is turned into eye points"""
    draw = f"family-{who}:{name}"
    # every pose of a character is drawn at the same scale on its sheets: size them all as the standing drawing
    # (their own eye spacing varies with the expression and the turn of the head)
    ed_p = ed_at(who, ppm) * CAST.get(draw)[1]["ed"] / CAST.get(DRAW[who])[1]["ed"]
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


def ecu(t, who, name, bg, eye=(900, 400), push=(1.0, 1.06), drift=0.6, **kw):
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
PPM_NEAR = 360                                    # px to the metre where the boy stands to throw
WIDE = (470, 560, 1.0)

# the throws: the hand that lets go (plate px) and where it lands on the screen (uv on the screen, 0..1)
THROW = {1: dict(t0=m("throw1"), t1=m("smash1"), toy="car", hit=(0.42, 0.44)),
         2: dict(t0=m("throw2"), t1=m("smash2"), toy="ball", hit=(0.52, 0.5))}

BOY_X, BOY_Y = 240, 860                          # the boy's feet when throwing
T_SNEAK = m("cut_sneak")

SHOTS = finish([
    # ---------------------------------------------------------------- 1. five minutes of peace
    world(0.0, "LR", (470, 700, 1.0), cams=[(0.0, (470, 690, 1.0)), (m("cut_vroom"), (480, 712, 1.08))], drift=0.4,
          layers=[("actors", [actor("mum", "armchair", 175, 990, 270, rest="armchair"),
                              actor("boy", "play", 600, 958, 285)])]),
    world(m("cut_vroom"), "TW", (560, 640, 2.4), cam1=(600, 640, 2.5), drift=0.3, layers=[("props", "vroom")]),
    close(m("cut_mum1"), "mum", "hips", MUM_BG, ed=150, eye=(820, 400), push=(1.0, 1.06)),
    ecu(m("cut_look"), "boy", "smile", BOY_BG, eye=(1000, 410), push=(1.0, 1.03)),
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
    single(m("cut_shock1"), "mum", "family-mum:shock", MUM_BG, None, ed=96, eye=(860, 400), push=(1.0, 1.12),
           drift=0.3),
    world(m("cut_point1"), "TWc", (560, 540, 1.15), cam1=(560, 540, 1.2), drift=0.4,
          layers=[("occl", "plant"), ("actors", [actor("boy", "point", 300, 770, 300)]), ("props", "fallen_car")]),
    ecu(m("cut_boy1"), "boy", "smile", TV_BG["TWc"], eye=(900, 410), push=(1.0, 1.06)),
    close(m("cut_mum2"), "mum", "crossed", MUM_BG, ed=150, eye=(840, 400)),
    # ---------------------------------------------------------------- 2. the call
    close(m("cut_office"), "dad", "phone", ("OF", 260, 330, 1.7, 4.0), ed=104, mirror=True, eye=(1130, 420)),
    close(m("cut_mumph1"), "mum", "phone", TV_BG["TWc"], ed=104, eye=(760, 420)),
    close(m("cut_dad2"), "dad", "phone", ("OF", 260, 330, 1.7, 4.0), ed=110, mirror=True, eye=(1130, 420)),
    close(m("cut_mumph2"), "mum", "phone", TV_BG["TWc"], ed=110, eye=(760, 420), push=(1.0, 1.04)),
    world(m("cut_pointing"), "TWc", (560, 540, 1.15), cam1=(560, 540, 1.17), drift=0.3,
          layers=[("occl", "plant"), ("actors", [actor("boy", "point", 300, 770, 300)]), ("props", "fallen_car")]),
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
          layers=[("props", "sparkle"), ("occl", "plant"), ("actors", [actor("dad", "install", 470, 800, 300)])]),
    world(m("cut_ban"), "LR", (470, 720, 1.0), cam1=(500, 720, 1.03), drift=0.3,
          layers=[("actors", [actor("mum", "toys", 60, 965, 250,
                                    path=[(m("cut_ban"), 60, 965), (le("L015") + 0.3, 720, 965)],
                                    cycle=(["toys"], 2.6), bob=4.0, linear=True)])]),
    single(m("cut_sulk"), "boy", "family-boy:grump", BOY_BG, None, ed=112, eye=(960, 400), push=(1.0, 1.1),
           drift=0.3),
    # ---------------------------------------------------------------- 4. two weeks later
    insert(m("card_weeks"), "card_weeks"),
    world(m("cut_dad5"), "TW", (500, 520, 1.0), cam1=(500, 516, 1.04), drift=0.3,
          layers=[("occl", "plant"), ("actors", [actor("dad", "shrug", 330, 790, 270)]), ("props", "toy_box")]),
    single(m("cut_mum5"), "mum", "family-mum:tired", MUM_BG, None, ed=104, eye=(900, 410), push=(1.0, 1.04)),
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
    world(m("cut_run"), "TWs", (470, 545, 1.0), drift=0.5,
          layers=[("occl", "plant"),
                  ("actors", [actor("boy", "point", 610, 760, 290),
                              actor("dad", "panic", 420, 800, 280,
                                    path=[(m("cut_run"), -150, 800), (m("cut_run") + 0.3, 420, 800)]),
                              actor("mum", "shock", 135, 870, 310,
                                    path=[(m("cut_run") + 0.08, -200, 870), (m("cut_run") + 0.4, 135, 870)])])]),
    ecu(m("cut_dad6"), "dad", "angry", TV_BG["TWs"], eye=(820, 400), push=(1.0, 1.12)),
    ecu(m("cut_boy2"), "boy", "smile", TV_BG["TWs"], eye=(940, 410), push=(1.0, 1.1)),
    close(m("cut_mum6"), "mum", "crossed", TV_BG["TWs"], ed=150, eye=(820, 400)),
    # ---------------------------------------------------------------- 5. the solution
    world(m("cut_sofa"), "TWs", (470, 600, 1.0), cam1=(470, 600, 1.05), drift=0.3,
          layers=[("occl", "plant"),
                  ("actors", [actor("dad", "sofa", 300, 900, 300), actor("mum", "tired", 690, 905, 300)])]),
    ecu(m("cut_dad7"), "dad", "worried", TV_BG["TWs"], eye=(1040, 400)),
    ecu(m("cut_mum7"), "mum", "cross", TV_BG["TWs"], eye=(860, 410), push=(1.0, 1.08)),
    ecu(m("cut_dad8"), "dad", "deadpan", TV_BG["TWs"], eye=(1040, 400)),
    world(m("cut_proj"), "TWp", (520, 300, 1.0), cams=[(m("cut_proj"), (520, 300, 1.0)),
                                                       (m("cut_proj") + 1.6, (520, 560, 1.0))], drift=0.2,
          layers=[("props", "projection"), ("actors", [actor("boy", "sit", 470, 790, 300)])]),
    ecu(m("cut_boy3"), "boy", "smile", ("TWp", 560, 420, 1.9, 5.0), eye=(960, 400), push=(1.0, 1.1)),
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
