"""Shot-list helpers for an episode's direction.py (from All or Something). Times come from the dialogue edit:

    from studio.film.shots import Marks, single, world, group, card, insert, finish
    T = Marks(TL, LINES)        # T.m("cut_roy1"), T.ls("L002") line start, T.le("L002") line end,
                                # T.wt("L003", "nineteen") a word's start, T.we(...) its end
    SHOTS = finish([...])       # each shot runs to the next one's start

Layout is in 1920 x 1080 screen px. A single places the point between the character's eyes at `eye` with an eye
distance of `ed` px (MCU ~ 110, CU ~ 140, two-shot ~ 75): the same character is the same size in every drawing."""


class Marks:
    def __init__(self, TL, lines):
        self.TL, self.L = TL, lines

    def m(self, k):
        return self.TL["marks"][k]

    def ls(self, k):
        return self.TL["lines"][k]["start"]

    def le(self, k):
        return self.TL["lines"][k]["end"]

    def wt(self, lid, word, k=1):
        """timeline time of the k-th occurrence of a word in a line"""
        n = 0
        for w in self.L[lid]["words"]:
            if w["w"] == word:
                n += 1
                if n == k:
                    return self.ls(lid) + w["s"]
        raise KeyError(word)

    def we(self, lid, word, k=1):
        n = 0
        for w in self.L[lid]["words"]:
            if w["w"] == word:
                n += 1
                if n == k:
                    return self.ls(lid) + w["e"]
        raise KeyError(word)


def single(t, who, draw, bg, fg=None, ed=110.0, eye=(760, 430), table=4.5, push=(1.0, 1.04), drift=1.0,
           grade="studio", mirror=False, punch=None, **extra):
    """one character on screen. bg = (plate, cx, cy, zoom, blur px); fg = (plate, occluder mask, cx, the edge's y
    in the plate, zoom, blur px) or None; table = the edge's distance below the eyes in eye distances; push =
    scale at the shot's start / end; punch = (t, factor) a snap punch-in"""
    d = dict(t=t, kind="single", who=who, draw=draw, ed=ed, eye=eye, table=table, push=push, drift=drift,
             grade=grade, bg=bg, fg=fg, punch=punch, mirror=mirror)
    d.update(extra)
    return d


def world(t, plate, cam0, cam1=None, layers=(), grade="studio", drift=0.6, blur=0.0, ease="inout", cams=None,
          **extra):
    """characters in a plate at true scale. layers: ("actors", [(who, drawing, (x, y) 1x plate px of the eyes,
    eye distance in plate px, mirror[, {clip: y}])]), ("occl", mask name) or ("props", props.py function),
    composited in order. cam = (cx, cy, zoom); cams: [(t, cam)] keyframes"""
    d = dict(t=t, kind="world", plate=plate, cam0=cam0, cam1=cam1 or cam0, layers=list(layers), grade=grade,
             drift=drift, blur=blur, ease=ease, cams=cams)
    d.update(extra)
    return d


def group(t, actors, cams, bg, fg=None, table_y=None, grade="studio", drift=0.5, **extra):
    """several characters composited like a single; cams: [(t, (stage x, stage y, zoom))]"""
    d = dict(t=t, kind="group", actors=actors, cams=cams, table_y=table_y, bg=bg, fg=fg, grade=grade, drift=drift)
    d.update(extra)
    return d


def insert(t, draw, **extra):
    """a full-frame close-up drawn by the episode's props.<draw>(shot, t)"""
    d = dict(t=t, kind="insert", draw=draw)
    d.update(extra)
    return d


def card(t, kind, **extra):
    d = dict(t=t, kind=kind)
    d.update(extra)
    return d


def finish(shots, total):
    for i, s in enumerate(shots):
        s["end"] = shots[i + 1]["t"] if i + 1 < len(shots) else total
        s["i"] = i
    return shots


def shot_at(shots, t):
    for s in reversed(shots):
        if t >= s["t"] - 1e-9:
            return s
    return shots[0]


def ease(u, kind="inout"):
    u = min(1.0, max(0.0, u))
    if kind == "inout":
        return u * u * (3 - 2 * u)
    if kind == "out":
        return 1 - (1 - u) ** 2
    return u
