"""Character drawings for the film engine: every drawing a character can be filmed in, cut whole from their art
(never chopped into parts), upscaled 4x with Real-ESRGAN, and given face landmarks.

    python3 -m studio.film.art CHARACTER [DRAWING ...] [--force]
        build/film/<id>/<drawing>.png    RGBA, 4 part px per sheet px (8 with `x8: true`)
        build/film/<id>/meta.json        {drawing: {off: [x, y] (sheet px of the part's corner), scale, size}}
        build/film/<id>/marks.json       face landmarks per drawing, in sheet px (see marks())
        build/film/<id>_check.jpg        every drawing on magenta with its landmarks drawn: check it by eye

Which drawings a character has is library/characters/<id>/film.yaml:

    drawings:
      front: {kit: casual/front}                        # a kit sheet's assembled guide figure, whole
      q34:   {kit: casual/three_quarter, faces: R, close_mouth: [cx, cy, rx, ry]}
      hero:  {sheet: reference/model-sheet.png, box: [x0, y0, x1, y1], faces: F}
      talk:  {sheet: reference/model-sheet.png, box: [...], extend: 0.4, x8: true}   # waist-up gesture pose

  kit      the guide figure of library/characters/<id>/kit/<outfit>/<view>.png (its YAML says which drawing)
  sheet    a box on any sheet in the character's folder; the paper is flood-filled away (model sheets, poses), or
           a drawing already cut out on transparent keeps its own alpha
  faces    which way the drawing faces: F (front), L / R (turned towards the viewer's left / right), B (back)
  close_mouth   an open mouth (centre and radii, sheet px) painted shut so the lip sync can drive it
  close_fit     true: close_mouth masks the drawn opening itself (rim, teeth, tongue) instead of an ellipse
  extend   a waist-up drawing's body continued down by this fraction of its height (it never ends in mid-air)
  x8       a second upscale pass for small drawings seen large
  marks    hand-set landmarks where detection can't see them (beards): {eyes, mouth, chin, neck, head}
  head     the head's box [x0, y0, x1, y1] (sheet px) if the automatic one (top of the figure) is wrong
  plain    no face to animate (backs, walking poses seen small)
  holes    points in paper the drawing encloses that the cut keeps (between an arm and the body)
  main     true: a box on a sheet of drawings on transparent keeps only the figure in its middle (pose sheets
           whose neighbouring poses reach into the box)
  auto_holes  false: keep flat paper-coloured patches inside the figure (cream boots, a white shirt drawn flat);
           by default they are taken out as enclosed paper (between the legs, closed off by the ground shadow)"""
import argparse
import json
import sys

import cv2
import numpy as np
import yaml
from PIL import Image
from scipy import ndimage

from studio.ingest import kit
from studio.paths import CHARACTERS, build_dir

GREY = 128


def spec_of(cid):
    return yaml.safe_load((CHARACTERS / cid / "film.yaml").read_text())


# ---------------------------------------------------------------- upscaling
def x4(bgr):
    from studio.episode.upscale import x4 as up
    return up(bgr)


def bleed(rgba):
    """every transparent pixel takes the colour of the nearest opaque one, so the upscaler never sees a border
    colour that isn't the drawing's own (its dark outline)"""
    a = rgba[..., 3]
    solid = a >= 200
    if not solid.any():
        return rgba
    _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
    out = rgba.copy()
    out[..., :3] = rgba[..., :3][iy, ix]
    return out


