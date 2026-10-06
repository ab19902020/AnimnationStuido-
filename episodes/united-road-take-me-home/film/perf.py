"""Who sings what, how everyone dances, and the faces: the band on the pub stage and the crowd in front of it.
Everything is keyed to the song's bars (timeline.bar) and lyric lines (timeline.LINES), so it lands on the music.

The arc: Gary sings every word from the first verse; Roy stands with his arms folded through the verses, gives a
reluctant nod in the second chorus, and by the finale he is headbanging and roaring the Glory Glory with everyone.
Every other United fan sings along with every line and jumps through every chorus; the backing singers sing every
line into their mics; Yoro takes the harmonica bit (the instrumental after the second chorus). And in the middle of
it all Jim Ratcliffe and Omar Berrada stand with faces like a wet weekend, not singing a word, nodding along out
of time when they try at all."""
import zlib

from studio.film.perf import Performance
from studio.film.stage import Groove, sing
from film.direction import SHOTS
from film.timeline import LINES, TL, bar

BAND = ["bruno", "sesko", "cunha", "maguire", "mainoo", "shaw", "deligt", "yoro"]
CROWD = ["gary", "roy", "rio", "rooney", "evra", "carrick", "ratcliffe", "lammens", "tielemans", "amad", "mount",
         "ugarte", "zirkzee", "mbeumo", "dalot", "martinez", "dorgu", "mazraoui", "cantona",
         "holland", "berrada"]
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
# Use the musical bar boundaries for every chorus. This prevents a lyric-line boundary from
# leaving a visible singer resting in the middle of a chorus when the camera cuts to them.
CHORUSES = [(bar(27), bar(36)), (bar(47), bar(57)), (bar(75), bar(83)), (bar(97), bar(108))]
GLORY = [(L(32) - 0.2, Le(34))]
LEAD = [(0.0, END)]                                     # Bruno: the lead vocal, every note of it
ALL = [(L(0) - 0.2, Le(len(LINES) - 1) + 0.3)]          # every line of the song
HARMONICA = [(bar(56), bar(64))]                        # the harmonica bit: the instrumental after the second chorus
PLAYS = {"yoro": HARMONICA}                             # his harmonica comes up to his lips for it
MISERABLE = ("ratcliffe", "berrada")

# ---------------------------------------------------------------- dancing
def spans(*items):
    return [(a, b, m, k) for (a, b), m, k in items]


def B(n, frac=0.0):
    """a time inside bar n (frac of the bar)"""
    return bar(n) + frac * (bar(n + 1) - bar(n))


hype = lambda s, m="jump", k=1.0: (sec(s), m, k)     # noqa: E731

