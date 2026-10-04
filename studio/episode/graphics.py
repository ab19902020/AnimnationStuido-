"""Set dressing and insert cards for animatics, drawn in the studio's bold-outline cartoon style.

    sprite = PROPS["bench"]()                  # a Prop: premultiplied BGRA at SS pixels per plate pixel, plus its anchor
    card = INSERTS["reader_total"](1920, 1080) # a full-frame BGR card

Props are drawn in the background plate's own units (1 plate pixel = SS sprite pixels) so they scale with the camera
like the set does. The anchor is the point of the prop that sits on the floor (or where it hangs). Everything is
plain shapes and lettering: stand-ins that carry the story points (the fee sign, the reader's total, the pass, the
refund, the sponsor line) clearly; final props are drawn to the kit's style.

Fonts are the system's Liberation Sans Bold / DejaVu Sans Bold."""
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS = 3                                                  # sprite pixels per plate pixel
INK = (24, 18, 18)
PAPER = (244, 246, 250)
TAPE = (170, 190, 200)
FONT_FILES = ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(px):
    for f in FONT_FILES:
        try:
            return ImageFont.truetype(f, int(px))
        except OSError:
            continue
    return ImageFont.load_default()


@dataclass
class Prop:
    img: np.ndarray            # premultiplied BGRA uint8
    ax: float                  # anchor, in sprite pixels from the top-left
    ay: float


def canvas(w, h):
    """a transparent drawing surface of w x h plate pixels (RGBA PIL image, SS times larger)"""
    im = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def finish(im, ax, ay):
    a = np.asarray(im).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255
    bgra = np.dstack([a[..., 2], a[..., 1], a[..., 0], a[..., 3]])
    return Prop(np.clip(bgra, 0, 255).astype(np.uint8), ax * SS, ay * SS)


def rrect(d, box, r, fill, outline=INK, width=3):
    s = lambda v: [x * SS for x in v]
    d.rounded_rectangle(s(box), radius=r * SS, fill=fill, outline=outline, width=int(width * SS))


def text_c(d, xy, s, px, fill=INK, anchor="mm"):
    d.text((xy[0] * SS, xy[1] * SS), s, font=font(px * SS), fill=fill, anchor=anchor)


def shadow(d, cx, cy, w, h, a=70):
    d.ellipse([(cx - w / 2) * SS, (cy - h / 2) * SS, (cx + w / 2) * SS, (cy + h / 2) * SS], fill=(0, 0, 0, a))


# ------------------------------------------------------------------------------------------- props
def fee_sign(extra=None):
    """the badly taped sign: the department's name and its two prices. extra: a strip taped across it ("JUNIOR HEARING")"""
    w, h = 330, 215
    drop = 46 if extra else 0                                           # room for the strip taped under the sign
    im, d = canvas(w + 40, h + 40 + drop)
    ox, oy = 20, 20
    rrect(d, (ox, oy, ox + w, oy + h), 6, PAPER)
    text_c(d, (ox + w / 2, oy + 46), "THE APPEALS", 46, (150, 30, 40))
    text_c(d, (ox + w / 2, oy + 90), "DEPARTMENT", 46, (150, 30, 40))
    d.line([(ox + 24) * SS, (oy + 120) * SS, (ox + w - 24) * SS, (oy + 120) * SS], fill=INK, width=3 * SS)
    text_c(d, (ox + w / 2, oy + 148), "£19.99 PER APPEAL", 32)
    text_c(d, (ox + w / 2, oy + 187), "UNDER-14s GO FREE", 32, (20, 110, 50))
    for tx, ty, ang in ((ox + 14, oy + 2, 18), (ox + w - 46, oy + 4, -22), (ox + 10, oy + h - 10, -20), (ox + w - 40, oy + h - 14, 24)):
        t = Image.new("RGBA", (60 * SS, 20 * SS), (0, 0, 0, 0))
        ImageDraw.Draw(t).rectangle([0, 0, 60 * SS, 20 * SS], fill=(*TAPE, 190), outline=(110, 130, 140, 220), width=SS)
        im.alpha_composite(t.rotate(ang, expand=True, resample=Image.BICUBIC), (int((tx - 8) * SS), int((ty - 8) * SS)))
    if extra:                                                           # a strip taped under it: the prices stay readable
        rrect(d, (ox + 6, oy + h + 6, ox + w - 6, oy + h + 44), 4, (255, 224, 90))
        text_c(d, (ox + w / 2, oy + h + 25), extra, 30)
        for tx in (ox + 18, ox + w - 48):
            t = Image.new("RGBA", (30 * SS, 14 * SS), (*TAPE, 190))
            im.alpha_composite(t.rotate(8, expand=True, resample=Image.BICUBIC), (int(tx * SS), int((oy + h - 2) * SS)))
    im = im.rotate(-3.5, expand=True, resample=Image.BICUBIC)
    return finish(im, im.width / SS / 2, im.height / SS / 2)


