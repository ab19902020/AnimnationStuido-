"""Parts charts: every named part of a sheet drawn in one fixed layout, to check the labels at a glance.

    python3 -m studio.ingest.chart [CHARACTER ...]      -> build/ingest/<id>/<outfit>/<view>_chart.jpg
                                                           and build/ingest/<id>_charts.jpg (all sheets)

Body sheets: row 1 head, eyes, mouth, neck, torso, pelvis; row 2 the right arm then the left arm; row 3 the right
leg then the left leg (each limb top to bottom: upper, lower, end). Hand sheets: one column per pose, right hand
above left. Anything in the wrong box, or a right/left swap, shows immediately."""
import sys

import cv2
import numpy as np
import yaml

from studio.ingest import classify, kit
from studio.paths import build_dir

BODY_ROWS = [["head", "eyes", "mouth", "neck", "torso", "pelvis"],
             ["upper_arm_R", "forearm_R", "hand_R", "upper_arm_L", "forearm_L", "hand_L"],
             ["thigh_R", "shin_R", "foot_R", "thigh_L", "shin_L", "foot_L"]]
CELL = 210


def cutout(rgba, pieces):
    """the pieces' pixels, cropped to their joint box, on transparent"""
    m = np.zeros(rgba.shape[:2], bool)
    for p in pieces:
        m |= p.mask
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = rgba[y0:y1, x0:x1].copy()
    out[..., 3] = np.where(m[y0:y1, x0:x1], out[..., 3], 0)
    return out


def cell(img, label, size=CELL):
    tile = np.full((size + 22, size, 3), 140, np.uint8)
    if img is not None:
        h, w = img.shape[:2]
        s = min((size - 10) / w, (size - 10) / h)
        im = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
        a = im[..., 3:4].astype(np.float32) / 255
        rgb = im[..., :3].astype(np.float32) * a + 140 * (1 - a)
        y, x = (size - im.shape[0]) // 2, (size - im.shape[1]) // 2
        tile[y:y + im.shape[0], x:x + im.shape[1]] = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    else:
        cv2.line(tile, (20, 20), (size - 20, size - 20), (0, 0, 255), 3)
    cv2.putText(tile, label, (4, size + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return tile


def chart(cid, outfit, view, png):
    spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
    rgba, named, guide, unused = kit.resolve(png, spec)
    if view == "hands":
        rows = [[f"{p}_R" for p in classify.HAND_POSES], [f"{p}_L" for p in classify.HAND_POSES]]
    else:
        rows = BODY_ROWS
    grid = []
    for row in rows:
        grid.append(np.hstack([cell(cutout(rgba, named[n]) if n in named else None, n) for n in row]))
    width = max(g.shape[1] for g in grid)
    grid = [cv2.copyMakeBorder(g, 0, 0, 0, width - g.shape[1], cv2.BORDER_CONSTANT, value=(90, 90, 90))
            for g in grid]
    body = np.vstack(grid)
    if guide is not None:
        gimg = cell(cutout(rgba, [guide]), "guide", size=body.shape[0] - 22)
        body = np.hstack([body, gimg])
    title = np.full((34, body.shape[1], 3), 40, np.uint8)
    flag = "" if spec.get("checked") else "  (unchecked)"
    cv2.putText(title, f"{cid} / {outfit} / {view}{flag}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                (255, 255, 255), 2, cv2.LINE_AA)
    out = np.vstack([title, body])
    cv2.imwrite(str(build_dir("ingest", cid, outfit) / f"{view}_chart.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


def main():
    chars = sys.argv[1:] or None
    per = {}
    for cid, outfit, view, png in kit.sheets(chars):
        per.setdefault(cid, []).append(chart(cid, outfit, view, png))
    for cid, charts in per.items():
        w = max(c.shape[1] for c in charts)
        charts = [cv2.copyMakeBorder(c, 0, 6, 0, w - c.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
                  for c in charts]
        cv2.imwrite(str(build_dir("ingest") / f"{cid}_charts.jpg"), np.vstack(charts), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(cid, file=sys.stderr)


if __name__ == "__main__":
    main()
