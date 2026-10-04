"""Face rigs: each view's eye overlay and mouth placement turned into animatable pieces, in head-image pixels.

    python3 -m studio.face.build CHARACTER [CHARACTER ...]     (after studio.rig.build)

Where the features go comes from the kit's guide figure, which shows the face as designed. Its head is drawn into
the head drawing's pixels and fine-aligned to it (ECC); the eye overlay is matched into that face (in profile, the
one overlay eye that matches); the mouth is the ink the guide adds below the eyes that the bare head lacks (its
smile line or lips), searched where faces keep their mouths and scored against the house proportion, which is
also the fallback. A sheet YAML can pin the mouth by hand: face: {mouth: [x, y], mouth_width: w} in sheet pixels
on the loose head drawing (side view: the lips at the front of the face).

From the overlay: per eye the white (its convex hull: cartoon eyes are convex), the pupil with its highlight
(moves for gaze), the outline ring; each brow on its own (moves for expressions); anything else (glasses frames)
as a fixed overlay. Lids are drawn in skin colour at render time. The mouth is the shared library's (mouth.py):
this records where it sits, how wide it is and its line colour. Bearded faces get their moustache lifted out to
be drawn over the mouth; clean-shaven heads get any faint drawn mouth painted out.
Output: build/rig/<id>/<outfit>/<view>/face/ (PNGs + face.json) and head_face.png (the cleaned head)."""
import json
import sys

import cv2
import numpy as np
import yaml
from scipy import ndimage

from studio.ingest import chart, kit, register
from studio.paths import CHARACTERS, BUILD
from studio.rig import skeleton

# mouth width as a fraction of the head drawing's width, per view (one house proportion, like a mouth library)
MOUTH_WIDTH = {"front": 0.3, "three_quarter": 0.27, "side": 0.2}
# where a mouth sits: its centre this many eye heights below the eyes' centre (front and three-quarter faces)
MOUTH_DROP = 1.15
SQUASH = 0.72          # three-quarter mouths: the far half drawn this much narrower (draw.py)
PROFILE_DEPTH = 0.55   # profile mouths: the corner this far back from the lips, in mouth widths (mouth.py)


def rgba(path):
    return cv2.cvtColor(cv2.imread(str(path), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)


def save(path, img):
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA))


def local_matrix(p):
    """part pixels -> parent pixels for a part in the rest pose"""
    return skeleton.mat(p["socket"][0], p["socket"][1], p["rel_angle"], p["rel_scale"], *p["pivot"])


def crop(img, mask):
    """RGBA crop of the pixels in mask, and its offset"""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = img[y0:y1, x0:x1].copy()
    out[..., 3] = np.where(mask[y0:y1, x0:x1], out[..., 3], 0)
    return out, (int(x0), int(y0))


def flat(img, bg=128):
    """RGB on a plain background, float"""
    a = img[..., 3:4].astype(np.float32) / 255
    return img[..., :3].astype(np.float32) * a + bg * (1 - a)


def grey(img):
    return cv2.cvtColor(flat(img).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)


# ---------------------------------------------------------------- the guide's face

def guide_head(cid, outfit, view, head, hp):
    """The kit's guide figure drawn into the head drawing's pixels and fine-aligned to it, the head drawing's
    origin on the sheet, and the sheet YAML's face overrides."""
    png = CHARACTERS / cid / "kit" / outfit / f"{view}.png"
    spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
    sheet, named, guide, _ = kit.resolve(png, spec)
    G = chart.cutout(sheet, [guide])
    m = np.zeros(sheet.shape[:2], bool)
    for p in named["head"]:
        m |= p.mask
    ys, xs = np.nonzero(m)
    origin = (int(xs.min()), int(ys.min()))
    H, W = head.shape[:2]
    r = hp["rest"]
    M0 = skeleton.mat(r["x"], r["y"], r["angle"], r["scale"], *hp["pivot"])      # head px -> guide px
    Gh = cv2.warpAffine(G, cv2.invertAffineTransform(M0[:2]), (W, H), flags=cv2.INTER_LINEAR,
                        borderValue=(0, 0, 0, 0))
    # the head was registered on a coarse grid of scales and angles; ECC lines the two drawings up exactly. A
    # guide head drawn a little differently can drag it off: then keep the registration
    warp = np.eye(2, 3, dtype=np.float32)
    mask = cv2.dilate((head[..., 3] >= 128).astype(np.uint8), np.ones((9, 9), np.uint8))
    try:
        _, w = cv2.findTransformECC(grey(head), grey(Gh), warp.copy(), cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), mask, 5)
        sv = np.linalg.svd(w[:, :2], compute_uv=False)
        if sv.max() < 1.12 and sv.min() > 0.89 and np.abs(w[:, 2]).max() < 0.12 * max(W, H):
            warp = w
    except cv2.error:
        pass
    Ga = cv2.warpAffine(Gh, warp, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                        borderValue=(0, 0, 0, 0))
    return Ga, origin, spec.get("face") or {}