def card_reader(screen="REGISTER GUEST", size=1.0):
    w, h = 44 * size, 74 * size
    im, d = canvas(w + 10, h + 10)
    rrect(d, (5, 5, 5 + w, 5 + h), 7 * size, (46, 50, 58))
    rrect(d, (5 + 5 * size, 5 + 8 * size, 5 + w - 5 * size, 5 + 30 * size), 3, (160, 235, 190), width=2)
    for r in range(3):
        for c in range(3):
            d.ellipse([(5 + (9 + c * 12) * size - 3) * SS, (5 + (40 + r * 10) * size - 3) * SS,
                       (5 + (9 + c * 12) * size + 3) * SS, (5 + (40 + r * 10) * size + 3) * SS], fill=(190, 196, 206))
    return finish(im, 5 + w / 2, 5 + h / 2)


def printer():
    w, h = 150, 84
    im, d = canvas(w + 20, h + 40)
    shadow(d, 10 + w / 2, 10 + h + 12, w * 0.95, 14)
    rrect(d, (10, 22, 10 + w, 10 + h), 8, (214, 218, 224))
    rrect(d, (26, 8, 10 + w - 26, 34), 4, (240, 242, 246))             # the paper tray
    rrect(d, (26, 54, 10 + w - 26, 66), 3, (60, 64, 72))                # the slot
    d.ellipse([(10 + w - 24) * SS, 40 * SS, (10 + w - 14) * SS, 50 * SS], fill=(90, 220, 120), outline=INK, width=SS)
    return finish(im, 10 + w / 2, 10 + h)


def bench():
    w, h = 300, 74
    im, d = canvas(w + 20, h + 30)
    shadow(d, 10 + w / 2, 10 + h + 12, w, 16)
    rrect(d, (10, 10, 10 + w, 32), 5, (176, 118, 66))
    for x in (30, w - 20):
        rrect(d, (10 + x, 30, 10 + x + 16, 10 + h), 3, (140, 92, 52))
    d.line([(14) * SS, 20 * SS, (6 + w) * SS, 20 * SS], fill=(214, 160, 104), width=2 * SS)
    return finish(im, 10 + w / 2, 10 + h)


def chair():
    w, h = 74, 118
    im, d = canvas(w + 20, h + 20)
    shadow(d, 10 + w / 2, 10 + h + 4, w, 10)
    rrect(d, (14, 10, 10 + w - 4, 62), 5, (120, 126, 140))               # the back
    rrect(d, (10, 58, 10 + w, 72), 4, (150, 156, 170))                   # the seat
    for x in (14, w - 4):
        d.rectangle([(10 + x) * SS, 70 * SS, (10 + x + 6) * SS, (10 + h) * SS], fill=(70, 74, 84), outline=INK, width=SS)
    return finish(im, 10 + w / 2, 10 + h)


def suitcase():
    w, h = 78, 118
    im, d = canvas(w + 40, h + 50)
    shadow(d, 20 + w / 2, 20 + h + 18, w * 1.1, 12)
    d.line([(20 + w / 2) * SS, 20 * SS, (20 + w / 2) * SS, -2 * SS + 20 * SS], fill=INK)
    rrect(d, (20 + w / 2 - 24, 4, 20 + w / 2 + 24, 24), 5, (60, 62, 70))      # the handle
    rrect(d, (20, 22, 20 + w, 20 + h), 9, (176, 36, 52))
    for y in (50, 90):
        d.line([(20 + 8) * SS, y * SS, (20 + w - 8) * SS, y * SS], fill=(120, 20, 34), width=3 * SS)
    for x in (20 + 14, 20 + w - 14):
        d.ellipse([(x - 8) * SS, (20 + h - 2) * SS, (x + 8) * SS, (20 + h + 14) * SS], fill=(50, 50, 56), outline=INK, width=2 * SS)
    return finish(im, 20 + w / 2, 20 + h + 14)


