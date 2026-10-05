"""Who sings what, how everyone dances, and the faces: the band on the pub stage and the crowd in front of it.
Everything is keyed to the song's bars (timeline.bar) and lyric lines (timeline.LINES), so it lands on the music.

The arc: Gary sings every word from the first verse; Roy stands with his arms folded through the verses, gives a
reluctant nod in the second chorus, and by the finale he is headbanging and roaring the Glory Glory with everyone."""
import zlib

from studio.film.perf import Performance
from studio.film.stage import Groove, sing
from film.direction import SHOTS
from film.timeline import LINES, TL, bar

BAND = ["bruno", "sesko", "cunha", "maguire", "mainoo", "shaw", "deligt"]
CROWD = ["gary", "roy", "rio", "rooney", "evra", "carrick", "ratcliffe", "lammens", "tielemans", "amad", "mount",
         "ugarte", "zirkzee", "mbeumo", "dalot", "martinez", "yoro", "dorgu", "mazraoui", "cantona",
         "holland", "berrada", "shearer", "lineker", "carragher", "micah"]
WHO = BAND + CROWD
END = TL["total"]


def L(n):
    return LINES[n][0]


def Le(n):
    return LINES[n][1]


# the song's sections, in bars
INTRO, VERSE1, CHORUS1, VERSE2, CHORUS2, BREAK, BRIDGE, BUILD, CHORUS3, OUTRO, FINALE, CANTONA, CODA = (
    (0, 16), (16, 27), (27, 36), (36, 47), (47, 57), (57, 64), (64, 72), (72, 75), (75, 83), (83, 97), (97, 108),
    (108, 111), (111, 116))


def sec(s):
    return bar(s[0]), bar(s[1]) if s[1] < 116 else END


# ---------------------------------------------------------------- singing
CHORUSES = [(L(6) - 0.2, Le(7)), (L(14) - 0.2, bar(57)), (L(22) - 0.2, Le(29)), (L(30) - 0.2, Le(34))]
GLORY = [(L(32) - 0.2, Le(34))]
LEAD = [(0.0, END)]                                     # Bruno: the lead vocal, every note of it

# ---------------------------------------------------------------- dancing
def spans(*items):
    return [(a, b, m, k) for (a, b), m, k in items]


hype = lambda s, m="jump", k=1.0: (sec(s), m, k)     # noqa: E731

