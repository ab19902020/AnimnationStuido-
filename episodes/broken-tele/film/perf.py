"""The acting: each line's delivery, who it is said to and its stressed words, and the script's silent beats (the
boy's look from Mum to the car to the telly and back with his best smile; Mum's narrowed eyes and her phone; the
looks into the lens). See studio/film/perf.py for what each table does."""
import json

from studio.film import ep
from studio.film.perf import Performance
from studio.film.shots import Marks
from film.direction import SHOTS, T_SNEAK
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le = T.m, T.ls, T.le

WHO = ["boy", "mum", "dad"]
SPK = {"boy": "boy", "mum": "mum", "dad": "dad", "shop": "shop"}

# delivery tag, who the line is said to, stressed words (small nods)
META = {
    "L001": ("relieved", "down", ["peace", "all"]),
    "L002": ("firm", "boy", ["oi", "telly", "break"]),
    "L003": ("firm", "down", ["dare"]),                        # she doesn't even look up
    "L004": ("innocent", "cam", ["broken"]),
    "L005": ("deadpan", "boy", ["yes", "thank", "mummy"]),
    "L006": ("casual", "mum", ["hiya"]),
    "L007": ("flat", "dad", ["son's", "telly"]),
    "L008": ("concerned", "mum", ["alright"]),
    "L009": ("deadpan", "dad", ["fine", "stood", "pointing"]),
    "L010": ("frustrated", "mum", ["sake", "paid"]),
    "L011": ("irritated", ("dir", 0.15, 0.0, 0.05), ["cushion", "sock", "car", "metal"]),
    "L012": ("casual", "dad", []),
    "L013": ("resigned", "shop", ["same"]),
    "L014": ("proud", "mum", ["right", "christmas"]),
    "L015": ("firm", "boy", ["banned", "all"]),
    "L016": ("pleased", "mum", ["learned", "lesson", "soft"]),
    "L017": ("sarcastic", "dad", ["head"]),
    "L018": ("stunned", "boy", []),
    "L019": ("innocent", "cam", ["broken"]),
    "L020": ("flat", "boy", ["yes", "see"]),
    "L021": ("disbelieving", "mum", ["how", "soft"]),
    "L022": ("exhausted", "dad", ["can't", "projector"]),
    "L023": ("resigned", "mum", ["yeah", "best"]),
    "L024": ("firm", "boy", ["don't", "dare"]),
    "L025": ("innocent", "cam", ["broken"]),
}
BASE = dict(boy=(0.2, 0.2), mum=(0.0, 0.05), dad=(0.1, 0.1))

UP_LEFT = ("dir", -0.5, -0.85, -0.15)           # the projector on the ceiling, from the rug
DOWN = ("dir", 0.1, 0.9, 0.0)
L0 = m("cut_look")
GAZE = {
    "boy": [(L0, L0 + 0.8, "mum"), (L0 + 0.8, L0 + 1.6, DOWN), (L0 + 1.6, L0 + 2.4, "tv"), (L0 + 2.4, L0 + 3.3, "mum"),
            (m("cut_wind1"), m("cut_crack1"), "tv"),
            (m("cut_point1"), m("cut_boy1") + 0.45, "tv"), (m("cut_boy1") + 0.45, m("cut_mum2"), "cam"),
            (m("cut_pointing"), m("cut_dad3"), "tv"),
            (m("cut_sulk"), m("card_weeks"), "mum"),
            (T_SNEAK, T_SNEAK + 1.25, ("dir", 0.6, 0.05, 0.2)), (T_SNEAK + 1.3, m("cut_wind2"), "cam"),
            (m("cut_wind2"), m("cut_run"), "tv"), (m("cut_run"), m("cut_dad6"), "dad"),
            (m("cut_boy2"), m("cut_mum6"), "cam"),
            (m("cut_proj"), m("cut_boy3") + 0.8, UP_LEFT), (m("cut_boy3") + 0.8, ls("L024") + 0.1, DOWN),
            (ls("L024") + 0.1, m("smile"), "dad"), (m("smile"), m("cut_black"), "cam")],
    "mum": [(0.0, ls("L001") - 0.1, "down"), (le("L001"), m("cut_mum1") + 0.15, "down"),
            (m("cut_narrow"), m("cut_narrow") + 1.0, "boy"), (m("cut_narrow") + 1.0, m("smash1") + 0.05, "down"),
            (m("smash1") + 0.05, m("cut_point1"), "tv"),
            (m("cut_run"), m("cut_dad6"), "tv"), (m("cut_sofa"), m("cut_dad7"), "cam")],
    "dad": [(m("cut_office"), m("answer") - 0.1, DOWN),
            (m("cut_car"), m("cut_shop"), ("dir", 0.15, 0.0, 0.05)),
            (m("cut_shop"), ls("L012") + 0.25, ("dir", 0.6, 0.1, 0.25)), (ls("L012") + 0.25, m("cut_dad4"), "shop"),
            (m("cut_install"), ls("L014"), "tv"),
            (m("cut_run"), m("cut_dad6"), "tv"), (m("cut_sofa"), m("cut_dad7"), "cam")],
}
# reactions outside their own lines: (t0, t1, brow, smile, ease-in)
EXPR = {
    "boy": [(L0 + 2.35, L0 + 3.3, 0.7, 1.0, 0.15),                      # his best smile
            (m("cut_sulk"), m("card_weeks"), -0.6, -0.4, 0.3),
            (T_SNEAK + 1.3, m("cut_wind2") + 0.6, 0.4, 0.8, 0.2),
            (m("smile"), m("cut_black"), 0.5, 1.0, 0.2)],
    "mum": [(m("cut_narrow"), m("cut_narrow") + 1.05, -1.0, -0.3, 0.25),
            (m("cut_shock1"), m("cut_point1"), 1.0, -0.4, 0.08),
            (m("cut_sofa"), m("cut_dad7"), -0.2, -0.3, 0.3)],
    "dad": [(m("cut_office"), m("answer"), 0.3, 0.3, 0.2),
            (m("cut_install"), ls("L014"), 0.3, 0.6, 0.3),
            (m("cut_sofa"), m("cut_dad7"), -0.1, -0.3, 0.3)],
}
NODS = {"boy": [(L0 + 2.45, 1, 3.0)], "mum": [(le("L005") - 0.2, 1, 2.0)], "dad": [(le("L013") - 0.1, 1, 2.0)]}
TURN = {}
FORCED = {"mum": [m("cut_narrow") + 0.95, m("cut_sofa") + 0.9], "boy": [L0 + 2.3, m("cut_boy3") + 0.75],
          "dad": [m("cut_dad4") + 0.4, m("cut_sofa") + 0.5]}
NOBLINK = {"boy": [(m("cut_boy1") + 0.5, m("cut_mum2")), (m("cut_boy2"), m("cut_mum6")),
                   (T_SNEAK + 1.3, m("cut_wind2")), (m("smile"), m("cut_black"))]}
REST = dict(boy="mum", mum="boy", dad="mum")

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, gaze=GAZE,
                   expr=EXPR, nods=NODS, turn=TURN, forced=FORCED, noblink=NOBLINK, rest_target=REST,
                   cuts=[s["t"] for s in SHOTS])