# Nobody dances like anyone else. Each has a way of moving for the verses, the choruses and the anthem (outro and
# finale), and a feel (style: late = behind the beat, lag = how far the head trails). They all go together only
# where a real crowd does: the drop into every chorus (one bar of everyone jumping), the terrace sway in the
# bridge, and the Glory Glory.
DROPS = [(bar(27), bar(28)), (bar(47), bar(48)), (bar(75), bar(76)), (bar(97), bar(98))]
GLORY_BARS = (B(105), B(106, 0.7))
#            verse                               chorus                               anthem                          late   lag
PERSONA = {
    "gary":     ([("sway", 0.7), ("pump", 0.7)],   [("hop2", 1.0), ("pump", 0.6)],      [("pogo", 1.1)],                 -0.02, 0.07),
    "rooney":   ([("bounce", 1.1)],                [("pogo", 1.05)],                    [("pogo", 1.3)],                  0.00, 0.05),
    "rio":      ([("skank", 1.0)],                 [("hop", 0.9), ("skank", 0.5)],      [("jump", 1.1), ("twist", 0.6)],  0.05, 0.08),
    "evra":     ([("shuffle", 1.0), ("bob", 0.7)], [("skank", 1.0), ("hop2", 0.8)],     [("pogo", 1.2)],                  0.03, 0.06),
    "carrick":  ([("nod", 0.6)],                   [("bounce", 0.75)],                  [("hop", 0.9)],                   0.06, 0.09),
    "lammens":  ([("rock", 0.8)],                  [("jump", 1.0)],                     [("jump", 1.2), ("rock", 0.4)],   0.01, 0.08),
    "tielemans": ([("sway", 0.9)],                 [("hop2", 0.9)],                     [("jump", 1.1)],                  0.04, 0.07),
    "amad":     ([("bob", 1.0), ("bounce", 0.6)],  [("pogo", 1.0)],                     [("pogo", 1.25)],                -0.03, 0.05),
    "mount":    ([("bounce", 0.9)],                [("jump", 1.0)],                     [("jump", 1.2), ("sway", 0.4)],   0.00, 0.06),
    "ugarte":   ([("nod", 1.0)],                   [("headbang", 0.6), ("bounce", 0.6)], [("headbang", 0.8), ("jump", 0.8)], 0.02, 0.06),
    "zirkzee":  ([("sway", 1.0)],                  [("hop", 0.9)],                      [("hop", 1.1), ("sway", 0.5)],    0.07, 0.10),
    "mbeumo":   ([("shuffle", 1.0)],               [("skank", 0.9), ("jump", 0.6)],     [("pogo", 1.1)],                  0.00, 0.06),
    "dalot":    ([("bounce", 1.0)],                [("hop2", 1.0)],                     [("jump", 1.2)],                  0.03, 0.07),
    "martinez": ([("nod", 0.9), ("pump", 0.5)],    [("jump", 1.0), ("pump", 0.7)],      [("headbang", 0.7), ("jump", 0.9)], -0.02, 0.05),
    "dorgu":    ([("skank", 0.9)],                 [("pogo", 1.0)],                     [("pogo", 1.2)],                  0.02, 0.06),
    "mazraoui": ([("sway", 0.8)],                  [("hop", 1.0)],                      [("jump", 1.1)],                  0.05, 0.08),
    "holland":  ([("nod", 0.6)],                   [("bounce", 0.7)],                   [("hop", 0.8)],                   0.08, 0.10),
}
VERSES = (VERSE1, VERSE2, BUILD)
CHORUS_SECS = (CHORUS1, CHORUS2, BREAK)
ANTHEM_SECS = (CHORUS3, OUTRO, FINALE, CANTONA, CODA)


def persona(who):
    verse, chorus, anthem, late, lag = PERSONA[who]
    out = [(sec(INTRO), m, 0.45 * k) for m, k in verse]
    for s in VERSES:
        out += [(sec(s), m, k) for m, k in verse]
    for s in CHORUS_SECS:
        a, b = sec(s)
        a = max(a, next((d1 for d0, d1 in DROPS if d0 <= a < d1), a))     # after the drop
        out += [((a, b), m, k) for m, k in chorus]
    out += [(sec(BREAK), "pump", 0.5)]
    for s in ANTHEM_SECS:
        a, b = sec(s)
        a = max(a, next((d1 for d0, d1 in DROPS if d0 <= a < d1), a))
        for a2, b2 in ((a, min(b, GLORY_BARS[0])), (max(a, GLORY_BARS[1]), b)):     # (the Glory Glory is everyone's)
            if b2 > a2:
                out += [((a2, b2), m, k) for m, k in anthem]
    out += [(d, "jump", 1.15) for d in DROPS]                       # the drop: everyone goes up together
    out += [(sec(BRIDGE), "wave", 1.0), (sec(BRIDGE), "nod", 0.3)]  # the terrace sway
    out += [(GLORY_BARS, "pogo", 1.25)]                            # Glory Glory: the whole room bouncing as one
    return spans(*out), dict(late=late, lag=lag)