DANCE = {
    "bruno": spans((sec(INTRO), "bounce", 0.5), (sec(INTRO), "sway", 0.4), (sec(VERSE1), "bounce", 0.6),
                   (sec(VERSE1), "sway", 0.5), (sec(CHORUS1), "bounce", 1.0), (sec(CHORUS1), "hop", 0.6),
                   (sec(VERSE2), "bounce", 0.7), (sec(VERSE2), "sway", 0.5), (sec(CHORUS2), "bounce", 1.0),
                   (sec(CHORUS2), "hop", 0.7), (sec(BREAK), "pump", 0.8), (sec(BREAK), "bounce", 0.8),
                   (sec(BRIDGE), "sway", 0.9), (sec(BUILD), "bounce", 1.0), (sec(CHORUS3), "jump", 0.9),
                   (sec(OUTRO), "jump", 1.0), (sec(FINALE), "jump", 1.1), (sec(CODA), "bounce", 0.8)),
    "sesko": spans((sec(INTRO), "rock", 0.9), (sec(VERSE1), "rock", 0.9), (sec(CHORUS1), "rock", 1.2),
                     (sec(CHORUS1), "hop", 0.5), (sec(VERSE2), "rock", 1.0), (sec(CHORUS2), "rock", 1.2),
                     (sec(CHORUS2), "hop", 0.6), (sec(BREAK), "rock", 1.5), (sec(BREAK), "lean", -4.0),
                     (sec(BRIDGE), "sway", 0.6), (sec(BUILD), "rock", 1.2), (sec(CHORUS3), "rock", 1.2),
                     (sec(CHORUS3), "hop", 0.8), (sec(OUTRO), "jump", 0.9), (sec(FINALE), "jump", 1.0),
                     (sec(CODA), "rock", 1.0)),
    "cunha": spans((sec(INTRO), "bounce", 0.8), (sec(VERSE1), "rock", 0.8), (sec(CHORUS1), "jump", 0.7),
                   (sec(VERSE2), "rock", 0.9), (sec(CHORUS2), "jump", 0.8), (sec(BREAK), "bounce", 1.0),
                   (sec(BRIDGE), "sway", 0.7), (sec(BUILD), "bounce", 1.0), (sec(CHORUS3), "jump", 0.9),
                   (sec(OUTRO), "jump", 1.0), (sec(FINALE), "jump", 1.0), (sec(CODA), "bounce", 0.8)),
    "maguire": spans(((bar(2), END), "headbang", 0.8), (sec(CHORUS1), "headbang", 0.4),
                     (sec(CHORUS2), "headbang", 0.4), (sec(BREAK), "headbang", 0.5), (sec(OUTRO), "headbang", 0.5),
                     (sec(FINALE), "headbang", 0.6), (sec(BRIDGE), "headbang", -0.5)),
    "mainoo": spans((sec(INTRO), "bounce", 0.6), (sec(VERSE1), "sway", 0.6), (sec(VERSE1), "nod", 0.8),
                    (sec(CHORUS1), "bounce", 1.0), (sec(VERSE2), "sway", 0.6), (sec(CHORUS2), "bounce", 1.0),
                    (sec(BREAK), "bounce", 1.0), (sec(BRIDGE), "sway", 0.8), (sec(BUILD), "bounce", 0.9),
                    (sec(CHORUS3), "bounce", 1.1), (sec(OUTRO), "hop", 0.8), (sec(FINALE), "hop", 1.0),
                    (sec(CODA), "bounce", 0.8)),
}
for bv in ("shaw", "deligt"):
    DANCE[bv] = spans((sec(INTRO), "sway", 0.6), (sec(VERSE1), "sway", 0.8), (sec(VERSE1), "bounce", 0.4),
                      (sec(CHORUS1), "hop", 0.7), (sec(VERSE2), "sway", 0.8), (sec(CHORUS2), "hop", 0.8),
                      (sec(BREAK), "bounce", 0.9), (sec(BRIDGE), "sway", 1.0), (sec(BUILD), "bounce", 0.9),
                      (sec(CHORUS3), "jump", 0.8), (sec(OUTRO), "jump", 0.9), (sec(FINALE), "jump", 1.0),
                      (sec(CODA), "sway", 0.8))
# the crowd: dancing in the verses, jumping in the choruses
for i, c in enumerate(CROWD):
    verse = ("bounce", "sway", "nod", "shuffle")[i % 4]
    DANCE[c] = spans((sec(INTRO), "nod", 0.6), (sec(VERSE1), verse, 0.8), (sec(VERSE1), "bounce", 0.4),
                     (sec(CHORUS1), "jump", 0.8 + 0.1 * (i % 3)), (sec(VERSE2), verse, 0.9),
                     (sec(VERSE2), "bounce", 0.5), (sec(CHORUS2), "jump", 0.9), (sec(BREAK), "pump", 1.0),
                     (sec(BREAK), "bounce", 0.8), (sec(BRIDGE), "sway", 1.0), (sec(BUILD), "bounce", 1.0),
                     (sec(CHORUS3), "jump", 1.0), (sec(OUTRO), "jump", 1.1), (sec(FINALE), "jump", 1.2),
                     (sec(CODA), "bounce", 1.0))
DANCE["gary"] += spans((sec(VERSE1), "pump", 0.8), (sec(VERSE2), "pump", 0.8))
# Roy: arms folded through the verses; a reluctant nod in the second chorus; headbanging by the finale
DANCE["roy"] = spans((sec(CHORUS2), "nod", 0.35), (sec(BREAK), "nod", 0.25), (sec(CHORUS3), "nod", 0.7),
                     (sec(OUTRO), "bounce", 0.7), (sec(FINALE), "headbang", 1.2), (sec(FINALE), "bounce", 0.6),
                     (sec(CODA), "bounce", 1.0))