def upscale_rgba(rgba):
    """RGBA (sheet px) -> RGBA at 4x: colour through Real-ESRGAN, alpha resized and kept crisp"""
    b = bleed(rgba)
    big = x4(cv2.cvtColor(b[..., :3], cv2.COLOR_RGB2BGR))
    big = cv2.cvtColor(big, cv2.COLOR_BGR2RGB)
    al = cv2.resize(rgba[..., 3], (big.shape[1], big.shape[0]), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    al = np.clip((al - 128) * 1.6 + 128, 0, 255).astype(np.uint8)
    return np.dstack([big, al])


# ---------------------------------------------------------------- cutting
def cut_kit(cid, ref):
    """the guide figure of a kit sheet, whole, with its own alpha: (RGBA crop at 1x, (x0, y0) sheet px)"""
    outfit, view = ref.split("/")
    png = CHARACTERS / cid / "kit" / outfit / f"{view}.png"
    spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
    rgba, named, guide, _ = kit.resolve(png, spec)
    m = cv2.dilate(guide.mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    ys, xs = np.nonzero(m)
    pad = 10
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(rgba.shape[1], xs.max() + pad + 1), min(rgba.shape[0], ys.max() + pad + 1)
    out = rgba[y0:y1, x0:x1].copy()
    out[..., 3] = np.where(m[y0:y1, x0:x1], out[..., 3], 0)
    return out, (int(x0), int(y0))


def main_figure(rgba):
    """a box cut from a sheet of drawings on transparent: only the figure in the middle of the box (and the soft
    edge round it), never a neighbour's hand or shoe that reaches into the box"""
    a = rgba[..., 3]
    h, w = a.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 96).astype(np.uint8), 8)
    core = set(np.unique(lab[int(0.3 * h):int(0.7 * h), int(0.3 * w):int(0.7 * w)])) - {0}
    keep = np.isin(lab, [k for k in core if st[k, cv2.CC_STAT_AREA] > 0.01 * w * h])
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    out = rgba.copy()
    out[..., 3] = np.where(keep, a, 0)
    return out


