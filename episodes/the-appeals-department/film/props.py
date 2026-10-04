"""Set dressing and inserts for the test: Gary's taped sign on the studio wall, and the card reader close-ups
(Micah turning it over; the charge going through). Drawn in the house look: flat colours, a dark ink outline."""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from studio.film import graphics as G
from studio.film.engine import OH, OW, RS
from studio.film.shots import ease
from film.timeline import TL

INK = (24, 20, 22)


def m(k):
    return TL["marks"][k]


# ---------------------------------------------------------------- the studio, with Gary's sign on the wall
SIGN_AT = (448, 168)          # 1x plate px: the sign's centre, taped over the lower half of the big stadium print
SIGN_W = 236


def sign_image(w):
    """the taped paper sign, w px wide (RGBA, PIL)"""
    h = int(w * 0.56)
    pad = int(w * 0.08)
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    lw = max(3, int(w * 0.012))
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    dr.polygon([(x0, y0 + 3), (x1, y0), (x1 - 2, y1), (x0 + 2, y1 - 2)], fill=(247, 243, 230, 255), outline=INK + (255,))
    dr.line([(x0, y0 + 3), (x1, y0), (x1 - 2, y1), (x0 + 2, y1 - 2), (x0, y0 + 3)], fill=INK + (255,), width=lw)

    def text(t, fnt, size, y, col, track=0):
        f = G.font(fnt, size)
        widths = [dr.textlength(ch, font=f) for ch in t]
        total = sum(widths) + track * (len(t) - 1)
        x = (im.width - total) / 2
        for ch, cw in zip(t, widths):
            dr.text((x, y), ch, font=f, fill=col)
            x += cw + track

    text("THE APPEALS", G.BEBAS, h * 0.26, y0 + h * 0.05, (20, 20, 24, 255), w * 0.006)
    text("DEPARTMENT", G.BEBAS, h * 0.26, y0 + h * 0.29, (20, 20, 24, 255), w * 0.006)
    text("£19.99 PER APPEAL", G.BEBAS, h * 0.17, y0 + h * 0.56, (205, 28, 34, 255), w * 0.003)
    text("UNDER-14s GO FREE", G.BEBAS, h * 0.13, y0 + h * 0.77, (40, 40, 44, 255), w * 0.003)
    # tape strips at the corners, a little crooked
    for (cx, cy, ang) in ((x0 + w * 0.06, y0 + 2, -28), (x1 - w * 0.06, y0, 24), (x0 + w * 0.08, y1 - 2, 22)):
        tw, th = int(w * 0.13), int(w * 0.045)
        tape = Image.new("RGBA", (tw, th), (236, 222, 176, 205))
        tape = tape.rotate(ang, expand=True, resample=Image.BICUBIC)
        im.alpha_composite(tape, (int(cx - tape.width / 2), int(cy - tape.height / 2)))
    return im.rotate(-2.2, expand=True, resample=Image.BICUBIC)


RIM = (842.3, 583.4, 267.0, 34.6)       # the low table's far rim, an ellipse (centre x, centre y, a, b; 1x plate px)
PLANT_HOLE = [(791, 546), (915, 546), (915, 571), (922, 571), (922, 577), (848, 577), (843, 590), (841, 603),
              (828, 610), (776, 610), (776, 577), (791, 577)]           # the plant and its shadows, down to the book
WOOD = ((708, 738), (966, 1000))       # clean table top either side of it, between the mugs


def rim_y(x):
    xc, yc, a, b = RIM
    u = np.clip((np.asarray(x, np.float64) - xc) / a, -0.9999, 0.9999)
    return yc - b * np.sqrt(1 - u * u)


