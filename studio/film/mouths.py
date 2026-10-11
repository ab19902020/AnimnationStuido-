"""A character's drawn mouths (the "mouth / phoneme set" on a model sheet) as a lip-sync bank: each mouth shape is cut
out of the sheet (upscaled 4x, the lips and what is inside them, no skin), so the lip sync shows mouths drawn in the
character's own style instead of an opening painted onto the face. This is how Pass Mic's engine animated mouths.

film.yaml (top level):

    mouths:
      sheet: reference/model-sheet.png
      rest: [cx, cy, width, chin]     # the closed mouth's line centre, its width and the line-to-chin distance
      cells:                          # each mouth: its box, and where that cell's closed mouth line would be (the
        a: {box: [x0, y0, x1, y1], ref: [x, y]}   #  same point under the nose in every cell)
        ...

and a drawing opts in with `mouth_bank: true` (optionally `bank_scale`). Visemes map to cells (BANK_OF); closed shapes
(REST, MBP, BREATH) keep the drawing's own mouth.

    python3 -m studio.film.mouths CHARACTER     -> build/film/<id>/mouths/<cell>.png, mouths.json, mouths_check.jpg"""
import json
import sys

import cv2
import numpy as np
import yaml

from studio.paths import CHARACTERS, build_dir

# viseme -> bank cell (None: the drawing's own closed mouth)
BANK_OF = {"REST": None, "MBP": None, "BREATH": None, "AI": "a", "E": "e", "I": "i", "O": "o", "U": "u", "FV": "i",
           "L": "e", "CDG": "i", "R": "o"}
# on a shouted line the big shapes become the wide shout
SHOUTED = {"a": "shout", "e": "shout", "o": "shout"}


def cut_mouth(rgb4, concave=False):
    """the mouth in a 4x crop of a sheet cell -> RGBA: everything inside the lips' outer outline (the dark outline,
    teeth, tongue, inside), soft-edged; the skin round it (and stray stubble) transparent"""
    hsv = cv2.cvtColor(rgb4, cv2.COLOR_RGB2HSV).astype(np.int16)
    S, V = hsv[..., 1], hsv[..., 2]
    H, W = V.shape
    dark = (V < 110).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(dark, 8)
    if n < 2:
        return np.dstack([rgb4, np.zeros((H, W), np.uint8)])
    # the mouth: the biggest dark piece near the middle of the box
    cx, cy = W / 2, H / 2
    best, score = 1, -1
    for k in range(1, n):
        x, y, w, h, a = st[k]
        d = abs(x + w / 2 - cx) / W + abs(y + h / 2 - cy) / H
        sc = a * (1.2 - d)
        if sc > score:
            best, score = k, sc
    m = (lab == best).astype(np.uint8)
    # inside the outline: fill it (teeth, tongue), then take in the outline's soft edge
    ff = (1 - m).copy()
    cv2.floodFill(ff, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 0)
    m = m | ff
    hull = cv2.convexHull(cv2.findNonZero(m))
    inside = np.zeros_like(m)
    cv2.fillConvexPoly(inside, hull, 1)
    if concave:          # a smile's top line curves up: only what the outline closes in, plus its teeth and lip
        lip = inside & ((S > 60) & (V < 235) | (V > 215) & (S < 40)).astype(np.uint8)
        m = m | (lip & cv2.dilate(m, np.ones((9, 9), np.uint8)))
    else:                # an open mouth is everything inside the lips' outer outline: teeth, tongue, throat
        m = m | inside
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    a = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)
    return np.dstack([rgb4, (np.clip(a * 1.15, 0, 1) * 255).astype(np.uint8)])


def build(cid):
    spec = yaml.safe_load((CHARACTERS / cid / "film.yaml").read_text())["mouths"]
    from studio.film.art import x4
    img = cv2.imread(str(CHARACTERS / cid / spec["sheet"]), cv2.IMREAD_COLOR)
    out = build_dir("film", cid, "mouths")
    meta = dict(rest=spec["rest"], cells={})
    tiles = []
    for name, c in spec["cells"].items():
        x0, y0, x1, y1 = c["box"]
        big = cv2.cvtColor(x4(img[y0:y1, x0:x1]), cv2.COLOR_BGR2RGB)
        rgba = cut_mouth(big, concave=(name == "smile"))
        cv2.imwrite(str(out / f"{name}.png"), cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
        meta["cells"][name] = dict(box=c["box"], ref=c["ref"])
        a = rgba[..., 3:4].astype(np.float32) / 255
        t = (rgba[..., :3] * a + np.float32([255, 0, 255]) * (1 - a)).astype(np.uint8)
        t = cv2.resize(t, (int(t.shape[1] * 160 / t.shape[0]), 160))
        cv2.putText(t, name, (4, 18), 0, 0.6, (255, 255, 255), 2)
        tiles.append(t)
    (out / "mouths.json").write_text(json.dumps(meta, indent=1))
    chk = build_dir("film") / f"{cid}_mouths.jpg"
    cv2.imwrite(str(chk), cv2.cvtColor(np.hstack(tiles), cv2.COLOR_RGB2BGR))
    print(chk)
    return meta


_BANKS = {}


def load(cid):
    """-> {rest: [cx, cy, w, chin], cells: {name: (RGBA float 4x, (ref x, ref y) in its px)}} or None"""
    if cid in _BANKS:
        return _BANKS[cid]
    spec = yaml.safe_load((CHARACTERS / cid / "film.yaml").read_text()).get("mouths")
    if not spec:
        _BANKS[cid] = None
        return None
    d = build_dir("film", cid, "mouths")
    if not (d / "mouths.json").exists():
        build(cid)
    meta = json.loads((d / "mouths.json").read_text())
    cells = {}
    for name, c in meta["cells"].items():
        im = cv2.imread(str(d / f"{name}.png"), cv2.IMREAD_UNCHANGED)
        rgba = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255
        x0, y0 = c["box"][:2]
        cells[name] = (rgba, ((c["ref"][0] - x0) * 4, (c["ref"][1] - y0) * 4))
    _BANKS[cid] = dict(rest=meta["rest"], cells=cells, scale=4)
    return _BANKS[cid]


if __name__ == "__main__":
    build(sys.argv[1])
