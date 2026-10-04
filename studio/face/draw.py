"""Drawing a face: eyes (whites, gaze, lids), brows, the shared mouth and the moustache, with Skia, on a canvas
already transformed into the head drawing's pixel space.

Eyes and brows are vector shapes fitted to the kit's drawing (build.py), so they stay sharp in a close-up and
their lids can close inside the outline the way cartoon eyes do: the eye opening clips everything drawn in it
(white, pupil, highlight, lids), and its outline is drawn last, over the lid edges."""
import json
import math
from dataclasses import dataclass, field

import cv2
import numpy as np
import skia

from studio.face import mouth as mouths


def skimage(path):
    a = cv2.cvtColor(cv2.imread(str(path), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    return skia.Image.fromarray(np.ascontiguousarray(a), colorType=skia.kRGBA_8888_ColorType,
                                alphaType=skia.kUnpremul_AlphaType).withDefaultMipmaps()


SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)
CLOSED = 0.62          # where a shut eye's lid line sits, as a fraction of the eye's height from the top


@dataclass
class FaceState:
    blink: float = 0.0                 # upper lids: 0 open .. 1 shut
    squint: float = 0.0                # lower lids rising: 0 .. 1
    gaze: tuple = (0.0, 0.0)           # pupils: -1..1 (x right, y down), 0 = centred
    pupil: float = 1.0                 # pupil size
    brows: tuple = ((0.0, 0.0), (0.0, 0.0))   # per brow, screen left to right: (raise, tilt); tilt > 0 lifts the
    mouth: mouths.Mouth = field(default_factory=mouths.Mouth)  # inner end (worried), < 0 drops it (angry)


# expressions: brows, lids and the mouth's expression offsets; speech shapes add on top of the mouth part
EXPRESSIONS = {
    "neutral": dict(),
    "happy": dict(brows=(0.12, 4), squint=0.18, mouth=dict(smile=0.6)),
    "laughing": dict(brows=(0.2, 6), squint=0.45, mouth=dict(smile=0.9, wide=0.3)),
    "angry": dict(brows=(-0.3, -20), blink=0.12, mouth=dict(smile=-0.45)),
    "furious": dict(brows=(-0.4, -26), squint=0.2, mouth=dict(smile=-0.7, wide=0.2)),
    "sad": dict(brows=(0.05, 18), blink=0.22, mouth=dict(smile=-0.55)),
    "surprised": dict(brows=(0.55, 2), pupil=0.85, mouth=dict(round=0.3)),
    "skeptical": dict(brows_lr=((0.45, 0), (-0.15, -6)), mouth=dict(asym=0.45)),
    "worried": dict(brows=(0.28, 15), mouth=dict(smile=-0.3, wide=-0.1)),
    "smug": dict(brows=(-0.06, -5), blink=0.32, mouth=dict(asym=0.7, smile=0.25)),
    "deadpan": dict(blink=0.38, mouth=dict()),
    "confused": dict(brows_lr=((0.35, 10), (0.05, -4)), mouth=dict(asym=-0.3, smile=-0.15)),
}


def expression(name, mouth=None, **over):
    """FaceState for an expression; `mouth` is the speech shape it is applied to"""
    e = EXPRESSIONS.get(name, {})
    m = (mouth or mouths.Mouth()).plus(**e.get("mouth", {}))
    brows = e.get("brows_lr") or (e.get("brows", (0.0, 0.0)),) * 2
    st = FaceState(blink=e.get("blink", 0.0), squint=e.get("squint", 0.0), pupil=e.get("pupil", 1.0),
                   brows=tuple(tuple(b) for b in brows), mouth=m)
    for k, v in over.items():
        setattr(st, k, v)
    return st


def _colour(rgb, a=255):
    return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), a)


def _fill(rgb):
    return skia.Paint(AntiAlias=True, Color=_colour(rgb))


