"""The dialogue edit: the eight lines with the beats the director asks for, and the marks the shots, the acting and
the sound hang off. Real British football-chat rhythm: comebacks land on the last word of the line before (a
negative gap overlaps only the silence after it), the one big silence after "Brent!", BLUE NOSE cutting in over the
tail of Jamie's stretched FRAUD, a tiny freeze and a hard cut to black."""
import json

from studio.film import ep
from studio.film.timeline import build

L = json.loads(ep.path("lines.json").read_text())

SEQ = [
    ("gap", 0.50, "open"),                    # the two-shot: Jamie already laughing, Mark rolling his eyes
    ("line", "L001"),                         # Jamie: "First show... biggest fraud... You're a Forest fan, Mark!"
    ("gap", 0.02, "cut_mark1"),               # Mark, straight back
    ("line", "L002"),                         # "That's rich coming from an Everton fan..." (Jamie's face on "who")
    ("gap", -0.10),                           # Jamie in on "Liverpool": only the silence after it overlaps
    ("line", "L003"),                         # "I won the Champions League with Liverpool, mate!"
    ("gap", -0.12, "cut_mark2"),              # "Exactly!" on top of "mate"
    ("line", "L004"),                         # "...than Everton have in thirty years!" (Jamie's grin dies)
    ("gap", 0.12),
    ("gap", 0.72, "cut_laugh"),               # Mark cracks up pointing at him
    ("gap", 0.06, "cut_jamie3"),              # Jamie leans in
    ("line", "L005"),                         # "At least I use me real name, Brent!"
    ("gap", 0.42),                            # held on his delighted grin, a glance to us
    ("gap", 0.52, "cut_mark3"),               # crash zoom: Mark, stunned, in silence; a slow blink
    ("line", "L006"),                         # "Oh, here we go... anyone who gives you a payslip!"
    ("gap", 0.04, "cut_jamie4"),
    ("line", "L007"),                         # "FRAUD!" (a long, stretched shout)
    ("gap", -0.44),
    ("gap", 0.06, "cut_mark4"),               # BLUE NOSE cuts in over the tail of it
    ("line", "L008"),                         # "BLUE NOSE!"
    ("gap", 0.12),
    ("gap", 0.36, "freeze"),                  # both pointing, glaring: the frame freezes
    ("gap", 0.25, "black"),                   # hard cut to black on the sting
]

TL = build(SEQ, L)
