"""The acting: each line's delivery, who it is said to and its stressed words, and the beats between: Gary's slow,
unimpressed blink at the rant, Mark's slump, Gary staring into the middle distance then looking to Mark, the held
deadpan, Mark's wheeze, Gary's side-eye at the pointing finger, Mark's hopeful brows, the look, the pause, the eyes
coming round to the lens and holding there, Mark's slow nod. See studio/film/perf.py."""
import json

from studio.film import ep
from studio.film.perf import Performance
from studio.film.shots import Marks
from film.direction import SHOTS
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt, we = T.m, T.ls, T.le, T.wt, T.we

WHO = ["mark", "gary"]
SPK = {w: w for w in WHO}

# delivery tag, who the line is said to, stressed words (small nods)
META = {
    "L001": ("angry", "gary", ["worst", "football", "bloody", "kid"]),
    "L002": ("exhausted", "mark", ["three", "worst", "manchester"]),
    "L003": ("deadpan", "mark", ["challenge"]),
    "L004": ("frustrated", "gary", ["honestly", "gary", "rock", "bottom", "idiots", "shovel"]),
    "L005": ("hopeful", "gary", ["still", "consistent"]),
    "L006": ("flat", "mark", []),
    "L007": ("flat", "cam", []),
}
BASE = dict(mark=(-0.35, -0.15), gary=(-0.1, -0.15))
REST = dict(mark="gary", gary="mark")

GAZE = {
    "gary": [(ls("L002"), wt("L002", "united"), ("dir", 0.55, -0.35, 0.0)),        # staring into the distance
             (wt("L002", "united"), ls("L003") + 0.25, "mark"),                    # ...then to Mark
             (m("cut_gary3"), m("turn") + 0.12, "mark"),                           # the look at Mark
             (m("turn") + 0.12, m("end"), "cam")],                                 # and round to us, held
    "mark": [(m("slump"), m("cut_gary1"), ("dir", 0.2, 0.75, 0.0)),               # slumped, eyes down
             (m("cut_nod"), m("toast"), ("dir", 0.15, 0.55, 0.0)),                 # nodding at the desk
             (m("toast"), m("end"), "cam")],
}
# reactions outside their own lines: (t0, t1, brow, smile, ease-in)
EXPR = {
    "gary": [(0.0, ls("L002"), -0.35, -0.3, 0.2),                                  # unimpressed
             (m("cut_mark2"), m("cut_palm"), -0.5, -0.25, 0.15),                   # side-eye at the finger
             (le("L005"), ls("L006"), 0.25, -0.2, 0.25)],                          # ...really?
    "mark": [(m("slump"), m("cut_gary1"), 0.6, -0.4, 0.15),                        # defeated
             (le("L003"), m("cut_mark2"), 0.3, 0.6, 0.1),
             (ls("L005") - 0.1, le("L005") + 0.1, 0.75, 0.35, 0.15),               # hopeful brows
             (m("cut_nod"), m("toast"), 0.55, -0.35, 0.2)],
}
NODS = {"mark": [(m("cut_nod") + 0.12, 2, 3.2)]}                                    # yes. yes.
# the body: Mark slumps after the rant and sinks into the nod; Gary sinks into his hand
BODY = {"mark": [(m("slump") - 0.02, m("cut_gary1"), 0.0, 0.5, 0.35), (m("cut_nod"), m("toast"), 0.0, 0.25, 0.4)],
        "gary": [(m("cut_palm"), m("cut_mark3"), 0.0, 0.35, 0.3)]}
SHAKE = {"mark": [(m("cut_laugh"), m("cut_mark2"), 7.5, 0.14)]}                    # the wheeze
SQUINT = {"gary": [(m("cut_mark2"), m("cut_palm"), 0.3)],                          # side-eye
          "mark": [(ls("L005") + 0.6, le("L005") + 0.05, 0.15)]}
SHUT = {"gary": [(wt("L001", "seen") + 0.25, wt("L001", "seen") + 0.55)]}          # one long, slow, unimpressed blink
FORCED = {"gary": [m("turn") + 0.02], "mark": [m("slump") + 0.2]}
NOBLINK = {"gary": [(m("turn") + 0.2, m("end"))], "mark": [(m("toast"), m("end"))]}

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, gaze=GAZE,
                   expr=EXPR, nods=NODS, body=BODY, forced=FORCED, noblink=NOBLINK, rest_target=REST, shut=SHUT,
                   squint=SQUINT, shake=SHAKE, darts=0.08, cuts=[s["t"] for s in SHOTS])