def _stroke(rgb, width):
    return skia.Paint(AntiAlias=True, Color=_colour(rgb), Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                      StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def smooth_path(pts):
    """closed curve through a polygon's edge midpoints, its corners as control points"""
    pts = [tuple(p) for p in pts]
    n = len(pts)
    mid = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    p = skia.Path()
    p.moveTo(*mid[-1])
    for i in range(n):
        p.quadTo(*pts[i], *mid[i])
    p.close()
    return p


class Face:
    """One view's face rig (from studio.face.build), ready to draw."""

    def __init__(self, face_dir):
        self.dir = face_dir
        self.f = json.loads((face_dir / "face.json").read_text())
        self.img = {}
        for k in ("static", "moustache"):
            if k in self.f:
                self.img[self.f[k]["file"]] = skimage(face_dir / self.f[k]["file"])
        self.skin = tuple(self.f["skin"])
        self.line = tuple(self.f["line"])
        self.line_width = float(self.f.get("line_width", 4.0))
        mw = self.f["mouth"]["width"]
        self.style = mouths.Style(line=self.line, weight=0.9 * self.line_width / mw)
        self.brow_paths = [smooth_path(b["path"]) for b in self.f["brows"]]
        eh = [2 * e["axes"][1] for e in self.f["eyes"]] or [30]
        self.eye_h = float(max(eh))

    def draw(self, canvas, st):
        for e in self.f["eyes"]:
            self._eye(canvas, e, st)
        for i, (b, path) in enumerate(zip(self.f["brows"], self.brow_paths)):
            raise_, tilt = st.brows[min(i, len(st.brows) - 1)] if len(self.f["brows"]) > 1 else st.brows[0]
            canvas.save()
            cx, cy = b["centre"]
            canvas.translate(cx, cy - raise_ * 0.35 * self.eye_h)
            canvas.rotate(-tilt if self._inner_is_right(i) else tilt)
            canvas.translate(-cx, -cy)
            canvas.drawPath(path, _fill(b["fill"]))
            if b["stroke"] > 0:
                canvas.drawPath(path, _stroke(self.line, b["stroke"]))
            canvas.restore()
        if "static" in self.f:
            s = self.f["static"]
            canvas.drawImage(self.img[s["file"]], *s["offset"], SAMPLING, skia.Paint(AntiAlias=True))
        self.draw_mouth(canvas, st.mouth)

    def _eye(self, canvas, e, st):
        (cx, cy), (rx, ry), ang = e["centre"], e["axes"], e["angle"]
        canvas.save()
        canvas.translate(cx, cy)
        canvas.rotate(ang)
        oval = skia.Path()
        oval.addOval(skia.Rect.MakeLTRB(-rx, -ry, rx, ry))
        canvas.save()
        canvas.clipPath(oval, skia.ClipOp.kIntersect, True)
        canvas.drawPaint(_fill((255, 255, 255)))
        if "pupil" in e:
            p = e["pupil"]
            # gaze is on screen; the eye may be tilted
            a = math.radians(-ang)
            gx = st.gaze[0] * math.cos(a) - st.gaze[1] * math.sin(a)
            gy = st.gaze[0] * math.sin(a) + st.gaze[1] * math.cos(a)
            px, py = gx * e["travel"][0], gy * e["travel"][1]
            prx, pry = p["axes"][0] * st.pupil, p["axes"][1] * st.pupil
            canvas.drawOval(skia.Rect.MakeLTRB(px - prx, py - pry, px + prx, py + pry), _fill(p["colour"]))
            for h in p["highlights"]:
                hx, hy = px + h["offset"][0] * prx, py + h["offset"][1] * pry
                r = h["r"] * pry
                canvas.drawOval(skia.Rect.MakeLTRB(hx - r, hy - r, hx + r, hy + r), _fill((255, 255, 255)))
        lw = e["outline"]
        # a closing eye: the upper lid comes down to just past half way, the lower lid rises to meet it for the
        # last stretch, so a shut eye is skin with the lid line across it
        b = min(1.0, max(0.0, st.blink))
        lower = 0.55 * min(1.0, max(0.0, st.squint))
        if b > 0.8:
            lower = max(lower, (1 - CLOSED) * (b - 0.8) / 0.2)
        if lower > 0.01:
            self._lid(canvas, rx, ry, lower, lw, upper=False)
        if b > 0.01:
            self._lid(canvas, rx, ry, CLOSED * b, lw, upper=True)
        canvas.restore()
        canvas.drawPath(oval, _stroke(self.line, lw))
        canvas.restore()

    def _lid(self, canvas, rx, ry, t, lw, upper):
        """skin over the eye from the top (or bottom) down to an edge curve t of the way across, and the lid's
        line along that edge; the caller clips to the eye. The edge sags a little at half-closed, like a lid."""
        n = 24
        xs = np.linspace(-rx * 1.02, rx * 1.02, n)
        half = ry * np.sqrt(np.clip(1 - (xs / rx) ** 2, 0, 1))
        sag = 0.6 * t * (1 - t) * ry * (1 - (xs / rx) ** 2)
        edge = (-half + t * 2 * half + sag) if upper else (half - t * 2 * half + 0.3 * sag)
        far = -ry * 1.5 if upper else ry * 1.5
        lid = skia.Path()
        lid.moveTo(xs[0], far)
        for x, y in zip(xs, edge):
            lid.lineTo(x, y)
        lid.lineTo(xs[-1], far)
        lid.close()
        canvas.drawPath(lid, _fill(self.skin))
        if upper or t < 1 - CLOSED - 0.01:
            ln = skia.Path()
            ln.moveTo(xs[0], edge[0])
            for x, y in zip(xs[1:], edge[1:]):
                ln.lineTo(x, y)
            canvas.drawPath(ln, _stroke(self.line, lw * (1.15 if upper else 0.9)))

    def draw_mouth(self, canvas, m):
        mo = self.f["mouth"]
        canvas.save()
        canvas.translate(*mo["centre"])
        canvas.rotate(mo["angle"])
        canvas.scale(mo["width"], mo["width"])
        if mo["kind"] == "profile":
            mouths.draw_profile(canvas, m, self.style)
        else:
            mouths.draw_front(canvas, m, self.style, squash=0.72 if mo["kind"] == "three_quarter" else 1.0)
        canvas.restore()
        if "moustache" in self.f:
            s = self.f["moustache"]
            canvas.drawImage(self.img[s["file"]], *s["offset"], SAMPLING, skia.Paint(AntiAlias=True))

    def _inner_is_right(self, i):
        """is this brow's inner end (towards the nose) its right-hand end on screen?"""
        if self.f["view"] == "side" or len(self.f["brows"]) == 1:
            return True                     # profile faces screen-right: the inner end is in front
        return i == 0                       # the screen-left brow's inner end is on its right