STYLE = {}
DANCE = {
    # Bruno: weight from foot to foot through the verses, working the stage; hops on 1 and 3 in the choruses
    "bruno": spans((sec(INTRO), "strut", 0.6), (sec(INTRO), "bounce", 0.4), (sec(VERSE1), "strut", 0.85),
                   (sec(VERSE1), "bounce", 0.4), (sec(CHORUS1), "bounce", 1.0), (sec(CHORUS1), "hop", 0.6),
                   (sec(VERSE2), "strut", 0.9), (sec(VERSE2), "bounce", 0.45), (sec(CHORUS2), "bounce", 1.0),
                   (sec(CHORUS2), "hop", 0.7), (sec(BREAK), "pump", 0.8), (sec(BREAK), "bounce", 0.8),
                   (sec(BRIDGE), "sway", 0.9), (sec(BUILD), "bounce", 1.0), (sec(CHORUS3), "jump", 0.9),
                   (sec(OUTRO), "jump", 1.0), (sec(FINALE), "jump", 1.1), (sec(CODA), "bounce", 0.8)),
    # Šeško: the guitarist's rock, laid back, his head a beat behind his shoulders
    "sesko": spans((sec(INTRO), "rock", 0.9), (sec(VERSE1), "rock", 0.9), (sec(CHORUS1), "rock", 1.2),
                   (sec(CHORUS1), "hop", 0.5), (sec(VERSE2), "rock", 1.0), (sec(CHORUS2), "rock", 1.2),
                   (sec(CHORUS2), "hop", 0.6), (sec(BREAK), "rock", 1.5), (sec(BREAK), "lean", -3.0),
                   (sec(BRIDGE), "sway", 0.6), (sec(BUILD), "rock", 1.2), (sec(CHORUS3), "rock", 1.2),
                   (sec(CHORUS3), "hop", 0.8), (sec(OUTRO), "jump", 0.9), (sec(FINALE), "jump", 1.0),
                   (sec(CODA), "rock", 1.0)),
    # Cunha: the bass player's skank on the off-beat; hops on 2 and 4 against Bruno's 1 and 3
    "cunha": spans((sec(INTRO), "bounce", 0.8), (sec(VERSE1), "skank", 0.9), (sec(CHORUS1), "hop2", 0.85),
                   (sec(VERSE2), "skank", 1.0), (sec(CHORUS2), "hop2", 0.9), (sec(BREAK), "skank", 1.0),
                   (sec(BRIDGE), "sway", 0.7), (sec(BUILD), "bounce", 1.0), (sec(CHORUS3), "jump", 0.9),
                   (sec(OUTRO), "jump", 1.0), (sec(FINALE), "jump", 1.0), (sec(CODA), "skank", 0.9)),
    # Maguire: the drummer is the beat; a heavy head on it, quieter in the bridge
    "maguire": spans(((bar(2), END), "headbang", 0.8), (sec(CHORUS1), "headbang", 0.4),
                     (sec(CHORUS2), "headbang", 0.4), (sec(BREAK), "headbang", 0.5), (sec(OUTRO), "headbang", 0.5),
                     (sec(FINALE), "headbang", 0.6), (sec(BRIDGE), "headbang", -0.5)),
    # Mainoo: at the keys, swaying, his head bobbing on the eighths in the choruses
    "mainoo": spans((sec(INTRO), "bounce", 0.6), (sec(VERSE1), "sway", 0.6), (sec(VERSE1), "nod", 0.8),
                    (sec(CHORUS1), "bounce", 0.9), (sec(CHORUS1), "bob", 0.6), (sec(VERSE2), "sway", 0.6),
                    (sec(CHORUS2), "bounce", 0.9), (sec(CHORUS2), "bob", 0.6), (sec(BREAK), "bounce", 1.0),
                    (sec(BRIDGE), "sway", 0.8), (sec(BUILD), "bounce", 0.9), (sec(CHORUS3), "bounce", 1.1),
                    (sec(OUTRO), "hop", 0.8), (sec(FINALE), "hop", 1.0), (sec(CODA), "bounce", 0.8)),
    # the backing singers: Shaw sways and hops, de Ligt bounces on the beat and pogos in the choruses
    "shaw": spans((sec(INTRO), "sway", 0.6), (sec(VERSE1), "sway", 0.8), (sec(VERSE1), "bounce", 0.4),
                  (sec(CHORUS1), "hop", 0.7), (sec(VERSE2), "sway", 0.8), (sec(CHORUS2), "hop", 0.8),
                  (sec(BREAK), "bounce", 0.9), (sec(BRIDGE), "sway", 1.0), (sec(BUILD), "bounce", 0.9),
                  (sec(CHORUS3), "jump", 0.8), (sec(OUTRO), "jump", 0.9), (sec(FINALE), "jump", 1.0),
                  (sec(CODA), "sway", 0.8)),
    "deligt": spans((sec(INTRO), "bounce", 0.6), (sec(VERSE1), "bounce", 0.7), (sec(VERSE1), "nod", 0.6),
                    (sec(CHORUS1), "pogo", 0.6), (sec(VERSE2), "bounce", 0.75), (sec(VERSE2), "nod", 0.6),
                    (sec(CHORUS2), "pogo", 0.7), (sec(BREAK), "bounce", 0.9), (sec(BRIDGE), "sway", 0.9),
                    (sec(BUILD), "bounce", 0.9), (sec(CHORUS3), "pogo", 0.75), (sec(OUTRO), "pogo", 0.8),
                    (sec(FINALE), "pogo", 0.9), (sec(CODA), "bounce", 0.9)),
}
DANCE["yoro"] = spans((sec(INTRO), "bounce", 0.7), (sec(VERSE1), "sway", 0.8), (sec(VERSE1), "bounce", 0.5),
                      (sec(CHORUS1), "hop2", 0.8), (sec(VERSE2), "sway", 0.8), (sec(CHORUS2), "hop2", 0.9),
                      ((bar(56), bar(64)), "rock", 1.4), ((bar(56), bar(64)), "nod", 0.8), (sec(BRIDGE), "sway", 1.0),
                      (sec(BUILD), "bounce", 1.0), (sec(CHORUS3), "jump", 1.0), (sec(OUTRO), "jump", 1.0),
                      (sec(FINALE), "jump", 1.1), (sec(CODA), "bounce", 0.9))