def cut_sheet(cid, path, box, holes=(), auto_holes=True, main=False):
    """a drawing on paper: the box upscaled, then the paper flood-filled away from the box border (the ink outline
    stops it); everything inside the outline is kept, so white eyes and shirts stay solid. -> (RGBA 4x, (x0, y0))"""
    img = cv2.imread(str(CHARACTERS / cid / path), cv2.IMREAD_UNCHANGED)
    x0, y0, x1, y1 = box
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        if (img[y0:y1, x0:x1, 3] < 128).mean() > 0.02:   # cut out already (a drawing on transparent): its own alpha
            crop = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGRA2RGBA)
            return upscale_rgba(main_figure(crop) if main else crop), (x0, y0)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    im = x4(img[y0:y1, x0:x1])
    h, w = im.shape[:2]
    ff = cv2.GaussianBlur(im, (3, 3), 0)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    border = np.concatenate([np.stack([np.arange(w), np.zeros(w, int)], 1), np.stack([np.arange(w), np.full(w, h - 1)], 1),
                             np.stack([np.zeros(h, int), np.arange(h)], 1), np.stack([np.full(h, w - 1), np.arange(h)], 1)])
    g = cv2.cvtColor(ff, cv2.COLOR_BGR2GRAY)
    for x, y in border[::7]:
        if g[y, x] > 200 and mask[y + 1, x + 1] == 0:
            cv2.floodFill(ff, mask, (int(x), int(y)), 0, (3, 3, 3), (3, 3, 3), flags)
    paper = mask[1:-1, 1:-1] > 0
    fig = cv2.morphologyEx((~paper).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(fig, 8)
    cx0, cy0, cx1, cy1 = int(0.3 * w), int(0.15 * h), int(0.7 * w), int(0.85 * h)
    core = set(np.unique(lab[cy0:cy1, cx0:cx1])) - {0}
    keep = np.isin(lab, [k for k in core if st[k, cv2.CC_STAT_AREA] > 0.002 * w * h]).astype(np.uint8)
    inv = 1 - keep
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
    for k in range(1, n2):                       # paper-coloured regions fully inside the figure are part of it
        xx, yy, ww, hh, a = st2[k]
        if xx > 0 and yy > 0 and xx + ww < w and yy + hh < h and a < 0.02 * w * h:
            keep[lab2 == k] = 1
    keep = cv2.erode(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))     # 2 px inside the outline
    a = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 0.9)
    a = np.clip((a - 0.25) / 0.5, 0, 1)
    # paper the drawing encloses (between the legs, closed off by the ground shadow under the boots; between an arm
    # and the body): flat patches of exactly the paper's colour inside the figure. Nothing drawn is that flat and
    # that colour (white shorts are shaded, eye whites are whiter, cream boots are textured)
    if auto_holes and paper.any():
        pc = np.median(im[paper].reshape(-1, 3).astype(np.float32), 0)
        f = im.astype(np.float32)
        dist = np.abs(f - pc).max(2)
        mu = cv2.blur(f, (9, 9))
        sd = np.sqrt(np.maximum(0, cv2.blur(f * f, (9, 9)) - mu * mu)).max(2)
        cand = ((a > 0.5) & (dist < 6) & (sd < 2.5)).astype(np.uint8)
        ys_, _ = np.nonzero(a > 0.5)
        below = ys_.min() + 0.42 * (ys_.max() - ys_.min()) if len(ys_) else 0     # under the shoulders only: eye
        n3, lab3, st3, _ = cv2.connectedComponentsWithStats(cand, 4)                # whites and collars are flat white
        for k in range(1, n3):
            if st3[k, cv2.CC_STAT_AREA] > 0.0008 * w * h and st3[k, cv2.CC_STAT_TOP] > below:
                m3 = cv2.dilate((lab3 == k).astype(np.uint8), np.ones((11, 11), np.uint8)) > 0     # and its halo
                a[m3 & (g > 175)] = 0
    for hx, hy in holes:                         # paper enclosed by the drawing (between an arm and the body)
        sx, sy = int((hx - x0) * 4), int((hy - y0) * 4)
        r = 60
        win = g[max(0, sy - r):sy + r, max(0, sx - r):sx + r]
        yy_, xx_ = np.nonzero(win > 222)
        if len(yy_) == 0:
            continue
        k = int(np.argmin((yy_ + max(0, sy - r) - sy) ** 2 + (xx_ + max(0, sx - r) - sx) ** 2))
        sx, sy = int(xx_[k] + max(0, sx - r)), int(yy_[k] + max(0, sy - r))
        hole = np.zeros((h + 2, w + 2), np.uint8)
        # against the seed's own colour (a neighbour-to-neighbour fill creeps along light skin into a face)
        cv2.floodFill(ff, hole, (sx, sy), 0, (12, 12, 12), (12, 12, 12), flags | cv2.FLOODFILL_FIXED_RANGE)
        hm = (cv2.dilate(hole[1:-1, 1:-1], np.ones((3, 3), np.uint8)) > 0) & (g > 150)
        if hm.sum() > 0.12 * w * h:                 # it leaked into the figure: leave the paper rather than lose it
            print(f"{cid}: hole at {hx},{hy} would take {hm.sum() / (w * h):.0%} of the drawing; skipped", file=sys.stderr)
            continue
        a[hm] = 0
    # the holes' fringe: the paper there is shaded and noisy at its edges, which the fills stop short of. Grow each
    # hole into the paper-like pixels round it (light and colourless), never across the ink outline, and only so
    # far (white shorts behind a gap in a line stay)
    gone = (keep > 0) & (a < 0.05)
    if gone.any():
        f = im.astype(np.int16)
        paperish = ((g > 140) & ((f.max(2) - f.min(2)) < 26)).astype(np.uint8)
        grow = gone.astype(np.uint8)
        k5 = np.ones((5, 5), np.uint8)
        for _ in range(10):                                  # 2 px a step: up to 20 px (5 px of the sheet)
            nxt = cv2.dilate(grow, k5) & paperish
            if not (nxt & (1 - grow)).any():
                break
            grow |= nxt
        a[grow > 0] = 0
        a = np.minimum(a, np.clip((cv2.GaussianBlur((grow == 0).astype(np.float32), (0, 0), 0.8) - 0.25) / 0.5, 0, 1))
    rgba = np.dstack([cv2.cvtColor(im, cv2.COLOR_BGR2RGB), (a * 255).astype(np.uint8)])
    return rgba, (x0, y0)


def ink_of(rgba):
    """the drawing's line colour: the median of its darkest opaque pixels (RGB)"""
    rgb = rgba[..., :3][rgba[..., 3] > 200].astype(np.float32)
    lum = rgb.mean(1)
    return np.median(rgb[lum <= np.percentile(lum, 4)], 0)