def curtain(width=560, height=900):
    im, d = canvas(width, height)
    n = 9
    for i in range(n):
        shade = 70 + (i % 2) * 22
        d.rectangle([(i * width / n) * SS, 14 * SS, ((i + 1) * width / n) * SS, height * SS], fill=(shade, shade + 30, 110 + (i % 2) * 20, 255),
                    outline=(30, 40, 80, 255), width=2 * SS)
    d.rectangle([0, 0, width * SS, 16 * SS], fill=(60, 62, 70, 255), outline=INK, width=2 * SS)
    for i in range(0, n + 1):
        d.ellipse([(i * width / n - 7) * SS, 2 * SS, (i * width / n + 7) * SS, 22 * SS], fill=(190, 192, 200, 255), outline=INK, width=2 * SS)
    return finish(im, width / 2, 0)


def paper_strip(length, y_off=0):
    """a long strip of continuous forms lying on the floor, `length` plate pixels, drawn flat"""
    h = 22
    im, d = canvas(length, h + 10)
    pts = [(0, 5), (length, 5), (length, 5 + h), (0, 5 + h)]
    d.polygon([(x * SS, y * SS) for x, y in pts], fill=(250, 250, 252), outline=INK)
    for x in range(0, int(length), 46):
        d.line([x * SS, 5 * SS, x * SS, (5 + h) * SS], fill=(120, 130, 150), width=SS)
    for x in range(8, int(length), 46):
        d.line([x * SS, 12 * SS, (x + 26) * SS, 12 * SS], fill=(150, 160, 175), width=SS)
        d.line([x * SS, 19 * SS, (x + 18) * SS, 19 * SS], fill=(150, 160, 175), width=SS)
    return finish(im, 0, 5 + h / 2)


def forms_pile():
    im, d = canvas(120, 80)
    rng = np.random.default_rng(3)
    for i in range(8):
        w, h = 74, 52
        t = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        td = ImageDraw.Draw(t)
        td.rectangle([0, 0, w * SS, h * SS], fill=(250, 250, 252, 255), outline=(*INK, 255), width=SS)
        for y in (12, 22, 32):
            td.line([8 * SS, y * SS, (w - 10) * SS, y * SS], fill=(150, 160, 175, 255), width=SS)
        t = t.rotate(float(rng.uniform(-35, 35)), expand=True, resample=Image.BICUBIC)
        im.alpha_composite(t, (int((20 + rng.uniform(0, 20)) * SS), int((10 + rng.uniform(0, 12)) * SS)))
    return finish(im, 60, 60)


def pass_card(title, sub, w=92):
    h = 56
    im, d = canvas(w + 8, h + 8)
    rrect(d, (4, 4, 4 + w, 4 + h), 4, (252, 252, 255), width=2)
    d.rectangle([4 * SS, 4 * SS, (4 + w) * SS, (4 + 15) * SS], fill=(170, 28, 40, 255), outline=INK, width=2 * SS)
    text_c(d, (4 + w / 2, 4 + 8), "JUNIOR PASS", 10, (255, 255, 255))
    text_c(d, (4 + w / 2, 4 + 31), title, 15 if len(title) < 10 else 11)
    text_c(d, (4 + w / 2, 4 + 47), sub, 11, (170, 28, 40))
    return finish(im, 4 + w / 2, 4 + h / 2)


def clipboard():
    im, d = canvas(60, 84)
    rrect(d, (6, 8, 54, 80), 4, (170, 120, 70))
    rrect(d, (10, 16, 50, 74), 2, PAPER, width=2)
    rrect(d, (20, 4, 40, 16), 3, (130, 134, 144), width=2)
    for y in (28, 38, 48, 58):
        d.line([15 * SS, y * SS, 45 * SS, y * SS], fill=(150, 160, 175), width=SS)
    return finish(im, 30, 42)


def mug():
    im, d = canvas(40, 40)
    rrect(d, (6, 8, 28, 34), 4, (250, 250, 252), width=2)
    d.arc([22 * SS, 12 * SS, 38 * SS, 28 * SS], 270, 90, fill=INK, width=3 * SS)
    d.ellipse([7 * SS, 8 * SS, 27 * SS, 14 * SS], fill=(70, 50, 40, 255), outline=INK, width=2 * SS)
    return finish(im, 17, 21)


