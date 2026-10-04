"""The dialogue edit for the test (Scene 1 and the start of Scene 2): every line in script order with the beats
between them, and the marks the shots, the acting and the sound hang off. Sitcom pacing: a few frames between
lines, holds only where the script asks for a reaction."""
import json

from studio.film import ep
from studio.film.timeline import build

L = json.loads(ep.path("lines.json").read_text())

SEQ = [
    ("gap", 0.45, "open"),                    # the studio, a slow track along the chairs to Gary and his sign
    ("line", "L001"),                         # Gary, mid-pitch
    ("gap", 0.22, "cut_roy1"),                # Roy, unmoved
    ("line", "L002"),
    ("gap", 0.14, "cut_gm1"),                 # Gary and Micah: the sales team
    ("line", "L003"),
    ("gap", 0.10, "cut_micah1"),
    ("line", "L004"),                         # "Guaranteed result?"
    ("gap", 0.10, "cut_gary1"),
    ("line", "L005"),                         # "...It's on the sign."
    ("gap", 0.32, "cut_roy2"),
    ("line", "L006"),                         # the Post Office
    ("gap", 0.20, "cut_gary2"),
    ("line", "L007"),                         # under-fourteens: his eyes check the card reader
    ("gap", 0.16, "cut_roy3"),
    ("line", "L008"),                         # "...on a toddler."
    ("gap", 0.40),                            # it lands
    ("gap", 2.00, "cut_reader1"),             # Micah turns the card reader over: PROPERTY OF GARY NEVILLE'S...
    ("gap", 0.95, "squeak"),                  # a quiet door squeak: they all look to the door
    ("gap", 0.70, "cut_pep1"),                # Pep, standing behind the empty guest chair
    ("line", "L009"),
    ("gap", 0.16, "cut_gary3"),
    ("line", "L010"),                         # "And you object to all of them?"
    ("gap", 0.14, "cut_pep2"),
    ("line", "L011"),                         # "All of them."
    ("gap", 0.30),                            # held on Pep
    ("gap", 1.40, "cut_look"),                # Gary and Micah: a tiny look of commercial understanding
    ("gap", 1.05, "cut_reader2"),             # hard cut to the card reader: REGISTER GUEST... tap...
    ("gap", 1.15, "tap"),                     # 115 APPEALS  £2,298.85  APPROVED
    ("gap", 0.60, "cut_pep3"),                # Pep has felt his phone buzz
    ("line", "L012"),
    ("gap", 0.14, "cut_gary4"),
    ("line", "L013"),
    ("gap", 0.40, "cut_roy4"),                # Roy has seen enough
    ("line", "L014"),
    ("gap", 1.20),                            # he looks at us
    ("gap", 3.00, "cut_title"),               # hard cut to the title
]

TL = build(SEQ, L)
