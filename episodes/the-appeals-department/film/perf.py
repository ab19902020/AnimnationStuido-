"""The acting for the test: each line's delivery, who it is said to and its stressed words, and the script's beats
(the door, the look, Roy into the lens). See studio/film/perf.py for what each table does."""
import json

from studio.film import ep
from studio.film.perf import Performance
from studio.film.shots import Marks
from film.direction import SHOTS
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le = T.m, T.ls, T.le

WHO = ["gary", "roy", "micah", "pep"]
SPK = {w: w for w in WHO}

# delivery tag, who the line is said to, stressed words (small nods)
META = {
    "L001": ("salesman", "roy", ["ruling", "appealing", "gap", "market"]),
    "L002": ("dry", "gary", ["football"]),
    "L003": ("salesman", "roy", ["appeals", "anyone", "nineteen", "complaint"]),
    "L004": ("hopeful", "gary", ["guaranteed"]),
    "L005": ("confident", "micah", ["hear", "sign"]),
    "L006": ("deadpan", "gary", ["invented", "glass", "problem"]),
    "L007": ("salesman", "roy", ["fourteens", "free", "community"]),
    "L008": ("dry", "gary", ["card", "toddler"]),
    "L009": ("irritated", "gary", ["hundred", "fifteen", "five"]),
    "L010": ("salesman", "pep", ["object", "all"]),
    "L011": ("cold", "gary", ["all"]),
    "L012": ("indignant", "gary", ["charged", "thousand"]),
    "L013": ("matter", "pep", ["two", "ninety", "important", "finances"]),
    "L014": ("deadpan", "gary", ["mugging", "seminar"]),
}
# resting faces: Gary the salesman, Roy dour, Micah keen (his drawing already smiles), Pep wary
BASE = dict(gary=(0.25, 0.25), roy=(-0.3, -0.12), micah=(0.15, 0.0), pep=(-0.15, -0.1))
SMILE_BIAS = dict(micah=-0.25)

READER = ("dir", 0.25, 0.8, 0.08)          # down at the card reader in Micah's hands
DOOR = {"gary": ("dir", 1.0, -0.05, 0.4), "micah": ("dir", 1.0, -0.05, 0.4), "roy": ("dir", 0.95, -0.05, 0.38)}

GAZE = {
    "gary": [(ls("L007") + 0.55, ls("L007") + 1.35, READER),             # "free"... his eyes check the reader
             (m("squeak") + 0.1, m("cut_pep1"), DOOR["gary"]),
             (m("cut_look"), m("cut_reader2"), "micah")],
    "micah": [(m("cut_reader1"), m("squeak") + 0.15, ("dir", 0.0, 0.85, 0.0)),   # turning the reader over
              (m("squeak") + 0.22, m("cut_pep1"), DOOR["micah"]),
              (m("cut_look"), m("cut_reader2"), "gary")],
    "roy": [(m("squeak") + 0.32, m("cut_pep1"), DOOR["roy"]),
            (le("L014") + 0.18, m("cut_title"), "cam")],                  # Roy, to us
    "pep": [],
}
# reactions outside their own lines: (t0, t1, brow, smile, ease-in)
EXPR = {
    "gary": [(m("cut_look"), m("cut_reader2"), 0.35, 0.65, 0.2),          # the look: commercial understanding
             (m("squeak"), m("cut_pep1"), 0.4, 0.2, 0.15)],
    "micah": [(m("cut_look") + 0.12, m("cut_reader2"), 0.3, 0.8, 0.15),
              (m("cut_reader1"), m("squeak"), 0.45, 0.05, 0.2)],
    "roy": [(m("cut_gm1"), le("L005"), -0.4, -0.15, 0.3),
            (le("L014"), m("cut_title"), -0.25, -0.05, 0.3)],
    "pep": [(m("cut_pep3") - 0.2, ls("L012"), 0.8, -0.3, 0.12)],
}
NODS = {"micah": [(m("cut_look") + 0.3, 2, 2.2)],                  # a small silent laugh
        "gary": [(m("cut_look") + 0.35, 1, 2.0)]}
TURN = {"roy": [(le("L014") + 0.15, m("cut_title"), 0.0, -1.5)]}
# blinks on cue: as the line lands, as the look starts (after the cut has settled), a startle at the squeak
FORCED = {"roy": [le("L014") + 0.05], "gary": [m("cut_look") + 0.4], "pep": [le("L011") + 0.12],
          "micah": [m("squeak") + 0.12]}
NOBLINK = {"roy": [(le("L014") + 0.3, m("cut_title"))]}
REST = dict(gary="roy", roy="gary", micah="gary", pep="gary")

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, gaze=GAZE,
                   expr=EXPR, nods=NODS, turn=TURN, forced=FORCED, noblink=NOBLINK, smile_bias=SMILE_BIAS,
                   rest_target=REST, cuts=[s["t"] for s in SHOTS])
