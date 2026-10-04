"""On-screen graphics and the picture finish (from All or Something): documentary captions (name lower thirds,
location slugs, closing lines), title cards, colour grades, vignette and grain. Everything is drawn at the output
resolution from a 1920 x 1080 layout (scaled by RS). Fonts: library/fonts (Bebas Neue, Inter, Montserrat; OFL)."""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from studio.film.engine import OH, OW, RS
from studio.paths import FONTS

BEBAS, INTER, MONT = str(FONTS / "BebasNeue-Regular.ttf"), str(FONTS / "Inter.ttf"), str(FONTS / "Montserrat.ttf")
RED, AMBER = (218, 22, 30), (246, 160, 30)


def sm(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


@functools.lru_cache(maxsize=64)
def font(path, size, weight=None):
    f = ImageFont.truetype(path, int(round(size)))
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def premult(im):
    a = np.asarray(im).astype(np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a


FONT_NAMES = {"BEBAS": BEBAS, "INTER": INTER, "MONT": MONT}


@functools.lru_cache(maxsize=32)
def text_layer(lines):
    """lines: ((text, font (path or BEBAS / INTER / MONT), size, weight, tracking px, y, colour rgb), ...) centred
    -> premult RGBA float"""
    im = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for text, fp, size, weight, track, y, col in lines:
        f = font(FONT_NAMES.get(fp, fp), size * RS, weight)
        widths = [dr.textlength(ch, font=f) for ch in text]
        total = sum(widths) + track * RS * (len(text) - 1)
        x = (OW - total) / 2
        for ch, w in zip(text, widths):
            dr.text((x, y * RS), ch, font=f, fill=tuple(col) + (255,))
            x += w + track * RS
    return premult(im)


def shadow_of(layer, blur, offset, strength):
    a = cv2.GaussianBlur(layer[..., 3], (0, 0), blur * RS)
    a = np.roll(np.roll(a, int(offset[1] * RS), 0), int(offset[0] * RS), 1)
    return a * strength


def over(img, layer, alpha=1.0):
    return img * (1 - layer[..., 3:4] * alpha) + layer[..., :3] * alpha


def scaled(layer, s, cx, cy):
    if abs(s - 1) < 1e-3:
        return layer
    M = cv2.getRotationMatrix2D((cx, cy), 0, s)
    return cv2.warpAffine(layer, M, (OW, OH), flags=cv2.INTER_LINEAR)


# ---------------------------------------------------------------- title card
def title_card(t, t0, title, tag, glow=(0.30, 0.02, 0.03), rule=RED):
    """black, a glow behind the title that pulses once on the boom, the title punching in, a rule, the tagline"""
    u = t - t0
    img = np.zeros((OH, OW, 3), np.float32)
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    g = np.exp(-(((xx - OW / 2) / (OW * 0.4)) ** 2 + ((yy - OH * 0.42) / (OH * 0.3)) ** 2))
    boom = 0.55 + 0.45 * math.exp(-u * 2.2)
    img += g[..., None] * np.float32(glow) * boom
    s = 1.0 + 0.10 * math.exp(-u * 7.0)
    lay = scaled(text_layer(title), s, OW / 2, OH * 0.42)
    img = over(img, lay)
    y = int(700 * RS)
    w = int(560 * RS * sm(u / 0.35))
    img[y:y + int(7 * RS), OW // 2 - w // 2:OW // 2 + w // 2] = np.float32(rule) / 255
    if tag:
        img = over(img, text_layer(tag), sm((u - 0.3) / 0.3))
    return img


# ---------------------------------------------------------------- grades, finish
def grade(img, kind, t=0.0):
    if kind == "studio":                                 # warm practical lights, a little contrast
        l = img.mean(2, keepdims=True)
        img = l + (img - l) * 0.96
        img = (img - 0.5) * 1.05 + 0.5
        img = img * np.float32([1.02, 1.0, 0.975])
    elif kind == "sunny":
        l = img.mean(2, keepdims=True)
        img = l + (img - l) * 1.05
        img = (img - 0.5) * 1.04 + 0.5
        img = img * np.float32([1.03, 1.0, 0.96]) + 0.01
    elif kind == "room":
        l = img.mean(2, keepdims=True)
        img = l + (img - l) * 0.94
        img = (img - 0.5) * 1.06 + 0.5
        img *= np.float32([1.02, 1.0, 0.975])
    elif kind == "insert":                               # close on a prop: neutral, crisp
        img = (img - 0.5) * 1.03 + 0.5
    return img


@functools.lru_cache(maxsize=2)
def _vignette():
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    r = np.sqrt(((xx - OW / 2) / (OW * 0.62)) ** 2 + ((yy - OH / 2) / (OH * 0.62)) ** 2)
    return (1 - 0.26 * np.clip(r - 0.55, 0, 1) ** 1.5)[..., None].astype(np.float32)


def finish(img, frame):
    img = img * _vignette()
    rng = np.random.default_rng(frame)
    g = rng.standard_normal((OH // 2, OW // 2)).astype(np.float32)
    g = cv2.resize(g, (OW, OH), interpolation=cv2.INTER_LINEAR)
    img = img + g[..., None] * 0.009
    return np.clip(img, 0, 1)


# ---------------------------------------------------------------- documentary captions
@functools.lru_cache(maxsize=32)
def caption_layer(kind, a, b):
    """a caption drawn once (premultiplied RGBA float, full frame)"""
    im = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    S = RS
    if kind == "name":                                    # lower third: red bar, name, role
        x, y = int(96 * S), int(842 * S)
        fn, fr = font(BEBAS, 76 * S), font(INTER, 34 * S, 600)
        wn = dr.textlength(a, font=fn)
        wr = dr.textlength(b, font=fr)
        w = int(max(wn, wr) + 56 * S)
        dr.rectangle((x - int(20 * S), y - int(12 * S), x + w, y + int(128 * S)), fill=(12, 12, 14, 170))
        dr.rectangle((x - int(20 * S), y - int(12 * S), x - int(11 * S), y + int(128 * S)), fill=RED + (255,))
        dr.text((x + int(8 * S), y - int(6 * S)), a, font=fn, fill=(255, 255, 255, 255))
        dr.text((x + int(10 * S), y + int(78 * S)), b, font=fr, fill=(215, 215, 215, 255))
    elif kind == "place":                                 # location slug, top left
        x, y = int(96 * S), int(84 * S)
        fn, fr = font(BEBAS, 68 * S), font(INTER, 32 * S, 600)
        w = int(max(dr.textlength(a, font=fn), dr.textlength(b, font=fr)) + 44 * S)
        dr.rectangle((x - int(22 * S), y - int(14 * S), x + w, y + int(142 * S)), fill=(12, 12, 14, 175))
        dr.text((x, y), a, font=fn, fill=(255, 255, 255, 255))
        dr.rectangle((x, y + int(78 * S), x + int(86 * S), y + int(83 * S)), fill=RED + (255,))
        dr.text((x, y + int(94 * S)), b, font=fr, fill=(240, 240, 240, 255))
    elif kind in ("epilogue", "epilogue2"):             # closing captions, centred on black
        f = font(INTER, 46 * S, 500)
        txt = a or b
        tw = dr.textlength(txt, font=f)
        y = int((470 if kind == "epilogue" else 540) * S)
        dr.text(((OW - tw) / 2, y), txt, font=f, fill=(236, 236, 236, 255))
    return premult(im)


def captions(img, t, caps):
    """caps: [(t0, t1, kind, text 1, text 2)]: name / place / epilogue"""
    for t0, t1, kind, a, b in caps:
        if not (t0 <= t < t1):
            continue
        k = sm((t - t0) / 0.22) * (1 - sm((t - (t1 - 0.2)) / 0.2))
        lay = caption_layer(kind, a, b)
        dx = int(round((1 - sm((t - t0) / 0.3)) * -36 * RS)) if kind in ("name", "place") else 0
        if kind.startswith("epilogue"):
            k = sm((t - t0) / 0.45)
        if dx:
            lay = np.roll(lay, dx, 1)
        if not kind.startswith("epilogue"):
            sh = shadow_of(lay, 8, (0, 4), 0.35)
            img = img * (1 - sh[..., None] * k)
        img = img * (1 - lay[..., 3:4] * k) + lay[..., :3] * k
    return img
