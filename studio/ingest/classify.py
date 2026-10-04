"""Name the drawings on a kit sheet.

Body sheets (front / three_quarter / side / back) carry the 18-part inventory of the kit brief plus an assembled
guide figure: head, eyes (eyes and brows, one or several pieces), mouth, neck, torso, pelvis and the pairs
upper_arm, forearm, hand, thigh, shin, foot. Hand sheets carry ten paired gestures in two rows of five.

The guesses use colour (skin / white / clothing), shape and position, and pair up the limbs. They are a first
draft: every sheet's result is written to a YAML file next to the sheet, checked by eye on the overview, and
corrected there (a part is recorded as a point inside its drawing, so the file survives re-slicing)."""
import cv2
import numpy as np

HAND_POSES = ["open_palm", "relaxed", "fist", "point", "thumbs_up",
              "ok", "wave", "grip", "stop", "back"]
PAIRED = ["upper_arm", "forearm", "hand", "thigh", "shin", "foot"]


# ------------------------------------------------------------------------------------------------ features
def _rgb(rgba, p):
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    return rgba[p.y0:p.y1, p.x0:p.x1, :3][m].astype(np.float32)


def skin_tone(rgba, ps):
    """The character's skin colour: the median fill colour of the hand drawings (hands are all skin)."""
    cols = []
    for p in ps:
        rgb = _rgb(rgba, p)
        lum = rgb.mean(1)
        cols.append(rgb[(lum > 70) & (rgb.min(1) < 235)])
    allc = np.concatenate(cols) if cols else np.zeros((1, 3), np.float32)
    return np.median(allc, 0)


