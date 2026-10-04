"""Procedural face animation on a character drawing's own head: lip sync, blinks, gaze and brows.

Every character keeps the head drawn on its own body / pose drawing (no head swaps, so no seams at the neck).
On that head, at the 4x part resolution:
  * mouth - the jaw drops: everything below the mouth line is warped down (most at the lips' middle, nothing at
    the corners), and the gap is painted as a mouth interior in the art's own style: dark throat, upper / lower
    teeth, tongue, and an ink line on the lip edges. Rounded shapes (O, U, W) also purse the lips inwards; wide
    shapes (E, I) pull the corners out a little.
  * blink - a skin-coloured lid (sampled above each eye) slides down with an ink lash line.
  * gaze  - the iris is slid inside the eye opening (left / right / up / down).
  * brows - the brow area is lifted or lowered (raise = surprise / question, lower = stern / annoyed).
All warps are one cv2.remap of the face box, driven by landmarks given in part pixels.
"""
import numpy as np, cv2

# viseme -> (open, width, top teeth, bottom teeth, tongue, pucker, stretch)
VIS = {
    "REST": (0.00, 1.00, 0.0, 0.0, 0.0, 0.00, 0.0),
    "MBP":  (0.00, 1.00, 0.0, 0.0, 0.0, 0.00, 0.0),
    "AI":   (0.62, 0.96, 1.0, 0.25, 0.9, 0.00, 0.0),
    "E":    (0.40, 1.00, 1.0, 0.6, 0.5, 0.00, 0.5),
    "I":    (0.24, 1.02, 1.0, 1.0, 0.0, 0.00, 0.8),
    "O":    (0.52, 0.70, 0.5, 0.0, 0.7, 0.45, 0.0),
    "U":    (0.20, 0.50, 0.0, 0.0, 0.0, 0.85, 0.0),
    "FV":   (0.10, 0.92, 1.0, 0.0, 0.0, 0.00, 0.2),
    "L":    (0.34, 0.90, 1.0, 0.0, 1.0, 0.00, 0.0),
    "CDG":  (0.18, 0.94, 1.0, 0.8, 0.0, 0.00, 0.3),
    "R":    (0.22, 0.72, 0.6, 0.0, 0.2, 0.40, 0.0),
    "BREATH": (0.07, 0.90, 0.0, 0.0, 0.0, 0.00, 0.0),
}

