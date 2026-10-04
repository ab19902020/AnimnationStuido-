"""The shared mouth library: one parametric cartoon mouth, drawn as vectors in the house style (bold outline,
dark interior, white teeth, tongue), and the mouth shapes lip sync uses as presets of it.

Like South Park's mouth library, every character uses the same shapes; each character only sets the size, the
line colour and where the mouth sits on the face. Parameters (all 0..1 unless noted):
    open    how far the lips part               wide   -1 (pursed) .. +1 (stretched)
    round   O-shape (pursing)                    smile  -1 (frown) .. +1 (smile), the corners
    teeth   upper teeth showing                  lower  lower teeth showing
    tongue  tongue showing (raise > 0 lifts it behind the upper teeth, for L and TH)
    fv      lower lip tucked under the upper teeth (F, V)
    asym    -1..1 one corner up (a smirk)
Shapes are drawn in mouth space: centre (0, 0), width 1 corner to corner, y down; the caller scales and places."""
from dataclasses import dataclass, replace

import numpy as np
import skia

# Rhubarb Lip Sync's shapes (A-H, X) plus a few for expressions
SHAPES = {
    "X": dict(),                                                        # rest
    "A": dict(wide=0.06, press=1.0),                                    # M B P: lips pressed together
    "B": dict(open=0.16, wide=0.18, teeth=1.0, lower=1.0),              # K S T EE: teeth together, slightly open
    "C": dict(open=0.42, wide=0.18, teeth=1.0, lower=0.45, tongue=0.3), # EH AE: open
    "D": dict(open=0.82, wide=0.08, teeth=1.0, lower=0.3, tongue=0.65), # AA: wide open
    "E": dict(open=0.48, wide=-0.22, round=0.45, teeth=0.6, tongue=0.35),  # AO ER: rounded
    "F": dict(open=0.26, wide=-0.62, round=1.0),                        # UW OW W: puckered
    "G": dict(open=0.1, wide=0.1, fv=1.0, teeth=1.0),                   # F V: upper teeth on the lower lip
    "H": dict(open=0.5, wide=0.04, teeth=1.0, tongue=1.0, raise_=1.0),  # L: tongue behind the upper teeth
    # expressions
    "smile": dict(smile=0.8, wide=0.25),
    "grin": dict(open=0.3, smile=0.9, wide=0.5, teeth=1.0, lower=1.0),
    "frown": dict(smile=-0.75, wide=-0.05),
    "shout": dict(open=1.0, wide=0.2, teeth=1.0, lower=0.6, tongue=0.7),
    "o": dict(open=0.7, round=1.0, wide=-0.4, tongue=0.4),
    "smirk": dict(asym=0.8, wide=0.1),
}


@dataclass
class Mouth:
    open: float = 0.0
    wide: float = 0.0
    round: float = 0.0
    smile: float = 0.0
    teeth: float = 0.0
    lower: float = 0.0
    tongue: float = 0.0
    raise_: float = 0.0
    fv: float = 0.0
    press: float = 0.0
    asym: float = 0.0

    def mix(self, other, t):
        """blend towards another mouth (t = 0..1): used for the one-frame in-between of the smooth style"""
        return Mouth(**{k: getattr(self, k) + (getattr(other, k) - getattr(self, k)) * t
                        for k in self.__dataclass_fields__})

    def plus(self, **kw):
        """add expression offsets (smile, asym, wide) on top of a speech shape"""
        return replace(self, **{k: getattr(self, k) + v for k, v in kw.items()})


def shape(name, **expr):
    m = Mouth(**SHAPES.get(name, {}))
    return m.plus(**expr) if expr else m


@dataclass
class Style:
    line: tuple = (26, 18, 16)          # outline colour (from the character's own linework)
    inside: tuple = (66, 16, 22)
    tongue: tuple = (205, 92, 96)
    teeth: tuple = (250, 247, 240)
    weight: float = 0.05               # line width as a fraction of the mouth width (set per face from its
                                       # own line weight)


def _c(rgb, a=255):
    return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), a)


def _paint(rgb, stroke=None):
    p = skia.Paint(AntiAlias=True, Color=_c(rgb))
    if stroke is not None:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def _cubic(p0, p1, p2, p3, n=24):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def _tapered(canvas, pts, width, rgb, ends=0.45):
    """a filled stroke along pts: full width in the middle, `ends` of it at the round tips"""
    d = np.gradient(pts, axis=0)
    d /= np.maximum(1e-9, np.linalg.norm(d, axis=1, keepdims=True))
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    s = np.linspace(0, 1, len(pts))
    half = 0.5 * width * (ends + (1 - ends) * np.sin(np.pi * s))[:, None]
    side_a, side_b = pts + nrm * half, pts - nrm * half
    p = skia.Path()
    p.moveTo(*side_a[0])
    for q in side_a[1:]:
        p.lineTo(*q)
    for q in side_b[::-1]:
        p.lineTo(*q)
    p.close()
    paint = _paint(rgb)
    canvas.drawPath(p, paint)
    for q in (pts[0], pts[-1]):
        canvas.drawCircle(float(q[0]), float(q[1]), 0.5 * width * ends, paint)


