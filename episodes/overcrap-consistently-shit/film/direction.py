"""The shot list: every cut and camera move, keyed to the dialogue edit (timeline.py). Portrait (EP_RES=1080x1920,
YouTube Shorts); the same list frames a landscape film too.

Where everyone is (the Overcrap Daily studio, Pass Mic's front view: the long desk, Manchester at night through the
window): Mark in the big chair left of centre, Gary in the chair on the right. So Mark looks screen right to Gary and
Gary looks screen left to Mark, in every shot; Gary's last line goes into the lens.

Everyone is a whole upper-body drawing from his model sheet, exactly as drawn (arms, hands and ears his own), sitting
at his seat in the plate at true scale (a `world` shot) with the desk and what is on it in front of his waist. The
face acts on the drawing: his own drawn mouths for the lip sync (film.yaml mouths), eyes, brows, blinks and nods; the
drawings with a drawn-open shouting mouth are held on the shouted words. A pose changes only on a cut.

The layout is the Shorts debate: a split screen, Mark above and Gary below, so the one listening reacts live under
the line; full-screen singles punch in on the big beats (WORST, the slump, SHOVEL, Gary's last line)."""
import json
import math

from studio.film import ep
from studio.film.cast import CAST
from studio.film.engine import VERTICAL
from studio.film.shots import Marks, card, finish, shot_at as _shot_at, world
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt, we = T.m, T.ls, T.le, T.wt, T.we

PLATES = {"S": "tv-and-media/overcrap-studio-front"}


def capsule(a, b, r, n=10):
    """a rounded bar from a to b, r wide each side (1x plate px) -> polygon"""
    (x0, y0), (x1, y1) = a, b
    ang = math.atan2(y1 - y0, x1 - x0)
    pts = [(x1 + r * math.cos(ang + math.pi / 2 - math.pi * k / n), y1 + r * math.sin(ang + math.pi / 2 - math.pi * k / n))
           for k in range(n + 1)]
    pts += [(x0 + r * math.cos(ang - math.pi / 2 - math.pi * k / n), y0 + r * math.sin(ang - math.pi / 2 - math.pi * k / n))
            for k in range(n + 1)]
    return pts


def ellipse(c, r, n=24):
    return [(c[0] + r[0] * math.cos(2 * math.pi * k / n), c[1] + r[1] * math.sin(2 * math.pi * k / n)) for k in range(n)]


# what is in front of the actors (1x plate px), from Pass Mic's studio_front_a.json: the desk and the things on it
DESK = [(172, 628), (185, 612), (215, 604), (260, 598), (330, 595), (400, 592), (480, 589), (560, 586), (700, 584),
        (850, 586), (950, 588), (1050, 590), (1130, 593), (1200, 597), (1280, 602), (1340, 608), (1380, 616),
        (1400, 628), (1400, 941), (172, 941)]
MIC = [capsule((603, 512), (674, 461), 19), ellipse((600, 518), (13, 13)), capsule((522, 452), (598, 492), 6),
       capsule((583, 522), (583, 580), 7)]
THINGS = [[(632, 550), (690, 550), (690, 612), (632, 612)], ellipse((624, 580), (14, 17)),           # the red mug
          [(362, 495), (545, 493), (560, 600), (370, 604), (352, 560), (356, 520)],                    # the laptop
          [(1123, 552), (1169, 552), (1169, 617), (1123, 617)], [(1176, 548), (1227, 548), (1227, 617), (1176, 617)],
          [(1234, 612), (1245, 560), (1258, 548), (1300, 548), (1300, 612)],                           # the tablet
          [(1330, 568), (1412, 568), (1412, 604), (1330, 604)],
          [(935, 590), (960, 578), (1120, 578), (1130, 592), (935, 596)]]                              # the notebook
OCCL = {"S": {"desk": [DESK] + MIC + THINGS}}