def feats(rgba, p, skin):
    rgb = _rgb(rgba, p)
    lum = rgb.mean(1)
    sat = rgb.max(1) - rgb.min(1)
    skinf = float(np.mean(np.linalg.norm(rgb - skin, axis=1) < 48)) if len(rgb) else 0.0
    white = float(np.mean(rgb.min(1) > 225))
    dark = float(np.mean(lum < 55))
    m = p.mask[p.y0:p.y1, p.x0:p.x1].astype(np.uint8)
    per = float(np.count_nonzero(m[1:, :] != m[:-1, :]) + np.count_nonzero(m[:, 1:] != m[:, :-1]))
    # eye whites are solid white shapes; white in a beard or on a shirt print is scattered or thin
    wm = np.zeros(m.shape, np.uint8)
    crop = rgba[p.y0:p.y1, p.x0:p.x1, :3]
    wm[(crop.min(2) > 225) & (m > 0)] = 1
    wm = cv2.morphologyEx(wm, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(wm, connectivity=8)
    solid_white = float(st[1:, cv2.CC_STAT_AREA][st[1:, cv2.CC_STAT_AREA] > 0.04 * p.area].sum()) / max(1, p.area) \
        if n > 1 else 0.0
    # colour histogram over every pixel; a gamma lift spreads the dark clothes over several bins
    hist = _hist(rgb)
    # the colours at the two ends of a drawing (top and bottom quarter): where a limb segment meets its neighbours
    ys = np.nonzero(m)[0]
    top = _hist(rgba[p.y0:p.y1, p.x0:p.x1, :3][(m > 0) & (np.arange(m.shape[0])[:, None] < 0.25 * m.shape[0])]
                .astype(np.float32))
    bot = _hist(rgba[p.y0:p.y1, p.x0:p.x1, :3][(m > 0) & (np.arange(m.shape[0])[:, None] > 0.75 * m.shape[0])]
                .astype(np.float32))
    return dict(skin=skinf, white=white, solid_white=solid_white, dark=dark,
                sat=float(np.median(sat)) if len(sat) else 0.0,
                fill=p.area / max(1, p.w * p.h), complexity=per * per / max(1.0, p.area), hist=hist,
                top=top, bot=bot, aspect=p.h / max(1, p.w))


def _hist(rgb):
    """normalised colour histogram; the colour fill only (black outline excluded), gamma-lifted so dark clothes
    spread over several bins"""
    if len(rgb):
        keep = rgb.max(1) > 45
        rgb = rgb[keep] if keep.sum() > 0.1 * len(rgb) else rgb
    lifted = 255 * (np.clip(rgb, 0, 255) / 255) ** 0.5
    h = np.histogramdd(lifted, bins=(6, 6, 6), range=((0, 256),) * 3)[0].ravel() if len(rgb) else np.zeros(216)
    return h / max(1.0, h.sum())


def _hsim(a, b):
    return float(np.minimum(a, b).sum())


# ------------------------------------------------------------------------------------------------ labels
def drop_text(rgba, ps, H):
    """Small grey pieces sitting in a row with other small grey pieces are label text."""
    cand = []
    for p in ps:
        # label lettering is ~15 px tall on a 1024 px sheet; brows (dark, side by side) are twice that
        if p.kind != "part" or p.h > 0.022 * H or p.area > 0.002 * H * H:
            continue
        rgb = _rgb(rgba, p)
        if np.median(rgb.max(1) - rgb.min(1)) < 40 and np.median(rgb.mean(1)) < 170:
            cand.append(p)
    for p in cand:
        row = [q for q in cand if q is not p and abs(q.cy - p.cy) < max(p.h, q.h) * 0.8
               and abs(q.cx - p.cx) < 6 * max(p.h, q.h)]
        if len(row) >= 1:
            p.kind = "label"
    # fragments of a word: tiny, black, several letter blobs (a mouth line is tiny too, but a single stroke)
    for p in ps:
        if p.kind == "part" and p.area < 0.0005 * H * H and p.blobs >= 2:
            if np.median(_rgb(rgba, p).mean(1)) < 70:
                p.kind = "label"


# ------------------------------------------------------------------------------------------------ hand sheets
def hands(rgba, ps, cuts=None):
    """{pose: {"R": piece, "L": piece}} for a hand sheet, plus the guide piece. Touching pairs are split; the cut
    lines are appended to `cuts` (sheet pixels) so the sheet's YAML can reproduce them."""
    from studio.ingest.sheet import split_wide
    parts = [p for p in ps if p.kind == "part"]
    guide = max(parts, key=lambda p: p.h)
    rest = [p for p in parts if p is not guide]
    med = np.median(sorted(p.area for p in rest)[-20:])
    for p in rest:
        if p.area < 0.2 * med:
            p.kind = "speck"
    rest = [p for p in rest if p.kind == "part"]
    # a pair drawn touching comes out as one double-width drawing: split it
    wmed = np.median([p.w for p in rest])
    for p in list(rest):
        if p.w > 1.6 * wmed:
            rest.remove(p)
            halves = split_wide(p)
            for q in halves:
                q.idx = len(ps)
                ps.append(q)
            rest += halves
            if cuts is not None:
                x = halves[1].x0
                cuts.append([x, p.y0 - 2, x, p.y1 + 2])
    hs = sorted(rest, key=lambda p: -p.area)[:20]
    # two rows by vertical centre, then left to right; poses come in pairs
    ys = np.array([p.cy for p in hs])
    split = (ys.min() + ys.max()) / 2
    rows = [sorted([p for p in hs if p.cy < split], key=lambda p: p.cx),
            sorted([p for p in hs if p.cy >= split], key=lambda p: p.cx)]
    out = {}
    for r, row in enumerate(rows):
        for k in range(len(row) // 2):
            pose = HAND_POSES[r * 5 + k]
            a, b = row[2 * k], row[2 * k + 1]
            out[pose] = {"R": a, "L": b}          # provisional; handedness fixed by thumb side below
    _hand_sides(out)
    return guide, out


def thumb_side(p):
    """+1 if the thumb sticks out on the sheet-right side of a fingers-up hand drawing, -1 if on the left.
    The thumb is the lone protrusion at mid-height: compare how far each side reaches there vs. at the wrist."""
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    h = m.shape[0]
    xs = np.arange(m.shape[1])

    def extent(r0, r1):
        band = m[int(r0 * h):int(r1 * h)]
        cols = band.any(0)
        if not cols.any():
            return 0.0, 0.0
        return xs[cols].min(), xs[cols].max()

    l_mid, r_mid = extent(0.45, 0.75)
    l_wr, r_wr = extent(0.85, 1.0)
    return 1 if (r_mid - r_wr) > (l_wr - l_mid) else -1


# which way each gesture is drawn: the palm towards the camera, or the back of the hand
PALM_POSES = ("open_palm", "wave", "stop", "ok")
BACK_POSES = ("back",)


def _hand_sides(out):
    """Anatomical handedness. Seen fingers-up with the palm to the camera, a right hand has its thumb on the
    sheet-right side; seen from the back, on the sheet-left. The generator draws each pair in thumb order, not
    hand order, so every palm or back pose is decided on its own. The other gestures (relaxed, fist, point,
    thumbs up, grip) have no clear facing and follow the stop pose's order."""
    def right_first(pose):
        a = out[pose]["R"]                          # the sheet-left drawing of the pair
        t = thumb_side(a)
        return t > 0 if pose in PALM_POSES else t < 0
    ref = right_first("stop") if "stop" in out else True
    for pose in out:
        first = right_first(pose) if pose in PALM_POSES + BACK_POSES else ref
        if not first:
            out[pose] = {"R": out[pose]["L"], "L": out[pose]["R"]}


# ------------------------------------------------------------------------------------------------ body sheets
def body(rgba, ps, skin, view):
    """{part name: [pieces]} for a body sheet, plus the guide piece. Paired parts are named <part>_R / <part>_L
    (anatomical: the character's own right and left).

    Structure, not layout: the limbs come as mirror pairs and the torso, pelvis, neck and mouth are one-offs, so
    the drawings are paired up first; then every way of naming the limb pairs is scored (size, colour shared with
    the torso or the pelvis, which pair sits next to the hands and which next to the feet) and the best wins."""
    import itertools
    H, W = rgba.shape[:2]
    drop_text(rgba, ps, H)
    parts = [p for p in ps if p.kind == "part"]
    guide = max(parts, key=lambda p: p.h)
    rest = [p for p in parts if p is not guide]
    F = {id(p): feats(rgba, p, skin) for p in rest}
    f = lambda p: F[id(p)]
    named = {}
    left = set(map(id, rest))

    def take(name, p):
        named.setdefault(name, []).append(p)
        left.discard(id(p))

    def avail():
        return [p for p in rest if id(p) in left]

    # head: the most skin in the upper part of the sheet
    top = [p for p in avail() if p.cy < 0.6 * H]
    head = max(top, key=lambda p: f(p)["skin"] * p.area)
    take("head", head)
    hs = head.area
    near_head = lambda p, k: abs(p.cx - head.cx) < k * head.w and abs(p.cy - head.cy) < k * head.h

    # eyes: white-rich drawings with dark pupils, close to the head; brows: dark thin drawings just above them
    eyes = [p for p in avail() if f(p)["solid_white"] > 0.12 and f(p)["dark"] > 0.03 and p.area < 0.2 * hs
            and f(p)["skin"] < 0.45 and near_head(p, 1.9)]
    for p in eyes:
        take("eyes", p)
    if eyes:
        ex0, ex1 = min(p.x0 for p in eyes), max(p.x1 for p in eyes)
        ey0 = min(p.y0 for p in eyes)
        eh = max(p.h for p in eyes)
        for p in avail():
            # a brow: a dark (brown, grey or black) stroke, wider than tall, just above the eyes
            browish = np.median(_rgb(rgba, p).mean(1)) < 125 and p.w > 1.3 * p.h and f(p)["skin"] < 0.3
            if browish and p.cy < ey0 + 0.3 * eh and p.y1 > ey0 - 1.6 * eh and \
                    p.x1 > ex0 - eh and p.x0 < ex1 + eh and p.area < 0.15 * hs:
                take("eyes", p)

    # pair the remaining drawings: mutual best matches with a high likeness
    pool = avail()
    sim = {}
    for a, b in itertools.combinations(pool, 2):
        sim[id(a), id(b)] = sim[id(b), id(a)] = _likeness(a, b, f)
    pairs, paired = [], set()
    for a, b in sorted(itertools.combinations(pool, 2), key=lambda ab: -sim[id(ab[0]), id(ab[1])]):
        if id(a) in paired or id(b) in paired or sim[id(a), id(b)] < 0.45 or \
                min(a.area, b.area) < 0.8 * max(a.area, b.area) or min(a.area, b.area) < 0.03 * hs:
            continue
        pairs.append((a, b))
        paired |= {id(a), id(b)}
    singles = [p for p in pool if id(p) not in paired]
    # more than six pairs: the weakest extra pairs were one-offs that happen to look alike (neck + mouth)
    pairs.sort(key=lambda pr: -sim[id(pr[0]), id(pr[1])])
    while len(pairs) > 6:
        singles += list(pairs.pop())

    # one-offs: torso and pelvis are the two biggest, the torso being the bigger; neck and mouth are small, by the head
    singles.sort(key=lambda p: -p.area)
    big = [p for p in singles if p.area > 0.12 * hs][:2]
    if big:
        take("torso", big[0])
    if len(big) > 1:
        take("pelvis", big[1])
    small = [p for p in singles if id(p) in left and p.area < 0.35 * hs and near_head(p, 3.0)]
    # the neck is a short skin cylinder: straight sides, so the same width on every row; a mouth tile is an oval,
    # a curve or a beard patch whose width changes
    necks = sorted((p for p in small if f(p)["skin"] > 0.4),
                   key=lambda p: -f(p)["skin"] * f(p)["fill"] * max(0.05, 1 - 6 * _width_cv(p)))
    if necks:
        take("neck", necks[0])
        small.remove(necks[0])
    if small:
        e = named.get("eyes", [head])
        tx, ty = np.mean([p.cx for p in e]), np.mean([p.cy for p in e])
        take("mouth", min(small, key=lambda p: abs(p.cx - tx) + abs(p.cy - ty)))

    # limb pairs: try every naming, keep the best score
    tor = named.get("torso", [None])[0]
    pel = named.get("pelvis", [None])[0]
    th = feats(rgba, tor, skin)["hist"] if tor else None
    ph = feats(rgba, pel, skin)["hist"] if pel else None
    names = ["hand", "foot", "upper_arm", "forearm", "thigh", "shin"]
    pairs = pairs[:6]
    mean_h = lambda pr, key: np.mean([f(p)[key] for p in pr], 0)
    P = [dict(cx=np.mean([p.cx for p in pr]), cy=np.mean([p.cy for p in pr]),
              area=np.mean([p.area for p in pr]), wide=np.mean([p.w / p.h for p in pr]),
              skin=np.mean([f(p)["skin"] for p in pr]), cx_=np.mean([f(p)["complexity"] for p in pr]),
              top=mean_h(pr, "top"), bot=mean_h(pr, "bot"))
         for pr in pairs]
    G = guide.h

    def near(a, b):     # 1 when two pairs sit next to each other on the sheet, falling to 0 a guide-height away
        return max(0.0, 1 - np.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]) / (0.6 * G))

    sim = lambda a, b: _hsim(a, b) if a is not None and b is not None else 0.0
    best, bs = None, -1e9
    for perm in itertools.permutations(range(len(pairs)), min(6, len(pairs))):
        R = {names[k]: P[i] for k, i in enumerate(perm)}
        s = 0.0
        if "hand" in R:
            s += 2 * R["hand"]["skin"] + 0.02 * R["hand"]["cx_"]
        if "foot" in R:
            s += 1.5 * min(R["foot"]["wide"], 2.0) + 1.0 * R["foot"]["cy"] / H - 1.5 * R["foot"]["skin"]
        # a sleeve carries on from the shirt, a trouser leg or shorts hem from the pelvis
        if "upper_arm" in R:
            s += 2.0 * sim(R["upper_arm"]["top"], th) - 1.0 * sim(R["upper_arm"]["top"], ph)
        if "thigh" in R:
            s += 2.0 * sim(R["thigh"]["top"], ph) - 1.0 * sim(R["thigh"]["top"], th)
            s += 0.6 * (R["thigh"]["area"] >= max(p["area"] for k, p in R.items()
                                                  if k in ("upper_arm", "forearm", "shin")))
        # consecutive segments meet in the same colour (the sleeve or trouser carries on, or skin meets skin)
        for a, b in (("upper_arm", "forearm"), ("thigh", "shin"), ("forearm", "hand")):
            if a in R and b in R:
                s += 1.0 * sim(R[a]["bot"], R[b]["top"])
        for a, b in (("forearm", "hand"), ("upper_arm", "forearm"), ("shin", "foot"), ("thigh", "shin")):
            if a in R and b in R:
                s += 1.0 * near(R[a], R[b])
        for a, b in (("forearm", "foot"), ("shin", "hand")):
            if a in R and b in R:
                s -= 0.6 * near(R[a], R[b])
        if "forearm" in R and "upper_arm" in R:      # arm segments sit above leg segments on almost every sheet
            s += 0.4 * float(R["upper_arm"]["cy"] <= R.get("thigh", R["upper_arm"])["cy"])
        if s > bs:
            best, bs = perm, s
    for k, i in enumerate(best or []):
        for p in pairs[i]:
            take(names[k], p)
    for p in avail():
        take("unknown", p)
    return guide, _sides(named, view)