STYLE.update(bruno=dict(late=0.0, lag=0.07), sesko=dict(late=0.045, lag=0.10), cunha=dict(late=0.025, lag=0.08),
             maguire=dict(late=0.0, lag=0.05), mainoo=dict(late=-0.01, lag=0.07), shaw=dict(late=0.03, lag=0.08),
             deligt=dict(late=-0.015, lag=0.06), yoro=dict(late=0.015, lag=0.07))
for c in PERSONA:
    DANCE[c], STYLE[c] = persona(c)
# Roy: arms folded through the verses; a reluctant nod in the second chorus; headbanging by the finale. Standing
# there he still breathes, heavily
DANCE["roy"] = spans((sec(CHORUS2), "nod", 0.35), (sec(BREAK), "nod", 0.25), (sec(CHORUS3), "nod", 0.7),
                     (sec(OUTRO), "bounce", 0.7), (sec(FINALE), "headbang", 1.2), (sec(FINALE), "bounce", 0.6),
                     (sec(CODA), "bounce", 1.0))
STYLE["roy"] = dict(late=0.02, lag=0.08, breathe=1.4)
# the two who cannot dance: stock still while the place jumps, an out-of-time nod when they try
DANCE["ratcliffe"] = spans((sec(CHORUS2), "awkward", 0.7), (sec(CHORUS3), "awkward", 0.9), (sec(FINALE), "awkward", 1.0))
DANCE["berrada"] = spans((sec(CHORUS3), "awkward", 0.7), (sec(OUTRO), "awkward", 0.6), (sec(FINALE), "awkward", 0.9))
STYLE["ratcliffe"] = dict(breathe=0.8, lag=0.05)
STYLE["berrada"] = dict(breathe=0.8, lag=0.05)
DANCE["cantona"] = spans((sec(CODA), "nod", 0.5))
STYLE["cantona"] = dict(breathe=1.0, late=0.03)

# The opening: a band already in motion rather than people waiting to be introduced
for _w in ("bruno", "sesko", "cunha", "mainoo", "shaw", "deligt", "yoro"):
    DANCE[_w] += spans((sec(INTRO), "bounce", 0.38), (sec(INTRO), "sway", 0.22))
GROOVE = Groove(DANCE, style=STYLE)

# ---------------------------------------------------------------- faces
BASE = dict(bruno=(0.35, 0.45), sesko=(-0.1, 0.45), yoro=(0.3, 0.55), cunha=(0.25, 0.65), maguire=(0.02, 0.28), mainoo=(0.3, 0.5),
            shaw=(0.2, 0.4), deligt=(0.3, 0.4), gary=(0.6, 0.8), roy=(-0.75, -0.45), rio=(0.3, 0.7),
            rooney=(0.2, 0.6), evra=(0.4, 0.8), carrick=(0.0, 0.25), ratcliffe=(-0.85, -0.9), berrada=(-0.8, -0.85),
            cantona=(-0.3, 0.1), amad=(0.6, 0.9), mount=(0.4, 0.7), ugarte=(-0.2, 0.4), zirkzee=(0.2, 0.6),
            mbeumo=(0.5, 0.85), dalot=(0.5, 0.75), martinez=(-0.35, 0.35), dorgu=(0.55, 0.8), mazraoui=(0.35, 0.7),
            lammens=(0.3, 0.6), tielemans=(0.4, 0.7), holland=(0.1, 0.3))
