"""The cast: every character drawing an episode uses, by "<character id>:<drawing>", with its face landmarks
(build/film/<id>/marks.json, from studio.film.art) and how it is sized and aimed on screen.

ed     = the eye distance used for sizing (sheet px): a shot asks for an eye distance in screen px, so every drawing
         of a character comes out the same size (three-quarter views count their foreshortened eyes as 85 %)
anchor = the point placed on screen (between the eyes)
look0  = gaze offset that makes the drawing look straight into the lens (a sheet's pupils may wander)
faces  = which way the drawing faces: F (front), L / R (towards the viewer's left / right), B (back)"""
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


CAST = Cast()
