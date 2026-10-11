"""The dialogue edit: the seven lines with the beats the director asks for (the slump, Gary's held deadpan, the
facepalm, the pause before the last line, Mark's nod) and the marks the shots, the acting and the sound hang off.
Snappy: lines butt up against each other; the silences are the reactions, and every one of them is a cut."""
import json

from studio.film import ep
from studio.film.timeline import build

L = json.loads(ep.path("lines.json").read_text())

SEQ = [
    ("gap", 0.06, "open"),                    # hard start: Mark mid-fury
    ("line", "L001"),                         # "That is the WORST half of football..." (Gary's eyes cut in)
    ("gap", 0.06),
    ("gap", 0.50, "slump"),                   # Mark's defeated slump
    ("gap", 0.04, "cut_gary1"),
    ("line", "L002"),                         # Gary, exhausted: "I said three weeks ago..."; looks to Mark
    ("gap", 0.10, "cut_gary2"),               # tighter
    ("line", "L003"),                         # "Turns out they took it as a fucking challenge."
    ("gap", 0.45),                            # held deadpan, mouth shut
    ("gap", 0.70, "cut_laugh"),               # Mark wheezes a silent laugh
    ("gap", 0.04, "cut_mark2"),
    ("line", "L004"),                         # "Honestly, Gary..." (split), "...a bloody SHOVEL!"
    ("gap", 0.08),
    ("gap", 0.80, "cut_palm"),                # Gary's facepalm
    ("gap", 0.04, "cut_mark3"),
    ("line", "L005"),                         # "Still... at least we're consistent." (hopeful)
    ("gap", 0.10, "cut_gary3"),               # Gary looks at him
    ("gap", 0.40),
    ("line", "L006"),                         # "Yeah."
    ("gap", 0.50, "turn"),                    # the pause: his eyes come round to the lens
    ("line", "L007"),                         # "We are consistent at being shit."
    ("gap", 0.30),
    ("gap", 0.85, "cut_nod"),                 # Mark nods, slowly
    ("gap", 1.90, "toast"),                   # both of them: NEW LOW UNLOCKED
    ("gap", 0.12, "black"),                   # hard cut to black
]

TL = build(SEQ, L)
