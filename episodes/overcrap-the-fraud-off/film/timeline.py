"""The dialogue edit: the eight lines back to back with the beats the director asks for, and the marks the shots,
the acting and the sound hang off. Real British football-chat rhythm: a few frames between lines, the one big
silence after "Brent!", FRAUD / BLUE NOSE near-instant, a tiny freeze and a hard cut to black."""
import json

from studio.film import ep
from studio.film.timeline import build

L = json.loads(ep.path("lines.json").read_text())

SEQ = [
    ("gap", 0.62, "open"),                    # the two-shot: Jamie already laughing, Mark side-eyeing him
    ("line", "L001"),                         # Jamie: "First show... biggest fraud... You're a Forest fan, Mark!"
    ("gap", 0.14, "cut_mark1"),               # Mark, unimpressed
    ("line", "L002"),                         # "That's rich coming from an Everton fan..."
    ("gap", 0.12, "cut_jamie2"),
    ("line", "L003"),                         # "I won the Champions League with Liverpool, mate!"
    ("gap", 0.10, "cut_mark2"),
    ("line", "L004"),                         # "Exactly! You've done more for Liverpool than Everton..."
    ("gap", 0.15),
    ("gap", 0.82, "cut_laugh"),               # Mark cracks up pointing at him; Jamie's grin has gone
    ("gap", 0.12, "cut_jamie3"),              # Jamie leans in
    ("line", "L005"),                         # "At least I use me real name, Brent!"
    ("gap", 0.32),                            # the biggest silence: held on Jamie's delighted grin
    ("gap", 0.48, "cut_mark3"),               # Mark, stung; then the rant
    ("line", "L006"),                         # "Oh, here we go... anyone who gives you a payslip!"
    ("gap", 0.08, "cut_jamie4"),
    ("line", "L007"),                         # "FRAUD!"
    ("gap", 0.04, "cut_mark4"),               # instantly
    ("line", "L008"),                         # "BLUE NOSE!"
    ("gap", 0.10),
    ("gap", 0.30, "freeze"),                  # both glaring: the frame freezes
    ("gap", 0.28, "black"),                   # hard cut to black on the sting
]

TL = build(SEQ, L)
