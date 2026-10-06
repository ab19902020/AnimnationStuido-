"""The compositing engine (from All or Something): background plates, character drawings with their face and head
animation, and the helpers that put them on screen.

A character drawing is placed on screen by a 2x3 matrix from its sheet coordinates (1x sheet px); every layer is
warped straight from its source pixels to the screen, so nothing is resampled twice.

Memory / speed: plates and drawings are kept as uint8. A drawing's premultiplied float image is built once per
level and reused; each frame only the head region (a small "patch") is re-rendered with the face effects and head
motion, and warped over the base.

Resolution: EP_RES (default 1920x1080, 16:9). Layouts are written in 1920 x 1080 px and scaled by RS."""
import math
import os
import zlib

import cv2
import numpy as np
from PIL import Image

from studio.film.face import Face

OW, OH = (int(v) for v in os.environ.get("EP_RES", "1920x1080").split("x"))
FPS = 30
RS = OW / 1920.0          # resolution scale relative to the 1920 x 1080 layout


def seed(s):
    return zlib.crc32(s.encode()) & 0x7fffffff


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- plates (backgrounds)
class Plate:
    """a 4x-upscaled background. Views are given in 1x plate px: centre (cx, cy) and zoom z (z = 1: the plate's
    width fills the frame). Kept as uint8 at 4x / 2x / 1x; each view is warped from the level just above the
    screen scale, so it is never aliased. `occl`: {name: [polygon, ...]} in 1x plate px, things in front of actors."""

    def __init__(self, path, occl=None, image=None):
        p = image if image is not None else cv2.imread(str(path), cv2.IMREAD_COLOR)[..., ::-1].copy()
        self.lv = {4: p, 2: cv2.resize(p, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
                   1: cv2.resize(p, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)}
        self.W1, self.H1 = p.shape[1] / 4.0, p.shape[0] / 4.0
        self.occl = {}
        for name, polys in (occl or {}).items():
            m = np.zeros((p.shape[0], p.shape[1]), np.uint8)
            for poly in polys:
                cv2.fillPoly(m, [np.int32(np.round(np.float32(poly) * 4 * 8))], 255, cv2.LINE_AA, 3)
            m = cv2.GaussianBlur(m, (0, 0), 1.2)
            self.occl[name] = {4: m, 2: cv2.resize(m, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
                               1: cv2.resize(m, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)}

    def scale(self, z):
        return OW / self.W1 * z

    def clamp(self, cx, cy, z):
        """keep a view inside the plate"""
        s = self.scale(z)
        hw, hh = OW / (2 * s), OH / (2 * s)
        cx = self.W1 / 2 if hw * 2 >= self.W1 else min(max(cx, hw), self.W1 - hw)
        cy = self.H1 / 2 if hh * 2 >= self.H1 else min(max(cy, hh), self.H1 - hh)
        return cx, cy

    def M(self, cx, cy, z):
        """2x3: 1x plate px -> screen px"""
        s = self.scale(z)
        return np.float32([[s, 0, OW / 2 - s * cx], [0, s, OH / 2 - s * cy]])

    def _warp(self, levels, cx, cy, z, interp=cv2.INTER_LINEAR, border=cv2.BORDER_REFLECT):
        s = self.scale(z)
        L = next((l for l in (1, 2, 4) if l >= s * 0.95), 4)
        A = np.float32([[s / L, 0, OW / 2 - s * cx], [0, s / L, OH / 2 - s * cy]])
        return cv2.warpAffine(levels[L], A, (OW, OH), flags=interp, borderMode=border)

    def render(self, cx, cy, z):
        return self._warp(self.lv, cx, cy, z).astype(np.float32) / 255.0

    def mask(self, name, cx, cy, z):
        return self._warp(self.occl[name], cx, cy, z, border=cv2.BORDER_CONSTANT).astype(np.float32) / 255.0


# ---------------------------------------------------------------- drawings
LEVELS = (1.0, 0.5, 0.25, 0.125)


class Drawing:
    """one character drawing (a cut part) + its face landmarks (sheet coords). meta: {off: [x, y], scale: part px
    per sheet px}; the part image is RGBA at that scale."""

    def __init__(self, name, path, meta, mouth=None, chin=None, eyes=(), facing="front", neck=None, head=None,
                 jaw=1.0, anchors=None, brow_gain=1.0, ink=None, lid=None, pupils=True):
        self.name = name
        self.ox, self.oy = meta["off"]
        self.S = meta.get("scale", 4)                    # part px per sheet px
        full = np.asarray(Image.open(path).convert("RGBA"))
        self.anchors = {k: self.P(*v) for k, v in (anchors or {}).items()}
        self.u8 = {1.0: full}
        for L in LEVELS[1:]:
            self.u8[L] = cv2.resize(full, None, fx=L, fy=L, interpolation=cv2.INTER_AREA)
        self.spec = dict(mouth=mouth, chin=chin, eyes=eyes, facing=facing, neck=neck, head=head, jaw=jaw,
                         brow_gain=brow_gain, ink=ink, lid=lid, pupils=pupils)
        self.has_face = bool(mouth or eyes or head)
        self._base = {}
        self._face = {}
        self._patch = {}

    def P(self, x, y):
        """sheet coords -> full-res part px"""
        return ((x - self.ox) * self.S, (y - self.oy) * self.S)

    def size(self, L):
        h, w = self.u8[L].shape[:2]
        return w, h

    def base(self, L, clip=None):
        k = (L, clip)
        if k not in self._base:
            a = self.u8[L].astype(np.float32) / 255.0
            if clip is not None:
                yc = (clip - self.oy) * self.S * L
                yy = np.arange(a.shape[0], dtype=np.float32)[:, None]
                a[..., 3] *= np.clip(1 - (yy - yc) / max(2.0, 24 * L), 0, 1)
            a[..., :3] *= a[..., 3:4]
            self._base[k] = a
            if len(self._base) > 2:
                self._base.pop(next(iter(self._base)))
        return self._base[k]

    def _face_at(self, L):
        """Face object working on the head patch of level L; patch rect in level px"""
        if L in self._face:
            return self._face[L]
        sp = self.spec
        s = self.S * L

        def Q(x, y):
            return ((x - self.ox) * s, (y - self.oy) * s)

        W, H = self.size(L)
        pts = []
        if sp["head"]:
            pts += [Q(sp["head"][0], sp["head"][1]), Q(sp["head"][2], sp["head"][3])]
        if sp["mouth"]:
            pts += [Q(sp["mouth"][0], sp["mouth"][1]), Q(sp["mouth"][2], sp["mouth"][3])]
        for e in sp["eyes"]:
            pts += [Q(e[0] - 3 * e[2], e[1] - 5 * e[3]), Q(e[0] + 3 * e[2], e[1] + 3 * e[3])]
        if sp["chin"]:
            pts.append((pts[0][0] if pts else 0, Q(0, sp["chin"])[1]))
        if sp["neck"]:
            pts.append(Q(*sp["neck"]))
        p = np.float32(pts)
        bw = p[:, 0].max() - p[:, 0].min()
        mg = 0.16 * bw + 6
        x0 = int(max(0, p[:, 0].min() - mg))
        x1 = int(min(W, p[:, 0].max() + mg))
        y0 = int(max(0, p[:, 1].min() - mg))
        y1 = int(min(H, p[:, 1].max() + 0.06 * bw + 6))
        sub = self.u8[L][y0:y1, x0:x1].astype(np.float32) / 255.0

        def R(x, y):
            q = Q(x, y)
            return (q[0] - x0, q[1] - y0)

        mo = None
        if sp["mouth"]:
            a, b, c = R(sp["mouth"][0], sp["mouth"][1]), R(sp["mouth"][2], sp["mouth"][3]), R(sp["mouth"][4], sp["mouth"][5])
            mo = (a[0], a[1], b[0], b[1], c[0], c[1])
        ey = [(R(e[0], e[1])[0], R(e[0], e[1])[1], e[2] * s, e[3] * s) for e in sp["eyes"]]
        f = Face(sub, mouth=mo, chin=R(0, sp["chin"])[1] if sp["chin"] else None, eyes=ey, facing=sp["facing"],
                 jaw=sp["jaw"], brow_gain=sp["brow_gain"], ink=sp["ink"], lid=sp["lid"], pupils=sp.get("pupils", True))
        hb = None
        if sp["head"]:
            h0, h1 = R(sp["head"][0], sp["head"][1]), R(sp["head"][2], sp["head"][3])
            hb = (h0[0], h0[1], h1[0], h1[1])
        nk = R(*sp["neck"]) if sp["neck"] else None
        chin = R(0, sp["chin"])[1] if sp["chin"] else None
        self._face[L] = dict(face=f, rect=(x0, y0, x1, y1), head=hb, neck=nk, chin=chin)
        return self._face[L]

    def patch(self, L, st, clip=None):
        """-> (x0, y0, premultiplied RGBA float patch) or None when the face is at rest"""
        if not self.has_face:
            return None
        fa = self._face_at(L)
        key = (L, clip, st.get("vis", "REST"), round(st.get("amp", 1.0), 2), round(st.get("blink", 0.0), 2),
               round(st.get("lookx", 0.0), 2), round(st.get("looky", 0.0), 2), round(st.get("brow", 0.0), 2),
               round(st.get("smile", 0.0), 2), round(st.get("tilt", 0.0), 2), round(st.get("nod", 0.0), 2),
               round(st.get("turn", 0.0), 2))
        if key in self._patch:
            return self._patch[key]
        f = fa["face"]
        img = f.render(st.get("vis", "REST"), amp=st.get("amp", 1.0), blink=st.get("blink", 0.0),
                       look=(st.get("lookx", 0.0), st.get("looky", 0.0)), brow=st.get("brow", 0.0),
                       smile=st.get("smile", 0.0))
        tilt, nod, turn = st.get("tilt", 0.0), st.get("nod", 0.0), st.get("turn", 0.0)
        if fa["head"] is not None and fa["neck"] is not None and (abs(tilt) > 0.02 or abs(nod) > 0.02 or abs(turn) > 0.01):
            img = head_motion(img, fa, tilt, nod, turn)
        x0, y0, x1, y1 = fa["rect"]
        img = img.copy() if img is f.img else img
        if clip is not None:
            yc = (clip - self.oy) * self.S * L - y0
            yy = np.arange(img.shape[0], dtype=np.float32)[:, None]
            img[..., 3] *= np.clip(1 - (yy - yc) / max(2.0, 24 * L), 0, 1)
        pm = img.copy()
        pm[..., :3] *= pm[..., 3:4]
        out = (x0, y0, pm)
        if len(self._patch) > 6:
            self._patch.pop(next(iter(self._patch)))      # memory: big 8x faces
        self._patch[key] = out
        return out


def head_motion(img, fa, tilt, nod, turn):
    """rotate the head about the neck base (deg), drop it (nod, % of head height), turn the face sideways
    (-1..1); the effect fades out towards the collar so the neck stays attached."""
    x0, y0, x1, y1 = fa["head"]
    px, py = fa["neck"]
    chin = fa["chin"] if fa["chin"] else (y0 + 0.8 * (y1 - y0))
    hh = y1 - y0
    hw = x1 - x0
    H, W = img.shape[:2]
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    wy = 1 - smooth((Y - chin) / max(1.0, (py - chin)))
    wx = 1 - smooth((np.maximum(x0 - X, X - x1)) / max(1.0, 0.16 * hw))
    w = (wy * wx).astype(np.float32)
    th = math.radians(tilt)
    c, s = math.cos(th), math.sin(th)
    dxr = (c * (X - px) + s * (Y - py) + px) - X
    dyr = (-s * (X - px) + c * (Y - py) + py) - Y
    mx = X + w * dxr
    my = Y + w * dyr - w * nod * 0.01 * hh
    if abs(turn) > 0.01:
        fx = (x0 + x1) / 2
        fy = chin - 0.45 * (chin - y0)
        r2 = ((X - fx) / (0.55 * hw)) ** 2 + ((Y - fy) / (0.6 * max(1.0, chin - y0))) ** 2
        wf = np.clip(1 - r2, 0, 1) ** 1.3
        mx = mx - turn * 0.075 * hw * (0.35 + 0.65 * wf) * wy
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- compositing helpers
def warp_into(dst, img_pm, A, alpha=1.0, mode="over"):
    """composite a premultiplied RGBA image into dst (premultiplied RGBA float) through 2x3 affine A.
    mode 'over' or 'replace' (a patch that replaces what is under it inside its own footprint)."""
    H, W = dst.shape[:2]
    hh, ww = img_pm.shape[:2]
    c = cv2.transform(np.float32([[[0, 0], [ww, 0], [0, hh], [ww, hh]]]), A)[0]
    bx0, by0 = int(max(0, np.floor(c[:, 0].min()) - 2)), int(max(0, np.floor(c[:, 1].min()) - 2))
    bx1, by1 = int(min(W, np.ceil(c[:, 0].max()) + 2)), int(min(H, np.ceil(c[:, 1].max()) + 2))
    if bx1 <= bx0 or by1 <= by0:
        return None
    A2 = A.copy()
    A2[0, 2] -= bx0
    A2[1, 2] -= by0
    sc = math.sqrt(abs(A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]))
    src = img_pm
    if sc < 0.5:                       # no true area filter in warpAffine: pre-shrink the source
        f = min(1.0, sc * 1.6)
        src = cv2.resize(img_pm, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        A2 = (A2.astype(np.float64) @ np.array([[1 / f, 0, 0], [0, 1 / f, 0], [0, 0, 1]]))[:2].astype(np.float32)
    border = cv2.BORDER_CONSTANT if mode == "over" else cv2.BORDER_REPLICATE
    wl = cv2.warpAffine(src, A2.astype(np.float32), (bx1 - bx0, by1 - by0), flags=cv2.INTER_LINEAR,
                        borderMode=border, borderValue=0)
    if alpha != 1.0:
        wl *= alpha
    reg = dst[by0:by1, bx0:bx1]
    if mode == "over":
        dst[by0:by1, bx0:bx1] = wl + reg * (1 - wl[..., 3:4])
    else:
        # the patch replaces what is under it inside its own footprint (feathered 2 px inside its edge); the patch
        # image is edge-replicated so its border never pulls in black
        m = np.ones((hh, ww), np.float32)
        b = 2
        r = np.linspace(0, 1, b + 2)[1:-1]
        m[:b, :] *= r[:, None]
        m[-b:, :] *= r[::-1][:, None]
        m[:, :b] *= r[None, :]
        m[:, -b:] *= r[::-1][None, :]
        if src is not img_pm:
            m = cv2.resize(m, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_AREA)
        mw = cv2.warpAffine(m, A2.astype(np.float32), (bx1 - bx0, by1 - by0), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)[..., None]
        dst[by0:by1, bx0:bx1] = wl * mw + reg * (1 - mw)
    return (bx0, by0, bx1, by1)


def rim(layer_pm, dirx, diry, strength, color, width):
    """edge light on the side the light comes from (premultiplied layer); computed at half resolution for big
    layers"""
    a = layer_pm[..., 3]
    if a.max() <= 0:
        return layer_pm
    H, W = a.shape
    f = 2 if H * W > 1_500_000 else 1
    a2 = cv2.resize(a, (W // f, H // f), interpolation=cv2.INTER_AREA) if f > 1 else a
    w2 = width / f
    sh = cv2.warpAffine(a2, np.float32([[1, 0, dirx * w2], [0, 1, diry * w2]]), (a2.shape[1], a2.shape[0]))
    r = np.clip(a2 - sh, 0, 1)
    r = cv2.GaussianBlur(r, (0, 0), max(0.7, w2 * 0.45))
    if f > 1:
        r = cv2.resize(r, (W, H), interpolation=cv2.INTER_LINEAR)
    r *= a
    out = layer_pm
    out[..., :3] += r[..., None] * (np.float32(color) * strength)
    return out


# ---------------------------------------------------------------- placing a drawing
def _level_affine(d, M, L):
    """sheet px -> screen px (2x3) as level-L drawing px -> screen px"""
    A = np.zeros((2, 3), np.float64)
    A[:, :2] = M[:, :2] / (d.S * L)
    A[:, 2] = M[:, :2] @ np.float64([d.ox, d.oy]) + M[:, 2]
    return A


def _feather(h, w, b=2):
    m = np.ones((h, w), np.float32)
    r = np.linspace(0, 1, b + 2)[1:-1]
    m[:b, :] *= r[:, None]
    m[-b:, :] *= r[::-1][:, None]
    m[:, :b] *= r[None, :]
    m[:, -b:] *= r[::-1][None, :]
    return m


def place(dst, d, st, Ms, clip=None, alpha=1.0, head=None):
    """composite drawing d (face state st) into dst (premultiplied RGBA float, screen size) through Ms (2x3: sheet
    px -> screen px). Drawn on its own local canvas first, so its face patch never erases anyone behind it.
    head=(Mh, y0, y1): above sheet y0 the drawing goes through Mh instead, blending into Ms by y1 (the neck), so a
    body that squashes and stretches as it dances carries its head without squashing the face"""
    Ms = np.asarray(Ms, np.float64)
    sc = math.sqrt(abs(Ms[0, 0] * Ms[1, 1] - Ms[0, 1] * Ms[1, 0]))       # screen px per sheet px
    L = next((l for l in (0.125, 0.25, 0.5, 1.0) if sc / (d.S * l) <= 1.25), 1.0)
    base = d.base(L, clip)
    A = _level_affine(d, Ms, L)
    hh, ww = base.shape[:2]
    corners = np.float32([[[0, 0], [ww, 0], [0, hh], [ww, hh]]])
    c = cv2.transform(corners, A.astype(np.float32))[0]
    if head is not None:
        Ah = _level_affine(d, np.asarray(head[0], np.float64), L)
        c = np.vstack([c, cv2.transform(corners, Ah.astype(np.float32))[0]])
    H, W = dst.shape[:2]
    bx0, by0 = int(max(0, np.floor(c[:, 0].min()) - 3)), int(max(0, np.floor(c[:, 1].min()) - 3))
    bx1, by1 = int(min(W, np.ceil(c[:, 0].max()) + 3)), int(min(H, np.ceil(c[:, 1].max()) + 3))
    if bx1 <= bx0 or by1 <= by0:
        return
    loc = np.zeros((by1 - by0, bx1 - bx0, 4), np.float32)
    A2 = A.copy()
    A2[0, 2] -= bx0
    A2[1, 2] -= by0
    p = d.patch(L, st, clip)
    if head is not None:
        # the face patch goes into the drawing first; then one remap through the body's transform below the neck
        # and the head's above it, blended between (what the body's inverse lands on decides which)
        src = base
        if p is not None:
            x0, y0, pm = p
            src = base.copy()
            ph, pw = pm.shape[:2]
            sx0, sy0 = max(0, x0), max(0, y0)
            sx1, sy1 = min(ww, x0 + pw), min(hh, y0 + ph)
            if sx1 > sx0 and sy1 > sy0:
                m = _feather(ph, pw)[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0, None]
                src[sy0:sy1, sx0:sx1] = pm[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * m + src[sy0:sy1, sx0:sx1] * (1 - m)
        Ah2 = Ah.copy()
        Ah2[0, 2] -= bx0
        Ah2[1, 2] -= by0
        Yo, Xo = np.mgrid[0:by1 - by0, 0:bx1 - bx0].astype(np.float32)
        ib = cv2.invertAffineTransform(A2.astype(np.float32))
        ih = cv2.invertAffineTransform(Ah2.astype(np.float32))
        bxs = ib[0, 0] * Xo + ib[0, 1] * Yo + ib[0, 2]
        bys = ib[1, 0] * Xo + ib[1, 1] * Yo + ib[1, 2]
        hxs = ih[0, 0] * Xo + ih[0, 1] * Yo + ih[0, 2]
        hys = ih[1, 0] * Xo + ih[1, 1] * Yo + ih[1, 2]
        ly0 = (head[1] - d.oy) * d.S * L
        ly1 = (head[2] - d.oy) * d.S * L
        w = 1.0 - smooth((bys - ly0) / max(1.0, ly1 - ly0))
        mx = bxs + w * (hxs - bxs)
        my = bys + w * (hys - bys)
        s_ = sc / (d.S * L)
        if s_ < 0.5:                                     # (shrinking a lot: take the edge off first)
            src = cv2.GaussianBlur(src, (0, 0), 0.45 / s_)
        loc = cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    else:
        warp_into(loc, base, A2.astype(np.float32))
        if p is not None:
            x0, y0, pm = p
            Ap = A2.copy()
            Ap[:, 2] += A2[:, :2] @ np.float64([x0, y0])
            warp_into(loc, pm, Ap.astype(np.float32), mode="replace")
    if alpha != 1.0:
        loc *= alpha
    reg = dst[by0:by1, bx0:bx1]
    dst[by0:by1, bx0:bx1] = loc + reg * (1 - loc[..., 3:4])
