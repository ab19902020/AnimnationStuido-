"""A web episode's studio.json, read once, with the defaults filled in (see studio/web/auto/__init__.py)."""
import json

import yaml
from PIL import Image

from studio.film import ep
from studio.paths import BACKGROUNDS, CHARACTERS
from studio.web.auto import normalize

SPEC = normalize(json.loads((ep.DIR / "studio.json").read_text()))
CAST = {c["id"]: c for c in SPEC["cast"]}
WHO = [c["id"] for c in SPEC["cast"]]
SCENES = SPEC["scenes"]
LINES = [dict(ln) for ln in SPEC["lines"] if ln.get("text", "").strip() and ln.get("who") in CAST]
for _ln in LINES:                           # whoever speaks in a scene is in it, staged or not
    _st = SCENES[_ln["scene"]].setdefault("stage", {})
    if _ln["who"] not in _st:
        _st[_ln["who"]] = {}
for _sc in SCENES:                          # the unstaged spread out across the set
    _st = _sc.setdefault("stage", {})
    _free = [c for c in _st if "x" not in _st[c]]
    for _k, _c in enumerate(_free):
        _st[_c] = dict(x=round(0.5 if len(_free) == 1 else 0.22 + 0.56 * _k / (len(_free) - 1), 3), floor=0.93,
                       height=0.62, **_st[_c])
    for _c, _v in _st.items():
        _v.setdefault("floor", 0.93)
        _v.setdefault("height", 0.62)
BGS = sorted({sc["background"] for sc in SCENES})
PLATE = {sc["background"]: f"P{BGS.index(sc['background'])}" for sc in SCENES}
SIZE = {b: Image.open(BACKGROUNDS / f"{b}.png").size for b in BGS}


def draw(cid):
    return f"{cid}:{CAST[cid].get('drawing') or 'front'}"


def info(cid):
    y = CHARACTERS / cid / "character.yaml"
    return yaml.safe_load(y.read_text()) if y.exists() else {}


def name(cid):
    return info(cid).get("name") or cid.replace("-", " ").title()


def tone(ln):
    """the line's delivery: as given, or guessed from its punctuation"""
    if ln.get("tone"):
        return ln["tone"]
    t = ln["text"].strip()
    if t.endswith("!"):
        return "energised"
    if t.endswith("?"):
        return "hopeful"
    if t.endswith("...") or t.endswith("…"):
        return "deadpan"
    return "casual"


STOP = set("""a an the and or but if so to of in on at by for with from as is am are was were be been being it its
it's this that these those i you he she we they me him her us them my your his our their mine yours not no do does
did done have has had will would can could should shall may might must just very really then than there here what
who whom which when where why how all any some more most such only own same too also yeah yes oh well okay ok i'm
you're we're they're don't can't won't isn't aren't i've you've i'll you'll that's there's what's let's""".split())


def stressed(text, n=3):
    """the words a line leans on: its longest content words (small nods land on them)"""
    from studio.film.voices import words_of
    ws = [w for w in words_of(text) if w not in STOP and len(w) > 3]
    return sorted(set(ws), key=lambda w: (-len(w), ws.index(w)))[:n]
