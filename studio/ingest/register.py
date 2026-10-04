"""Find where each loose part sits in the sheet's assembled guide figure.

The kit brief asks for the guide to be drawn at the same scale as the loose parts, so every part can be matched
into it: a search over scale and rotation with colour template matching (the part's own alpha as the mask),
coarse at half resolution, then refined at full resolution. The result is the part's rest placement: a similarity
transform from part pixels to guide pixels, plus a match error. Where a part lands in the figure also says what
it is (a sock lands low on the legs, a sleeve at the shoulder)."""
from dataclasses import dataclass

import cv2
import numpy as np

BG = np.array([255, 0, 255], np.float32)      # the guide's transparent background matches no drawing


@dataclass
class Fit:
    x: float        # where the part's own centre (cx, cy of its crop) lands in the guide, guide pixels
    y: float
    scale: float
    angle: float    # degrees, counter-clockwise (OpenCV convention)
    err: float      # mean squared colour error over the part's opaque pixels (0..~1)

    def matrix(self, w, h):
        """2x3 affine taking part-crop pixels to guide pixels"""
        M = cv2.getRotationMatrix2D((w / 2, h / 2), self.angle, self.scale)
        M[:, 2] += [self.x - w / 2, self.y - h / 2]
        return M


LINES = 0.8          # weight of the line-structure channel against the colour channels


def _flat(rgba):
    """matching image: colour on the magenta background, plus a channel of the drawing's own lines. The lines
    (collars, seams, hems, buttons) are what tell a plain black shirt where it sits inside a black figure: found
    as dark strokes relative to the local fill (morphological black-hat), so they show on black cloth too."""
    a = rgba[..., 3:4].astype(np.float32) / 255
    rgb = (rgba[..., :3].astype(np.float32) * a + BG * (1 - a)) / 255
    lum = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    k = max(5, int(round(min(rgba.shape[:2]) * 0.012)) | 1)
    hat = cv2.morphologyEx(lum, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    hat = np.clip(hat / 40.0, 0, 1) * (a[..., 0] > 0.5)
    hat = cv2.GaussianBlur(hat, (0, 0), 1.2)
    return np.dstack([rgb, LINES * hat]).astype(np.float32)


def _templates(part, scales, angles):
    h, w = part.shape[:2]
    for s in scales:
        for ang in angles:
            M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, s)
            c, si = abs(M[0, 0]), abs(M[0, 1])
            W, H = int(h * si + w * c) + 2, int(h * c + w * si) + 2
            M[:, 2] += [W / 2 - w / 2, H / 2 - h / 2]
            t = cv2.warpAffine(part, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            mask = (t[..., 3] >= 128).astype(np.float32)
            if mask.sum() < 20:
                continue
            yield s, ang, t, mask, M


def _search(guide_f, part, scales, angles, region=None, prior=None, unit=1.0):
    """best (err, cx, cy, s, ang) of the part's centre in guide coords; region = (x0, y0, x1, y1) limits the search.
    prior(cx, cy, s) -> penalty added to the match error (cx, cy arrays of candidate centres in full-size guide
    pixels; `unit` converts this search's pixels to those): the anatomy's say where the image is ambiguous."""
    gx0, gy0 = 0, 0
    g = guide_f
    if region is not None:
        gx0, gy0, gx1, gy1 = [int(round(v)) for v in region]
        gx0, gy0 = max(0, gx0), max(0, gy0)
        gx1, gy1 = min(guide_f.shape[1], gx1), min(guide_f.shape[0], gy1)
        g = guide_f[gy0:gy1, gx0:gx1]
    best = (np.inf, 0, 0, 1, 0)
    h, w = part.shape[:2]
    for s, ang, t, mask, M in _templates(part, scales, angles):
        if t.shape[0] >= g.shape[0] or t.shape[1] >= g.shape[1]:
            continue
        tf = _flat(t)
        r = cv2.matchTemplate(g, tf, cv2.TM_SQDIFF, mask=np.dstack([mask] * 4))
        r /= (mask.sum() * 4)
        # the part's centre (w/2, h/2) in template coords
        cx, cy = M @ np.array([w / 2, h / 2, 1.0])
        if prior is not None:
            ys, xs = np.mgrid[0:r.shape[0], 0:r.shape[1]]
            r = r + prior((gx0 + xs + cx) * unit, (gy0 + ys + cy) * unit, s)
        mn, _, loc, _ = cv2.minMaxLoc(r)
        if mn < best[0]:
            best = (mn, gx0 + loc[0] + cx, gy0 + loc[1] + cy, s, ang)
    return best


def fit(part, guide, coarse=0.5, scales=(0.8, 0.9, 1.0, 1.1, 1.2), angles=range(-35, 36, 7), region=None,
        prior=None):
    """Register a part crop (RGBA) into the guide crop (RGBA). Returns a Fit in guide-crop pixels.
    `region` (x0, y0, x1, y1, guide pixels) limits where the part's centre may land; `prior(cx, cy, s)` adds an
    anatomical penalty (see _search)."""
    small_g = cv2.resize(guide, None, fx=coarse, fy=coarse, interpolation=cv2.INTER_AREA)
    small_p = cv2.resize(part, None, fx=coarse, fy=coarse, interpolation=cv2.INTER_AREA)
    sreg = None
    if region is not None:
        # the search window must hold the whole template around any allowed centre
        r = 0.5 * max(part.shape[:2]) * max(scales) * coarse + 2
        sreg = (region[0] * coarse - r, region[1] * coarse - r, region[2] * coarse + r, region[3] * coarse + r)
    err, cx, cy, s, ang = _search(_flat(small_g), small_p, scales, angles, sreg, prior, 1 / coarse)
    cx, cy = cx / coarse, cy / coarse
    # refine at full resolution around the coarse answer
    gf = _flat(guide)
    pad = 0.6 * max(part.shape[:2]) * s + 12
    fine_s = [s * k for k in (0.96, 0.98, 1.0, 1.02, 1.04)]
    fine_a = [ang + d for d in (-4, -2, 0, 2, 4)]
    err, fx, fy, s, ang = _search(gf, part, fine_s, fine_a, (cx - pad, cy - pad, cx + pad, cy + pad), prior)
    return Fit(float(fx), float(fy), float(s), float(ang), float(err))