DANCE["ratcliffe"] = spans((sec(VERSE1), "nod", 0.4), (sec(CHORUS1), "bounce", 0.4), (sec(CHORUS2), "bounce", 0.5),
                           (sec(OUTRO), "bounce", 0.7), (sec(FINALE), "jump", 0.7))
DANCE["carrick"] = spans((sec(VERSE1), "nod", 0.6), (sec(CHORUS1), "bounce", 0.6), (sec(VERSE2), "nod", 0.6),
                         (sec(CHORUS2), "bounce", 0.7), (sec(CHORUS3), "bounce", 0.9), (sec(OUTRO), "jump", 0.8),
                         (sec(FINALE), "jump", 1.0))
DANCE["cantona"] = spans((sec(CODA), "nod", 0.5))
GROOVE = Groove(DANCE)

# ---------------------------------------------------------------- faces
BASE = dict(bruno=(0.35, 0.45), sesko=(-0.1, 0.45), cunha=(0.25, 0.65), maguire=(-0.35, 0.2), mainoo=(0.3, 0.5),
            shaw=(0.2, 0.4), deligt=(0.3, 0.4), gary=(0.6, 0.8), roy=(-0.75, -0.45), rio=(0.3, 0.7),
            rooney=(0.2, 0.6), evra=(0.4, 0.8), carrick=(0.0, 0.25), ratcliffe=(0.1, 0.2), cantona=(-0.3, 0.1))
EXPR = {
    "roy": [(sec(CHORUS3)[0], sec(OUTRO)[1], -0.3, 0.1, 0.6),          # thawing
            (sec(FINALE)[0], END, 0.4, 0.8, 0.5)],                      # roaring
    "maguire": [(sec(BREAK)[0], sec(BREAK)[1], 0.2, 0.6, 0.4)],
    "bruno": [(sec(BRIDGE)[0], sec(BRIDGE)[1], 0.6, 0.2, 0.6)],         # the quiet bit: earnest
}
for c in CROWD:
    if c not in BASE:
        BASE[c] = (0.35, 0.6)
# where they look: the band at the crowd (the lens in the front shots), Šeško at his guitar in the solo,
# Maguire at his drums; the crowd up at the stage
GAZE = {"sesko": [(bar(57), bar(61), ("dir", 0.15, 0.75, 0.05))],
        "maguire": [(bar(2), END, ("dir", 0.0, 0.45, 0.0))],
        "cantona": [(0.0, END, ("dir", 0.6, -0.15, 0.25))]}
for c in CROWD:
    GAZE.setdefault(c, [(0.0, END, ("dir", 0.05 * ((zlib.crc32(c.encode()) % 5) - 2), -0.22, 0.0))])
for b in ("bruno", "cunha", "mainoo", "shaw", "deligt"):
    GAZE.setdefault(b, [])

PERF = Performance(TL, {}, WHO, {w: w for w in WHO}, {}, lambda lid: None, base=BASE, gaze=GAZE, expr=EXPR,
                   rest_target={w: "cam" for w in WHO}, cuts=[s["t"] for s in SHOTS])

sing(PERF, "bruno", LEAD, gain=1.0)
for bv in ("shaw", "deligt", "sesko", "cunha"):
    sing(PERF, bv, CHORUSES, gain=0.8)
for c in CROWD:
    if c not in ("roy", "cantona"):
        sing(PERF, c, CHORUSES, gain=0.7, lag=1)
sing(PERF, "gary", [(L(0) - 0.2, Le(34))], gain=0.75, lag=1)        # every word
sing(PERF, "rooney", [(L(0) - 0.2, Le(34))], gain=0.8, lag=1)       # and so does Rooney
sing(PERF, "roy", GLORY, gain=0.9, lag=1)