def phone(screen=(60, 70, 90)):
    im, d = canvas(30, 52)
    rrect(d, (4, 4, 26, 48), 4, (30, 32, 38), width=2)
    rrect(d, (7, 8, 23, 42), 2, screen, width=1)
    return finish(im, 15, 26)


def notice(text):
    """a lit plaque on the wall (ON AIR, then PRIVATE HEARING)"""
    w, h = 130, 56
    im, d = canvas(w + 8, h + 8)
    rrect(d, (4, 4, 4 + w, 4 + h), 5, (255, 232, 120))
    lines = text.split("\n")
    for i, s in enumerate(lines):
        text_c(d, (4 + w / 2, 4 + h * (i + 1) / (len(lines) + 1)), s, 22 if len(lines) > 1 else 24)
    return finish(im, 4 + w / 2, 4 + h / 2)


PROPS = dict(fee_sign=fee_sign, card_reader=card_reader, printer=printer, bench=bench, chair=chair, suitcase=suitcase,
             curtain=curtain, paper_strip=paper_strip, forms_pile=forms_pile, pass_card=pass_card, clipboard=clipboard,
             mug=mug, phone=phone, notice=notice)


# ------------------------------------------------------------------------------------------ inserts
def _card(w, h, bg=(24, 22, 30)):
    img = Image.new("RGB", (w, h), (bg[2], bg[1], bg[0]))
    return img, ImageDraw.Draw(img)


def _tx(d, xy, s, px, fill=(255, 255, 255), anchor="mm"):
    d.multiline_text(xy, s, font=font(px), fill=fill, anchor=anchor, align="center", spacing=int(px * 0.12))


def _bgr(img):
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def _device(d, w, h, lines, glow=(150, 240, 190), screen=0.5):
    """a big card reader filling the middle of the frame; returns its screen box"""
    dw, dh = int(h * 0.62), int(h * 0.88)
    x0, y0 = w // 2 - dw // 2, h // 2 - dh // 2
    d.rounded_rectangle([x0, y0, x0 + dw, y0 + dh], radius=34, fill=(46, 50, 58), outline=(10, 10, 14), width=6)
    sx0, sy0, sx1, sy1 = x0 + 34, y0 + 40, x0 + dw - 34, y0 + int(dh * screen)
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=14, fill=glow, outline=(10, 40, 24), width=5)
    for r in range(3):
        for c in range(3):
            cx, cy = x0 + dw * (0.26 + 0.24 * c), y0 + dh * (0.69 + 0.09 * r)
            d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(190, 196, 206), outline=(10, 10, 14), width=3)
    return (sx0, sy0, sx1, sy1)


def reader_register(w, h):
    img, d = _card(w, h)
    sx0, sy0, sx1, sy1 = _device(d, w, h, [])
    _tx(d, ((sx0 + sx1) / 2, (sy0 + sy1) / 2), "REGISTER\nGUEST", 56, (12, 50, 30))
    return _bgr(img)


def reader_total(w, h):
    img, d = _card(w, h)
    sx0, sy0, sx1, sy1 = _device(d, w, h, [])
    cx = (sx0 + sx1) / 2
    _tx(d, (cx, sy0 + (sy1 - sy0) * 0.28), "115 APPEALS", 48, (12, 50, 30))
    _tx(d, (cx, sy0 + (sy1 - sy0) * 0.72), "£2,298.85", 72, (12, 50, 30))
    return _bgr(img)


def reader_plus(w, h):
    img, d = _card(w, h)
    sx0, sy0, sx1, sy1 = _device(d, w, h, [])
    cx = (sx0 + sx1) / 2
    _tx(d, (cx, sy0 + (sy1 - sy0) * 0.3), "+£19.99", 84, (12, 50, 30))
    _tx(d, (cx, sy0 + (sy1 - sy0) * 0.74), "116 PAID APPEALS", 38, (12, 50, 30))
    return _bgr(img)