EXPR = {
    "roy": [(sec(CHORUS3)[0], sec(OUTRO)[1], -0.3, 0.1, 0.6),          # thawing
            (sec(FINALE)[0], END, 0.4, 0.8, 0.5)],                      # roaring
    # Keep Maguire's brow neutral: the source drawing has a low, heavy brow and pushing it
    # down reads as an eyebrow inside the eye at close range. Expression comes from smile/head motion instead.
    "maguire": [(sec(BREAK)[0], sec(BREAK)[1], 0.0, 0.58, 0.35)],
    "bruno": [(sec(BRIDGE)[0], sec(BRIDGE)[1], 0.6, 0.2, 0.6)],         # the quiet bit: earnest
}
# singing the choruses: the brows go up, the faces open
for c in CROWD + ["shaw", "deligt", "cunha", "mainoo", "yoro"]:
    if c in ("roy", "cantona") + MISERABLE:
        continue
    b0, s0 = BASE[c]
    for a, b in CHORUSES + [sec(OUTRO)]:
        EXPR.setdefault(c, []).append((a, b, min(1.0, b0 + 0.3), min(1.0, s0 + 0.12), 0.4))
# where they look: the band at the crowd (the lens in the front shots), Šeško at his guitar in the solo,
# Maguire at his drums; the crowd up at the stage
GAZE = {"sesko": [(bar(57), bar(61), ("dir", 0.15, 0.75, 0.05))],
        "maguire": [(bar(2), END, ("dir", 0.0, 0.22, 0.0))],
        "cantona": [(0.0, END, ("dir", 0.6, -0.15, 0.25))],
        "yoro": [(bar(56), bar(64), ("dir", 0.0, 0.55, 0.0))],         # eyes down on his harmonica
        "ratcliffe": [(0.0, END, ("dir", 0.0, 0.05, 0.0))],           # a dead stare into the lens
        "berrada": [(0.0, END, ("dir", 0.0, 0.05, 0.0))]}
for c in CROWD:
    GAZE.setdefault(c, [(0.0, END, ("dir", 0.05 * ((zlib.crc32(c.encode()) % 5) - 2), -0.22, 0.0))])
for b in ("bruno", "cunha", "mainoo", "shaw", "deligt", "yoro"):
    GAZE.setdefault(b, [])

# Glances (stage.glance): someone looks away to a mate in the shot, up, or into the lens, and back. The crowd's
# running joke is Roy: his mates keep checking on him, and when he finally sings they turn to him and beam. The band
# look at each other in the two-shots and all turn to Yoro when his harmonica comes in; Bruno works the room.
LEFT, RIGHT = ("dir", -0.6, 0.04, -0.3), ("dir", 0.6, 0.04, 0.3)
GLANCE = {
    "rooney": [(B(4, 0.30), B(4, 0.62), "roy"), (B(29, 0.15), B(29, 0.5), "roy"), (B(52, 0.15), B(52, 0.55), "gary"),
               (B(60, 0.35), B(60, 0.75), "roy"), (B(79, 0.2), B(79, 0.62), "roy"), (B(88, 0.08), B(88, 0.45), "cam"),
               (B(102, 0.1), B(102, 0.5), "roy"), (B(106, 0.6), B(106, 0.95), "roy")],
    "rio": [(B(29, 0.55), B(29, 0.88), "roy"), (B(43, 0.4), B(43, 0.82), "roy"), (B(60, 0.3), B(60, 0.7), "roy"),
            (B(88, 0.25), B(88, 0.62), "rooney"), (B(93, 0.15), B(93, 0.92), "roy"), (B(105, 0.7), B(106, 0.25), "roy")],
    "gary": [(B(43, 0.2), B(43, 0.6), "roy"), (B(52, 0.1), B(52, 0.55), "rooney"), (B(86, 0.5), B(86, 0.9), "rooney"),
             (B(93, 0.05), B(93, 0.9), "roy"), (B(105, 0.1), B(105, 0.6), "roy")],
    "roy": [(B(25, 0.45), B(25, 0.85), "gary"), (B(102, 0.2), B(102, 0.5), "rooney")],
    "carrick": [(B(86, 0.2), B(86, 0.6), "roy")],
    "evra": [(B(21, 0.5), B(21, 0.85), "rooney")],
    "amad": [(B(49, 0.3), B(49, 0.6), "dalot")],
    "zirkzee": [(B(77, 0.4), B(77, 0.7), "mbeumo")],
    "lammens": [(B(90, 0.3), B(90, 0.65), "tielemans")],
    # the band
    "bruno": [(B(18, 0.1), B(18, 0.8), LEFT), (B(19, 0.1), B(19, 0.8), RIGHT), (B(26, 0.15), B(26, 0.5), "cunha"),
              (B(34, 0.2), B(34, 0.5), "sesko"), (B(35, 0.1), B(35, 0.6), RIGHT), (B(46, 0.1), B(46, 0.5), LEFT),
              (B(57, 0.3), B(57, 0.9), "yoro"), (B(71, 0.38), B(71, 0.85), "up"), (B(82, 0.2), B(82, 0.7), RIGHT),
              (B(92, 0.1), B(92, 0.48), LEFT), (B(92, 0.55), B(92, 0.95), RIGHT), (B(111, 0.2), B(111, 0.7), LEFT),
              (B(112, 0.1), B(112, 0.6), RIGHT)],
    "cunha": [(B(26, 0.2), B(26, 0.6), "bruno"), (B(42, 0.2), B(42, 0.6), "mainoo"), (B(47, 0.3), B(47, 0.7), "sesko"),
              (B(57, 0.4), B(57, 0.9), "yoro"), (B(111, 0.5), B(112, 0.2), "sesko")],
    "sesko": [(B(27, 0.3), B(27, 0.7), "bruno"), (B(34, 0.1), B(34, 0.55), "bruno"), (B(57, 0.1), B(57, 0.9), "yoro"),
              (B(59, 0.1), B(59, 0.9), "yoro"), (B(83, 0.2), B(83, 0.6), "bruno"), (B(111, 0.5), B(112, 0.2), "cunha")],
    "mainoo": [(B(42, 0.3), B(42, 0.6), "cunha"), (B(57, 0.5), B(57, 0.95), "yoro")],
    "shaw": [(B(100, 0.2), B(100, 0.7), "deligt"), (B(113, 0.3), B(113, 0.8), "deligt")],
    "deligt": [(B(100, 0.25), B(100, 0.7), "shaw"), (B(113, 0.35), B(113, 0.8), "shaw")],
}
# the flags go up, and so do their eyes: "we lift our flags to the sky"
for c in CROWD:
    GLANCE.setdefault(c, []).append((L(19) - 0.1, Le(19) + 0.1, "up"))
