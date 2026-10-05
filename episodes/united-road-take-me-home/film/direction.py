"""The shot list for United Road (Take Me Home): the band on the pub stage, the crowd in front of it, cut on the
bars of the song (timeline.bar), with the lights and the camera playing to the music.

Blocking, front view (plate F, 1x px), from the crowd's left: Šeško (lead guitar), Shaw upstage (backing vocals),
Bruno front and centre (lead vocals), Maguire behind the drums, de Ligt upstage (backing vocals), Cunha (bass),
Mainoo at the keys by the right speaker. The fans in front are cut from the crowd view (plate FC) so they can jump.

The film: the room in the dark, then the lights; the band introduced one by one over the intro; verses cut every two
bars, choruses every bar with the fans jumping; Šeško's solo in a follow spot; the bridge in the dark; the build;
the last choruses as an anthem, the crowd one face after another; Roy, who has stood with a face like thunder all
night, headbanging through the Glory Glory; Cantona; the last chord; the title."""
import math

import numpy as np

from studio.film.shots import card, finish, shot_at as _shot_at, stage
from film.timeline import SONG_END, TL, bar

PLATES = {"F": "pub-and-restaurant/united-pub-stage", "FC": "pub-and-restaurant/united-pub-stage-crowd",
          "PUB": "pub-and-restaurant/pub"}            # PUB: the back of the pub at night (props.plate_image), from the stage


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def stand(x, y0, y1, w=2.2):
    return rect(x - w, y0, x + w, y1)


# the drum kit (in front of whoever is behind it) and the stage monitors (in front of the front row's feet)
KIT = [
    [(717, 333), (735, 326), (760, 323), (785, 329), (805, 341), (809, 352), (795, 358), (770, 356), (745, 350),
     (724, 343)],                                                                         # left crash
    [(741, 393), (760, 386), (800, 386), (813, 393), (813, 463), (800, 471), (752, 471), (741, 463)],     # floor tom
    [(883, 359), (895, 353), (935, 353), (946, 360), (946, 404), (935, 413), (895, 413), (883, 405)],     # rack tom
    [(904, 401), (960, 397), (967, 405), (967, 423), (955, 429), (912, 429), (904, 421)],                 # snare
    [(925, 330), (945, 319), (975, 315), (1000, 319), (1011, 327), (995, 338), (965, 344), (940, 343)],  # right crash
    [(959, 372), (990, 365), (1031, 369), (1036, 377), (1010, 385), (975, 386), (959, 380)],             # hi-hat
    stand(742, 355, 500), stand(965, 342, 500), stand(990, 384, 500), stand(948, 428, 500),
    [(688, 520), (742, 470), (790, 518), (782, 522), (742, 482), (696, 524)],             # left crash legs
    [(915, 515), (965, 468), (1012, 512), (1004, 516), (965, 480), (922, 518)],           # right crash legs
    [(955, 512), (990, 470), (1030, 508), (1022, 512), (990, 482), (962, 515)],           # hi-hat legs
    [(850 + 62 * math.cos(a / 20 * 2 * math.pi), 455 + 62 * math.sin(a / 20 * 2 * math.pi)) for a in range(20)],
]
MONITORS = [[(372, 556), (398, 500), (470, 486), (512, 490), (529, 540), (521, 561), (470, 567), (380, 567)],
            [(1145, 541), (1166, 490), (1212, 485), (1281, 491), (1301, 555), (1291, 567), (1200, 567), (1150, 561)]]
OCCL = {k: {"kit": KIT, "monitors": MONITORS} for k in ("F", "FC")}

# the lamps on the truss: soft beams swinging with the bars
RED, WHITE, AMBER = (1.0, 0.16, 0.10), (1.0, 0.92, 0.82), (1.0, 0.55, 0.15)
BLUE, MAGENTA, CYAN = (0.20, 0.42, 1.0), (1.0, 0.18, 0.66), (0.12, 0.95, 1.0)
LAMPS = {k: [
    dict(at=(527, 112), aim=75, colors=[WHITE, RED, MAGENTA, BLUE], swing=24, power=0.23),
    dict(at=(603, 132), aim=95, colors=[RED, AMBER, MAGENTA, CYAN], swing=28, power=0.24),
    dict(at=(672, 112), aim=100, colors=[BLUE, WHITE, RED, MAGENTA], swing=25, power=0.23),
    dict(at=(836, 112), aim=90, colors=[WHITE, RED, BLUE, CYAN, MAGENTA], swing=30, power=0.27),
    dict(at=(1002, 112), aim=80, colors=[MAGENTA, WHITE, BLUE, RED], swing=25, power=0.23),
    dict(at=(1072, 132), aim=85, colors=[AMBER, RED, CYAN, MAGENTA], swing=28, power=0.24),
    dict(at=(1143, 112), aim=105, colors=[WHITE, BLUE, RED, MAGENTA], swing=24, power=0.23),
] for k in ("F", "FC")}