THROAT_T = np.float32([0.11, 0.028, 0.024])
THROAT_B = np.float32([0.25, 0.062, 0.05])
TEETH = np.float32([0.96, 0.94, 0.89])
TONGUE = np.float32([0.74, 0.30, 0.29])
INK = np.float32([0.15, 0.07, 0.05])


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Face:
    """landmarks (part px): mouth=(xl, yl, xr, yr, xc, yc), chin=y, eyes=[(cx, cy, rx, ry)...], facing='front'|'left'|'right'
    (for a profile: xl..xr runs from the mouth corner to the lips' front)."""

    def __init__(self, img, mouth=None, chin=None, eyes=(), facing="front", jaw=1.0, ink=None, lid=None, brow_gain=1.0):
        self.img = img.astype(np.float32) / 255 if img.dtype == np.uint8 else img.astype(np.float32)
        self.H, self.W = self.img.shape[:2]
        self.mouth, self.chin, self.eyes = mouth, chin, [tuple(e) for e in eyes]
        self.facing, self.jaw, self.brow_gain = facing, jaw, brow_gain
        self.ink = INK if ink is None else np.float32(ink)
        # the face box that any effect can touch
        pts = []
        if mouth:
            xl, yl, xr, yr, xc, yc = mouth
            mw = xr - xl
            pts += [(xl - 1.4 * mw, yc - 0.6 * mw), (xr + 1.4 * mw, (chin or yc + mw) + 1.2 * mw)]
        for cx, cy, rx, ry in self.eyes:
            pts += [(cx - 2.2 * rx, cy - 5.0 * ry), (cx + 2.2 * rx, cy + 2.5 * ry)]
        if pts:
            p = np.float32(pts)
            self.box = (int(max(0, p[:, 0].min())), int(max(0, p[:, 1].min())),
                        int(min(self.W, p[:, 0].max() + 1)), int(min(self.H, p[:, 1].max() + 1)))
        else:
            self.box = None
        # lid colours: lit skin in a ring around each eye (the brighter skin pixels: no brow, lashes or shadow)
        self.lids = []
        for cx, cy, rx, ry in self.eyes:
            r = max(rx, ry)
            y0, y1, x0, x1 = int(cy - 3 * r), int(cy + 3 * r), int(cx - 3 * r), int(cx + 3 * r)
            y0, x0 = max(0, y0), max(0, x0)
            y1, x1 = max(y0 + 1, min(self.H, y1)), max(x0 + 1, min(self.W, x1))
            sub = self.img[y0:y1, x0:x1]
            yy, xx = np.mgrid[y0:y1, x0:x1]
            d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
            ring = (d > 1.6) & (d < 3.2) & (sub[..., 3] > 0.9)
            p = sub[..., :3][ring]
            if len(p) > 20:
                sk = (p[:, 0] > p[:, 2] + 0.10) & (p[:, 0] > 0.45)
                p = p[sk] if sk.sum() > 10 else p
                lum = p.mean(1)
                q = p[lum >= np.percentile(lum, 70)]
                skin = np.median(q, axis=0)
            else:
                skin = np.float32([0.88, 0.62, 0.46])
            self.lids.append(np.float32(skin) * 0.97 if lid is None else np.float32(lid))
        self.pupils = [self._find_pupil(e) for e in self.eyes]

    def _find_pupil(self, e):
        """the dark pupil inside an eye opening: its mask, sprite and centre, so gaze can move it cleanly"""
        cx, cy, rx, ry = e
        x0, x1 = int(max(0, cx - rx - 2)), int(min(self.W, cx + rx + 3))
        y0, y1 = int(max(0, cy - ry - 2)), int(min(self.H, cy + ry + 3))
        if x1 - x0 < 4 or y1 - y0 < 4: return None
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        inner = ((xx - cx) / (rx * 0.97)) ** 2 + ((yy - cy) / (ry * 0.97)) ** 2 <= 1
        sub = self.img[y0:y1, x0:x1]
        v = sub[..., :3].max(2)
        dark = (inner & (v < 0.42)).astype(np.uint8)
        n, lab, st, cen = cv2.connectedComponentsWithStats(dark, 8)
        if n < 2: return None
        k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        if st[k, cv2.CC_STAT_AREA] < 4: return None
        pm = (lab == k).astype(np.uint8)
        hull = cv2.convexHull(cv2.findNonZero(pm))
        pm = np.zeros_like(pm); cv2.fillConvexPoly(pm, hull, 1)            # keep the highlight inside it
        pm = cv2.dilate(pm, np.ones((3, 3), np.uint8)) & inner.astype(np.uint8)
        white = inner & (v > 0.8) & (pm == 0)
        wc = np.median(sub[..., :3][white], axis=0) if white.sum() > 8 else np.float32([0.98, 0.98, 0.98])
        ys, xs = np.nonzero(pm)
        px, py = xs.mean() + x0, ys.mean() + y0
        pr = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2 + 1
        soft = cv2.GaussianBlur(pm.astype(np.float32), (0, 0), 0.7)
        spr = np.dstack([sub[..., :3], np.clip(soft * 1.3, 0, 1)]).astype(np.float32)
        return dict(box=(x0, y0, x1, y1), inner=inner, mask=soft, px=px, py=py, pr=pr, white=np.float32(wc), sprite=spr)

    # ------------------------------------------------------------------ mouth geometry
    def _lipline(self, X):
        xl, yl, xr, yr, xc, yc = self.mouth
        # quadratic through the corners and the centre
        A = np.array([[xl * xl, xl, 1], [xc * xc, xc, 1], [xr * xr, xr, 1]], np.float64)
        a, b, c = np.linalg.solve(A, np.array([yl, yc, yr], np.float64))
        return (a * X * X + b * X + c).astype(np.float32)

    def render(self, vis="REST", amp=1.0, blink=0.0, look=(0.0, 0.0), brow=0.0, smile=0.0):
        """-> float32 RGBA image (straight colour) with all effects applied."""
        if self.box is None:
            return self.img
        o, ws, tt, tb, tg, pk, st = VIS.get(vis, VIS["REST"])
        o = o * amp * self.jaw
        if o < 0.004 and blink <= 0.01 and abs(brow) < 0.01 and abs(smile) < 0.01 and pk == 0 and not any(self.pupils):
            return self.img
        x0, y0, x1, y1 = self.box
        sub = self.img[y0:y1, x0:x1]
        h, w = sub.shape[:2]
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        mx, my = X.copy(), Y.copy()           # source coords
        opening = None
        if self.mouth:
            xl, yl, xr, yr, xc, yc = self.mouth
            mw = xr - xl
            hw = mw / 2
            chin = self.chin if self.chin else yc + 0.9 * mw
            line = self._lipline(X)
            if self.facing == "front":
                cx_ = xc
                hwo = max(2.0, ws * hw * 0.9)
                u = (X - cx_) / hwo
                g = np.clip(1 - u * u, 0, 1) ** 0.6
                J = 1 - smooth((np.abs(X - cx_) - 0.35 * mw) / (0.95 * mw))
            else:
                # profile: the opening grows from the corner (back) to the lips' front
                back, front = (xl, xr) if self.facing == "right" else (xr, xl)
                span = front - back
                u = (X - back) / span
                g = np.where((u > 0) & (u < 1.15), np.clip(u, 0, 1) ** 0.7, 0.0).astype(np.float32)
                J = 1 - smooth((back - X) * np.sign(span) / (1.2 * abs(span)))
                J = np.where((X - back) * np.sign(span) > 0, 1.0, J).astype(np.float32)
                hw = abs(span)
            Hmax = 0.50 * mw if self.facing == "front" else 0.55 * abs(xr - xl)
            Hc = o * Hmax
            below = Y - line
            wv = smooth(below / (0.40 * mw))
            F = (1 - wv) * g + wv * J
            F = F * (1 - smooth((Y - chin) / (0.45 * mw)))
            F = np.where(below > -1.0, F, 0.0).astype(np.float32)
            # fixed-point for the inverse map: source row = output row - drop at the source
            dy = Hc * F
            for _ in range(2):
                ys = Y - dy
                below_s = ys - line
                wv_s = smooth(below_s / (0.40 * mw))
                Fs = ((1 - wv_s) * g + wv_s * J) * (1 - smooth((ys - chin) / (0.45 * mw)))
                Fs = np.where(below_s > -1.0, Fs, 0.0)
                dy = Hc * Fs.astype(np.float32)
            my = my - dy
            # purse (O, U) / stretch (E, I, smile): horizontal warp of the lip area
            if pk > 0 or st > 0 or smile != 0:
                r2 = ((X - xc) / (1.35 * hw)) ** 2 + ((Y - line) / (0.55 * mw)) ** 2
                wlip = np.clip(1 - r2, 0, 1) ** 1.2
                k = 1 + pk * 0.42 * amp - st * 0.07 * amp - smile * 0.06
                mx = xc + (mx - xc) * (1 + (k - 1) * wlip)
                if smile != 0:        # corners up
                    my = my + smile * (0.07 if smile > 0 else 0.13) * mw * np.clip(np.abs(X - xc) / hw, 0, 1.3) ** 2 * wlip
            # the opening itself (output space): between the lip line and the lowered lower lip
            if Hc > 0.6:
                top = line - Hc * 0.10 * g
                bot = line + Hc * g
                opening = (Y >= top) & (Y < bot) & (g > 0.001)
        # gaze and brows
        for i, (cx, cy, rx, ry) in enumerate(self.eyes):
            if abs(look[0]) + abs(look[1]) > 0.005 and self.pupils[i] is None:
                r2 = ((X - cx) / (rx * 1.08)) ** 2 + ((Y - cy) / (ry * 1.25)) ** 2
                wg = np.clip(1 - r2, 0, 1) ** 1.4
                mx = mx - look[0] * rx * 0.42 * wg
                my = my - look[1] * ry * 0.30 * wg
            if abs(brow) > 0.005:
                by = cy - 2.1 * max(ry, rx * 0.6)
                r2 = ((X - cx) / (rx * 1.9)) ** 2 + ((Y - by) / (max(ry, rx * 0.6) * 1.6)) ** 2
                wb = np.clip(1 - r2, 0, 1) ** 1.2
                my = my + brow * self.brow_gain * max(ry, rx * 0.6) * 0.45 * wb
        out = cv2.remap(sub, mx - x0, my - y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if opening is not None and opening.any():
            out = self._paint_mouth(out, X, Y, line, top, bot, g, Hc, tt, tb, tg, o)
        res = self.img.copy()
        res[y0:y1, x0:x1] = out
        res = self._pupils(res, look)
        if blink > 0.01:
            sub2 = res[y0:y1, x0:x1]
            res[y0:y1, x0:x1] = self._blink(sub2, X, Y, blink)
        return res

    def _pupils(self, img, look):
        """re-place each pupil inside its eye: look (0, 0) = into the lens, +-1 = to the edge of the opening"""
        for (cx, cy, rx, ry), p in zip(self.eyes, self.pupils):
            if p is None: continue
            tx = cx + np.clip(look[0], -1.2, 1.2) * max(0.0, rx - p["pr"]) * 0.78
            ty = cy + np.clip(look[1], -1.0, 1.0) * max(0.0, ry - p["pr"]) * 0.62
            dx, dy = tx - p["px"], ty - p["py"]
            if abs(dx) < 0.3 and abs(dy) < 0.3: continue
            x0, y0, x1, y1 = p["box"]
            reg = img[y0:y1, x0:x1].copy()
            m = p["mask"][..., None]
            reg[..., :3] = reg[..., :3] * (1 - m) + p["white"] * m             # the old pupil painted out
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            spr = cv2.warpAffine(p["sprite"], M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderValue=0)
            a = spr[..., 3:4] * p["inner"][..., None]
            reg[..., :3] = reg[..., :3] * (1 - a) + spr[..., :3] * a
            img[y0:y1, x0:x1] = reg
        return img

    def _paint_mouth(self, out, X, Y, line, top, bot, g, Hc, tt, tb, tg, o):
        xl, yl, xr, yr, xc, yc = self.mouth
        mw = xr - xl
        ss = 4                                   # soft edges: coverage from a blurred mask
        m = ((Y >= top) & (Y < bot) & (g > 0.001)).astype(np.float32)
        m = cv2.GaussianBlur(m, (0, 0), 0.9)
        depth = np.clip((Y - top) / np.maximum(bot - top, 1), 0, 1)[..., None]
        col = THROAT_T * (1 - depth) + THROAT_B * depth
        if tg > 0:                               # tongue: a soft mound at the bottom
            tcy = bot - (bot - top) * 0.18
            r2 = ((X - xc) / (0.42 * mw)) ** 2 + ((Y - tcy) / np.maximum((bot - top) * 0.55, 1)) ** 2
            wt = np.clip(1 - r2, 0, 1) ** 0.5 * tg * np.clip(Hc / (0.12 * mw), 0, 1)
            wt = cv2.GaussianBlur(wt.astype(np.float32), (0, 0), 0.8)[..., None]
            hl = np.clip(1 - ((X - xc) / (0.16 * mw)) ** 2 - ((Y - (tcy - (bot - top) * 0.12)) / np.maximum((bot - top) * 0.12, 1)) ** 2, 0, 1)[..., None]
            col = col * (1 - wt) + (TONGUE * (1 - 0.25 * depth) + 0.18 * hl) * wt
        if tt > 0:                               # upper teeth hanging from the top edge
            th = np.minimum(0.16 * mw, 0.45 * (bot - top)) * tt
            wtop = ((Y - top) < th) & (np.abs(X - xc) < 0.46 * mw)
            wtop = cv2.GaussianBlur(wtop.astype(np.float32), (0, 0), 0.7)[..., None]
            shade = np.clip((Y - top) / np.maximum(th, 1), 0, 1)[..., None]
            col = col * (1 - wtop) + TEETH * (1 - 0.12 * shade) * wtop
        if tb > 0:
            thb = np.minimum(0.10 * mw, 0.30 * (bot - top)) * tb
            wbt = ((bot - Y) < thb) & (np.abs(X - xc) < 0.34 * mw)
            wbt = cv2.GaussianBlur(wbt.astype(np.float32), (0, 0), 0.7)[..., None]
            col = col * (1 - wbt) + TEETH * 0.88 * wbt
        # ink along the upper and lower lip edges
        lw = max(1.2, 0.022 * mw)
        edge = np.zeros(m.shape, np.float32)
        d_top = np.abs(Y - top); d_bot = np.abs(Y - bot)
        inside = np.abs(X - xc) < (xr - xl) * 0.55
        edge = np.maximum(edge, np.clip(1 - d_top / lw, 0, 1) * (g > 0.02) * inside)
        edge = np.maximum(edge, 0.7 * np.clip(1 - d_bot / (lw * 0.8), 0, 1) * (g > 0.02) * inside)
        edge = cv2.GaussianBlur(edge, (0, 0), 0.6)[..., None]
        mm = m[..., None]
        rgb = out[..., :3] * (1 - mm) + col * mm
        rgb = rgb * (1 - edge * 0.85) + self.ink * edge * 0.85
        res = out.copy(); res[..., :3] = rgb
        return res

    def _blink(self, out, X, Y, amount):
        """the lid comes down over the whole eye, outline included, in the cheek's colour; a firm lash line on
        its edge (these cartoon eyes are big and outlined, so a partial lid would leave the outline showing)"""
        res = out.copy()
        for (cx, cy, rx, ry), skin in zip(self.eyes, self.lids):
            x0, y0 = X[0, 0], Y[0, 0]
            yc, xc = int(cy + ry * 1.75 - y0), int(cx - x0)
            h, w = res.shape[:2]
            cheek = res[max(0, yc - 2):min(h, yc + 3), max(0, xc - 3):min(w, xc + 4), :3].reshape(-1, 3)
            lidc = np.median(cheek, 0) if len(cheek) else skin
            top = cy - ry * 1.55
            bot = top + ry * 3.1 * amount
            m = (((X - cx) / (rx * 1.34)) ** 2 + ((Y - (top + bot) / 2) / max(0.5, (bot - top) / 2)) ** 2 <= 1)
            m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), max(0.6, rx * 0.02))[..., None]
            res[..., :3] = res[..., :3] * (1 - m) + lidc[None, None, :] * m
            if amount > 0.35:
                ln = np.zeros(X.shape, np.float32)
                th = max(2, int(round(min(ry * 0.22, rx * 0.12) * min(1.0, (amount - 0.35) * 2.5))))
                cv2.ellipse(ln, (int(round((cx - x0) * 4)), int(round((bot - ry * 0.55 - y0) * 4))),
                            (int(rx * 1.02 * 4), int(ry * 0.5 * 4)), 0, 10, 170, 1, th, cv2.LINE_AA, 2)
                ln = cv2.GaussianBlur(ln, (0, 0), 0.6)[..., None]
                res[..., :3] = res[..., :3] * (1 - ln) + self.ink * ln
        return res