def opening_mask(rgb, X, Y, RX, RY, K):
    """the drawn opening of a mouth (its ink rim, teeth, tongue, throat), found as everything round (X, Y) that is
    the opening's colours and connected to its middle; grown past the rim's antialiasing"""
    H, W = rgb.shape[:2]
    reg = np.zeros((H, W), np.uint8)
    cv2.ellipse(reg, (int(X), int(Y)), (int(RX * 1.5), int(RY * 1.7)), 0, 0, 360, 1, -1)
    lab = cv2.cvtColor(rgb, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, A, B = lab[..., 0], lab[..., 1] - 128, lab[..., 2] - 128
    # the opening's own colours: ink and throat (dark), teeth (white), tongue (pink); never the skin, the brown of a
    # moustache or the stubble round it
    off = (L < 75) | ((L > 185) & (np.hypot(A, B) < 22)) | ((A > 26) & (B < A * 0.9))
    cand = (off & (reg > 0)).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((K + 1, K + 1), np.uint8))
    n, labl, st, _ = cv2.connectedComponentsWithStats(cand, 8)
    core = np.zeros((H, W), np.uint8)
    cv2.ellipse(core, (int(X), int(Y)), (int(RX * 0.5), int(RY * 0.5)), 0, 0, 360, 1, -1)
    keep = [k for k in set(np.unique(labl[core > 0])) - {0}]
    m = np.isin(labl, keep).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4 * K + 1, 4 * K + 1)))
    return cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * K + 1, 2 * K + 1))) * 255


def close_mouth(rgba, K, off, cx, cy, rx, ry, fit=False):
    """paint an open mouth shut on a part (K part px per sheet px): the opening inpainted from the skin round it,
    a soft closed-mouth line drawn across its upper third. fit: the mask is the drawn opening itself (its rim, teeth
    and tongue) rather than an ellipse, so no ink is left at its edge to be smeared into stubble"""
    rgb = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2BGR)
    X, Y = (cx - off[0]) * K, (cy - off[1]) * K
    RX, RY = rx * K * 1.22, ry * K * 1.35
    if fit:
        m = opening_mask(rgb, X, Y, rx * K, ry * K, K)
        rgb = cv2.inpaint(rgb, m, 3 * K, cv2.INPAINT_NS)
        # the stubble's grain over the smooth repair, so it doesn't read as a patch
        grain = cv2.GaussianBlur(np.random.default_rng(1).normal(0, 1, rgb.shape[:2]).astype(np.float32), (0, 0), K * 0.35)
        grain = (grain - grain.mean()) / (grain.std() + 1e-6)
        dark = np.clip(-grain - 0.9, 0, None) * 26
        w = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), K)[..., None]
        rgb = np.clip(rgb.astype(np.float32) - dark[..., None] * w * np.float32([0.8, 1.0, 1.1]), 0, 255).astype(np.uint8)
    else:
        m = np.zeros(rgb.shape[:2], np.uint8)
        cv2.ellipse(m, (int(X), int(Y)), (int(RX), int(RY)), 0, 0, 360, 255, -1)
        rgb = cv2.inpaint(rgb, m, 9, cv2.INPAINT_TELEA)
    w = rx * K * 0.78
    yl = Y - ry * K * 0.25
    pts = np.array([[X - w, yl + 0.10 * w], [X - 0.45 * w, yl - 0.02 * w], [X, yl - 0.05 * w],
                    [X + 0.45 * w, yl - 0.02 * w], [X + w, yl + 0.10 * w]], np.float32)
    lay = np.zeros(rgb.shape[:2], np.float32)
    cv2.polylines(lay, [np.int32(np.round(pts * 8))], False, 1.0, max(4, int(round(0.4 * K * 4))), cv2.LINE_AA, 3)
    lay = cv2.GaussianBlur(lay, (0, 0), 0.7)[..., None]
    ink = ink_of(rgba)[::-1]
    rgb = (rgb * (1 - lay) + ink * lay).astype(np.uint8)
    out = rgba.copy()
    out[..., :3] = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
    return out


