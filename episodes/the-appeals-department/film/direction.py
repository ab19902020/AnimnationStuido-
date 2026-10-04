"""The shot list for the test: every cut, camera move and caption, keyed to the dialogue edit (timeline.py).

Where everyone is (one podcast studio, five armchairs round a low table): Gary in the second chair from the left
(screen left), Micah in the middle, Roy in the fourth (screen right); the door is off to the right, past Roy,
where Pep appears. The taped sign is on the wall above Gary. So Gary looks screen right to Micah, Roy and the
door; Roy looks screen left to them and right to the door; Micah looks left to Gary, right to Roy.

The All or Something grammar: close singles (the wall behind out of focus, the character, the low table's edge in
front: it hides where a standing drawing would show it isn't sitting), two-shots as a pair behind the table,
inserts on the props that change the story, an opening move along the set to Gary's sign."""
import json

from studio.film import ep
from studio.film.shots import Marks, card, ease, finish, group, insert, shot_at as _shot_at, single, world
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt = T.m, T.ls, T.le, T.wt

PLATES = {"S": "tv-and-media/podcast-studio", "T": "tv-and-media/podcast-studio"}     # T: the table without its plant
# things in front of the actors (1x plate px): the low table (its far rim traced, the slatted side) with its mugs,
# plant and books; plate "T" is the same table with the plant taken off (props.plate_image)
RIM = [(572, 586), (582, 576), (600, 569), (630, 562), (650, 559), (708, 554), (726, 552), (738, 552), (972, 553),
       (996, 555), (1056, 563), (1080, 568), (1104, 576), (1114, 590)]    # the far rim's top edge, traced between
                                                                           # the mugs; flat behind the plant
TABLE = [(566, 640), (570, 600)] + RIM + [(1116, 592), (1118, 610), (1118, 760), (566, 760)]
MUGS = [[(639, 556), (641, 548), (653, 543), (656, 537), (688, 537), (692, 543), (704, 548), (707, 556), (707, 580),
         (639, 580)],
        [(741, 555), (742, 540), (754, 536), (754, 530), (790, 530), (792, 540), (792, 576), (741, 576)],
        [(915, 540), (917, 529), (950, 528), (952, 536), (961, 540), (963, 550), (963, 570), (915, 570)],
        [(1003, 545), (1005, 540), (1042, 539), (1044, 546), (1055, 548), (1057, 560), (1057, 586), (1003, 586)]]
PLANT = [(783, 553), (790, 530), (800, 515), (825, 500), (850, 494), (880, 502), (900, 515), (910, 535), (915, 553)]
# the empty guest chair at the right-hand end (the one nearest the door): Pep stands behind it
CHAIR = [(1442, 560), (1446, 492), (1451, 446), (1454, 434), (1456.5, 426), (1460, 419), (1465, 411.5), (1470, 406.5),
         (1480, 404), (1550, 404), (1605, 405.5), (1615, 409), (1622, 413), (1628, 419), (1631.5, 426), (1633, 440),
         (1633, 478), (1648, 488), (1652, 560)]
OCCL = {"S": {"table": [TABLE] + MUGS + [PLANT], "chair": [CHAIR]}, "T": {"table": [TABLE] + MUGS}}
RIM_Y = 552                         # the table's far rim at its middle (plate x 843)

# gaze towards characters who are out of frame: screen direction (x: -1 left .. 1 right, y: + down) and head turn
EYES = {
    "gary": dict(micah=(0.65, 0.05, 0.22), roy=(0.9, 0.02, 0.32), pep=(1.0, -0.05, 0.4)),
    "micah": dict(gary=(-0.85, 0.02, -0.3), roy=(0.85, 0.02, 0.3), pep=(1.0, -0.05, 0.38)),
    "roy": dict(gary=(-0.9, 0.02, -0.34), micah=(-0.65, 0.05, -0.22), pep=(0.95, -0.05, 0.36)),
    "pep": dict(gary=(-0.95, 0.08, -0.36), micah=(-0.8, 0.08, -0.3), roy=(-0.6, 0.06, -0.24)),
}
DRAW = {"gary": "gary-neville:front", "micah": "micah-richards:front", "roy": "roy-keane:front",
        "pep": "pep-guardiola:front"}
# each one's set-up: the wall behind them (plate, cx, cy, zoom, blur) and the table's edge in front (plate, mask,
# cx, the edge's y in the plate, zoom, blur); Pep stands by the door with nothing in front of him
EYE = {"gary": (760, 400), "micah": (980, 400), "roy": (1160, 400), "pep": (1180, 400)}
FZ = 3.4                            # the table's zoom in a single


def under(x_plate, x_screen):
    """the foreground's view centre that puts plate x (the middle of the table's far rim, the chair back) under a
    character standing at screen x"""
    return x_plate - (x_screen - 960) / (1920 / 1672 * FZ)


