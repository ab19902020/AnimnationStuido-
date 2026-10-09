"""The dialogue edit: every line in script order with the beats between them, and the marks the shots, the acting
and the sound hang off. ("gap", s, "mark"): the mark names the gap's START. Sitcom pacing: lines tight, holds only
where a look, an insert or a smash needs them; the smashes and the reactions to them get room."""
import json

from studio.film import ep
from studio.film.timeline import build

L = json.loads(ep.path("lines.json").read_text())

SEQ = [
    ("gap", 1.50, "open"),           # the living room: Mum drops into the armchair; the boy plays on the rug
    ("line", "L001"),                # "Five minutes of peace."
    ("gap", 0.25),
    ("gap", 1.70, "cut_vroom"),      # the boy, low on the floor: vroom, the car rolls towards the telly
    ("gap", 0.20, "cut_mum1"),       # Mum
    ("line", "L002"),                # "Oi. Not near the telly."
    ("gap", 0.25),
    ("gap", 3.30, "cut_look"),       # the boy: Mum... the car... the telly... his best smile to Mum
    ("gap", 1.60, "cut_narrow"),     # Mum narrows her eyes, then back to her phone
    ("gap", 0.15, "cut_wind1"),      # the telly wall: the boy stands winding up the car
    ("gap", 0.75, "wind1"),          # (he winds up while Mum doesn't look)
    ("line", "L003"),                # "Don't you dare." (off, from the armchair)
    ("gap", 0.05),
    ("gap", 0.36, "throw1"),         # the throw: the car leaves his hand
    ("gap", 0.42, "smash1"),         # SMASH: white frame, shake, glass
    ("gap", 1.10, "cut_crack1"),     # close on the screen: the crack still spreading; a shard drops, tinkles
    ("gap", 1.40, "cut_shock1"),     # Mum, frozen
    ("gap", 1.10, "cut_point1"),     # the boy beside the telly, pointing at it
    ("gap", 1.00, "cut_boy1"),       # the boy, close, to us
    ("gap", 0.25),
    ("line", "L004"),                # "TV's broken."
    ("gap", 0.55, "cut_mum2"),       # Mum
    ("line", "L005"),                # "Yes. Thank you. Mummy can see that."
    ("gap", 0.40, "cut_office"),     # Dad's office: his phone buzzes on the desk
    ("gap", 1.00, "answer"),         # he picks up
    ("line", "L006"),                # "Hiya love."
    ("gap", 0.15, "cut_mumph1"),
    ("line", "L007"),                # "Your son's broken the telly."
    ("gap", 0.18, "cut_dad2"),
    ("line", "L008"),                # "Is he alright?"
    ("gap", 0.18, "cut_mumph2"),
    ("line", "L009"),                # "He's fine. He's stood next to it. Pointing at it."
    ("gap", 0.15),
    ("gap", 1.50, "cut_pointing"),   # the boy, still pointing, perfectly content
    ("gap", 0.15, "cut_dad3"),
    ("line", "L010"),                # "For fuck's sake. I've only just paid it off."
    ("gap", 0.30),
    ("gap", 0.45, "cut_car"),        # Dad's car
    ("line", "L011"),                # "Could've thrown a cushion..."
    ("gap", 0.30),
    ("gap", 2.00, "cut_shop"),       # the shop: Dad trudges down the aisle of tellies
    ("line", "L012"),                # "Same one again, mate?" (off)
    ("gap", 0.20, "cut_dad4"),
    ("line", "L013"),                # "Same one again."
    ("gap", 0.25),
    ("gap", 1.00, "cut_reader"),     # the card reader: £799
    ("gap", 1.40, "beep"),           # tap, beep: APPROVED
    ("gap", 2.40, "cut_hall"),       # the front door: Dad staggers in with the box
    ("gap", 1.10, "cut_install"),    # the new telly, set up; Dad kneeling by the box
    ("line", "L014"),                # "Right. This one had better see Christmas."
    ("gap", 0.15, "cut_ban"),        # Mum marches through with the toy box
    ("line", "L015"),                # "And toys are banned. All of them."
    ("gap", 0.25),
    ("gap", 1.70, "cut_sulk"),       # the boy sulks
    ("gap", 1.80, "card_weeks"),     # TWO WEEKS LATER
    ("gap", 0.25, "cut_dad5"),       # Dad, generous, by the toy box
    ("line", "L016"),                # "He's learned his lesson..."
    ("gap", 0.20, "cut_mum5"),
    ("line", "L017"),                # "On your head be it."
    ("gap", 0.30),
    ("gap", 1.60, "card_minutes"),   # TWO MINUTES LATER
    ("gap", 2.40, "cut_sneak"),      # the boy creeps in with the soft ball, stops: finger to his lips, to us
    ("gap", 1.10, "cut_wind2"),      # he winds up
    ("gap", 0.45, "throw2"),
    ("gap", 0.36, "smash2"),         # SMASH, bigger
    ("gap", 1.50, "cut_crack2"),     # the hole; the glass falls
    ("gap", 1.15, "cut_run"),        # Mum and Dad run in
    ("gap", 0.10, "cut_dad6"),
    ("line", "L018"),                # "What the f..."
    ("gap", 0.05, "cut_boy2"),       # the boy cuts in
    ("line", "L019"),                # "TV's brooooken."
    ("gap", 0.55, "cut_mum6"),
    ("line", "L020"),                # "Yes. We can see that."
    ("gap", 0.30),
    ("gap", 1.90, "cut_sofa"),       # the two of them, slumped, the wrecked telly behind
    ("gap", 0.20, "cut_dad7"),
    ("line", "L021"),                # "How? It's a soft ball."
    ("gap", 0.25, "cut_mum7"),
    ("line", "L022"),                # "...We're getting a projector."
    ("gap", 0.30, "cut_dad8"),
    ("line", "L023"),                # "Yeah. Probably for the best."
    ("gap", 0.40),
    ("gap", 2.60, "cut_proj"),       # the projector: a dinosaur on the wall; the boy on the rug looks up at it
    ("gap", 1.00, "cut_boy3"),       # the boy, close: the projector... the ball in his hand...
    ("line", "L024"),                # "Don't. You. Dare." (Dad, off)
    ("gap", 0.25),
    ("gap", 1.20, "smile"),          # his smile, to us
    ("gap", 1.10, "cut_black"),      # black: SMASH
    ("gap", 3.20, "cut_title"),      # BROKEN TELE
    ("gap", 0.60, "cut_post"),       # black again
    ("line", "L025"),                # "TV's broken?"
    ("gap", 1.40, "end"),
]

TL = build(SEQ, L)