def _geometry(m):
    """corner positions and lip curve controls of the front-view mouth (width 1)"""
    hw = 0.5 * (1 + 0.22 * m.wide) * (1 - 0.42 * m.round)
    lift = -0.13 * m.smile                    # corners up for a smile
    cr = lift - 0.12 * max(0.0, m.asym) + 0.06 * max(0.0, -m.asym)     # asym > 0 lifts the right corner
    cl = lift - 0.12 * max(0.0, -m.asym) + 0.06 * max(0.0, m.asym)
    o = max(0.0, m.open)
    top = -0.06 * o - 0.03 * m.round * o      # the upper lip lifts a little
    bot = 0.06 + 0.5 * o + 0.12 * m.round * o  # the jaw drops
    sag = 0.035 + 0.03 * max(0.0, m.smile)    # a closed mouth bows down in the middle (more when smiling)
    return hw, cl, cr, top, bot, sag


def draw_front(canvas, m, style, squash=1.0):
    """Draw a front (squash=1) or three-quarter (squash < 1: the far half narrower) mouth at the origin, width 1."""
    hw, cl, cr, top, bot, sag = _geometry(m)
    L, R = (-hw * squash, cl), (hw, cr)
    lw = style.weight
    if m.open < 0.05 and m.fv < 0.5:
        # closed: one bowed line, tapered to its corners like an ink stroke, heavier when the lips press (M B P)
        dip = sag + 0.02 * m.press
        _tapered(canvas, _cubic(L, (L[0] * 0.45, dip), (R[0] * 0.45, dip), R), lw * (1.15 + 0.4 * m.press),
                 style.line)
        return
    # the opening: upper lip curve over the top, lower lip curve under, joined at the corners
    rnd = m.round
    opening = skia.Path()
    opening.moveTo(*L)
    opening.cubicTo(L[0] * (0.55 - 0.3 * rnd), top - 0.02, R[0] * (0.55 - 0.3 * rnd), top - 0.02, *R)
    opening.cubicTo(R[0] * (0.75 - 0.25 * rnd), bot + 0.02, L[0] * (0.75 - 0.25 * rnd), bot + 0.02, *L)
    opening.close()
    canvas.save()
    canvas.clipPath(opening, skia.ClipOp.kIntersect, True)
    canvas.drawPaint(_paint(style.inside))
    h = bot - top
    if m.tongue > 0.02:
        if m.raise_ < 0.5:      # resting on the floor of the mouth, rising into view as the jaw opens
            ty = bot - 0.42 * h * m.tongue
            tongue = skia.Rect.MakeLTRB(L[0] * 0.62, ty, R[0] * 0.62, bot + 0.35 * h)
        else:                   # the tip lifted behind the upper teeth (L, TH)
            ty = top + 0.12 * h
            tongue = skia.Rect.MakeLTRB(L[0] * 0.4, ty, R[0] * 0.4, ty + 0.38 * h)
        canvas.drawOval(tongue, _paint(style.tongue))
    if m.teeth > 0.02:
        th = min(0.16, 0.35 * h + 0.05) * m.teeth
        canvas.drawRect(skia.Rect.MakeLTRB(-1, top - 0.05, 1, top + th), _paint(style.teeth))
    if m.lower > 0.02:
        bh = min(0.12, 0.25 * h + 0.04) * m.lower
        canvas.drawRect(skia.Rect.MakeLTRB(-1, bot - bh, 1, bot + 0.05), _paint(style.teeth))
    canvas.restore()
    if m.fv > 0.5:
        # F/V: the lower lip rolls in under the upper teeth - a lip line across the teeth
        lip = skia.Path()
        lip.moveTo(L[0] * 0.8, bot * 0.6)
        lip.quadTo(0, bot * 0.6 + 0.06, R[0] * 0.8, bot * 0.6)
        canvas.drawPath(lip, _paint(style.line, lw * 0.8))
    canvas.drawPath(opening, _paint(style.line, lw))


def draw_profile(canvas, m, style):
    """Draw a profile mouth facing screen-right: the lips at the origin (the front of the face), the corner back
    at x = -width/2."""
    hw, cl, cr, top, bot, sag = _geometry(m)
    depth = 0.55 * (1 + 0.15 * m.wide) * (1 - 0.35 * m.round)
    corner = (-depth, 0.5 * (cl + cr))
    lw = style.weight * 1.1
    if m.open < 0.05 and m.fv < 0.5:
        lips, ctrl = (0.02, 0.0), (-depth * 0.5, sag * 0.8)
        _tapered(canvas, _cubic(lips, ctrl, ctrl, corner), lw * (1.1 + 0.4 * m.press), style.line, ends=0.6)
        return
    # the front of the opening is the face's own edge: it stays on the profile line (rounded lips push out a
    # touch), the jaw dropping below it
    front = 0.02 + 0.05 * m.round
    o = skia.Path()
    o.moveTo(*corner)
    o.quadTo(-depth * 0.35, top - 0.02, front, top + 0.02)
    o.quadTo(front + 0.02, (top + bot) / 2, front - 0.03, bot)
    o.quadTo(-depth * 0.45, bot + 0.02, *corner)
    o.close()
    canvas.save()
    canvas.clipPath(o, skia.ClipOp.kIntersect, True)
    canvas.drawPaint(_paint(style.inside))
    h = bot - top
    if m.tongue > 0.02 and m.raise_ < 0.5:
        canvas.drawOval(skia.Rect.MakeLTRB(-depth * 0.8, bot - 0.3 * h * m.tongue, 0.05, bot + 0.3 * h),
                        _paint(style.tongue))
    if m.teeth > 0.02:
        canvas.drawRect(skia.Rect.MakeLTRB(-depth * 0.7, top - 0.05, 0.2, top + min(0.15, 0.35 * h + 0.05)),
                        _paint(style.teeth))
    canvas.restore()
    canvas.drawPath(o, _paint(style.line, lw))
