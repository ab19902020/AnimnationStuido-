"""The shot list: every cut and camera move, keyed to the dialogue edit (timeline.py). Portrait first (EP_RES=1080x1920,
YouTube Shorts); the same list frames a landscape film too.

Where everyone is (the Overcrap Daily studio, Pass Mic's front view: the long desk, Manchester at night through the
window): Mark in the big chair left of centre, Gary in the chair on the right. So Mark looks screen right to Gary and
Gary looks screen left to Mark, in every shot; Gary's last line goes into the lens.

Everyone is a whole drawing from his model sheet (an expression bust, or an upper-body pose) sitting at his seat in
the plate at true scale (a `world` shot): the desk and the things on it (the mic, the mugs, the laptop) are drawn in
front of him, so the bottom of a bust is always behind the desk. Singles are the camera pushed in on one seat, the
window behind softened; a two-shot is a split screen in portrait (Mark above, Gary below) and the plate's own
two-shot in landscape. The jokes are the faces: every reaction is its own cut, to its own drawn expression."""
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

# where each one sits: the point between his eyes (1x plate px, Pass Mic's seats) and his eye distance there
SEAT = {"mark": ((755, 432), 36.0), "gary": ((1200, 459), 32.0)}
CID = {"mark": "mark-goldbridge", "gary": "gary-neville"}
# off-screen eyelines (singles): screen direction (x: -1 left .. 1 right, y: + down) and head turn
EYES = {"mark": dict(gary=(0.85, 0.05, 0.25)), "gary": dict(mark=(-0.85, 0.05, -0.25))}
# Gary's drawings face the viewer's right (away from Mark): turned round to face him
MIRROR = {"gary-neville:h_sad", "gary-neville:u_crossed"}

LW, LH = (1080, 1920) if VERTICAL else (1920, 1080)      # the layout the shots are framed in (screen px)
S1 = LW / 1672                  # screen px per plate px at zoom 1


def seat(who, pose):
    """an actor at his seat: the drawing placed by the point between its eyes. A bust (h_) sits an eye-width lower,
    so that its drawn chest, not the plain cloth continued under it, meets the desk"""
    key = f"{CID[who]}:{pose}"
    (x, y), ed = SEAT[who]
    if pose.startswith("h_"):
        y += 0.9 * ed
    return (who, key, (x, y), ed, key in MIRROR)


def framed(a, sx, sy, ed_screen):
    """the camera that puts an actor's eyes at screen (sx, sy) with an eye distance of ed_screen px"""
    z = ed_screen / (a[3] * S1)
    s = S1 * z
    ex, ey = a[2]
    return (ex - (sx - LW / 2) / s, ey - (sy - LH / 2) / s, z)


def push(cam, f):
    return (cam[0], cam[1], cam[2] * f)


LAYERS = lambda *acts: [("actors", list(acts)), ("occl", "desk")]


def single(t, who, pose, ed_screen=170.0, push_to=1.04, end=None, crash=None, punch=None, shakes=(), blur=5.0):
    """a single: the camera pushed in on his seat, his eyes a third of the way down (portrait) with look room towards
    the other man, the window behind softened. crash = the eye distance a crash zoom starts from (it snaps in to
    ed_screen in 0.12 s); punch = (t, factor) a 3-frame snap in; shakes = [(t0, t1, px)] a jolt on a shout"""
    a = seat(who, pose)
    if VERTICAL:
        sx, sy = (600 if who == "mark" else 480), 690
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


def two(t, mpose, gpose, dur=2.0, push_to=1.03, still=False, over=("badge",)):
    """both of them: a split screen in portrait (Mark above, Gary below, the badge on the divider), the plate's own
    two-shot across the desk in landscape"""
    if not VERTICAL:
        cam = (978, 470, 1.9)
        return world(t, "S", cam, cams=[(t, cam), (t + dur, push(cam, push_to))],
                     layers=LAYERS(seat("mark", mpose), seat("gary", gpose)), drift=0.35, blur=1.5, still=still)
    parts = []
    for k, (who, pose, sx) in enumerate((("mark", mpose, 580), ("gary", gpose, 500))):
        a = seat(who, pose)
        c0 = framed(a, sx, 740, 120.0)               # his eyes a quarter of the way down his half
        sub = world(t, "S", c0, cams=[(t, c0), (t + dur, push(c0, push_to))], layers=LAYERS(a), drift=0.35,
                    blur=2.5, free=True)
        sub.update(i=90 + k, end=t + dur)
        parts.append(sub)
    return dict(t=t, kind="split", parts=parts, still=still, over=list(over))


SHOTS = finish([
    single(0.0, "mark", "h_angry", ed_screen=165, end=wt("L001", "worst")),                 # "That is the..."
    single(wt("L001", "worst") - 0.04, "mark", "h_shout", ed_screen=230, crash=150, push_to=1.02,
           shakes=[(wt("L001", "worst"), wt("L001", "worst") + 0.5, 10.0)]),                # "WORST half of football"
    single(wt("L001", "seen") - 0.04, "gary", "h_neutral", ed_screen=185, push_to=1.02),     # Gary: unmoved
    single(wt("L001", "i", 1) + 0.03, "mark", "u_shrug", ed_screen=120, push_to=1.05),       # "...since I was a bloody kid!"
    single(m("slump") - 0.02, "mark", "h_sad", ed_screen=165, push_to=1.0),                  # the slump
    single(m("cut_gary1"), "gary", "h_sad", ed_screen=170, push_to=1.0,
           punch=(wt("L002", "worst") - 0.03, 1.07)),                                       # "...the WORST Man United"
    single(m("cut_gary2"), "gary", "h_neutral", ed_screen=205, push_to=1.05),               # "...a fucking challenge."
    single(m("cut_laugh"), "mark", "h_laugh", ed_screen=175, push_to=1.0),                  # Mark wheezes
    two(m("cut_mark2"), "u_point", "u_crossed", dur=wt("L004", "every") - m("cut_mark2")),  # "Honestly, Gary,"
    single(wt("L004", "every") - 0.04, "mark", "h_angry", ed_screen=175, push_to=1.06),     # "...rock bottom..."
    single(wt("L004", "shovel") - 0.04, "mark", "h_shout", ed_screen=235, crash=160, push_to=1.02,
           shakes=[(wt("L004", "shovel"), wt("L004", "shovel") + 0.5, 10.0)]),              # "...SHOVEL!"
    single(m("cut_palm"), "gary", "h_facepalm", ed_screen=175, push_to=1.0),                # the facepalm
    single(m("cut_mark3"), "mark", "h_smug", ed_screen=170, push_to=1.03),                  # "Still... at least..."
    single(m("cut_gary3"), "gary", "h_neutral", ed_screen=200, push_to=1.06),               # "Yeah." ... "being shit."
    single(m("cut_nod"), "mark", "h_sad", ed_screen=165, push_to=1.0),                      # the nod
    two(m("toast"), "h_sad", "h_neutral", dur=m("black") - m("toast"), push_to=1.0, over=("badge", "toast")),
    card(m("black"), "black"),
], TL["total"])

TITLE = ()
TAGLINE = ()
# small name straps on each man's first clear single (never over a face)
CAPTIONS = [
    (wt("L001", "i", 1) + 0.15, m("slump") - 0.05, "name", "MARK GOLDBRIDGE", "Overcrap Daily. Furious."),
    (m("cut_gary1") + 0.12, le("L002") - 0.05, "name", "GARY NEVILLE", "Called it three weeks ago."),
]
WHIPS = []


def shot_at(t):
    return _shot_at(SHOTS, t)
