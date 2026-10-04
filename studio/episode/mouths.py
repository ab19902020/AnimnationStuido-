"""A speaking mouth for a character, made from the mouth drawing the kit already has.

    from studio.episode.mouths import MouthSet
    m = MouthSet(mouth_png)       # the kit's front-view mouth part (BGRA, as written by studio.rig.build)
    sprite, (ox, oy) = m.shape("D")      # Rhubarb shape A-H or X; the sprite is the part's own pixels plus a margin

The kit's mouth part is a lower-face tile (moustache, beard or stubble) with the mouth LINE drawn into it. X and A
(rest, closed lips) use the tile as it is. For the open shapes the line is found (the thin dark stroke in the middle
of the tile, apart from the thick hair), painted away from the surrounding face, and an open mouth is drawn in its
place in the same bold dark outline: teeth, tongue and a dark inside, all in sizes taken from the line's width.
Open mouths hang down from the line, like a dropping jaw, and may run past the tile's edge (hence the margin).
Shapes follow Rhubarb's set: X rest, A closed (M B P), B teeth together, C open, D wide, E rounded, F pursed,
G teeth on lip (F V), H tongue up (L)."""
import cv2
import numpy as np
from scipy import ndimage

SS = 4                                   # draw at 4x and shrink, for clean edges
OUTLINE = (16, 14, 22)                   # BGR, like the tiles
INSIDE = (26, 22, 58)
TONGUE = (110, 98, 206)
TEETH = (242, 250, 252)
MARGIN = 0.5                             # sprite margin as a fraction of the tile's size

# width and height of the opening as a fraction of the line's width
SHAPES = dict(B=(0.58, 0.15), C=(0.64, 0.32), D=(0.72, 0.56), E=(0.40, 0.42), F=(0.24, 0.24), G=(0.58, 0.19),
              H=(0.56, 0.30))


