"""Graphics: the divider of the portrait split screens with the show's badge on it, and the closing achievement, a
games-console style pop-up (a trophy, ACHIEVEMENT UNLOCKED, MANCHESTER UNITED: NEW LOW) that springs up over the
divider of the last split screen, drawn flat in the kit's look: dark navy, the heavy ink outline, United red and a gold
trophy. Both drawn at the frame's own resolution."""
import functools

import numpy as np
from PIL import Image, ImageDraw

from studio.film.engine import OH, OW
from studio.film.graphics import BEBAS, INTER, font

INK = (12, 12, 16, 255)
NAVY = (14, 22, 52, 255)
RED = (214, 30, 36, 255)
GOLD = (246, 190, 40, 255)


def _premult(im):
    a = np.asarray(im).astype(np.float32) / 255
    return a[..., :3] * a[..., 3:4], a[..., 3:4]


@functools.lru_cache(maxsize=1)
def _badge_layer():
    """the split screen's divider: an ink rule with a red core across the middle, the show's badge on it"""
    u = OW / 1080
    im = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = OH // 2
    d.rectangle((0, y - int(7 * u), OW, y + int(7 * u)), fill=INK)
    d.rectangle((0, y - int(2 * u), OW, y + int(2 * u)), fill=RED)
    f = font(BEBAS, 58 * u)
    w = d.textlength("OVERCRAP DAILY", font=f)
    x0, x1 = OW / 2 - w / 2 - 26 * u, OW / 2 + w / 2 + 26 * u
    d.rounded_rectangle((x0, y - 40 * u, x1, y + 40 * u), radius=10 * u, fill=NAVY, outline=INK, width=int(5 * u))
    d.text((x0 + 26 * u, y - 33 * u), "OVERCRAP", font=f, fill=(255, 255, 255, 255))
    d.text((x0 + 26 * u + d.textlength("OVERCRAP ", font=f), y - 33 * u), "DAILY", font=f, fill=(232, 40, 44, 255))
    return _premult(im)


def badge(img, s, t):
    rgb, a = _badge_layer()
    return img * (1 - a) + rgb


@functools.lru_cache(maxsize=1)
def _toast_layer():
    """the achievement pop-up, drawn once on a transparent strip as wide as the frame"""
    u = OW / 1080
    W, H = OW, int(300 * u)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 60 * u, 40 * u, W - 60 * u, H - 30 * u
    d.rounded_rectangle((x0 + 8 * u, y0 + 10 * u, x1 + 8 * u, y1 + 10 * u), radius=44 * u, fill=(0, 0, 0, 110))   # shadow
    d.rounded_rectangle((x0, y0, x1, y1), radius=44 * u, fill=NAVY, outline=INK, width=int(7 * u))
    # the trophy in a gold disc
    cx, cy, r = x0 + 120 * u, (y0 + y1) / 2, 78 * u
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD, outline=INK, width=int(6 * u))
    cup = [(cx - 38 * u, cy - 40 * u), (cx + 38 * u, cy - 40 * u), (cx + 30 * u, cy + 2 * u), (cx + 10 * u, cy + 14 * u),
           (cx - 10 * u, cy + 14 * u), (cx - 30 * u, cy + 2 * u)]
    d.polygon(cup, fill=(255, 255, 255, 255), outline=INK, width=int(5 * u))
    d.arc((cx - 58 * u, cy - 38 * u, cx - 22 * u, cy), 90, 270, fill=INK, width=int(6 * u))
    d.arc((cx + 22 * u, cy - 38 * u, cx + 58 * u, cy), 270, 90, fill=INK, width=int(6 * u))
    d.rectangle((cx - 7 * u, cy + 14 * u, cx + 7 * u, cy + 32 * u), fill=INK)
    d.rounded_rectangle((cx - 30 * u, cy + 30 * u, cx + 30 * u, cy + 44 * u), radius=4 * u, fill=INK)
    tx = cx + r + 34 * u
    d.text((tx, y0 + 30 * u), "ACHIEVEMENT UNLOCKED", font=font(INTER, 30 * u, 700), fill=GOLD)
    d.text((tx, y0 + 70 * u), "MANCHESTER UNITED", font=font(BEBAS, 60 * u), fill=(255, 255, 255, 255))
    d.text((tx, y0 + 128 * u), "NEW LOW UNLOCKED", font=font(BEBAS, 76 * u), fill=(232, 40, 44, 255))
    return _premult(im)


def toast(img, s, t):
    """the pop-up springs up over the divider 0.25 s into the shot (between Mark's desk and Gary's head: no face is
    covered), with a quick overshoot, and stays"""
    rgb, a = _toast_layer()
    u = (t - s["t"] - 0.25) / 0.16
    if u <= 0:
        return img
    sc = 1 - (1 - min(1.0, u)) ** 3 + (0.08 * np.sin(np.pi * min(1.0, (u - 1) / 0.9)) if u > 1 else 0.0)
    H, W = rgb.shape[:2]
    if abs(sc - 1) > 1e-3:                       # scaled about its centre as it springs up
        import cv2
        M = np.float32([[sc, 0, W / 2 * (1 - sc)], [0, sc, H / 2 * (1 - sc)]])
        rgb = cv2.warpAffine(rgb, M, (W, H))
        a = cv2.warpAffine(a[..., 0], M, (W, H))[..., None]
    y = int(round(OH / 2 - H / 2 + 10 * OW / 1080))
    out = img.copy()
    a0, a1 = max(0, y), min(OH, y + H)
    if a1 <= a0:
        return img
    r0 = a0 - y
    seg_a = a[r0:r0 + a1 - a0]
    out[a0:a1] = img[a0:a1] * (1 - seg_a) + rgb[r0:r0 + a1 - a0]
    return out
