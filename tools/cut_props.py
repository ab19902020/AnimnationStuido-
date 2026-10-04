"""Cut props out of a sheet drawn on plain paper: the paper is flood-filled away from the edges of each box (so
anything enclosed by the drawing's ink, like white piano keys, stays), the edge is softened by one pixel, and the
prop is saved on transparent with an entry in library/props/props.yaml.

    python3 tools/cut_props.py library/props/music/source/instruments-sheet.png music \\
        drum-kit=0,30,770,650 "electric-guitar=735,15,995,695:Red electric guitar" ...

name=x0,y0,x1,y1[@holes][:title]. Paper is anything within --tol of the sheet's corner colour and connected to the
box edge. Paper the drawing encloses (between drum stands, inside a coiled cable) is taken out too with @all (every
enclosed paper-coloured patch) or @flat (only large, flat ones: white piano keys are paper-coloured but shaded).
Check the result by eye (it is also tiled into build/props_<set>_check.jpg)."""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROPS = ROOT / "library" / "props"


def cut(sheet, box, tol, holes=""):
    x0, y0, x1, y1 = box
    rgb = sheet[y0:y1, x0:x1].copy()
    paper = np.median(np.concatenate([sheet[:8, :8].reshape(-1, 3), sheet[:8, -8:].reshape(-1, 3),
                                      sheet[-8:, :8].reshape(-1, 3), sheet[-8:, -8:].reshape(-1, 3)]), 0)
    near = (np.abs(rgb.astype(np.int16) - paper.astype(np.int16)).max(2) <= tol).astype(np.uint8)
    h, w = near.shape
    filled = np.zeros((h + 2, w + 2), np.uint8)
    seeds = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + \
            [(w - 1, y) for y in range(h)]
    m = near.copy()
    for x, y in seeds:
        if m[y, x] == 1 and filled[y + 1, x + 1] == 0:
            cv2.floodFill(m, filled, (x, y), 2, 0, 0, flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY)
    bg = filled[1:-1, 1:-1] > 0
    if holes:
        n, lab, st, _ = cv2.connectedComponentsWithStats((near.astype(bool) & ~bg).astype(np.uint8), 4)
        for i in range(1, n):
            px = rgb[lab == i].astype(np.float32)
            if (holes == "all" and st[i, cv2.CC_STAT_AREA] >= 80) or \
                    (holes == "flat" and st[i, cv2.CC_STAT_AREA] >= 2000 and px.std(0).max() < 3.0):
                bg |= lab == i
    alpha = (~bg).astype(np.uint8) * 255
    # keep the largest pieces only (specks of paper texture are dropped), soften the edge by a pixel
    n, lab, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype(np.uint8), 8)
    keep = np.zeros_like(alpha)
    big = stats[1:, cv2.CC_STAT_AREA].max() if n > 1 else 0
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= max(60, big * 0.03):        # slivers of a neighbouring drawing go
            keep[lab == i] = 255
    alpha = cv2.GaussianBlur(keep, (0, 0), 0.6)
    ys, xs = np.nonzero(alpha > 8)
    a, b, c, d = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    out = np.dstack([rgb, alpha])[b:d, a:c]
    return out, (x0 + int(a), y0 + int(b), x0 + int(c), y0 + int(d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("set")
    ap.add_argument("props", nargs="+")
    ap.add_argument("--tol", type=int, default=26)
    a = ap.parse_args()
    sheet = cv2.cvtColor(cv2.imread(a.sheet), cv2.COLOR_BGR2RGB)
    rel = str(Path(a.sheet).resolve().relative_to(PROPS))
    index = yaml.safe_load((PROPS / "props.yaml").read_text()) or {}
    (PROPS / a.set).mkdir(parents=True, exist_ok=True)
    tiles = []
    for spec in a.props:
        name, rest = spec.split("=", 1)
        coords, _, title = rest.partition(":")
        coords, _, holes = coords.partition("@")
        box = [int(v) for v in coords.split(",")]
        im, sb = cut(sheet, box, a.tol, holes)
        cv2.imwrite(str(PROPS / a.set / f"{name}.png"), cv2.cvtColor(im, cv2.COLOR_RGBA2BGRA))
        key = f"{a.set}/{name}"
        index[key] = dict(title=title or name.replace("-", " ").capitalize(), size=[im.shape[1], im.shape[0]],
                          cut_from=rel, sheet_box=list(sb))
        t = im.astype(np.float32) / 255
        mag = np.zeros_like(t[..., :3])
        mag[:] = (1.0, 0.0, 1.0)
        tiles.append((t[..., :3] * t[..., 3:] + mag * (1 - t[..., 3:])) * 255)
        print(key, im.shape[1], "x", im.shape[0])
    head = "".join(l + "\n" for l in (PROPS / "props.yaml").read_text().splitlines() if l.startswith("#"))
    body = yaml.safe_dump(dict(sorted((k, v) for k, v in index.items())), sort_keys=False, allow_unicode=True,
                          default_flow_style=None, width=120)
    (PROPS / "props.yaml").write_text(head + body)
    H = 300
    row = [cv2.resize(t, (int(t.shape[1] * H / t.shape[0]), H)) for t in tiles]
    out = ROOT / "build" / f"props_{a.set}_check.jpg"
    out.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(np.hstack(row).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print(out)


if __name__ == "__main__":
    sys.exit(main())
