"""Cut a kit sheet into its separate drawings.

The generated sheets have real alpha, but also a faint haze (alpha 1-15) around the drawings - on some sheets
over the whole page - coloured glow on the anti-aliased edges, and sometimes small text labels. Slicing:

1. drop the haze (alpha below FLOOR) and recolour every soft edge pixel from the nearest solid pixel, so no glow
   fringe survives when a part is drawn over a different background;
2. find the drawings as connected regions of solid alpha;
3. group the pieces of one drawing that sit closer together than the gutters between drawings (an eye, its pupil
   highlight and its brow), and drop label text and specks."""
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

FLOOR = 40          # alpha below this is haze
SOLID = 128         # alpha at or above this is the drawing
EDGE_SOLID = 250    # alpha below this is an anti-aliased edge whose colour is bled from inside


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).copy()


def clean(rgba):
    """Remove the haze and the coloured fringes. Returns a new RGBA array."""
    out = rgba.copy()
    a = out[..., 3]
    a[a < FLOOR] = 0
    solid = a >= EDGE_SOLID
    if solid.any():
        # every pixel takes the colour of its nearest fully solid pixel; only the soft edge pixels change
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        soft = (a > 0) & ~solid
        out[..., :3][soft] = out[..., :3][iy[soft], ix[soft]]
    out[..., :3][a == 0] = 0
    return out


@dataclass
class Piece:
    """One drawing on the sheet (possibly several touching-close blobs)."""
    idx: int
    x0: int
    y0: int
    x1: int
    y1: int
    area: int
    mask: np.ndarray = field(repr=False)     # bool, full-sheet size, solid pixels of this drawing
    blobs: int = 1
    kind: str = "part"                      # part | label | speck

    @property
    def w(self): return self.x1 - self.x0

    @property
    def h(self): return self.y1 - self.y0

    @property
    def cx(self): return (self.x0 + self.x1) / 2

    @property
    def cy(self): return (self.y0 + self.y1) / 2


def pieces(rgba, gap=None):
    """The drawings on a cleaned sheet, biggest first. `gap`: blobs closer than this (px) are one drawing."""
    H, W = rgba.shape[:2]
    gap = gap or max(8, int(round(0.012 * H)))
    solid = rgba[..., 3] >= SOLID
    n, lab = cv2.connectedComponents(solid.astype(np.uint8), connectivity=8)
    # group: blobs whose solid pixels come within `gap` of each other
    grown = cv2.dilate(solid.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap, gap)))
    ng, glab = cv2.connectedComponents(grown, connectivity=8)
    group_of = np.zeros(n, np.int32)
    ys, xs = np.nonzero(solid)
    group_of[lab[ys, xs]] = glab[ys, xs]
    out = []
    for g in range(1, ng):
        members = np.nonzero(group_of == g)[0]
        members = members[members > 0]
        if len(members) == 0:
            continue
        m = np.isin(lab, members)
        yy, xx = np.nonzero(m)
        p = Piece(0, int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1, int(m.sum()), m,
                  blobs=len(members))
        out.append(p)
    out.sort(key=lambda p: -p.area)
    for i, p in enumerate(out):
        p.idx = i
    _mark_labels(rgba, out, H)
    return out


def _mark_labels(rgba, ps, H):
    """Flag text labels and specks. Labels are rows of several small glyph blobs of similar height, drawn in
    dark grey with no white and no saturated colour; specks are tiny."""
    for p in ps:
        if p.area < 0.00012 * H * H:
            p.kind = "speck"
            continue
        if p.h > 0.06 * H or p.blobs < 3:
            continue
        rgb = rgba[..., :3][p.mask].astype(np.float32)
        lum = rgb.mean(1)
        sat = rgb.max(1) - rgb.min(1)
        glyphy = p.w > 2.2 * p.h
        if glyphy and np.mean(lum < 140) > 0.6 and np.mean(sat > 60) < 0.25 and np.mean(lum > 220) < 0.05:
            p.kind = "label"


def split_wide(p, ratio=0.5):
    """Split a drawing that is really two side-by-side drawings touching each other (a hand pair drawn too close)
    at the emptiest column near its middle. Returns the two halves as new Pieces (indices left to the caller)."""
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    cols = m.sum(0).astype(np.float32)
    lo, hi = int(p.w * (ratio - 0.18)), int(p.w * (ratio + 0.18))
    cut = p.x0 + lo + int(np.argmin(cols[lo:hi]))
    out = []
    for a, b in ((p.x0, cut), (cut, p.x1)):
        mm = np.zeros_like(p.mask)
        mm[:, a:b] = p.mask[:, a:b]
        yy, xx = np.nonzero(mm)
        out.append(Piece(-1, int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1, int(mm.sum()), mm))
    return out


def overview(rgba, ps, path, names=None, scale=0.6):
    """Save the sheet on mid grey with every piece boxed and numbered (and named, if names are given)."""
    H, W = rgba.shape[:2]
    bg = np.full((H, W, 3), (118, 118, 118), np.float32)
    a = rgba[..., 3:4].astype(np.float32) / 255
    img = (rgba[..., :3] * a + bg * (1 - a)).astype(np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    colour = dict(part=(0, 220, 255), label=(255, 80, 255), speck=(80, 80, 255))
    for p in ps:
        c = colour[p.kind]
        cv2.rectangle(img, (p.x0, p.y0), (p.x1, p.y1), c, 2)
        t = str(p.idx) if not names else f"{p.idx}:{names.get(p.idx, '?')}"
        if p.kind != "part":
            t = f"{p.idx}:{p.kind}"
        cv2.putText(img, t, (p.x0 + 3, p.y0 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, t, (p.x0 + 3, p.y0 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2, cv2.LINE_AA)
    img = cv2.resize(img, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