# eyes shut on the long notes, singing with everything: a few at a time, never everybody
SHUT = {"gary": [(50.6, 51.6), (B(52, 0.62), B(52, 0.95)), (197.2, 198.35)],
        "rooney": [(B(88, 0.55), B(88, 0.95)), (197.5, 198.4)],
        "bruno": [(56.3, 57.3), (134.15, 134.9), (138.2, 138.9), (151.7, 152.7), (195.5, 196.4)],
        "shaw": [(66.35, 67.25)],
        "deligt": [(177.9, 178.6)],
        "sesko": [(187.0, 188.2)],
        "mainoo": [(173.9, 174.7)]}

PERF = Performance(TL, {}, WHO, {w: w for w in WHO}, {}, lambda lid: None, base=BASE, gaze=GAZE, expr=EXPR,
                   rest_target={w: "cam" for w in WHO}, cuts=[s["t"] for s in SHOTS], shut=SHUT)

VOCAL_LAG = 0                                             # the mouth track already leads the voice by a frame or two (song.py)
sing(PERF, "bruno", LEAD, gain=1.1, lag=VOCAL_LAG)
for bv in ("shaw", "deligt"):                            # the backing singers sing every line into their mics
    sing(PERF, bv, ALL, gain=0.95, lag=VOCAL_LAG)
for pl in ("sesko", "cunha", "mainoo", "maguire"):      # the players belt every chorus along, off mic
    sing(PERF, pl, CHORUSES, gain=0.88, lag=VOCAL_LAG)
sing(PERF, "yoro", [(a, min(b, bar(56))) for a, b in CHORUSES if a < bar(56)] + [c for c in CHORUSES if c[0] >= bar(64)],
     gain=0.9, lag=VOCAL_LAG)
for c in CROWD:                                          # every United fan sings every word, and roars the choruses
    if c not in ("roy", "cantona") + MISERABLE:
        sing(PERF, c, ALL, gain=0.85, lag=VOCAL_LAG)
        sing(PERF, c, CHORUSES, gain=1.1, lag=VOCAL_LAG)
sing(PERF, "gary", ALL, gain=1.0, lag=VOCAL_LAG)
sing(PERF, "rooney", ALL, gain=1.0, lag=VOCAL_LAG)
for c in ("gary", "rooney"):
    sing(PERF, c, CHORUSES, gain=1.15, lag=VOCAL_LAG)
sing(PERF, "roy", [(bar(83), Le(len(LINES) - 1) + 0.3)], gain=1.0, lag=VOCAL_LAG)   # Roy, at last, from the outro
