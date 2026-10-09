"""A web episode's studio.json, read once, with the defaults filled in."""
import json
import re

import yaml
from PIL import Image

from studio.film import ep
from studio.paths import BACKGROUNDS, CHARACTERS

SPEC = json.loads((ep.DIR / "studio.json").read_text())
CAST = {c["id"]: c for c in SPEC["cast"]}
WHO = [c["id"] for c in SPEC["cast"]]
LINES = [dict(ln) for ln in SPEC["lines"] if ln.get("text", "").strip() and ln.get("who") in CAST]
BG = SPEC["background"]
W1, H1 = Image.open(BACKGROUNDS / f"{BG}.png").size


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
    best = sorted(set(ws), key=lambda w: (-len(w), ws.index(w)))[:n]
    return best


def ids():
    return [ln["id"] for ln in LINES]


def slug_words(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