def _width_cv(p):
    """how much a drawing's width changes over its middle rows (0 for straight sides)"""
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    h = m.shape[0]
    rows = m[int(0.2 * h):max(int(0.2 * h) + 1, int(0.8 * h))]
    w = np.array([np.ptp(np.nonzero(r)[0]) + 1 if r.any() else 0 for r in rows], float)
    return float(w.std() / max(1.0, w.mean()))


def _likeness(a, b, f):
    """0..1: how alike two drawings are in size, shape and colour (a mirror pair scores close to 1)"""
    size = min(a.area, b.area) / max(a.area, b.area)
    dims = min(a.h, b.h) / max(a.h, b.h) * min(a.w, b.w) / max(a.w, b.w)
    return size * dims * _hsim(f(a)["hist"], f(b)["hist"])


def _sides(named, view):
    """<part> -> <part>_R / <part>_L. Front view: a limb hanging away from the body slants outwards, so a drawing
    whose lower end sits further sheet-left is the character's right side; drawings with no clear slant follow
    sheet order (sheet-left = character's right, like the guide figure). Turned views: sheet-left = near side."""
    out = {}
    for name, ps in named.items():
        if name not in PAIRED or len(ps) != 2:
            out[name] = ps
            continue
        a, b = sorted(ps, key=lambda p: p.cx)
        r, l = a, b
        if view == "front" and name in ("upper_arm", "forearm", "thigh", "shin"):
            sa, sb = _slant(a), _slant(b)
            if sa > 0.06 and sb < -0.06:          # a leans down to the right, b down to the left: swapped
                r, l = b, a
        out[name + "_R"] = [r]
        out[name + "_L"] = [l]
    return out


def _slant(p):
    """horizontal shift of the bottom end vs the top end, as a fraction of the height (+ = bottom further right)"""
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    h = m.shape[0]
    xs = np.arange(m.shape[1])

    def cx(r0, r1):
        band = m[int(r0 * h):max(int(r0 * h) + 1, int(r1 * h))]
        w = band.sum(0)
        return float((w * xs).sum() / max(1, w.sum()))

    return (cx(0.8, 1.0) - cx(0.0, 0.2)) / max(1, h)