def eye_units(eyes):
    """the overlay split per eye (its white, and everything on its side of the gap: pupil, ring, brow)"""
    solid = eyes[..., 3] >= 128
    white = solid & (eyes[..., :3].min(2) > 185)
    white = cv2.morphologyEx(white.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(white, 8)
    if n <= 1:
        return []
    areas = st[1:, cv2.CC_STAT_AREA]
    keep = sorted([i + 1 for i in np.argsort(-areas) if areas[i] >= 0.15 * areas.max()][:2],
                  key=lambda i: cen[i][0])
    xs = [cen[i][0] for i in keep]
    units = []
    for k in range(len(keep)):
        lo = 0 if k == 0 else (xs[k - 1] + xs[k]) / 2
        hi = eyes.shape[1] if k == len(keep) - 1 else (xs[k] + xs[k + 1]) / 2
        side = np.zeros(solid.shape, bool)
        side[:, int(lo):int(np.ceil(hi))] = True
        units.append(solid & side)
    return units


def place_eyes(eyes, Ga, head, view, s0):
    """2x3 matrix from overlay pixels to head pixels, the overlay to use (in profile, one eye of a pair), and the
    match error"""
    H = head.shape[0]
    ys, xs = np.nonzero(head[..., 3] >= 128)
    region = (xs.min(), ys.min() + 0.1 * H, xs.max(), ys.min() + 0.75 * np.ptp(ys))
    search = dict(scales=tuple(s0 * k for k in (0.86, 0.93, 1.0, 1.07, 1.14)), angles=range(-8, 9, 4),
                  region=region)
    units = eye_units(eyes)
    if view == "side" and len(units) == 2:
        # profile: one eye shows; a sheet that drew the pair keeps whichever eye matches the guide
        best = None
        for u in units:
            part, (ox, oy) = crop(eyes, u)
            f = register.fit(part, Ga, **search)
            if best is None or f.err < best[0].err:
                M = np.vstack([f.matrix(part.shape[1], part.shape[0]), [0, 0, 1]])
                best = (f, (M @ np.array([[1, 0, -ox], [0, 1, -oy], [0, 0, 1.0]]))[:2], u)
        f, M, u = best
        one = eyes.copy()
        one[..., 3] = np.where(u, one[..., 3], 0)
        return M, one, f.err
    f = register.fit(eyes, Ga, **search)
    return f.matrix(eyes.shape[1], eyes.shape[0]), eyes, f.err


def neck_stub(head):
    """the neck below the jaw line: lighter pixels reached from the bottom of the drawing without crossing an
    outline (empty if the fill leaks through a gap into the face)"""
    hs = head[..., 3] >= 128
    free = cv2.erode((hs & (grey(head) > 85)).astype(np.uint8), np.ones((3, 3), np.uint8))
    lab, _ = ndimage.label(free)
    ys, _ = np.nonzero(hs)
    band = lab[max(0, ys.max() - 6):ys.max() + 1]
    seeds = np.unique(band[band > 0])
    stub = np.isin(lab, seeds) if len(seeds) else np.zeros_like(hs)
    if stub.any() and np.nonzero(stub)[0].min() < ys.min() + 0.55 * np.ptp(ys):
        return np.zeros_like(hs)
    return stub


def find_mouth(head, Ga, E, eyes, view):
    """Where the face's mouth goes: (centre, width, how). `eyes` = [(cx, cy, w, h)] screen left to right.
    A head drawn with its mouth on ("head") keeps it there; otherwise the mouth the guide adds ("guide"); with
    neither, the house proportion ("prior")."""
    H, W = head.shape[:2]
    hs = head[..., 3] >= 128
    hx = np.nonzero(hs)[1]
    head_w = np.ptp(hx)
    ecx, ecy = np.mean([e[0] for e in eyes]), np.mean([e[1] for e in eyes])
    eh, ew = max(e[3] for e in eyes), max(e[2] for e in eyes)
    ied = eyes[-1][0] - eyes[0][0] if len(eyes) > 1 else ew

    def front_at(y):
        """the face's front (screen-right) edge on row y, less its outline"""
        row = np.nonzero(hs[int(np.clip(y, 0, H - 1))])[0]
        return (row.max() if len(row) else hx.max()) - 0.015 * head_w

    py = ecy + MOUTH_DROP * eh
    if view == "side":
        px = front_at(py) - 0.5 * PROFILE_DEPTH * MOUTH_WIDTH["side"] * head_w
        x0, x1 = ecx - 0.5 * ew, W
    else:
        px = ecx + (0.08 * ied if view == "three_quarter" else 0.0)
        x0, x1 = ecx - 0.8 * ied, ecx + 0.8 * ied
    y0, y1 = ecy + 0.5 * eh, ecy + 2.6 * eh
    win = np.zeros((H, W), bool)
    win[int(max(0, y0)):int(min(H, y1)), int(max(0, x0)):int(min(W, x1))] = True
    eyezone = cv2.dilate((E[..., 3] >= 64).astype(np.uint8), np.ones((11, 11), np.uint8)) > 0
    stub = cv2.dilate(neck_stub(head).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    rim = hs & ~(cv2.erode(hs.astype(np.uint8), np.ones((11, 11), np.uint8)) > 0)

    def centred(cx, cy, x_right):
        if view == "side":
            return abs(x_right - front_at(cy)) < 0.08 * head_w
        return abs(cx - px) < (0.2 if view == "front" else 0.3) * ied

    # 1. the head drawn with its mouth: a dark line, wide and thin, on the face's centre line
    g = grey(head)
    k = max(7, int(0.05 * head_w) | 1)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    m = ((bh > 30) & win & ~eyezone & ~stub & ~rim).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    near_rim = cv2.dilate(rim.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    best = None
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if w < 0.13 * head_w or w > 0.45 * head_w or h > 0.3 * w or area < 0.5 * w or \
                not centred(cen[i][0], cen[i][1], x + w):
            continue
        if view != "side" and (near_rim & (lab == i)).any():
            continue                    # a jaw or chin line: it runs out to the face's outline, a mouth doesn't
        near = np.exp(-0.5 * ((cen[i][1] - py) / (0.8 * eh)) ** 2)
        score = w * bh[lab == i].mean() * (0.3 + near)
        if best is None or score > best[0]:
            best = (score, i)
    if best is not None:
        return _mouth_from(lab == best[1], bh, view, head_w, front_at) + ("head",)

    # 2. the ink the guide adds to the bare head (blurred, so stubble dots drawn a pixel apart cancel)
    inner = cv2.erode(hs.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    D = np.abs(cv2.GaussianBlur(flat(head), (0, 0), 1.0) - cv2.GaussianBlur(flat(Ga), (0, 0), 1.0)).max(2)
    D *= inner & (Ga[..., 3] >= 128)
    outline = cv2.dilate(((g < 70) & hs).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    Dm = D * (win & ~eyezone & ~stub & ~outline)
    m = (Dm > 24).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 12:                 # specks: stubble, misaligned dots
            m[lab == i] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 20:
            continue
        mass = Dm[lab == i].sum()
        elong = 1 + min(2.0, w / max(1, h))               # mouths are wide
        near = np.exp(-0.5 * (((cen[i][1] - py) / (0.7 * eh)) ** 2 + ((cen[i][0] - px) / (0.6 * ied)) ** 2))
        score = mass * elong * (0.25 + near)
        if best is None or score > best[0]:
            best = (score, i, mass)
    if best is None or best[2] < 40 * 30:                 # nothing like a drawn mouth: the house proportion
        return _mouth_from_prior(view, px, py, head_w, front_at)
    i = best[1]
    x, y, w, h, _ = st[i]
    keep = lab == i
    for j in range(1, n):                                  # the rest of the same mouth (lips, corners)
        xj, yj, wj, hj, aj = st[j]
        if j != i and aj >= 8 and max(0, max(x, xj) - min(x + w, xj + wj)) < 0.25 * w and \
                max(0, max(y, yj) - min(y + h, yj + hj)) < 0.5 * h + 3:
            keep |= lab == j
    ys, xs = np.nonzero(keep)
    if not centred(xs.mean(), ys.mean(), xs.max()):
        return _mouth_from_prior(view, px, py, head_w, front_at)
    return _mouth_from(keep, Dm, view, head_w, front_at) + ("guide",)


def _mouth_from(mask, weight, view, head_w, front_at):
    """centre and width of the mouth drawn by these pixels (its line or lips), in the shared mouth's terms"""
    ys, xs = np.nonzero(mask)
    wt = weight[ys, xs] + 1e-6
    cy = float((ys * wt).sum() / wt.sum())
    bx0, bx1 = float(xs.min()), float(xs.max())
    default = MOUTH_WIDTH[view] * head_w
    if view == "side":
        lips = front_at(cy)
        width = np.clip((lips - bx0) / PROFILE_DEPTH, 0.75 * default, 1.3 * default)
        return (float(lips), cy), float(width)
    if view == "three_quarter":
        width = np.clip((bx1 - bx0) / (0.5 * (1 + SQUASH)), 0.75 * default, 1.3 * default)
        cx = bx0 + 0.5 * SQUASH * (bx1 - bx0) / (0.5 * (1 + SQUASH))
        return (float(cx), cy), float(width)
    width = np.clip(bx1 - bx0, 0.75 * default, 1.3 * default)
    return (float((bx0 + bx1) / 2), cy), float(width)


def _mouth_from_prior(view, px, py, head_w, front_at):
    width = MOUTH_WIDTH[view] * head_w
    if view == "side":
        return (float(front_at(py)), float(py)), float(width), "prior"
    return (float(px), float(py)), float(width), "prior"


# ---------------------------------------------------------------- vector features

def _ellipse(points):
    """cv2.fitEllipse normalised: centre, (rx, ry) with rx the more horizontal semi-axis, angle in (-45, 45]
    degrees, clockwise on screen"""
    (cx, cy), (w, h), a = cv2.fitEllipse(points)
    if 45 < a <= 135:
        w, h, a = h, w, a - 90
    elif a > 135:
        a -= 180
    return [float(cx), float(cy)], [float(w / 2), float(h / 2)], float(a)


def vector_eyes(E):
    """The overlay's eyes as shapes: per eye the opening (an ellipse fitted to the white with its pupil), the
    pupil (its height as drawn, upright), the highlights on it and the outline's thickness. Screen left to right."""
    H, W = E.shape[:2]
    solid = E[..., 3] >= 128
    rgb = E[..., :3].astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    white = solid & (rgb.min(2) > 185)
    white = cv2.morphologyEx(white.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    dark = solid & (lum < 100)
    n, lab, st, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), 8)
    if n <= 1:
        return [], dark
    areas = st[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i in np.argsort(-areas) if areas[i] >= 0.15 * areas.max()][:2]
    eyes = []
    for i in keep:
        wm = lab == i
        hull = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(hull, cv2.convexHull(cv2.findNonZero(wm.astype(np.uint8))), 1)
        inside = cv2.erode(hull, np.ones((3, 3), np.uint8)) > 0
        # the pupil: the biggest dark blob inside the white's outline (holes filled: its highlight)
        pn, pl, ps, _ = cv2.connectedComponentsWithStats((dark & inside).astype(np.uint8), 8)
        pupil = None
        if pn > 1:
            pupil = ndimage.binary_fill_holes(pl == 1 + int(np.argmax(ps[1:, cv2.CC_STAT_AREA])))
            if pupil.sum() < 12:
                pupil = None
        full = ndimage.binary_fill_holes(wm | (pupil if pupil is not None else False))
        hp = cv2.convexHull(cv2.findNonZero(full.astype(np.uint8)))
        if len(hp) < 5:
            continue
        centre, axes, angle = _ellipse(hp)
        e = dict(centre=centre, axes=axes, angle=angle)
        if pupil is not None:
            ys, xs = np.nonzero(pupil)
            ry = 0.5 * (np.ptp(ys) + 1)                    # a pupil at the eye's edge is cut short sideways only
            rx = max(0.5 * (np.ptp(xs) + 1), 0.72 * ry)
            pc = [float(xs.mean()), float(ys.mean())]
            e["pupil"] = dict(axes=[float(rx), float(ry)], colour=[int(v) for v in np.median(rgb[pupil & dark], 0)])
            hl = pupil & ~dark & solid & (lum > 200)
            hn, hlab, hst, hcen = cv2.connectedComponentsWithStats(hl.astype(np.uint8), 8)
            e["pupil"]["highlights"] = [
                dict(offset=[round(float((hcen[j][0] - pc[0]) / rx), 3), round(float((hcen[j][1] - pc[1]) / ry), 3)],
                     r=round(float(np.sqrt(hst[j, cv2.CC_STAT_AREA] / np.pi) / ry), 3))
                for j in range(1, hn) if hst[j, cv2.CC_STAT_AREA] >= 3]
            e["travel"] = [max(1.0, axes[0] - 0.9 * rx), max(1.0, axes[1] - 0.9 * ry)]
        # the outline: the dark band just outside the opening
        ring = dark & (cv2.dilate(full.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0) & ~full
        e["outline"] = float(np.clip(ring.sum() / max(1.0, cv2.arcLength(hp, True)), 1.5, 0.16 * min(axes)))
        eyes.append(e)
    eyes.sort(key=lambda e: e["centre"][0])
    return eyes, dark


def eye_mask(eyes, shape, grow=0.0):
    m = np.zeros(shape, np.uint8)
    for e in eyes:
        g = e["outline"] + grow
        cv2.ellipse(m, (tuple(e["centre"]), (2 * e["axes"][0] + 2 * g, 2 * e["axes"][1] + 2 * g), e["angle"]), 1, -1)
    return m > 0


def outline_width(head):
    """thickness of the head drawing's silhouette line: the house line weight for this view"""
    hs = (head[..., 3] >= 128).astype(np.uint8)
    rim = hs & (cv2.erode(hs, np.ones((17, 17), np.uint8)) == 0)
    dark = (grey(head) < 80) & (rim > 0)
    cs, _ = cv2.findContours(hs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    per = sum(cv2.arcLength(c, True) for c in cs)
    return float(np.clip(dark.sum() / max(1.0, per), 2.0, 9.0))


def _smooth_polygon(mask):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    return cv2.approxPolyDP(c, 0.6, True)[:, 0, :].astype(float).round(1).tolist()


def vector_brows(E, eyes, dark, line):
    """Brows as filled shapes (with their outline if they have one), and whatever else the overlay carries
    (glasses) as a mask for the fixed overlay"""
    H, W = E.shape[:2]
    solid = E[..., 3] >= 128
    rest = solid & ~eye_mask(eyes, (H, W), grow=2.0)
    if len(eyes) == 2:
        # brows drawn meeting in the middle (a monobrow, or two touching): part them between the eyes
        mid = int(round((eyes[0]["centre"][0] + eyes[1]["centre"][0]) / 2))
        top = int(min(e["centre"][1] for e in eyes))
        rest[:top, mid:mid + 2] = False
    n, lab, st, cen = cv2.connectedComponentsWithStats(rest.astype(np.uint8), 8)
    eh = max(2 * e["axes"][1] for e in eyes) if eyes else 20
    eye_top = min(e["centre"][1] - e["axes"][1] for e in eyes) if eyes else H
    rgb = E[..., :3].astype(np.float32)
    brows, static = [], np.zeros((H, W), bool)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 30:
            continue
        m = lab == i
        if y + h / 2 < eye_top + 0.25 * eh and w > 1.1 * h and a < 1.0 * eh * eh:
            core = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            fill = np.median(rgb[core if core.sum() > 10 else m], 0)
            edge = m & ~(cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
            outlined = (dark & edge).sum() > 0.5 * edge.sum() and np.dot(fill, [0.299, 0.587, 0.114]) > 110
            brows.append(dict(path=_smooth_polygon(m), centre=[float(cen[i][0]), float(cen[i][1])],
                              fill=[int(v) for v in fill], stroke=1.8 if outlined else 0.0))
        else:
            static |= m
    brows.sort(key=lambda b: b["centre"][0])
    return brows, static


# ---------------------------------------------------------------- the face rig

def build_face(rig_dir, cid, outfit, skin, view):
    rig = json.loads((rig_dir / "rig.json").read_text())
    P = rig["parts"]
    head = rgba(rig_dir / "head.png")
    H, W = head.shape[:2]
    out = rig_dir / "face"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    face = dict(view=view, size=[W, H], skin=[int(v) for v in skin], line_width=round(outline_width(head), 2))
    Ga, origin, fixes = guide_head(cid, outfit, view, head, P["head"])

    # ---- eyes and brows: the overlay matched into the guide's face, then redrawn as shapes
    Me, eyes_img, err = place_eyes(rgba(rig_dir / "eyes.png"), Ga, head, view, P["eyes"]["rel_scale"])
    face["eyes_matrix"] = np.round(Me, 5).tolist()
    face["eyes_err"] = round(float(err), 4)
    E = cv2.warpAffine(eyes_img, Me, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    face["eyes"], dark = vector_eyes(E)
    used = eye_mask(face["eyes"], (H, W), grow=1.0)
    line = np.median(E[..., :3][dark & used], 0) if (dark & used).any() else np.array([26, 18, 16])
    face["line"] = [int(v) for v in line]
    face["brows"], static = vector_brows(E, face["eyes"], dark, face["line"])
    if static.sum() > 50:
        img, off = crop(E, static)
        save(out / "static.png", img)
        face["static"] = dict(file="static.png", offset=list(off))

    # ---- mouth: where the guide draws it (or the sheet YAML pins it)
    boxes = [(e["centre"][0], e["centre"][1], 2 * e["axes"][0], 2 * e["axes"][1]) for e in face["eyes"]]
    if boxes:
        c, width, how = find_mouth(head, Ga, E, boxes, view)
    else:
        hx = np.nonzero(head[..., 3] >= 128)[1]
        c, width, how = (W / 2, 0.7 * H), MOUTH_WIDTH[view] * np.ptp(hx), "prior"
    if "mouth" in fixes:
        c, how = (fixes["mouth"][0] - origin[0], fixes["mouth"][1] - origin[1]), "yaml"
    if "mouth_width" in fixes:
        width = float(fixes["mouth_width"])
    # the face's tilt: the line through the eyes (front and three-quarter)
    angle = 0.0
    if len(boxes) == 2 and view != "side":
        angle = float(np.degrees(np.arctan2(boxes[1][1] - boxes[0][1], boxes[1][0] - boxes[0][0])))
    face["mouth"] = dict(centre=[round(float(c[0]), 2), round(float(c[1]), 2)], width=round(float(width), 2),
                         angle=round(angle, 2), found=how, kind="profile" if view == "side" else
                         ("three_quarter" if view == "three_quarter" else "front"))

    # beard round the mouth: lift the moustache out (drawn over the mouth); clean-shaven: paint out old mouths
    hr = head[..., :3].astype(np.float32)
    hs = head[..., 3] >= 128
    ys, xs = np.mgrid[0:H, 0:W]
    mx = c[0] - (0.25 * width if view == "side" else 0.0)    # profile: the mouth runs back from the lips
    zone = hs & (np.abs(xs - mx) < 0.75 * width) & (ys > c[1] - 0.45 * width) & (ys < c[1] + 0.5 * width)
    far = np.linalg.norm(hr - skin, axis=2) > 75
    beard = zone & far
    bearded = beard.sum() > 0.25 * zone.sum()
    face["bearded"] = bool(bearded)
    clean = head.copy()
    if bearded:
        mous = beard & (ys < c[1] + 0.02 * width) & (np.abs(xs - mx) < 0.62 * width)
        mous = cv2.morphologyEx(mous.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        if mous.sum() > 30:
            img, off = crop(head, mous)
            save(out / "moustache.png", img)
            face["moustache"] = dict(file="moustache.png", offset=list(off))
    else:
        # only marks well darker than the skin, close round the mouth line, away from the outline
        oval = ((xs - mx) / (0.6 * width)) ** 2 + ((ys - c[1]) / (0.16 * width)) ** 2 < 1
        hl = hr @ np.array([0.299, 0.587, 0.114], np.float32)
        skin_l = float(np.dot(skin, [0.299, 0.587, 0.114]))
        edge = cv2.erode(hs.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        old = oval & edge & (hl < skin_l - 45)
        if old.any():
            bgr = cv2.cvtColor(clean[..., :3], cv2.COLOR_RGB2BGR)
            fixed = cv2.inpaint(bgr, cv2.dilate(old.astype(np.uint8), np.ones((3, 3), np.uint8)), 5,
                                cv2.INPAINT_TELEA)
            clean[..., :3] = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)
    save(rig_dir / "head_face.png", clean)
    (out / "face.json").write_text(json.dumps(face, indent=1))
    return face


def main():
    for cid in sys.argv[1:]:
        c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text())
        for outfit in c["outfits"]:
            skin = kit.skin_of(cid, outfit)
            for view in ("front", "three_quarter", "side"):
                d = BUILD / "rig" / cid / outfit / view
                if not (d / "rig.json").exists():
                    continue
                f = build_face(d, cid, outfit, skin, view)
                print(f"{cid} {outfit} {view}: {len(f['eyes'])} eyes (err {f['eyes_err']:.3f}),"
                      f" {len(f['brows'])} brows, mouth from {f['mouth']['found']},"
                      f" {'beard' if f['bearded'] else 'clean'}{', glasses/extra' if 'static' in f else ''}",
                      file=sys.stderr)


if __name__ == "__main__":
    main()