# ---------------------------------------------------------------- the band (feet, height: 1x px of plate F)
DRUMS = dict(grips={"R": (846, 388), "L": (916, 386)}, len=0.31, h=322, fist=None,
             drums={"hat": (995, 372), "snare": (935, 402), "tom": (778, 394), "crash_l": (765, 338),
                    "crash_r": (968, 326)})
BAND_F = {
    "maguire": dict(who="maguire", draw="harry-maguire:front", feet=(880, 516), h=322, clip=414),
    "shaw": dict(who="shaw", draw="luke-shaw:front", feet=(655, 508), h=312, mic=dict(side=1, drop=0.45)),
    "deligt": dict(who="deligt", draw="matthijs-de-ligt:squad", feet=(1086, 508), h=320, mic=dict(side=1, drop=0.45)),
    "sesko": dict(who="sesko", draw="benjamin-sesko:front", feet=(545, 552), h=368, inst="guitar"),
    "bruno": dict(who="bruno", draw="bruno-fernandes:front", feet=(760, 558), h=362, mic=dict(side=-1, drop=0.5)),
    "cunha": dict(who="cunha", draw="matheus-cunha:front", feet=(968, 552), h=358, inst="bass"),
    "mainoo": dict(who="mainoo", draw="kobbie-mainoo:front", feet=(1212, 548), h=348, inst="keys"),
    "yoro": dict(who="yoro", draw="leny-yoro:squad", feet=(432, 550), h=352, inst="harmonica"),
}
UPSTAGE, FRONT = ("maguire", "shaw", "deligt"), ("yoro", "sesko", "bruno", "cunha", "mainoo")


def band(*names, **over):
    out = []
    for n in names:
        a = dict(BAND_F[n])
        a.update(over.get(n, {}))
        out.append(a)
    return out


def layers(fans=False, focus=None, fg_blur=8.0, bg_blur=5.0, hide=(), **over):
    """the band on the front view: upstage, the kit, the sticks, the front line, the monitors, the fans. focus: the
    performer the lens is on; everyone nearer the camera than them is out of focus, everyone further back too"""
    over = {k: dict(v) for k, v in over.items()}
    if focus:
        near = FRONT if focus in UPSTAGE else ()
        far = UPSTAGE if focus in FRONT else ()
        for n in near:
            over.setdefault(n, {})["blur"] = fg_blur
        for n in far:
            over.setdefault(n, {})["blur"] = bg_blur
        over.setdefault(focus, {})["look_cam"] = True
    up = [n for n in UPSTAGE if n not in hide]
    fr = [n for n in FRONT if n not in hide]
    lay = [("actors", band(*up, **over))]
    if "maguire" not in hide:
        lay.append(("sticks", dict(DRUMS, blur=over.get("maguire", {}).get("blur", 0.0))))
    lay += [("occl", "kit"), ("actors", band(*fr, **over)), ("occl", "monitors")]
    if fans:
        lay.append(("fans", "FC"))
    return lay


def head_top(who):
    a = BAND_F[who]
    return a["feet"][1] - a["h"]


# framing a performer: (centre y as a share of their height below the head's top, the frame's height in heights)
SIZES = {"cu": (0.17, 0.36), "mcu": (0.27, 0.62), "ms": (0.45, 0.98), "full": (0.55, 1.28)}


def frame(who, size, dx=0.0, dy=0.0):
    a = BAND_F[who]
    k, span = SIZES[size]
    if who == "maguire":                                  # the drummer: room for the kit and the sticks
        dy += 0.09
    cy = head_top(who) + k * a["h"] + dy * a["h"]
    return (a["feet"][0] + dx * a["h"], cy, 940.0 / (span * a["h"]))


def pushed(cam, f):
    return (cam[0], cam[1], cam[2] * f) + tuple(cam[3:])


# lighting by section
CALM = dict(lights=0.82, beams=0.78, flash=0.45, punch=0.10, haze=0.20)
VERSE = dict(lights=1.00, beams=1.02, flash=0.72, punch=0.70, haze=0.28)
CHORUS = dict(lights=1.28, beams=1.38, flash=1.35, punch=1.25, shake=0.32, haze=0.40)
ANTHEM = dict(lights=1.48, beams=1.58, flash=1.55, punch=1.45, shake=0.52, haze=0.48, fans_jump=1.38)