# where each one sits: the point between his eyes (1x plate px, Pass Mic's seats) and his eye distance there; Gary's
# chair is further back
SEAT = {"mark": ((755, 443), 36.0), "gary": ((1200, 455), 26.0)}
# the slumped drawings (no face to place them by): their head's centre this many eye distances below the seat's eyes,
# so the drawn desk under the elbow is behind the real one
SEAT_DY = {"hoodie_slump": 1.9, "slump": 2.2}
# ...and sideways (eye distances): Gary's slumped head clear of the mugs on his desk
SEAT_DX = {"slump": -3.6}
CID = {"mark": "mark-goldbridge", "gary": "gary-neville"}
# off-screen eyelines (singles, and each half of a split): screen direction (x: -1 left .. 1 right, y: + down), turn
EYES = {"mark": dict(gary=(0.85, 0.05, 0.25)), "gary": dict(mark=(-0.85, 0.05, -0.25))}
MIRROR = set()
# the same head size on screen for both: their eye distances in sheet px are measured on differently drawn heads
EDK = {"mark": 1.0, "gary": 0.82}

LW, LH = (1080, 1920) if VERTICAL else (1920, 1080)      # the layout the shots are framed in (screen px)
S1 = LW / 1672                  # screen px per plate px at zoom 1


def seat(who, pose):
    """an actor at his seat: the drawing placed by the point between its eyes (a faceless one by its head)"""
    key = f"{CID[who]}:{pose}"
    (x, y), ed = SEAT[who]
    return (who, key, (x + SEAT_DX.get(pose, 0.0) * ed, y + SEAT_DY.get(pose, 0.0) * ed), ed, key in MIRROR)


def framed(a, sx, sy, ed_screen):
    """the camera that puts an actor's eyes at screen (sx, sy) with an eye distance of ed_screen px"""
    z = ed_screen / (a[3] * S1)
    s = S1 * z
    ex, ey = a[2]
    return (ex - (sx - LW / 2) / s, ey - (sy - LH / 2) / s, z)


def push(cam, f):
    return (cam[0], cam[1], cam[2] * f)


LAYERS = lambda *acts: [("actors", list(acts)), ("occl", "desk")]


def single(t, who, pose, ed_screen=150.0, push_to=1.04, end=None, crash=None, punch=None, shakes=(), blur=4.0):
    """a full-screen single: the camera pushed in on his seat, his eyes a third of the way down (portrait) with look
    room towards the other man, the window behind softened. crash = the eye distance a crash zoom starts from (it
    snaps in to ed_screen in 0.12 s); punch = (t, factor) a 3-frame snap in; shakes = [(t0, t1, px)] a jolt"""
    a = seat(who, pose)
    ed_screen *= EDK[who]
    crash = crash and crash * EDK[who]
    if VERTICAL:
        sx, sy = (600 if who == "mark" else 480), 720
    else:
        sx, sy, ed_screen, crash = (860 if who == "mark" else 1060), 430, ed_screen * 0.8, crash and crash * 0.8
    c0 = framed(a, sx, sy, ed_screen)
    t1 = end or t + 3.0
    cams = [(t, c0), (t1, push(c0, push_to))]
    if crash:
        cams = [(t, framed(a, sx, sy, crash)), (t + 0.12, c0), (t1, push(c0, push_to))]
    if punch:
        tp, f = punch
        u = (tp - t) / max(1e-3, t1 - t)
        cp = push(c0, 1 + (push_to - 1) * u)
        cams = [(t, c0), (tp, cp), (tp + 0.1, push(cp, f)), (t1, push(cp, f * (1 + (push_to - 1) * 0.3)))]
    return world(t, "S", cams[0][1], cams=cams, layers=LAYERS(a), drift=0.45, blur=blur, shakes=list(shakes),
                 who=who, eye=(sx, sy), ed=ed_screen)


def split(t, mpose, gpose, end, push_to=(1.0, 1.0), still=False, over=("badge",), punch=None):
    """the Shorts debate: Mark in his chair above, Gary in his below, the badge on the divider (the plate's own
    two-shot across the desk in landscape). push_to: each half's slow push (Mark, Gary); punch = (who, t, factor)"""
    dur = max(0.1, end - t)
    if not VERTICAL:
        cam = (978, 470, 1.9)
        return world(t, "S", cam, cams=[(t, cam), (t + dur, cam)],
                     layers=LAYERS(seat("mark", mpose), seat("gary", gpose)), drift=0.35, blur=1.5, still=still)
    parts = []
    for k, (who, pose, sx, pz) in enumerate((("mark", mpose, 580, push_to[0]), ("gary", gpose, 500, push_to[1]))):
        a = seat(who, pose)
        c0 = framed(a, sx, 820, 112.0 * EDK[who])          # his eyes a third of the way down his half
        cams = [(t, c0), (t + dur, push(c0, pz))]
        if punch and punch[0] == who:
            tp, f = punch[1], punch[2]
            u = (tp - t) / dur
            cp = push(c0, 1 + (pz - 1) * u)
            cams = [(t, c0), (tp, cp), (tp + 0.1, push(cp, f)), (t + dur, push(cp, f))]
        sub = world(t, "S", c0, cams=cams, layers=LAYERS(a), drift=0.3, blur=2.5, free=True, who=who)
        sub.update(i=90 + k, end=t + dur)
        parts.append(sub)
    return dict(t=t, kind="split", parts=parts, still=still, over=list(over))