def refund(w, h):
    img, d = _card(w, h)
    sx0, sy0, sx1, sy1 = _device(d, w, h, [], screen=0.6)
    cx, sh = (sx0 + sx1) / 2, sy1 - sy0
    _tx(d, (cx, sy0 + sh * 0.14), "PEP: CHILD", 34, (12, 50, 30))
    _tx(d, (cx, sy0 + sh * 0.30), "CRISTIANO: CHILD", 34, (12, 50, 30))
    _tx(d, (cx, sy0 + sh * 0.55), "REFUND DUE", 46, (120, 20, 20))
    _tx(d, (cx, sy0 + sh * 0.80), "£2,318.84", 76, (120, 20, 20))
    return _bgr(img)


def scoreboard(w, h):
    img, d = _card(w, h, (14, 24, 44))
    d.rounded_rectangle([w * 0.1, h * 0.22, w * 0.9, h * 0.78], radius=30, fill=(10, 14, 24), outline=(240, 240, 250), width=8)
    _tx(d, (w / 2, h * 0.31), "FULL TIME", 50, (250, 210, 80))
    _tx(d, (w * 0.3, h * 0.47), "CROATIA", 84)
    _tx(d, (w * 0.7, h * 0.47), "ENGLAND", 84)
    _tx(d, (w * 0.3, h * 0.65), "0", 170, (250, 210, 80))
    _tx(d, (w * 0.5, h * 0.65), "—", 120, (250, 250, 252))
    _tx(d, (w * 0.7, h * 0.65), "7", 170, (250, 210, 80))
    return _bgr(img)


def notice_private(w, h):
    img, d = _card(w, h, (60, 54, 40))
    d.rounded_rectangle([w * 0.18, h * 0.3, w * 0.82, h * 0.7], radius=26, fill=(255, 232, 120), outline=(20, 16, 16), width=10)
    _tx(d, (w / 2, h * 0.5), "PRIVATE\nHEARING", 130, (24, 18, 18))
    return _bgr(img)


def badge_cris(w, h):
    img, d = _card(w, h, (40, 30, 34))
    d.rounded_rectangle([w * 0.2, h * 0.24, w * 0.8, h * 0.76], radius=22, fill=(252, 252, 255), outline=(20, 16, 16), width=10)
    d.rectangle([w * 0.2 + 5, h * 0.24 + 5, w * 0.8 - 5, h * 0.24 + h * 0.13], fill=(170, 28, 40))
    _tx(d, (w / 2, h * 0.24 + h * 0.065), "JUNIOR PASS", 54, (255, 255, 255))
    _tx(d, (w / 2, h * 0.5), "LITTLE CRIS", 120, (24, 18, 18))
    _tx(d, (w / 2, h * 0.66), "AGE 7", 90, (170, 28, 40))
    return _bgr(img)


def sponsor(w, h):
    img, d = _card(w, h, (50, 48, 52))
    d.rounded_rectangle([w * 0.16, h * 0.14, w * 0.84, h * 0.86], radius=20, fill=(250, 250, 252), outline=(20, 16, 16), width=8)
    d.rectangle([w * 0.2, h * 0.2, w * 0.8, h * 0.4], fill=(240, 232, 214), outline=(20, 16, 16), width=5)
    _tx(d, (w / 2, h * 0.3), "GARY NEVILLE'S\nAPPEALS DEPARTMENT", 58, (150, 30, 40))
    d.line([w * 0.2, h * 0.5, w * 0.8, h * 0.5], fill=(150, 160, 175), width=5)
    for y in (0.57, 0.64):
        d.line([w * 0.2, h * y, w * 0.74, h * y], fill=(190, 198, 210), width=6)
    _tx(d, (w / 2, h * 0.76), "PRINTER LEASE —\nPAYABLE BY SPONSOR", 60, (20, 20, 24))
    return _bgr(img)


def end_card(w, h):
    img, d = _card(w, h, (10, 10, 14))
    _tx(d, (w / 2, h * 0.42), "END", 220, (250, 250, 252))
    _tx(d, (w / 2, h * 0.62), "UNITED ROAD — THE APPEALS DEPARTMENT", 46, (190, 190, 200))
    _tx(d, (w / 2, h * 0.9), "TEST RUN: TEXT-TO-SPEECH VOICES, NOT THE FINAL PERFORMANCES", 32, (160, 160, 170))
    return _bgr(img)


INSERTS = dict(reader_register=reader_register, reader_total=reader_total, reader_plus=reader_plus, refund=refund,
               scoreboard=scoreboard, notice_private=notice_private, badge_cris=badge_cris, sponsor=sponsor, end_card=end_card)
