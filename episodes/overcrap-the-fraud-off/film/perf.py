"""The acting: each line's delivery, who it is said to and its stressed words, and the script's beats (Jamie
enjoying himself, the private laugh, the grin after "Brent!", the glare at the end). See studio/film/perf.py."""
import json

from studio.film import ep
from studio.film.perf import Performance
from studio.film.shots import Marks
from film.direction import SHOTS
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt = T.m, T.ls, T.le, T.wt

WHO = ["jamie", "mark"]
SPK = {w: w for w in WHO}

# delivery tag, who the line is said to, stressed words (small nods); the director's hand-checked words are all here
META = {
    "L001": ("smug", "mark", ["first", "biggest", "fraud", "forest", "mark"]),
    "L002": ("sarcastic", "jamie", ["rich", "everton", "whole", "liverpool"]),
    "L003": ("proud", "mark", ["won", "champions", "liverpool", "mate"]),
    "L004": ("pleased", "jamie", ["exactly", "more", "liverpool", "everton", "thirty"]),
    "L005": ("deadpan_happy", "mark", ["least", "real", "brent"]),
    "L006": ("irritated", "jamie", ["here", "everton", "liverpool", "united", "legend", "anyone", "payslip"]),
    "L007": ("angry", "mark", ["fraud"]),
    "L008": ("angry", "jamie", ["blue", "nose"]),
}
# resting faces: Jamie cocky, Mark wary and dry
BASE = dict(jamie=(0.0, 0.3), mark=(-0.2, -0.05))
REST = dict(jamie="mark", mark="jamie")

GAZE = {
    # the open: Jamie cracks up looking at Mark; Mark glances sideways at him, suspicious
    "jamie": [(0.0, ls("L001"), "mark"),
              (le("L005") + 0.02, m("cut_mark3"), "mark")],          # holds the eye contact on "Brent!"
    "mark": [(0.0, ls("L001"), "jamie"),
             (m("cut_laugh"), m("cut_jamie3"), "jamie")],
}
# reactions outside their own lines: (t0, t1, brow, smile, ease-in)
EXPR = {
    "mark": [(0.0, ls("L001") + 0.4, 0.35, -0.2, 0.15),             # a raised eyebrow: here we go
             (wt("L001", "forest"), le("L001") + 0.1, 0.7, -0.35, 0.1),   # "Forest?!"
             (le("L005"), ls("L006") + 0.2, 0.85, -0.4, 0.06),       # "Brent" lands: stung
             (m("freeze"), m("black"), -0.95, -0.45, 0.01)],         # fuming
    "jamie": [(wt("L002", "everton"), le("L002"), -0.35, -0.2, 0.12),     # the Everton dig lands
              (m("cut_laugh"), m("cut_jamie3"), -0.55, -0.35, 0.08),     # the grin vanishes
              (T.we("L005", "brent"), m("cut_mark3"), 0.35, 0.95, 0.12),   # delighted grin after "Brent!"
              (wt("L006", "played"), wt("L006", "you'll"), 0.15, 0.6, 0.2),          # enjoying the rant
              (m("freeze"), m("black"), -0.8, 0.2, 0.01)],
}
# small nods on top of the stressed words: the laughs shake (several quick nods)
NODS = {"jamie": [(0.05, 3, 2.6)],                                     # laughing in the open
        "mark": [(m("cut_laugh") + 0.05, 3, 2.8)]}                     # the private laugh
TURN = {"jamie": [(ls("L005") + 0.2, m("cut_mark3"), 0.12, -2.0)]}     # leans in, head cocked, for "Brent"
BODY = {"jamie": [(ls("L005"), m("cut_mark3"), 0.4, 0.0, 0.6)],          # the lean in
        "mark": [(wt("L006", "you'll"), le("L006"), 0.4, 0.0, 0.5)]}     # into the rant
FORCED = {"mark": [le("L005") + 0.08], "jamie": [m("cut_laugh") + 0.35]}
NOBLINK = {"jamie": [(le("L005"), m("cut_mark3")), (m("cut_jamie4"), m("end"))],
           "mark": [(m("cut_mark4"), m("end"))]}

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, gaze=GAZE,
                   expr=EXPR, nods=NODS, turn=TURN, body=BODY, forced=FORCED, noblink=NOBLINK, rest_target=REST,
                   cuts=[s["t"] for s in SHOTS])