def find_line(tile):
    """the mouth line of a BGRA mouth tile: (mask, (x, y, w, h)), or (None, None)"""
    a = tile[..., 3] >= 128
    H, W = a.shape
    lum = tile[..., :3].astype(np.float32) @ np.array([0.114, 0.587, 0.299], np.float32)
    dark = (lum < 80) & a
    inner = ndimage.binary_erosion(a, iterations=4) if H >= 30 else a      # keep clear of the tile's own outline
    thick = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6, 6)))
    thin = dark & inner & ~cv2.dilate(thick, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(thin.astype(np.uint8), connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if w < 0.22 * W or w < 3 * h or not (0.0 <= (y + h / 2) / H < 0.7):
            continue
        score = w - abs((x + w / 2) - W / 2) * 0.5
        if best is None or score > best[0]:
            best = (score, i, (int(x), int(y), int(w), int(h)))
    return (lab == best[1], best[2]) if best else (None, None)


class MouthSet:
    def __init__(self, tile):
        self.tile = tile
        h, w = tile.shape[:2]
        self.mask, self.box = find_line(tile)
        # room round the tile for an open mouth running past it: sideways and, mostly, below
        lw = self.box[2] if self.box else w
        self.pad = (int(MARGIN * w), max(int(MARGIN * h), int(0.7 * lw)))
        self.cache = {}
        self.skin = self._skin()

    def _skin(self):
        """the face colour round the line (BGR): the tile's most common mid-tone away from hair and outline"""
        a = self.tile[..., 3] >= 128
        px = self.tile[..., :3][a].astype(np.int32)
        lum = px @ np.array([0.114, 0.587, 0.299])
        px = px[(lum > 120) & (lum < 235)]
        if not len(px):
            return (150, 180, 230)
        keys, counts = np.unique(px // 12, axis=0, return_counts=True)
        return tuple(int(min(v, 255)) for v in (keys[np.argmax(counts)] * 12 + 6))

    def _blank(self):
        """the tile with the line painted out, on the padded canvas (BGRA)"""
        h, w = self.tile.shape[:2]
        px, py = self.pad
        if self.mask is None:
            t = self.tile.copy()
        else:
            m = cv2.dilate(self.mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
            t = self.tile.copy()
            t[..., :3] = cv2.inpaint(np.ascontiguousarray(self.tile[..., :3]), m * 255, 3, cv2.INPAINT_TELEA)
        out = np.zeros((h + 2 * py, w + 2 * px, 4), np.uint8)
        out[py:py + h, px:px + w] = t
        return out

    def shape(self, name):
        """(BGRA sprite, (px, py)): the part's pixels sit at (px, py) in the sprite, so the sprite takes the part's place"""
        if name in self.cache:
            return self.cache[name]
        h, w = self.tile.shape[:2]
        px, py = self.pad
        if name in ("X", "A") or self.box is None:
            out = np.zeros((h + 2 * py, w + 2 * px, 4), np.uint8)
            out[py:py + h, px:px + w] = self.tile
        else:
            out = self._open(name)
        self.cache[name] = (out, (px, py))
        return self.cache[name]

    def _open(self, name):
        """the padded tile with its line painted out and the open mouth `name` drawn in its place (BGRA)"""
        blank = self._blank()
        H, W = blank.shape[:2]
        x, y, lw, lh = self.box
        px, py = self.pad
        cx, top = (x + lw / 2 + px) * SS, (y + lh / 2 + py) * SS - (0.5 * SS if lh < 4 else 0)
        L = lw * SS
        wf, hf = SHAPES[name]
        mw, mh = wf * L, hf * L
        lin = max(2.0, 0.045 * L)                                 # outline thickness
        size = (W * SS, H * SS)
        col = np.zeros(size[::-1] + (4,), np.uint8)

        def ellipse(c, rx, ry, a0, a1, n=72):
            t = np.radians(np.linspace(a0, a1, n))
            return np.round(np.stack([c[0] + rx * np.cos(t), c[1] + ry * np.sin(t)], 1)).astype(np.int32)

        def fill(img, pts, color):
            cv2.fillPoly(img, [pts], (*color, 255), cv2.LINE_AA)

        if name in ("E", "F"):                                    # a plain oval
            c = (cx, top + mh / 2)
            outer, inner = ellipse(c, mw / 2, mh / 2, 0, 360), ellipse(c, mw / 2 - lin, mh / 2 - lin, 0, 360)
        else:                                                     # a flat upper lip over a rounded lower one
            outer = ellipse((cx, top), mw / 2, mh, 0, 180)
            inner = ellipse((cx, top + 0.5 * lin), mw / 2 - lin, max(1.0, mh - 1.3 * lin), 0, 180)
        fill(col, outer, OUTLINE)
        fill(col, inner, INSIDE)
        inside = np.zeros(size[::-1], np.uint8)
        fill_mask = cv2.fillPoly(inside, [inner], 255, cv2.LINE_AA)

        layer = np.zeros_like(col)
        if name in ("B", "C", "D", "G", "H"):                     # the upper teeth
            th = mh * dict(B=0.55, C=0.22, D=0.17, G=0.62, H=0.22)[name]
            cv2.rectangle(layer, (int(cx - mw / 2), int(top - lin)), (int(cx + mw / 2), int(top + th)), (*TEETH, 255), -1)
        if name in ("C", "D", "E", "H"):                          # the tongue
            tc = (cx, top + mh * {"C": 0.82, "D": 0.8, "E": 0.62, "H": 0.34}[name])
            fill(layer, ellipse(tc, mw * (0.2 if name == "E" else 0.3), mh * 0.28, 0, 360), TONGUE)
        if name == "G":                                           # the lower lip, over the bottom teeth
            cv2.rectangle(layer, (int(cx - mw / 2), int(top + mh * 0.68)), (int(cx + mw / 2), int(top + mh * 1.2)),
                          (*self.skin, 255), -1)
        m = fill_mask > 0
        col[m] = np.where(layer[..., 3:4][m] > 0, layer[m], col[m])

        small = cv2.resize(col, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
        a = small[..., 3:4] / 255
        out = blank.astype(np.float32)
        oa = out[..., 3:4] / 255
        na = a + oa * (1 - a)
        out[..., :3] = (small[..., :3] * a + out[..., :3] * oa * (1 - a)) / np.maximum(na, 1e-6)
        out[..., 3:4] = na * 255
        return np.clip(out, 0, 255).astype(np.uint8)