def extend_down(rgba, frac):
    """continue a waist-up body below the drawing's edge: its lowest wide row (arms excluded) repeated downwards,
    with the outline down both sides, so the figure runs out of the frame as a solid body"""
    im = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2BGR)
    a = rgba[..., 3].astype(np.float32) / 255
    H, W = a.shape
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.int16)
    skin = (hsv[..., 0] >= 6) & (hsv[..., 0] <= 25) & (hsv[..., 1] > 60) & (hsv[..., 2] > 40)
    op = (a > 0.5) & ~skin
    op = cv2.morphologyEx(op.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 9), np.uint8)) > 0
    rows = np.where(op.sum(1) > 0.05 * W)[0]
    if len(rows) == 0:
        return rgba
    r = rows.max()

    def main_run(y):
        v = op[y].astype(np.int8)
        d = np.diff(np.concatenate([[0], v, [0]]))
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        if len(st) == 0:
            return None
        k = int(np.argmax(en - st))
        return st[k], en[k]

    run = main_run(r)
    if run is None:
        return rgba
    best = (run[1] - run[0], r, run)
    for y in range(r, max(0, int(r - 0.08 * H)), -2):
        rr = main_run(y)
        if rr and rr[1] - rr[0] > best[0]:
            best = (rr[1] - rr[0], y, rr)
    _, ry, (x0, x1) = best
    x0, x1 = x0 + 3, x1 - 3
    n = int(frac * H)
    band = im[ry - 2:ry + 1, x0:x1].astype(np.float32).mean(0)
    lum = band.mean(1)
    cloth = np.median(band[lum >= np.median(lum) * 0.6], 0)
    band[lum < np.median(lum) * 0.45] = cloth
    ink = ink_of(rgba)[::-1]
    lw = max(4, int(0.004 * W + 3))
    ext = np.zeros((n, W, 3), np.uint8)
    ext[:, x0:x1] = band.astype(np.uint8)
    ea = np.zeros((n, W), np.float32)
    ea[:, x0:x1] = 1.0
    ext[:, x0:x0 + lw] = ink
    ext[:, x1 - lw:x1] = ink
    im = im.copy()
    a = a.copy()
    fill = (slice(ry, r + 1), slice(x0, x1))
    holes = a[fill] < 0.5
    blk = im[fill]
    blk[holes] = band.astype(np.uint8)[None].repeat(r + 1 - ry, 0)[holes]
    im[fill] = blk
    a[fill] = np.maximum(a[fill], 1.0)
    im2 = np.concatenate([im[:r + 1], ext], 0)
    a2 = np.concatenate([a[:r + 1], ea], 0)
    return np.dstack([cv2.cvtColor(im2, cv2.COLOR_BGR2RGB), (a2 * 255).astype(np.uint8)])


def second_pass(rgba):
    """4x part -> 8x: Real-ESRGAN again (16x), halved"""
    big = upscale_rgba(rgba)
    h, w = rgba.shape[0] * 2, rgba.shape[1] * 2
    return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA)


def make(cid, name, d):
    """cut, upscale and finish one drawing -> (RGBA part, meta)"""
    if "image" in d:
        part = np.asarray(Image.open(CHARACTERS / cid / d["image"]).convert("RGBA")).copy()
        off, K = (0, 0), 1
    elif "kit" in d:
        crop, off = cut_kit(cid, d["kit"])
        part = upscale_rgba(crop)
        K = 4
    else:
        part, off = cut_sheet(cid, d["sheet"], d["box"], [tuple(h) for h in d.get("holes", [])],
                              d.get("auto_holes", True), d.get("main", False))
        K = 4
    if d.get("close_mouth"):
        part = close_mouth(part, K, off, *d["close_mouth"], fit=d.get("close_fit", False))
    if d.get("extend"):
        part = extend_down(part, d["extend"])
    ys, xs = np.nonzero(part[..., 3] > 5)
    bx0, by0 = max(0, xs.min() - 8), max(0, ys.min() - 8)
    bx1, by1 = min(part.shape[1], xs.max() + 9), min(part.shape[0], ys.max() + 9)
    part = part[by0:by1, bx0:bx1]
    off = [off[0] + bx0 / K, off[1] + by0 / K]
    if d.get("x8"):
        part = second_pass(part)
        K = 8
    return part, dict(off=off, scale=K, size=[int(part.shape[1]), int(part.shape[0])],
                      source=d.get("kit") or d.get("sheet"))


# ---------------------------------------------------------------- face landmarks
def auto_head(part, meta):
    """the head's box (sheet px): the top of the figure down to 38 % of its height"""
    a = part[..., 3] > 128
    ys, xs = np.nonzero(a)
    y0, y1 = ys.min(), ys.min() + 0.38 * np.ptp(ys)
    band = a[int(y0):int(y1)]
    bx = np.nonzero(band.any(0))[0]
    K = meta["scale"]
    ox, oy = meta["off"]
    return [round(bx.min() / K + ox, 1), round(y0 / K + oy, 1), round(bx.max() / K + ox, 1), round(y1 / K + oy, 1)]