def on(who, t0, t1, size="mcu", push=1.06, dx=0.0, dy=0.0, roll=0.0, **kw):
    """a shot on a band member: the lens on them, the rest of the band out of focus, a slow push"""
    c0 = frame(who, size, dx, dy)
    c1 = pushed(c0, push)
    if roll:
        c0, c1 = c0 + (roll,), c1 + (roll * 0.7,)
    # the lens on an upstage player (the drummer, the backing singers) is a stage camera, behind the front line
    hide = kw.pop("hide", FRONT if who in UPSTAGE else ())
    tight = size in ("cu", "mcu")
    lay = layers(fans=kw.pop("fans", False), focus=who, hide=hide,
                 bg_blur=5.0 if tight else 3.0, fg_blur=8.0 if tight else 5.0)
    return stage(t0, "F", [(t0, c0), (t1, c1)], lay, blur=kw.pop("blur", 4.0 if tight else 2.0),
                 occl_blur=kw.pop("occl_blur", 3.0 if who in FRONT and tight else 0.0), rim=kw.pop("rim", 0.5), **kw)


def two(a, b, t0, t1, size="ms", push=1.05, roll=0.0, **kw):
    ca, cb = frame(a, size), frame(b, size)
    fit = 1672.0 / (abs(BAND_F[a]["feet"][0] - BAND_F[b]["feet"][0]) + 0.9 * (BAND_F[a]["h"] + BAND_F[b]["h"]) / 2)
    c0 = ((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2, min(ca[2] * 0.82, cb[2] * 0.82, fit * push ** -1))
    c1 = pushed(c0, push)
    if roll:
        c0, c1 = c0 + (roll,), c1 + (roll * 0.7,)
    hide = FRONT if a in UPSTAGE and b in UPSTAGE else ()
    return stage(t0, "F", [(t0, c0), (t1, c1)], layers(fans=kw.pop("fans", False), hide=hide), blur=1.6,
                 rim=kw.pop("rim", 0.45), **kw)


def dance_floor(t0, y, n, scale):
    """the dance floor between the lens and the stage: a row of fans in silhouette, fists pumping, scarves up"""
    return ("fg_fans", dict(y=y, n=n, seed=int(t0 * 7) % 97, blur=5.0, arms=0.65, scale=scale, rim=0.75))


def wide(t0, t1, c0=(836, 470, 1.0), c1=(836, 452, 1.08), fans=True, **kw):
    lay = layers(fans=fans) + ([dance_floor(t0, 0.83, 15, 0.85)] if kw.pop("floor", True) else [])
    return stage(t0, "F", [(t0, c0), (t1, c1)], lay, rim=kw.pop("rim", 0.35), **kw)


def stage_wide(t0, t1, c0=(836, 372, 1.75), c1=(836, 365, 1.85), **kw):
    lay = layers() + ([dance_floor(t0, 0.86, 13, 0.95)] if kw.pop("floor", True) else [])
    return stage(t0, "F", [(t0, c0), (t1, c1)], lay, rim=kw.pop("rim", 0.4), **kw)


# ---------------------------------------------------------------- the crowd, from the stage
# The camera is on the stage among the band, looking out: the stage floor and its edge across the bottom of the
# frame, the crowd beyond it facing us (their eyes on the band, on the lens), the back of the pub at night behind
# them out of focus (the bar, the fire, the windows), the stage's moving lights sweeping over everything.
CROWD_BG = [(940, 300, 2.0), (360, 280, 2.2), (1330, 300, 2.1), (700, 270, 2.2)]
STAGE_EYES = (960, -260)                              # where the crowd looks (layout px): up at the band, by the lens
SWEEP = dict(n=3, amount=0.22)


def person(who, x, ed, eye_y=430, **kw):
    """someone in the crowd, placed by their eyes (layout px) and eye distance: heads match whatever the drawing's
    proportions. They watch the band"""
    d = dict(who=who, draw=DR[who], eye=(x, eye_y), ed=ed, screen=True,
             look_at=None if who in ("ratcliffe", "berrada") else STAGE_EYES)
    d.update(kw)
    return d


def crowd(t0, t1, people, bg=0, push=1.04, blur=7.0, edge=True, **kw):
    """a crowd shot from the stage: the back of the pub out of focus, the people (back row first) watching the band,
    the stage's own floor and edge in the foreground"""
    c0 = CROWD_BG[bg % len(CROWD_BG)]
    c1 = pushed(c0, push)
    if len(people) > 2 and not any(p.get("cloud") for p in people):
        people = far(people, seed=int(t0 * 3))                 # a packed pub: always more faces at the back
    lay = [("actors", people)]
    if edge:
        lay.append(("stage_edge", dict(y=kw.pop("edge_y", 0.9), monitor=kw.pop("monitor", 1 if bg % 2 else -1),
                                       mic=kw.pop("mic", None), blur=9.0)))
    lights = kw.pop("lights", 0.5)                    # how hard the stage's moving lights work the room
    return stage(t0, "PUB", [(t0, c0), (t1, c1)], lay, blur=blur, grade="crowd", lights=0.0, beams=0.0,
                 sweep=kw.pop("sweep", dict(SWEEP, amount=0.16 + 0.30 * lights)), drift=kw.pop("drift", 0.9),
                 rim=kw.pop("rim", 0.3), rim_color=(1.0, 0.72, 0.45), **kw)


DR = {  # crowd drawings
    "gary": "gary-neville:front", "roy": "roy-keane:front", "rio": "rio-ferdinand:front", "rooney": "wayne-rooney:front",
    "evra": "patrice-evra:front", "carrick": "michael-carrick:front", "ratcliffe": "jim-ratcliffe:front",
    "lammens": "senne-lammens:front", "tielemans": "youri-tielemans:front", "amad": "amad-diallo:squad",
    "mount": "mason-mount:squad", "ugarte": "manuel-ugarte:squad", "zirkzee": "joshua-zirkzee:squad",
    "mbeumo": "bryan-mbeumo:squad", "dalot": "diogo-dalot:squad",
    "martinez": "lisandro-martinez:squad", "yoro": "leny-yoro:squad", "dorgu": "patrick-dorgu:squad",
    "mazraoui": "noussair-mazraoui:squad", "cantona": "eric-cantona:pointing",
    "holland": "steve-holland:front", "berrada": "omar-berrada:front",
}


def trio(a, b, c):
    """three in the crowd: two in front, one behind between them, out of focus"""
    return [person(c, 960, 80, eye_y=372, blur=2.6), person(a, 540, 118, eye_y=468), person(b, 1380, 118, eye_y=468)]


def solo(a, x=960, back=()):
    out = [person(w, bx, 80, eye_y=360, blur=2.8) for w, bx in back]
    return out + [person(a, x, 146, eye_y=440)]


FAR = ("amad", "mount", "dalot", "zirkzee", "mbeumo", "ugarte", "martinez", "dorgu", "mazraoui", "lammens",
       "tielemans", "evra", "holland", "carrick", "rio", "gary")


def far(people, n=7, seed=0):
    """the back of a packed pub: a row of small faces, out of focus, behind everyone in a crowd shot"""
    used = {p["who"] for p in people}
    pool = [w for w in FAR if w not in used]
    pool = pool[seed % len(pool):] + pool[:seed % len(pool)]
    xs = np.linspace(110, 1810, n) + (seed % 3 - 1) * 40
    return [person(w, float(x), 40, eye_y=262, blur=4.2) for w, x in zip(pool, xs)] + people


def misery(who, t0, t1, back, bg=0):
    """the joke: the place going mad, and in the middle of it one face like a wet weekend, rained on"""
    xs = (300, 700, 1220, 1620, 960)
    ppl = [person(w, x, 70, eye_y=350, blur=2.4) for w, x in zip(back, xs)]
    ppl.append(person(who, 960, 120, eye_y=520, cloud=True, dance=1.0))
    return crowd(t0, t1, far(ppl, seed=int(t0)), bg=bg, lights=0.9, push=1.06)


GANG = ("roy", "rooney", "rio", "carrick")          # at the front of the crowd all night


def gang(back=("gary", "evra", "tielemans"), lead=("roy", "rooney")):
    """the four of them: two in front, the other two just behind, more faces at the back"""
    rest = [w for w in GANG if w not in lead]
    out = [person(w, x, 60, eye_y=328, blur=3.0) for w, x in zip(back, (960, 270, 1650))]
    out += [person(rest[0], 420, 86, eye_y=398, blur=1.5), person(rest[1], 1500, 86, eye_y=398, blur=1.5)]
    out += [person(lead[0], 720, 112, eye_y=470), person(lead[1], 1210, 112, eye_y=470)]
    return out


ROW_X = {1: [960], 2: [620, 1300], 3: [380, 960, 1540], 4: [250, 730, 1190, 1670]}


def packed(front, middle=(), back=()):
    """a fuller crowd: big faces in front, three behind them, four at the back"""
    out = [person(w, x, 58, eye_y=322, blur=3.2) for w, x in zip(back, ROW_X.get(len(back), []))]
    out += [person(w, x, 82, eye_y=392, blur=1.7) for w, x in zip(middle, ROW_X.get(len(middle), []))]
    out += [person(w, x, 116, eye_y=472) for w, x in zip(front, ROW_X.get(len(front), []))]
    return out


def whole(front, middle, back):
    """the whole crowd from the stage: three rows of everybody (5, 6 and 7 across)"""
    rows = [(back, 304, 31, 2.4, np.linspace(140, 1780, 7)), (middle, 384, 43, 1.2, np.linspace(250, 1670, 6)),
            (front, 474, 60, 0.0, np.linspace(170, 1750, 5))]
    out = []
    for names, ey, ed, bl, xs in rows:
        out += [person(w, float(x), ed, eye_y=ey, blur=bl) for w, x in zip(names, xs)]
    return out


def reverse(t0, t1, front, middle, back, push=1.05, **kw):
    """the reverse: the camera on the stage looking out over the whole pub, the stage's edge and a monitor below"""
    c0 = (836, 360, 1.35)
    return stage(t0, "PUB", [(t0, c0), (t1, pushed(c0, push))],
                 [("actors", whole(front, middle, back)),
                  ("stage_edge", dict(y=0.79, monitor=kw.pop("monitor", -1), mic=None, blur=8.0))],
                 blur=kw.pop("blur", 5.0), grade="crowd", lights=0.0, beams=0.0,
                 sweep=kw.pop("sweep", dict(SWEEP, n=4, amount=0.16 + 0.30 * kw.pop("lights", 0.8))),
                 drift=kw.pop("drift", 0.7), rim=kw.pop("rim", 0.35), rim_color=(1.0, 0.72, 0.45), **kw)


# ---------------------------------------------------------------- the shots
def b(n, frac=0.0):
    """a time inside bar n (frac of the bar)"""
    return bar(n) + frac * (bar(n + 1) - bar(n))


def lights_up(t):
    """the opening: the stage dark until the lights slam on at bar 2"""
    return 0.85 * (1 - min(1.0, max(0.0, (t - b(1, 0.6)) / (b(2) - b(1, 0.6)))))


SH = []


def add(*shots):
    SH.extend(shots)


# INTRO, bars 0-16: the room in the dark; the lights on bar 2; the band introduced one by one
add(wide(0.0, b(2), (836, 470, 1.0), (836, 455, 1.12), dark=lights_up, lights=0.4, beams=0.0, flash=0.0,
         props="title_over", floor=False),
    stage_wide(b(2), b(3), (836, 380, 1.6), (836, 372, 1.7), **CALM),
    crowd(b(3), b(4), gang(), bg=0),
    on("maguire", b(4), b(6), "mcu", push=1.08, **VERSE),
    on("cunha", b(6), b(8), "ms", push=1.06, dx=0.05, **VERSE),
    on("sesko", b(8), b(10), "ms", push=1.06, dx=-0.05, **VERSE),
    on("mainoo", b(10), b(12), "ms", push=1.06, **VERSE),
    crowd(b(12), b(13), packed(("rio", "evra"), ("ugarte", "carrick", "zirkzee"), ("tielemans", "amad", "mount", "dalot")), bg=2),
    wide(b(13), b(14), (836, 440, 1.2), (836, 425, 1.3), **VERSE),
    on("bruno", b(14), b(16), "mcu", push=1.10, **VERSE))

# VERSE 1, bars 16-27: Bruno sings; every two bars a cut
add(on("bruno", b(16), b(18), "ms", push=1.08, dx=0.04, **VERSE),
    stage_wide(b(18), b(20), (760, 360, 1.9), (800, 355, 2.0), **VERSE),
    on("bruno", b(20), b(21), "cu", push=1.04, **VERSE),
    crowd(b(21), b(22), packed(("rooney", "evra"), ("ugarte", "zirkzee", "tielemans"), ("lammens", "holland", "berrada", "ratcliffe")), bg=1),
    on("bruno", b(22), b(24), "ms", push=1.05, dx=0.08, **VERSE),
    on("sesko", b(24), b(25), "mcu", push=1.06, **VERSE),
    crowd(b(25), b(26), solo("gary", back=(("roy", 1450),)), bg=2),
    two("bruno", "cunha", b(26), b(27), size="ms", **VERSE))

# CHORUS 1, bars 27-36: lights up, the fans jump, a cut every bar
add(wide(b(27), b(28), (836, 430, 1.25), (836, 420, 1.32), **CHORUS),
    on("bruno", b(28), b(29), "mcu", push=1.05, roll=-3.0, **CHORUS),
    crowd(b(29), b(30), gang(back=("gary", "ugarte", "evra")), bg=3, lights=0.7),
    on("maguire", b(30), b(31), "mcu", push=1.08, **CHORUS),
    on("bruno", b(31), b(32), "cu", push=1.05, **CHORUS),
    on("shaw", b(32), b(33), "mcu", push=1.05, roll=-2.0, **CHORUS),
    on("deligt", b(33), b(34), "mcu", push=1.05, roll=2.0, **CHORUS),
    two("sesko", "bruno", b(34), b(35), size="ms", roll=2.5, **CHORUS),
    wide(b(35), b(36), (836, 440, 1.2), (836, 470, 1.0), **CHORUS))

# VERSE 2, bars 36-47
add(on("bruno", b(36), b(38), "mcu", push=1.06, dx=-0.06, **VERSE),
    crowd(b(38), b(39), packed(("ratcliffe", "berrada"), ("holland", "carrick", "lammens"), ("tielemans", "mount", "amad", "dalot")), bg=1),
    on("mainoo", b(39), b(40), "mcu", push=1.06, **VERSE),
    on("bruno", b(40), b(42), "cu", push=1.05, **VERSE),
    two("cunha", "mainoo", b(42), b(43), size="ms", **VERSE),
    crowd(b(43), b(44), solo("roy", back=(("gary", 520), ("rio", 1400))), bg=2),
    on("shaw", b(44), b(45), "mcu", push=1.05, **VERSE),
    on("deligt", b(45), b(46), "mcu", push=1.05, **VERSE),
    stage_wide(b(46), b(47), (836, 372, 1.7), (836, 366, 1.85), **VERSE))

# CHORUS 2, bars 47-57: bigger; Roy's first reluctant nod
add(wide(b(47), b(48), (836, 430, 1.25), (836, 420, 1.32), **CHORUS),
    on("bruno", b(48), b(49), "mcu", push=1.05, roll=3.0, **CHORUS),
    crowd(b(49), b(50), packed(("amad", "dalot"), ("mount", "zirkzee", "dorgu"), ("mazraoui", "martinez", "mbeumo", "ugarte")), bg=3, lights=0.7),
    on("sesko", b(50), b(51), "mcu", push=1.06, roll=-2.5, **CHORUS),
    on("cunha", b(51), b(52), "mcu", push=1.06, **CHORUS),
    crowd(b(52), b(53), solo("roy", back=(("gary", 520), ("evra", 1420))), bg=0, lights=0.7),
    on("maguire", b(53), b(54), "mcu", push=1.08, roll=2.0, **CHORUS),
    on("bruno", b(54), b(55), "cu", push=1.05, **CHORUS),
    on("shaw", b(55), b(55, 0.5), "mcu", push=1.04, roll=-2.0, **CHORUS),
    on("deligt", b(55, 0.5), b(56), "mcu", push=1.04, roll=2.0, **CHORUS),
    on("yoro", b(56), b(57), "ms", push=1.08, **dict(CHORUS, spot=dict(at="yoro", r=110, dark=0.5, fin=0.6))))

# THE HARMONICA, bars 56-64: Yoro in a follow spot; the crowd goes
SOLO = dict(CHORUS, spot=dict(at="yoro", r=105, dark=0.6), flash=1.2)
add(stage_wide(b(57), b(58), (640, 372, 1.6), (610, 376, 1.75), **SOLO),
    on("yoro", b(58), b(59), "mcu", push=1.08, roll=-4.0, **SOLO),
    two("yoro", "sesko", b(59), b(60), size="ms", roll=3.0, **SOLO),
    reverse(b(60), b(61), ("evra", "rio", "roy", "rooney", "carrick"), ("gary", "tielemans", "ugarte", "zirkzee", "lammens", "holland"), ("ratcliffe", "berrada", "amad", "mount", "dorgu", "mbeumo", "dalot"), lights=0.9),
    on("yoro", b(61), b(62), "mcu", push=1.08, dy=0.03, **SOLO),
    on("bruno", b(62), b(63), "ms", push=1.04, **CHORUS),
    on("yoro", b(63), b(64), "ms", push=1.12, roll=-5.0, **SOLO))

# BRIDGE, bars 64-72: the room goes dark; Bruno alone in a spot; the crowd swaying
BRIDGE = dict(CALM, spot=dict(at="bruno", r=110, dark=0.62), beams=0.35, haze=0.35)
add(stage_wide(b(64), b(66), (836, 380, 1.6), (780, 330, 2.6), **BRIDGE),
    on("bruno", b(66), b(68), "mcu", push=1.10, **BRIDGE),
    crowd(b(68), b(69), packed(("carrick", "ratcliffe"), ("tielemans", "holland", "berrada"), ("lammens", "dalot", "mount", "amad")), bg=2, lights=0.3),
    on("bruno", b(69), b(70), "cu", push=1.05, **BRIDGE),
    crowd(b(70), b(71), gang(lead=("rio", "carrick"), back=("gary", "lammens", "tielemans")), bg=3, lights=0.3),
    on("bruno", b(71), b(72), "cu", push=1.08, **BRIDGE))

# BUILD, bars 72-75: the drums come in; a cut on every bar; the camera pulls back
add(on("maguire", b(72), b(73), "mcu", push=1.10, **VERSE),
    on("bruno", b(73), b(74), "mcu", push=1.08, **VERSE),
    wide(b(74), b(75), (836, 380, 1.6), (836, 470, 1.0), **CHORUS))

# CHORUS 3, bars 75-83: the explosion
add(stage_wide(b(75), b(76), (836, 372, 1.7), (836, 362, 1.9), **ANTHEM),
    on("bruno", b(76), b(77), "mcu", push=1.05, roll=-3.0, **ANTHEM),
    crowd(b(77), b(78), packed(("zirkzee", "mbeumo"), ("ugarte", "martinez", "lammens"), ("dorgu", "amad", "dalot", "mazraoui")), bg=0, lights=0.8),
    on("sesko", b(78), b(79), "ms", push=1.06, roll=3.0, **ANTHEM),
    crowd(b(79), b(80), gang(back=("gary", "zirkzee", "evra")), bg=1, lights=0.8),
    on("cunha", b(80), b(81), "ms", push=1.06, **ANTHEM),
    on("maguire", b(81), b(82), "mcu", push=1.08, **ANTHEM),
    wide(b(82), b(83), (836, 420, 1.3), (836, 470, 1.0), **ANTHEM))

# OUTRO, bars 83-97: the anthem; the crowd one face after another
add(stage_wide(b(83), b(84), (836, 372, 1.7), (836, 365, 1.85), **ANTHEM),
    misery("ratcliffe", b(84), b(85), back=("gary", "rooney", "evra", "rio", "ugarte"), bg=2),
    on("bruno", b(85), b(86), "mcu", push=1.05, roll=2.5, **ANTHEM),
    reverse(b(86), b(87), ("rio", "carrick", "roy", "rooney", "gary"), ("evra", "ugarte", "tielemans", "lammens", "zirkzee", "holland"), ("berrada", "ratcliffe", "dorgu", "mazraoui", "mbeumo", "martinez", "amad"), lights=0.8),
    on("mainoo", b(87), b(88), "ms", push=1.06, **ANTHEM),
    crowd(b(88), b(89), gang(lead=("rooney", "rio"), back=("evra", "ugarte", "gary")), bg=0, lights=0.8),
    on("shaw", b(89), b(89, 0.5), "mcu", push=1.04, roll=-2.5, **ANTHEM),
    on("deligt", b(89, 0.5), b(90), "mcu", push=1.04, roll=2.5, **ANTHEM),
    crowd(b(90), b(91), packed(("tielemans", "lammens"), ("ugarte", "zirkzee", "evra"), ("amad", "mount", "dalot", "mbeumo")), bg=1, lights=0.8),
    on("bruno", b(91), b(92), "cu", push=1.05, **ANTHEM),
    wide(b(92), b(93), (836, 440, 1.2), (836, 425, 1.3), **ANTHEM),
    crowd(b(93), b(94), solo("roy", back=(("gary", 520), ("rio", 1400))), bg=2, lights=0.8),
    on("sesko", b(94), b(95), "mcu", push=1.06, roll=-3.0, **ANTHEM),
    misery("berrada", b(95), b(96), back=("carrick", "tielemans", "lammens", "zirkzee", "amad"), bg=3),
    on("maguire", b(96), b(97), "mcu", push=1.08, **ANTHEM))

# FINALE, bars 97-108: To Old Trafford... Glory, glory Man United: Roy goes
add(wide(b(97), b(98), (836, 470, 1.0), (836, 440, 1.2), **ANTHEM),
    on("bruno", b(98), b(99), "mcu", push=1.05, **ANTHEM),
    reverse(b(99), b(100), ("carrick", "rooney", "roy", "rio", "gary"), ("tielemans", "evra", "ugarte", "holland", "zirkzee", "lammens"), ("amad", "mount", "zirkzee", "mbeumo", "dalot", "martinez", "ratcliffe"), lights=0.95),
    stage_wide(b(100), b(101), (836, 372, 1.7), (836, 365, 1.85), **ANTHEM),
    on("bruno", b(101), b(102), "cu", push=1.05, **ANTHEM),
    crowd(b(102), b(103), gang(lead=("rooney", "roy"), back=("evra", "zirkzee", "gary")), bg=1, lights=0.9),
    on("cunha", b(103), b(104), "ms", push=1.06, roll=3.0, **ANTHEM),
    wide(b(104), b(105), (836, 430, 1.25), (836, 420, 1.3), **ANTHEM),
    crowd(b(105), b(106, 0.5), solo("roy", back=(("gary", 500), ("rio", 1420))), bg=2, lights=1.0, shake=0.6),
    crowd(b(106, 0.5), b(107), gang(back=("gary", "evra", "tielemans")), bg=3, lights=1.0, shake=0.6),
    on("bruno", b(107), b(108), "mcu", push=1.06, roll=-3.0, **ANTHEM))

# CANTONA, bars 108-111: Give Cantona on his own
add(crowd(b(108), b(108, 0.5), gang(back=("gary", "evra", "ugarte")), bg=0, lights=0.6),
    crowd(b(108, 0.5), b(110), [person("cantona", 900, 92, eye_y=300)], bg=1, blur=9.0,
          lights=0.5, spot=dict(at="cantona", r=420, dark=0.55, fin=0.15)),
    on("bruno", b(110), b(111), "ms", push=1.05, **ANTHEM))

# CODA, bars 111-116: everyone; the last chord; the end card over the cheering
add(wide(b(111), b(113), (836, 430, 1.25), (836, 470, 1.0), **ANTHEM),
    stage_wide(b(113), b(115), (836, 372, 1.7), (836, 400, 1.45), **ANTHEM),
    wide(b(115), SONG_END, (836, 470, 1.0), (836, 470, 1.04), **ANTHEM),
    card(SONG_END, "title"))

# a frame shows the instant it starts at: every cut half a frame early lands on the frame nearest its beat
for _s in SH[1:]:
    _s["t"] -= 0.5 / 30
SHOTS = finish(SH, TL["total"])

TITLE = (("UNITED ROAD", "BEBAS", 160, None, 14, 330, (255, 255, 255)),
         ("TAKE ME HOME", "BEBAS", 104, None, 14, 500, (255, 255, 255)))
TAGLINE = (("MANCHESTER UNITED", "BEBAS", 54, None, 10, 760, (236, 236, 236)),)
CAPTIONS = [
    (b(4, 0.12), b(6) - 0.15, "name", "HARRY MAGUIRE", "Drums."),
    (b(6, 0.12), b(8) - 0.15, "name", "MATHEUS CUNHA", "Bass."),
    (b(8, 0.12), b(10) - 0.15, "name", "BENJAMIN ŠEŠKO", "Lead guitar."),
    (b(10, 0.12), b(12) - 0.15, "name", "KOBBIE MAINOO", "Keys."),
    (b(32, 0.08), b(33) - 0.1, "name", "LUKE SHAW", "Backing vocals."),
    (b(33, 0.08), b(34) - 0.1, "name", "MATTHIJS DE LIGT", "Backing vocals."),
    (b(56, 0.15), b(57) - 0.1, "name", "LENY YORO", "Harmonica."),
    (b(84, 0.1), b(85) - 0.1, "name", "JIM RATCLIFFE", "Co-owner. Not singing."),
    (b(95, 0.1), b(96) - 0.1, "name", "OMAR BERRADA", "Chief executive. Checking ticket prices."),
    (b(14, 0.12), b(16) - 0.15, "name", "BRUNO FERNANDES", "Lead vocals. Captain."),
    (b(108, 0.6), b(110) - 0.15, "name", "ERIC CANTONA", "On his own."),
]
WHIPS = []
STROBE = [(b(35, 0.72), b(36)), (b(56, 0.72), b(57)), (b(63, 0.35), b(64)),
          (b(82, 0.72), b(83)), (b(107, 0.55), b(108)), (b(115, 0.30), b(115, 0.90))]


def shot_at(t):
    return _shot_at(SHOTS, t)
