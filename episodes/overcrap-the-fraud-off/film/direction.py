"""The shot list: every cut and camera move, keyed to the dialogue edit (timeline.py).

Where everyone is (the Overcrap Daily studio: two grey armchairs angled in towards each other, a little round table
between them, the stadium on the big screen behind): Jamie in the left-hand chair (screen left), Mark in the
right-hand chair (screen right). So Jamie looks screen right to Mark and Mark looks screen left to Jamie, in every
shot. Jamie points right at Mark; Mark points left at Jamie.

Everyone is a whole seated drawing sitting in a real chair of the set: every shot is the plate at true scale (a
`world` shot) with the camera moved in, never a figure cut off over a blurred wall. Singles are the camera pushed
in on one chair (the wall behind softened, the chair kept sharp); two-shots take in both chairs and the table.
A drawing is seated by its shoes on the floor in front of its chair (`seat`), so every pose sits at the same
place and size. Each pose changes on a cut, never inside a shot."""
import json

from studio.film import ep
from studio.film.cast import CAST, feet
from studio.film.shots import Marks, card, finish, shot_at as _shot_at, world
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt, we = T.m, T.ls, T.le, T.wt, T.we

PLATES = {"S": "tv-and-media/two-chair-pundit-studio"}       # with the show's logo on the screen (props.plate_image)
# 1x plate px. The table in front of the chairs (its top and the front of its frame); the chairs, kept sharp when
# the wall behind is softened
TABLE = [(603, 620), (612, 604), (640, 593), (700, 584), (780, 579), (835, 578), (900, 579), (970, 584), (1030, 593),
         (1060, 605), (1068, 622), (1060, 640), (1030, 652), (1050, 660), (1050, 760), (1035, 775), (835, 790),
         (640, 778), (620, 760), (620, 660), (640, 652), (610, 640)]
CHAIR_L = [(212, 478), (225, 466), (265, 462), (268, 430), (282, 400), (300, 393), (512, 393), (530, 405), (535, 455),
           (640, 458), (680, 470), (688, 490), (688, 580), (640, 598), (603, 610), (603, 640), (560, 650), (420, 668),
           (380, 722), (358, 724), (362, 680), (285, 655), (248, 690), (238, 680), (222, 640)]
CHAIR_R = [(985, 488), (1000, 465), (1040, 455), (1145, 452), (1150, 410), (1165, 395), (1385, 393), (1400, 405),
           (1405, 455), (1442, 462), (1458, 480), (1450, 645), (1430, 660), (1425, 690), (1408, 688), (1385, 668),
           (1310, 660), (1300, 722), (1280, 724), (1272, 666), (1180, 640), (1068, 622), (1060, 605), (1035, 590),
           (995, 590), (985, 560)]
OCCL = {"S": {"table": [TABLE], "chairs": [CHAIR_L, CHAIR_R]}}

# off-screen eyelines (singles): screen direction (x: -1 left .. 1 right, y: + down) and head turn
EYES = {"jamie": dict(mark=(1.05, 0.02, 0.3)), "mark": dict(jamie=(-1.05, 0.02, -0.3))}

# where each one sits: the middle of his shoes on the floor in front of his chair (1x plate px), and his size
SEAT = {"jamie": (452, 732), "mark": (1222, 732)}
ED = 40.0                       # eye distance in plate px: both men the same size
CID = {"jamie": "jamie-carragher", "mark": "mark-goldbridge"}


def seat(who, pose, ed=ED, dx=0.0):
    """an actor in his chair: the drawing placed so its shoes sit on his spot on the floor"""
    key = f"{CID[who]}:{pose}"
    d, info = CAST.get(key)
    fx, fy = feet(key)
    ax, ay = info["anchor"]
    k = ed / info["ed"]
    fx0, fy0 = SEAT[who]
    return (who, key, (fx0 + dx + (ax - fx) * k, fy0 - (fy - ay) * k), ed, False)


def eyes_of(a):
    return a[2]


S1 = 1920 / 1672                # screen px per plate px at zoom 1


def framed(a, sx, sy, ed_screen):
    """the camera that puts an actor's eyes at screen (sx, sy) with an eye distance of ed_screen px"""
    z = ed_screen / (a[3] * S1)
    s = S1 * z
    ex, ey = eyes_of(a)
    return (ex - (sx - 960) / s, ey - (sy - 540) / s, z)


def push(cam, f):
    return (cam[0], cam[1], cam[2] * f)