def plate_image(k):
    """the 4x studio with the sign added (RGB uint8); "T" is the same with the plant taken off the low table (its
    edge is the foreground of the close singles, where the plant would sit in front of a chest): the table top is
    rebuilt row by row from the clean wood either side, following the rim's curve"""
    if k == "T":
        big = plate_image("S").copy()
        H = big.shape[0]
        hole = np.zeros(big.shape[:2], np.uint8)
        cv2.fillPoly(hole, [np.int32(np.float32(PLANT_HOLE) * 4)], 1)
        f = big.astype(np.float32)
        (l0, l1), (r0, r1) = WOOD
        left, right = f[:, l0 * 4:l1 * 4].mean(1), f[:, r0 * 4:r1 * 4].mean(1)
        xl, xr = (l0 + l1) / 2, (r0 + r1) / 2
        ys, xs = np.nonzero(hole)
        x1 = xs / 4.0
        yl = np.clip(np.round(ys + (rim_y(xl) - rim_y(x1)) * 4).astype(int), 0, H - 1)
        yr = np.clip(np.round(ys + (rim_y(xr) - rim_y(x1)) * 4).astype(int), 0, H - 1)
        u = ((x1 - xl) / (xr - xl))[:, None]
        big[ys, xs] = np.clip(left[yl] * (1 - u) + right[yr] * u, 0, 255).astype(np.uint8)
        return big
    if k != "S":
        return None
    from studio.episode.upscale import upscaled
    from studio.paths import BACKGROUNDS
    big = upscaled(BACKGROUNDS / "tv-and-media" / "podcast-studio.png", 4.0)[..., ::-1].copy()
    sg = sign_image(SIGN_W * 4)
    arr = np.asarray(sg).astype(np.float32) / 255
    h, w = arr.shape[:2]
    x0, y0 = int(SIGN_AT[0] * 4 - w / 2), int(SIGN_AT[1] * 4 - h / 2)
    # a soft shadow on the wall, down and to the right
    sh = cv2.GaussianBlur(arr[..., 3], (0, 0), 10)
    sx, sy = x0 + 18, y0 + 22
    reg = big[sy:sy + h, sx:sx + w].astype(np.float32)
    big[sy:sy + h, sx:sx + w] = (reg * (1 - 0.45 * sh[..., None])).astype(np.uint8)
    reg = big[y0:y0 + h, x0:x0 + w].astype(np.float32)
    a = arr[..., 3:4]
    big[y0:y0 + h, x0:x0 + w] = (reg * (1 - a) + arr[..., :3] * 255 * a).astype(np.uint8)
    return big


# ---------------------------------------------------------------- the card reader
@functools.lru_cache(maxsize=1)
def table_backdrop():
    """the low table's wooden top, close and out of focus (RGB float, frame size)"""
    from film.direction import PLATES          # noqa: F401  (the same studio)
    from studio.film.render import plate
    P = plate("S")
    img = P.render(842, 600, 4.2)
    return cv2.GaussianBlur(img, (0, 0), 9 * RS)


# ---------------------------------------------------------------- hands holding things (point-of-view inserts)
SS = 4                                                   # drawn props are supersampled 4x, then shrunk
SKIN = {"micah": (179, 97, 51), "pep": (252, 172, 117)}             # from their hand sheets
SLEEVE = {"micah": ((41, 44, 65), (243, 243, 243)), "pep": ((33, 33, 33), None)}     # sleeve, shirt cuff


def _ink_ellipse(dr, box, fill, lw):
    x0, y0, x1, y1 = box
    dr.ellipse((x0 - lw, y0 - lw, x1 + lw, y1 + lw), fill=INK + (255,))
    dr.ellipse(box, fill=tuple(fill) + (255,))


def _ink_rect(dr, box, fill, lw, r):
    x0, y0, x1, y1 = box
    dr.rounded_rectangle((x0 - lw, y0 - lw, x1 + lw, y1 + lw), radius=r + lw, fill=INK + (255,))
    dr.rounded_rectangle(box, radius=r, fill=tuple(fill) + (255,))


def _finger(dr, p0, p1, r, fill, lw):
    """a rounded finger from its root p0 to its tip p1, outlined in ink"""
    for rr, col in ((r + lw, INK), (r, tuple(fill))):
        dr.line([p0, p1], fill=col + (255,), width=int(round(2 * rr)))
        for x, y in (p0, p1):
            dr.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (255,))


