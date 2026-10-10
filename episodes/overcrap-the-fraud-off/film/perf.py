"""The acting: each line's delivery, who it is said to and its stressed words, and the script's beats: Jamie
enjoying himself, Mark's eye-roll and suspicious squint, the offended face on "pretending to love Liverpool", the
grin dying on "thirty years", the private laugh, the delighted grin and the glance to us after "Brent!", Mark's
stunned stare and slow blink, the smug grin on "payslip", the glare at the end. The eyes never sit dead still
(small darts round wherever they look). See studio/film/perf.py."""
import json

from studio.film import ep
from studio.film.perf import Performance
from studio.film.shots import Marks
from film.direction import SHOTS
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt, we = T.m, T.ls, T.le, T.wt, T.we

WHO = ["jamie", "mark"]
SPK = {w: w for w in WHO}

# delivery tag, who the line is said to, stressed words (small nods); the director's hand-checked words are all here
META = {
    "L001": ("smug", "mark", ["first", "biggest", "fraud", "forest", "mark"]),
    "L002": ("sarcastic", "jamie", ["rich", "everton", "whole", "liverpool"]),
    "L003": ("indignant", "mark", ["won", "champions", "liverpool", "mate"]),
    "L004": ("pleased", "jamie", ["exactly", "more", "liverpool", "everton", "thirty"]),
    "L005": ("deadpan_happy", "mark", ["least", "real", "brent"]),
    "L006": ("irritated", "jamie", ["here", "everton", "liverpool", "united", "legend", "anyone", "payslip"]),
    "L007": ("angry", "mark", ["fraud"]),
    "L008": ("angry", "jamie", ["blue", "nose"]),
}
# resting faces: Jamie cocky, Mark wary and dry
BASE = dict(jamie=(0.0, 0.3), mark=(-0.2, -0.05))
REST = dict(jamie="mark", mark="jamie")
STUN = m("cut_mark3")                       # the crash zoom on Mark after "Brent!"

GAZE = {
    "jamie": [(0.0, ls("L001"), "mark"),                                  # laughing at him
              (le("L005") + 0.12, STUN, "cam")],                         # "Brent!"... a delighted glance to us
    "mark": [(0.0, 0.16, "jamie"),
             (0.16, ls("L001") + 0.2, ("dir", 0.3, -0.95, 0.05)),         # an eye-roll: here we go
             (m("cut_laugh"), m("cut_jamie3"), "jamie")],
}
# reactions outside their own lines: (t0, t1, brow, smile, ease-in)
EXPR = {
    "mark": [(0.0, ls("L001") + 0.4, 0.4, -0.2, 0.15),
             (wt("L001", "forest"), le("L001") + 0.05, 0.75, -0.35, 0.1),          # "Forest?!"
             (wt("L006", "payslip"), le("L006") + 0.1, 0.15, 0.55, 0.08),          # thinks he's won
             (le("L005"), ls("L006") + 0.25, 1.0, -0.45, 0.04),                    # "Brent": stunned
             (m("freeze"), m("black"), -0.95, -0.45, 0.01)],                       # fuming
    "jamie": [(wt("L002", "who") - 0.05, le("L002") + 0.05, 0.75, -0.45, 0.08),   # pretending?! offended
              (wt("L004", "than"), m("cut_jamie3"), -0.6, -0.45, 0.08),           # the grin dies
              (we("L005", "brent"), STUN, 0.45, 1.0, 0.1),                         # delighted
              (m("freeze"), m("black"), -0.8, 0.25, 0.01)],
}
NODS = {"jamie": [(we("L005", "brent") + 0.02, 1, 2.4)]}
TURN = {"jamie": [(ls("L005") + 0.2, le("L005") + 0.1, 0.12, -2.0)]}     # head cocked, leaning in for "Brent"
BODY = {"jamie": [(ls("L005"), STUN, 0.4, 0.0, 0.6)],                    # the lean in
        "mark": [(wt("L006", "you'll"), le("L006"), 0.4, 0.0, 0.5)]}     # into the rant
# the laughs shake them: (t0, t1, Hz, amount)
SHAKE = {"jamie": [(0.0, ls("L001") + 0.05, 7.0, 0.10),                  # the open
                   (wt("L006", "played"), wt("L006", "you'll"), 6.0, 0.05)],   # sniggering through the rant
         "mark": [(m("cut_laugh"), m("cut_jamie3"), 7.5, 0.13)]}         # the private laugh
# lids half down: (t0, t1, amount)
SQUINT = {"mark": [(0.0, le("L001"), 0.3),                               # suspicious
                   (ls("L004"), wt("L004", "than"), 0.22)],               # smug "Exactly!"
          "jamie": [(ls("L001"), wt("L001", "you're"), 0.2),              # smug
                    (we("L005", "brent"), STUN, 0.38)]}                   # the squinty grin
SHUT = {"mark": [(STUN + 0.24, STUN + 0.36)]}                            # one slow, deadpan blink before "Oh"
FORCED = {"jamie": [m("cut_laugh") + 0.3]}
NOBLINK = {"jamie": [(wt("L005", "name"), STUN), (m("cut_jamie4"), m("end"))],     # eyes wide open on "Brent!"
           "mark": [(STUN, STUN + 1.2), (m("cut_mark4"), m("end"))]}               # only the one slow blink

# the shouts: FRAUD and BLUE NOSE open far wider than talking (their "aw", "oo" and "o" would otherwise stay small;
# FRAUD less, its long "aw" already stretches Jamie's jaw a long way)
SHOUT = {"L007": 1.3, "L008": 1.45}

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, gaze=GAZE,
                   expr=EXPR, nods=NODS, turn=TURN, body=BODY, forced=FORCED, noblink=NOBLINK, rest_target=REST,
                   shut=SHUT, squint=SQUINT, shake=SHAKE, shout=SHOUT, darts=0.10, cuts=[s["t"] for s in SHOTS])
