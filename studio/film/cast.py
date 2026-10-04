"""The cast: every character drawing an episode uses, by "<character id>:<drawing>", with its face landmarks
(build/film/<id>/marks.json, from studio.film.art) and how it is sized and aimed on screen.

ed     = the eye distance used for sizing (sheet px): a shot asks for an eye distance in screen px, so every drawing
         of a character comes out the same size (three-quarter views count their foreshortened eyes as 85 %)
anchor = the point placed on screen (between the eyes)
look0  = gaze offset that makes the drawing look straight into the lens (a sheet's pupils may wander)
faces  = which way the drawing faces: F (front), L / R (towards the viewer's left / right), B (back)
hands  = where the hanging hands are: {R: [x, y, r], L: [x, y, r]} sheet px (R = the character's own right, on the
         viewer's left in a front view); found from the skin at the silhouette's outer edges, or film.yaml `hands`
feet   = the middle of the soles (sheet px): what a drawing stands on, squashes and sways about"""
import json

import numpy as np
import yaml

from studio.film.engine import Drawing
from studio.paths import BUILD, CHARACTERS


class Cast:
    def __init__(self):
        self.d, self.info, self._spec = {}, {}, {}

    def spec(self, cid):
        if cid not in self._spec:
            self._spec[cid] = yaml.safe_load((CHARACTERS / cid / "film.yaml").read_text())
        return self._spec[cid]

    def get(self, key):
        if key in self.d:
            return self.d[key], self.info[key]
        cid, name = key.split(":")
        sp = self.spec(cid)["drawings"][name]
        base = BUILD / "film" / cid
        meta = json.loads((base / "meta.json").read_text())[name]
        fm = json.loads((base / "marks.json").read_text())[name]
        path = base / f"{name}.png"
        faces = sp.get("faces", "F")
        if sp.get("plain") or not fm.get("eyes"):
            # no face to animate: sized by the head, placed by its centre
            x0, y0, x1, y1 = fm["head"]
            self.d[key] = Drawing(key, path, meta)
            self.info[key] = dict(anchor=((x0 + x1) / 2, (y0 + y1) / 2), ed=sp.get("ed", (x1 - x0) / 4.24),
                                  faces=faces, look0=(0.0, 0.0), feet=sp.get("feet"))
            return self.d[key], self.info[key]
        eyes = [tuple(e) for e in fm.get("eyes", [])]
        mouth = fm.get("mouth")
        self.d[key] = Drawing(key, path, meta, mouth=tuple(mouth) if mouth else None, chin=fm.get("chin"),
                              eyes=eyes, neck=tuple(fm["neck"]) if fm.get("neck") else None, head=tuple(fm["head"]),
                              facing="front" if faces in ("F", "L", "R") else "front", jaw=sp.get("jaw", 1.0),
                              brow_gain=sp.get("brow_gain", 1.0))
        em = np.mean([e[:2] for e in eyes], 0)
        ed = abs(eyes[1][0] - eyes[0][0]) if len(eyes) == 2 else (fm["head"][2] - fm["head"][0]) / 4.24
        if faces != "F" and len(eyes) == 2:
            ed /= 0.85
        ed = sp.get("ed", ed)
        self.info[key] = dict(anchor=(float(em[0]), float(em[1])), ed=float(ed), faces=faces,
                              look0=tuple(sp.get("look0", (0.0, 0.0))), feet=sp.get("feet"))
        return self.d[key], self.info[key]


def find_hands(d, info):
    """the hanging hands of a standing figure: the lowest skin at the outer edges of the silhouette, between 40 and
    80 % of its height -> {R: [x, y, r], L: [x, y, r]} sheet px"""
    import cv2
    im = d.u8[1.0]
    a = im[..., 3] > 128
    H, W = a.shape
    e = d.spec["eyes"][0]                                    # the skin: the cheek just under the first eye
    sx, sy = (int(v) for v in d.P(e[0], e[1] + 1.8 * e[3]))
    skin = np.median(im[sy - 5:sy + 5, sx - 5:sx + 5, :3].reshape(-1, 3).astype(np.float32), 0)
    sk = (np.abs(im[..., :3].astype(np.float32) - skin).max(2) < 48) & a
    rows = np.nonzero(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hf = bot - top
    out = {}
    for side in ("R", "L"):
        m = np.zeros_like(sk)
        for y in range(int(top + 0.40 * Hf), int(top + 0.80 * Hf)):
            xs = np.nonzero(a[y])[0]
            if len(xs):
                if side == "R":
                    m[y, xs.min():xs.min() + int(0.17 * W)] = True
                else:
                    m[y, max(0, xs.max() - int(0.17 * W)):xs.max() + 1] = True
        c = cv2.morphologyEx((sk & m).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(c, 8)
        big = [i for i in range(1, n) if st[i, 4] > 0.0004 * H * W]
        if not big:
            continue
        # the hands hang furthest out (the knees are further in); of the outermost blobs, the lowest is the hand
        # (a wristband splits a forearm from its hand)
        out_x = (lambda i: cen[i][0]) if side == "R" else (lambda i: -cen[i][0])
        edge = min(out_x(i) for i in big)
        near = [i for i in big if out_x(i) - edge < 0.06 * W]
        i = max(near, key=lambda i: st[i, 1] + st[i, 3])
        ys, xs = np.nonzero(lab == i)
        low = ys > ys.max() - 0.07 * Hf
        x, y = xs[low].mean(), ys[low].mean() - 0.015 * Hf
        out[side] = [float(x / d.S + d.ox), float(y / d.S + d.oy), float(0.045 * Hf / d.S)]
    return out


def find_feet(d):
    a = d.u8[1.0][..., 3] > 128
    ys, xs = np.nonzero(a)
    bot = ys.max()
    low = ys > bot - 0.02 * (bot - ys.min())
    return [float(xs[low].mean() / d.S + d.ox), float(bot / d.S + d.oy)]


def hands(key):
    """the hands of a drawing (cached): film.yaml `hands`, or found"""
    d, info = CAST.get(key)
    if "hands" not in info:
        cid, name = key.split(":")
        sp = CAST.spec(cid)["drawings"][name]
        info["hands"] = sp.get("hands") or find_hands(d, info)
    return info["hands"]


def feet(key):
    d, info = CAST.get(key)
    if not info.get("feet"):
        info["feet"] = find_feet(d)
    return info["feet"]


CAST = Cast()