def hand(who, w, h, ox, oy, cw, ch, mirror=False):
    """a hand holding a device (w x h at ox, oy on a cw x ch canvas; supersampled px) from below, seen by its owner:
    palm, wrist and sleeve behind the device, the thumb over its left edge and four fingertips over its right
    (mirror: the other way round) -> (behind, front) PIL RGBA"""
    skin = SKIN[who]
    sleeve, cuff = SLEEVE[who]
    lw = 9 * RS * SS
    X = (lambda x: 2 * ox + w - x) if mirror else (lambda x: x)
    box = lambda x0, y0, x1, y1: (min(X(x0), X(x1)), y0, max(X(x0), X(x1)), y1)
    cx = ox + w * 0.5
    back = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    dr = ImageDraw.Draw(back)
    _ink_rect(dr, box(cx - w * 0.27, oy + h * 1.27, cx + w * 0.27, ch + 4 * lw), sleeve, lw, int(w * 0.05))
    if cuff:
        _ink_rect(dr, box(cx - w * 0.23, oy + h * 1.21, cx + w * 0.23, oy + h * 1.29), cuff, lw, int(w * 0.03))
    _ink_rect(dr, box(cx - w * 0.21, oy + h * 0.95, cx + w * 0.21, oy + h * 1.23), skin, lw, int(w * 0.08))
    _ink_ellipse(dr, box(ox - w * 0.06, oy + h * 0.50, ox + w * 1.08, oy + h * 1.09), skin, lw)
    front = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    dr = ImageDraw.Draw(front)
    for i in range(4):                                   # index finger at the top, the little finger shortest
        y = oy + h * (0.585 + 0.083 * i)
        tip = ox + w * (0.955 + 0.02 * (i == 3))
        _finger(dr, (X(ox + w * 1.075), y + h * 0.012), (X(tip), y), w * 0.058, skin, lw)
    _finger(dr, (X(ox - w * 0.05), oy + h * 0.86), (X(ox + w * 0.125), oy + h * 0.665), w * 0.066, skin, lw)
    return back, front


def _device(w, h, body=(46, 49, 56)):
    """a blank handset body, w x h supersampled px -> (PIL RGBA, ImageDraw, ink width, corner radius)"""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    lw = int(9 * RS * SS)
    r = int(w * 0.15)
    dr.rounded_rectangle((lw, lw, w - lw, h - lw), radius=r, fill=body + (255,), outline=INK + (255,), width=lw)
    return im, dr, lw, r


def _lines(dr, items, x0, x1, y0, y1, gap):
    """centred lines of text [(text, font, colour)] spread over a box, gaps in px"""
    hs = [dr.textbbox((0, 0), t, font=f)[3] - dr.textbbox((0, 0), t, font=f)[1] for t, f, _ in items]
    y = (y0 + y1) / 2 - (sum(hs) + gap * (len(items) - 1)) / 2
    for (t, f, col), hh in zip(items, hs):
        bb = dr.textbbox((0, 0), t, font=f)
        dr.text(((x0 + x1) / 2 - (bb[2] - bb[0]) / 2 - bb[0], y - bb[1]), t, font=f, fill=col + (255,))
        y += hh + gap


READER_WH = (470, 760)                                   # px at 1920 x 1080
FLASH = (("", 0, (255, 255, 255)),)                      # the screen lit up white for a moment