SHOTS = finish([
    split(0.0, "hoodie_arms", "arms", wt("L001", "worst") - 0.04, push_to=(1.04, 1.0)),     # "That is the..."
    single(wt("L001", "worst") - 0.04, "mark", "hoodie_both", ed_screen=160, crash=110, push_to=1.02,
           end=wt("L001", "half"), shakes=[(wt("L001", "worst"), wt("L001", "worst") + 0.45, 10.0)]),    # "WORST!"
    split(wt("L001", "half"), "hoodie_point", "arms", wt("L001", "since") - 0.03,
          push_to=(1.03, 1.0)),                                                             # "...half of football"
    single(wt("L001", "since") - 0.03, "mark", "hoodie_shrug", ed_screen=140, push_to=1.05,
           end=m("slump")),                                                                 # "...a bloody kid!"
    single(m("slump"), "mark", "hoodie_slump", ed_screen=135, push_to=1.0, end=m("cut_gary1")),  # the slump
    split(m("cut_gary1"), "hoodie_slump", "crossed", wt("L002", "manchester") - 0.04,
          push_to=(1.0, 1.04)),                                                             # "I said three weeks ago..."
    single(wt("L002", "manchester") - 0.04, "gary", "crossed", ed_screen=150, push_to=1.03,
           end=m("cut_gary2")),                                                             # "...Manchester United"
    single(m("cut_gary2"), "gary", "arms", ed_screen=165, push_to=1.06, end=m("cut_laugh")),  # "...a fucking challenge."
    single(m("cut_laugh"), "mark", "hoodie_crossed", ed_screen=145, push_to=1.0, end=m("cut_mark2")),  # the wheeze
    split(m("cut_mark2"), "hoodie_point", "crossed", wt("L004", "these") - 0.04,
          push_to=(1.04, 1.0)),                                                             # "Honestly, Gary..."
    single(wt("L004", "these") - 0.04, "mark", "hoodie_arms", ed_screen=150, push_to=1.06,
           end=wt("L004", "shovel") - 0.04),                                                # "...these idiots..."
    single(wt("L004", "shovel") - 0.04, "mark", "hoodie_fist", ed_screen=165, crash=115, push_to=1.02,
           shakes=[(wt("L004", "shovel"), wt("L004", "shovel") + 0.45, 10.0)], end=m("cut_palm")),   # "SHOVEL!"
    single(m("cut_palm"), "gary", "slump", ed_screen=140, push_to=1.0, end=m("cut_mark3")),   # Gary: head in hand
    split(m("cut_mark3"), "hoodie_arms", "arms", m("cut_gary3"), push_to=(1.03, 1.0)),       # "Still... at least..."
    single(m("cut_gary3"), "gary", "arms", ed_screen=160, push_to=1.07, end=m("cut_nod")),   # "Yeah." ... "being shit."
    single(m("cut_nod"), "mark", "hoodie_arms", ed_screen=145, push_to=1.0, end=m("toast")),  # the nod
    split(m("toast"), "hoodie_arms", "arms", m("black"), over=("badge", "toast")),           # NEW LOW UNLOCKED
    card(m("black"), "black"),
], TL["total"])

TITLE = ()
TAGLINE = ()
# small name straps (never over a face)
CAPTIONS = [
    (wt("L001", "since") + 0.1, m("slump") - 0.05, "name", "MARK GOLDBRIDGE", "Overcrap Daily. Furious."),
    (wt("L002", "manchester") + 0.08, m("cut_gary2") - 0.05, "name", "GARY NEVILLE", "Called it three weeks ago."),
]
WHIPS = []


def shot_at(t):
    return _shot_at(SHOTS, t)