# ---------------------------------------------------------------- phones -> visemes
PH = {
    "AA": "AI", "AE": "AI", "AH": "E", "AO": "O", "AW": ("AI", "U"), "AY": ("AI", "I"), "EH": "E", "ER": "R",
    "EY": ("E", "I"), "IH": "I", "IY": "I", "OW": ("O", "U"), "OY": ("O", "I"), "UH": "U", "UW": "U",
    "B": "MBP", "P": "MBP", "M": "MBP", "F": "FV", "V": "FV", "TH": "L", "DH": "L", "L": "L",
    "S": "CDG", "Z": "CDG", "SH": "U", "ZH": "U", "CH": "U", "JH": "U", "R": "R", "W": "U", "Y": "I",
    "K": "CDG", "G": "CDG", "NG": "CDG", "D": "CDG", "T": "CDG", "N": "CDG", "HH": None, "SIL": "REST",
}
MUST = {"MBP", "FV"}


def viseme_events(phones, t0=0.0):
    """phones [{p, s, e}] (line time) -> [(start, end, viseme)] (scene time, t0 = line start)"""
    ev = []
    for k, x in enumerate(phones):
        p = x["p"]
        v = PH.get(p, "CDG")
        if v is None:                            # breathy onset: already shaped for the next vowel
            nxt = phones[k + 1]["p"] if k + 1 < len(phones) else "AH"
            v = PH.get(nxt, "E"); v = v[0] if isinstance(v, tuple) else (v or "E")
        if p == "AH" and x["e"] - x["s"] < 0.07:
            v = "CDG"
        s, e = t0 + x["s"], t0 + x["e"]
        if isinstance(v, tuple):
            mid = s + (e - s) * 0.55
            ev += [(s, mid, v[0]), (mid, e, v[1])]
        else:
            ev.append((s, e, v))
    return ev


def track(events, n, fps=30, lead=0.035):
    """per-frame visemes: shape one frame early, closures >= 2 frames, no single-frame flicker"""
    tr = ["REST"] * n
    events = sorted(events)
    j = 0
    for i in range(n):
        tt = i / fps + lead
        while j < len(events) and events[j][1] <= tt: j += 1
        for k in range(max(0, j - 2), min(len(events), j + 3)):
            a, b, v = events[k]
            if a <= tt < b: tr[i] = v; break
    for (a, b, v) in events:
        if v in MUST:
            c = int(round(((a + b) / 2 - lead) * fps))
            for q in (c, c + 1):
                if 0 <= q < n: tr[q] = v
    for i in range(1, n - 1):
        if tr[i] not in MUST and tr[i - 1] == tr[i + 1] and tr[i] != tr[i - 1] and tr[i] != "REST":
            tr[i] = tr[i - 1]
    return tr