def reader_device(screen, back=False):
    """the card reader face on (the screen and keypad) or its back (Gary's sticker) -> PIL RGBA, supersampled"""
    W, H = int(READER_WH[0] * RS * SS), int(READER_WH[1] * RS * SS)
    im, dr, lw, r = _device(W, H)
    k = RS * SS
    if back:
        dr.rounded_rectangle((W * 0.18, H * 0.58, W * 0.82, H * 0.88), radius=r // 3, outline=(30, 32, 37, 255),
                             width=lw // 2)
        sx0, sy0, sx1, sy1 = W * 0.11, H * 0.12, W * 0.89, H * 0.49
        dr.rounded_rectangle((sx0, sy0, sx1, sy1), radius=r // 4, fill=(250, 244, 226, 255), outline=INK + (255,),
                             width=lw // 2)
        _lines(dr, [("PROPERTY OF", G.font(G.BEBAS, 40 * k), (40, 40, 44)),
                    ("GARY NEVILLE'S", G.font(G.BEBAS, 60 * k), (20, 20, 24)),
                    ("APPEALS DEPT.", G.font(G.BEBAS, 60 * k), (205, 28, 34)),
                    ("DO NOT REMOVE", G.font(G.INTER, 22 * k, 700), (60, 60, 64))], sx0, sx1, sy0, sy1, 12 * k)
    else:
        sx0, sy0, sx1, sy1 = W * 0.12, H * 0.08, W * 0.88, H * 0.42
        dr.rounded_rectangle((sx0, sy0, sx1, sy1), radius=r // 3, fill=(222, 236, 230, 255), outline=INK + (255,),
                             width=lw // 2)
        if screen == FLASH:
            dr.rounded_rectangle((sx0, sy0, sx1, sy1), radius=r // 3, fill=(255, 255, 255, 255), outline=INK + (255,),
                                 width=lw // 2)
        else:
            _lines(dr, [(t, G.font(G.BEBAS, size * k) if size > 40 else G.font(G.INTER, size * k, 700), col)
                        for t, size, col in screen], sx0, sx1, sy0, sy1, 14 * k)
        kw, kh = W * 0.2, H * 0.075
        for row in range(4):
            for col_ in range(3):
                x, y = W * 0.17 + col_ * W * 0.24, H * 0.5 + row * H * 0.105
                fill = ((196, 52, 52), (70, 74, 82), (60, 160, 90))[col_] if row == 3 else (70, 74, 82)
                dr.rounded_rectangle((x, y, x + kw, y + kh), radius=int(kh * 0.3), fill=fill + (255,),
                                     outline=INK + (255,), width=lw // 3)
    return im


PHONE_WH = (250, 500)


def phone_device():
    """Pep's phone, its screen showing the card he pays with -> PIL RGBA, supersampled"""
    W, H = int(PHONE_WH[0] * RS * SS), int(PHONE_WH[1] * RS * SS)
    im, dr, lw, r = _device(W, H, body=(28, 28, 32))
    dr.rounded_rectangle((W * 0.08, H * 0.05, W * 0.92, H * 0.95), radius=r * 0.7, fill=(18, 20, 28, 255))
    cx0, cy0, cx1, cy1 = W * 0.14, H * 0.30, W * 0.86, H * 0.52
    dr.rounded_rectangle((cx0, cy0, cx1, cy1), radius=W * 0.05, fill=(52, 84, 170, 255), outline=INK + (255,),
                         width=lw // 3)
    dr.rounded_rectangle((cx0 + W * 0.07, cy0 + H * 0.05, cx0 + W * 0.21, cy0 + H * 0.09), radius=W * 0.015,
                         fill=(226, 190, 90, 255))
    f = G.font(G.INTER, 17 * RS * SS, 600)
    dr.text((cx0 + W * 0.07, cy1 - H * 0.055), "•••• 1971", font=f, fill=(235, 238, 245, 255))
    f = G.font(G.INTER, 15 * RS * SS, 600)
    _lines(dr, [("HOLD NEAR READER", f, (200, 205, 215))], 0, W, H * 0.60, H * 0.66, 0)
    return im


@functools.lru_cache(maxsize=8)
def held(kind, who, screen=(), back=False, mirror=False):
    """a device in someone's hand, on a canvas at frame scale -> (hand behind, device, hand in front) as premult
    float, and the device's box (x0, y0, x1, y1) in canvas px"""
    dev = phone_device() if kind == "phone" else reader_device(screen, back)
    w, h = dev.size
    ox, oy = int(w * 0.16), int(h * 0.03)
    cw, ch = int(w * 1.32) // SS * SS, int(h * 1.62) // SS * SS
    behind, front = hand(who, w, h, ox, oy, cw, ch, mirror)
    d = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d.paste(dev, (ox, oy))
    out = [G.premult(im.resize((cw // SS, ch // SS), Image.LANCZOS)) for im in (behind, d, front)]
    return out[0], out[1], out[2], (ox / SS, oy / SS, (ox + w) / SS, (oy + h) / SS)


def _stack(*lays):
    """premultiplied RGBA layers, bottom first, into one"""
    out = lays[0]
    for top in lays[1:]:
        out = top + out * (1 - top[..., 3:4])
    return out


def _xscale(lay, sx, cx):
    """squeeze a canvas about x = cx (a device turning about its vertical axis)"""
    if abs(sx - 1) < 1e-3:
        return lay
    M = np.float32([[sx, 0, cx * (1 - sx)], [0, 1, 0]])
    return cv2.warpAffine(lay, M, (lay.shape[1], lay.shape[0]), flags=cv2.INTER_LINEAR)


def _put(img, lay, anchor, at, rot=0.0, scale=1.0, shadow=1.0):
    """a canvas into the frame: its point `anchor` (canvas px) at frame point `at`, rotated (degrees, counter-
    clockwise) and scaled about it, with a soft drop shadow on what is behind"""
    M = cv2.getRotationMatrix2D((float(anchor[0]), float(anchor[1])), rot, scale)
    M[0, 2] += at[0] - anchor[0]
    M[1, 2] += at[1] - anchor[1]
    out = cv2.warpAffine(lay, M, (OW, OH), flags=cv2.INTER_LINEAR)
    if shadow > 0:
        img = img * (1 - G.shadow_of(out, 22, (14, 22), 0.5 * shadow)[..., None])
    return G.over(img, out)


READY = (("GARY NEVILLE'S APPEALS", 24, (30, 34, 36)), ("£19.99", 96, (20, 20, 24)), ("TAP TO APPEAL", 24, (40, 120, 70)))
GUEST = (("REGISTER GUEST", 54, (20, 20, 24)), ("PEP G.  x 115", 28, (60, 64, 68)))
CHARGED = (("115 APPEALS", 60, (20, 20, 24)), ("£2,298.85", 88, (205, 28, 34)), ("APPROVED", 26, (40, 140, 70)))
READER_AT = (OW / 2, OH / 2 - 30 * RS)                # where the reader's centre sits in an insert


def _reader(img, who, screen, sx, rot, push):
    """the reader in someone's hand, turned about its vertical axis by sx (1 face on, -1 its back), rotated and
    pushed in about its centre; the palm and sleeve stay where they are while it turns"""
    hb, dev, hf, (x0, y0, x1, y1) = held("reader", who, screen if sx >= 0 else (), back=sx < 0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    k = max(0.04, abs(sx))
    lay = _stack(_xscale(hb, max(0.3, k), cx), _xscale(dev, k, cx), _xscale(hf, k, cx))
    return _put(img, lay, (cx, cy), READER_AT, rot=rot, scale=push)


def reader_flip(s, t):
    """Micah turns the reader over: the front (ready to take £19.99), a quick turn, the back with Gary's sticker"""
    u = t - s["t"]
    img = table_backdrop().copy()
    push = 1.0 + 0.04 * ease(u / max(0.1, s["end"] - s["t"]))
    f = ease((u - 0.55) / 0.2)                            # 0 front .. 1 back
    sx = math.cos(math.pi * f)
    rot = 4.0 - 6.0 * f + 1.2 * math.sin(u * 3.1)         # a little nervous movement in the hands
    img = _reader(img, "micah", READY, sx, rot, push)
    return G.grade(img, "insert", t)


def reader_charge(s, t):
    """Pep's view: REGISTER GUEST on the reader in his hand; his phone comes in and taps it (the screen flashes)
    and goes; 115 APPEALS, £2,298.85"""
    u = t - s["t"]
    tap = m("tap") - s["t"]
    img = table_backdrop().copy()
    push = 1.0 + 0.05 * ease(u / max(0.1, s["end"] - s["t"]))
    screen = GUEST if u < tap else FLASH if u < tap + 0.07 else CHARGED      # the screen flashes on the tap
    img = _reader(img, "pep", screen, 1.0, -3.0 + 0.8 * math.sin(u * 2.3), push)
    # the phone: in from the bottom right, a tap on the reader's lower half, away again
    hb, dev, hf, (x0, y0, x1, y1) = held("phone", "pep", mirror=True)
    lay = _stack(hb, dev, hf)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rest = (OW * 0.80, OH * 1.30)
    touch = (READER_AT[0] + 150 * RS, READER_AT[1] + 330 * RS)
    if u < tap:
        e = ease((u - (tap - 0.62)) / 0.52, "out")
    else:
        e = 1 - ease((u - tap - 0.18) / 0.42)
    if e > 0:
        x = rest[0] + (touch[0] - rest[0]) * e
        y = rest[1] + (touch[1] - rest[1]) * e
        sc = 1.06 - 0.06 * max(0.0, 1 - abs(u - tap) / 0.12)    # pressed home on the tap
        img = _put(img, lay, (cx, cy), (x, y), rot=18 - 6 * e, scale=sc, shadow=e)
    return G.grade(img, "insert", t)