LAYERS = lambda *acts: [("near", "chairs"), ("actors", list(acts)), ("occl", "table")]


def single(t, who, pose, ed_screen=112.0, push_to=1.04, punch=None, blur=4.5, end=None):
    """a close single: the camera pushed in on his chair, his eyes 40 % down the frame with look room towards the
    other man, the wall behind softened; punch = (t, factor), a 3-frame snap in on a punchline"""
    a = seat(who, pose)
    sx = 790 if who == "jamie" else 1130
    c0 = framed(a, sx, 432, ed_screen)
    t1 = end or t + 3.0
    cams = [(t, c0), (t1, push(c0, push_to))]
    if punch:
        tp, f = punch
        u = (tp - t) / max(1e-3, t1 - t)
        cp = push(c0, 1 + (push_to - 1) * u)
        cams = [(t, c0), (tp, cp), (tp + 0.1, push(cp, f)), (t1, push(cp, f * (1 + (push_to - 1) * 0.3)))]
    return world(t, "S", c0, cams=cams, layers=LAYERS(a), drift=0.5, blur=blur, who=who, eye=(sx, 432), ed=ed_screen)


def two(t, jpose, mpose, cam=(838, 470, 1.35), push_to=1.03, dur=2.0, blur=1.2, **kw):
    """both men in their chairs, the table between them"""
    cams = [(t, cam), (t + dur, push(cam, push_to))]
    return world(t, "S", cam, cams=cams, layers=LAYERS(seat("jamie", jpose), seat("mark", mpose)), drift=0.35,
                 blur=blur, **kw)


SHOTS = finish([
    two(0.0, "laugh", "arms", cam=(838, 480, 1.18), push_to=1.04, dur=0.7),                 # Jamie already cracking up
    single(ls("L001"), "jamie", "shrug", end=wt("L001", "you're")),                         # "First show..."
    two(wt("L001", "you're") - 0.06, "point", "arms", cam=(838, 470, 1.36), push_to=1.05),   # "...a Forest fan, Mark!"
    single(m("cut_mark1"), "mark", "shrug", end=le("L002"),
           punch=(wt("L002", "everton") - 0.03, 1.07)),                                     # "...an Everton fan"
    single(m("cut_jamie2"), "jamie", "fist", ed_screen=118, end=le("L003")),                # Champions League, mate
    single(m("cut_mark2"), "mark", "arms", end=le("L004")),                                 # "Exactly!"
    two(m("cut_laugh"), "knees", "laughpoint", cam=(838, 470, 1.42), push_to=1.02, dur=0.8),  # Mark laughs; Jamie stops
    single(m("cut_jamie3"), "jamie", "thumb", ed_screen=132, push_to=1.12, end=m("cut_mark3")),   # leans in: "Brent!"
    single(m("cut_mark3"), "mark", "shrug2", end=wt("L006", "played")),                     # stung; "Oh, here we go"
    two(wt("L006", "played") - 0.06, "crossed", "finger", cam=(850, 465, 1.34), push_to=1.07, dur=2.6),  # the rant
    single(wt("L006", "you'll") - 0.06, "mark", "point", ed_screen=124, push_to=1.10, end=le("L006"),
           punch=(wt("L006", "payslip") - 0.03, 1.10)),                                     # "...a payslip!"
    single(m("cut_jamie4"), "jamie", "point", ed_screen=150, push_to=1.03, end=le("L007"),
           punch=(ls("L007") + 0.05, 1.08)),                                                # "FRAUD!"
    single(m("cut_mark4"), "mark", "point", ed_screen=165, push_to=1.03, end=le("L008"),
           punch=(ls("L008") + 0.03, 1.08)),                                                # "BLUE NOSE!"
    two(m("freeze"), "point", "point", cam=(838, 470, 1.28), push_to=1.0, dur=0.3, still=True),  # freeze: both glare
    card(m("black"), "black"),
], TL["total"])

TITLE = ()
TAGLINE = ()
# small lower-third names on each man's first single (never over a face)
CAPTIONS = [
    (ls("L001") + 0.3, wt("L001", "you're") - 0.1, "name", "JAMIE CARRAGHER", "Overcrap Daily. First show."),
    (m("cut_mark1") + 0.15, le("L002") - 0.3, "name", "MARK GOLDBRIDGE", "Overcrap Daily. Also first show."),
]
WHIPS = []


def shot_at(t):
    return _shot_at(SHOTS, t)