SET = {
    "gary": dict(bg=("S", 500, 300, 2.4, 4.5), fg=("T", "table", under(843, 760), RIM_Y, FZ, 2.5)),
    "micah": dict(bg=("S", 836, 300, 2.4, 4.5), fg=("T", "table", under(843, 980), RIM_Y, FZ, 2.5)),
    "roy": dict(bg=("S", 1150, 300, 2.4, 4.5), fg=("T", "table", under(843, 1160), RIM_Y, FZ, 2.5)),
    "pep": dict(bg=("S", 1470, 330, 2.3, 4.5), fg=("S", "chair", under(1545, 1180), 405, FZ, 2.5), table=3.4),
}
MCU = 112.0


def close(t, who, ed=MCU, eye=None, push=(1.0, 1.04), drift=0.8, table=None, **kw):
    """a close single: the wall behind blurred, the character, the low table's edge (Pep: the chair back) in front,
    `table` eye distances below the eyes"""
    st = SET[who]
    return single(t, who, DRAW[who], st["bg"], st["fg"], ed=ed, eye=eye or EYE[who], table=table or st.get("table", 3.9),
                  push=push, drift=drift, **kw)


def two(t, a, b, ed=80.0, push=(1.0, 1.03), **kw):
    """two of them side by side behind the table, the wall behind out of focus"""
    acts = [(a, DRAW[a], (690, 430), ed, False), (b, DRAW[b], (1230, 430), ed, False)]
    return group(t, acts, cams=[(t, (960, 540, push[0])), (t + 3.0, (960, 540, push[1]))],
                 bg=("S", 672, 300, 1.9, 3.5), fg=("S", "table", 830, RIM_Y, 2.3, 2.0), table_y=430 + 4.1 * ed, **kw)


# the opening: along the wall, past the framed shirts and trophies, until the taped sign spoils it
OPEN = [(0.0, (1440, 150, 2.9)), (wt("L001", "appealing") - 0.2, (470, 160, 2.9)),
        (wt("L001", "and") - 0.05, (464, 162, 2.98))]

SHOTS = finish([
    world(0.0, "S", OPEN[0][1], cams=OPEN, drift=0.35),                             # the set... the sign
    close(wt("L001", "and") - 0.05, "gary", push=(1.0, 1.03)),                      # "...a gap in the market."
    close(m("cut_roy1"), "roy"),                                                     # "A football match?"
    two(m("cut_gm1"), "gary", "micah"),                                              # the sales team
    close(m("cut_micah1"), "micah", ed=108),                                         # "Guaranteed result?"
    close(m("cut_gary1"), "gary"),                                                   # "...It's on the sign."
    close(m("cut_roy2"), "roy", push=(1.0, 1.07)),                                   # the Post Office
    close(m("cut_gary2"), "gary"),                                                   # under-fourteens; eyes on the reader
    close(m("cut_roy3"), "roy", ed=118),                                             # "...on a toddler."
    insert(m("cut_reader1"), "reader_flip"),                                         # Micah turns the reader over
    two(m("squeak") - 0.12, "gary", "micah", ed=74, push=(1.0, 1.0)),                # the door squeaks: they look
    close(m("cut_pep1"), "pep", ed=104, push=(1.0, 1.05)),                           # Pep in the doorway
    close(m("cut_gary3"), "gary"),                                                   # "And you object to all of them?"
    close(m("cut_pep2"), "pep", ed=120, push=(1.0, 1.02)),                           # "All of them."
    two(m("cut_look"), "gary", "micah", ed=86, push=(1.0, 1.05)),                    # the look
    insert(m("cut_reader2"), "reader_charge"),                                       # REGISTER GUEST... 115 APPEALS
    close(m("cut_pep3"), "pep", ed=110),                                             # "Why have you charged me..."
    close(m("cut_gary4"), "gary", push=(1.0, 1.06)),                                 # "Two thousand two hundred..."
    close(m("cut_roy4"), "roy", ed=120, push=(1.0, 1.07)),                           # the mugging; then to us
    card(m("cut_title"), "title"),
], TL["total"])

TITLE = (("UNITED ROAD", "BEBAS", 120, None, 14, 300, (255, 255, 255)),
         ("THE APPEALS DEPARTMENT", "BEBAS", 150, None, 10, 420, (255, 255, 255)))
TAGLINE = (("£19.99 PER APPEAL. UNDER-14s GO FREE.", "BEBAS", 60, None, 5, 760, (236, 236, 236)),)

# documentary captions: (start, end, kind, text 1, text 2)
CAPTIONS = [
    (wt("L001", "and") + 0.25, m("cut_roy1") - 0.05, "name", "GARY NEVILLE", "Host. Head of Appeals."),
    (m("cut_roy1") + 0.1, m("cut_gm1") - 0.05, "name", "ROY KEANE", "Co-host. Wants a cup of tea."),
    (m("cut_micah1") + 0.05, m("cut_gary1") - 0.05, "name", "MICAH RICHARDS", "Co-host. In charge of the card reader."),
    (m("cut_pep1") + 0.2, m("cut_gary3") - 0.05, "name", "PEP GUARDIOLA", "Guest. Here for a five-minute interview."),
]
WHIPS = []


def shot_at(t):
    return _shot_at(SHOTS, t)