def marks(part, meta, head):
    """eyes = (cx, cy, rx, ry) of each eye opening (the white, pupil included); mouth = (left corner x, y, right
    corner x, y, centre x, y) of the closed mouth line; chin = y of the chin outline under it; neck = the head's
    pivot (collar centre); head = the head's box. All sheet px. Found from the drawing: white eye blobs with a dark
    pupil, the dark wide thin stroke under them, the first ink row below that."""
    ox, oy = meta["off"]
    K = meta["scale"]

    def P(x, y):
        return (int(round((x - ox) * K)), int(round((y - oy) * K)))

    def S(px, py):
        return (px / K + ox, py / K + oy)

    img = cv2.cvtColor(np.ascontiguousarray(part[..., :3]), cv2.COLOR_RGB2BGR)
    alpha = part[..., 3]
    hx0, hy0, hx1, hy1 = head
    (X0, Y0), (X1, Y1) = P(hx0, hy0), P(hx1, hy1)
    HB = Y1 - Y0
    Y1 = Y1 + int(0.35 * HB)
    X0, Y0 = max(0, X0), max(0, Y0)
    X1, Y1 = min(img.shape[1], X1), min(img.shape[0], Y1)
    bgr, a = img[Y0:Y1, X0:X1], alpha[Y0:Y1, X0:X1]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    V, Sat = hsv[..., 2].astype(int), hsv[..., 1].astype(int)
    white = ((V > 200) & (Sat < 45) & (a > 200)).astype(np.uint8)
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(white, 8)
    H, W = white.shape
    cand = []
    for k in range(1, n):
        x, y, w, h, ar = st[k]
        if ar < 0.002 * HB * W or ar > 0.08 * HB * W:
            continue
        if y + h > 0.8 * HB or w > 0.45 * W:
            continue
        if not (0.4 < w / max(h, 1) < 2.6):
            continue
        box = bgr[y:y + h, x:x + w]
        if (box.max(2) < 90).mean() < 0.01:       # a real eye has a dark pupil inside its box
            continue
        cand.append((ar, x, y, w, h))
    cand.sort(reverse=True)
    eyes = []
    for ar, x, y, w, h in cand[:4]:
        if not eyes or all(abs((y + h / 2) - (e[1] + e[3] / 2)) < 0.12 * HB for e in eyes):
            eyes.append((x, y, w, h))
        if len(eyes) == 2:
            break
    eyes.sort()
    E = [((x + w / 2), (y + h / 2), w / 2, h / 2) for x, y, w, h in eyes]
    res = dict(eyes=[], head=list(head))
    for cx, cy, rx, ry in E:
        sx, sy = S(cx + X0, cy + Y0)
        res["eyes"].append([round(sx, 1), round(sy, 1), round(rx / K, 2), round(ry / K, 2)])
    if E:
        ecy = np.mean([e[1] for e in E])
        ecx = np.mean([e[0] for e in E])
        ed = (E[1][0] - E[0][0]) if len(E) == 2 else 3 * E[0][2]
        er = np.mean([e[3] for e in E])
        ya, yb = int(ecy + er + 0.55 * ed), int(min(H, ecy + 1.5 * ed))
        xa, xb = int(max(0, ecx - 0.9 * ed)), int(min(W, ecx + 0.9 * ed))
        dark = ((V < 105) & (a > 200)).astype(np.uint8)
        reg = np.zeros_like(dark)
        reg[ya:yb, xa:xb] = dark[ya:yb, xa:xb]
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(reg, 8)
        best = None
        for k in range(1, n2):
            x, y, w, h, ar = st2[k]
            if w < 0.18 * ed or w > 1.3 * ed or h > 0.6 * w:
                continue
            touches = x <= xa or x + w >= xb
            score = w - 2 * abs((x + w / 2) - ecx) - (50 if touches else 0)
            if best is None or score > best[0]:
                best = (score, k, x, y, w, h)
        if best:
            _, k, x, y, w, h = best
            ys, xs = np.where(lab2 == k)
            l, r = xs.min(), xs.max()
            yl = ys[xs <= l + 2].mean()
            yr = ys[xs >= r - 2].mean()
            mc = (l + r) / 2
            yc = ys[np.abs(xs - mc) <= 2].mean()
            L, R, C = S(l + X0, yl + Y0), S(r + X0, yr + Y0), S(mc + X0, yc + Y0)
            res["mouth"] = [round(L[0], 1), round(L[1], 1), round(R[0], 1), round(R[1], 1), round(C[0], 1), round(C[1], 1)]
            col = V[:, int(mc)]
            yy = int(yc + max(4, 0.12 * ed))
            while yy < H - 1 and not (col[yy] < 90 and yy > yc + 0.25 * ed):
                yy += 1
            res["chin"] = round(S(0, yy + Y0)[1], 1)
            res["neck"] = [round(C[0], 1), round(res["chin"] + 0.28 * (res["chin"] - S(0, ecy + Y0)[1]), 1)]
    return res


