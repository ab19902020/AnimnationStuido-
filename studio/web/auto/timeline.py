"""A web episode's dialogue edit: an establishing beat on the set, every line in order with the house pacing
between them (a few frames between one speaker and the next, a little more when the same one carries on, or the
pause the line asks for), a hold on the last line, then the title card.

Marks: open (the first frame), pre_<id> (the gap before each line from the second on: its cut), hold, cut_title."""
import json

from studio.film import ep
from studio.film.timeline import build
from studio.web.auto.spec import LINES, SPEC

L = json.loads(ep.path("lines.json").read_text())
OPEN = float(SPEC.get("open", 2.2))           # the set before anyone speaks

SEQ = [("gap", OPEN, "open")]
for i, ln in enumerate(LINES):
    if i:
        same = ln["who"] == LINES[i - 1]["who"]
        p = ln.get("pause")
        gap = float(p) if p not in (None, "") else (0.32 if same else 0.16)
        SEQ.append(("gap", gap, f"pre_{ln['id']}"))
    SEQ.append(("line", ln["id"]))
SEQ += [("gap", float(SPEC.get("hold", 1.3)), "hold")]
if SPEC.get("title") or SPEC.get("show"):
    SEQ += [("gap", 3.2, "cut_title")]

TL = build(SEQ, L)
