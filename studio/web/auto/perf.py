"""A web episode's acting: each line's delivery (its tone), who it is said to and the words it leans on; everyone's
resting face (their mood); between lines each one looks at whoever spoke last, and at the start at the nearest
other character in their first scene. The lip sync, blinks, eyes and head come from studio/film/perf.py."""
import json

from studio.film import ep
from studio.film.perf import TAGS, Performance
from studio.web.auto import spec as S
from studio.web.auto.direction import SHOTS, STAND, TO
from studio.web.auto.timeline import TL

L = json.loads(ep.path("lines.json").read_text())

WHO = list(S.WHO)
SPK = {w: w for w in WHO}
META = {ln["id"]: (S.tone(ln) if S.tone(ln) in TAGS else "casual", TO[ln["id"]], S.stressed(ln["text"]))
        for ln in S.LINES if ln["id"] in TL["lines"]}
BASE = {w: TAGS.get(S.CAST[w].get("mood") or "", (0.05, 0.1)) for w in WHO}


def _rest(w):
    for st in STAND:
        if w in st:
            others = [o for o in st if o != w]
            if others:
                return min(others, key=lambda o: abs(st[o]["x"] - st[w]["x"]))
    return "cam"


REST = {w: _rest(w) for w in WHO}

PERF = Performance(TL, L, WHO, SPK, META, lambda lid: ep.path("lines", f"{lid}.wav"), base=BASE, rest_target=REST,
                   cuts=[s["t"] for s in SHOTS])