def check_tile(part, meta, mk, h=520):
    ox, oy = meta["off"]
    K = meta["scale"]

    def P(x, y):
        return (int(round((x - ox) * K)), int(round((y - oy) * K)))

    a = part[..., 3:4].astype(np.float32) / 255
    c = (part[..., :3] * a + np.float32([255, 0, 255]) * (1 - a)).astype(np.uint8)
    c = cv2.cvtColor(c, cv2.COLOR_RGB2BGR)
    lw = max(2, int(K))
    for cx, cy, rx, ry in mk.get("eyes", []):
        cv2.ellipse(c, P(cx, cy), (int(rx * K), int(ry * K)), 0, 0, 360, (0, 255, 0), lw)
    if mk.get("mouth"):
        mo = mk["mouth"]
        for i in range(3):
            cv2.circle(c, P(mo[2 * i], mo[2 * i + 1]), 3 * lw, (0, 0, 255), -1)
    if mk.get("chin"):
        x = mk["mouth"][4] if mk.get("mouth") else (mk["head"][0] + mk["head"][2]) / 2
        cv2.line(c, P(x - 10, mk["chin"]), P(x + 10, mk["chin"]), (255, 0, 0), lw)
    if mk.get("neck"):
        cv2.circle(c, P(*mk["neck"]), 3 * lw, (255, 128, 0), -1)
    if mk.get("head"):
        hx0, hy0, hx1, hy1 = mk["head"]
        cv2.rectangle(c, P(hx0, hy0), P(hx1, hy1), (0, 200, 255), lw)
    s = h / c.shape[0]
    return cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def build(cid, only=(), force=False):
    sp = spec_of(cid)
    out = build_dir("film", cid)
    mf, kf = out / "meta.json", out / "marks.json"
    meta = json.loads(mf.read_text()) if mf.exists() else {}
    mks = json.loads(kf.read_text()) if kf.exists() else {}
    tiles = []
    for name, d in sp["drawings"].items():
        if only and name not in only:
            continue
        f = out / f"{name}.png"
        if force or name not in meta or not f.exists():
            part, m = make(cid, name, d)
            cv2.imwrite(str(f), cv2.cvtColor(part, cv2.COLOR_RGBA2BGRA))
            meta[name] = m
            mf.write_text(json.dumps(meta, indent=1))
            print(f"{cid} {name}: {m['size']} x{m['scale']}", file=sys.stderr)
        part = cv2.cvtColor(cv2.imread(str(f), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
        if d.get("plain"):
            mk = dict(head=d.get("head") or auto_head(part, meta[name]))
        else:
            mk = marks(part, meta[name], d.get("head") or auto_head(part, meta[name]))
        mk.update(d.get("marks") or {})
        mks[name] = json.loads(json.dumps(mk, default=float))
        tiles.append((name, check_tile(part, meta[name], mks[name])))
    kf.write_text(json.dumps(mks, indent=1))
    if tiles:
        h = max(t.shape[0] for _, t in tiles)
        row = []
        for name, t in tiles:
            t = cv2.copyMakeBorder(t, 0, h - t.shape[0] + 28, 4, 4, cv2.BORDER_CONSTANT, value=(60, 60, 60))
            cv2.putText(t, name, (8, h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            row.append(t)
        cv2.imwrite(str(build_dir("film") / f"{cid}_check.jpg"), np.hstack(row), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return meta, mks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("character")
    ap.add_argument("drawings", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    build(a.character, a.drawings, a.force)
    print(build_dir("film") / f"{a.character}_check.jpg")


if __name__ == "__main__":
    main()
