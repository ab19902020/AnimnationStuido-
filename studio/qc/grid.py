"""Draw a coordinate grid over (a crop of) an image, to read off sheet coordinates for YAML fixes.

    python3 -m studio.qc.grid IMAGE OUT.jpg [x0 y0 x1 y1] [--step 50] [--zoom 2]"""
import argparse

import cv2
import numpy as np
from PIL import Image


def grid(path, out, box=None, step=50, zoom=1.0):
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    a = im[..., 3:4] / 255
    rgb = im[..., :3] * a + np.array([255, 0, 255], np.float32) * (1 - a)     # transparent shows magenta
    img = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    x0, y0, x1, y1 = box or (0, 0, img.shape[1], img.shape[0])
    img = img[y0:y1, x0:x1]
    img = cv2.resize(img, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST if zoom > 1 else cv2.INTER_AREA)
    for x in range((x0 // step + 1) * step, x1, step):
        X = int((x - x0) * zoom)
        cv2.line(img, (X, 0), (X, img.shape[0]), (0, 200, 0) if x % (step * 2) else (0, 120, 255), 1)
        cv2.putText(img, str(x), (X + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 2)
        cv2.putText(img, str(x), (X + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    for y in range((y0 // step + 1) * step, y1, step):
        Y = int((y - y0) * zoom)
        cv2.line(img, (0, Y), (img.shape[1], Y), (0, 200, 0) if y % (step * 2) else (0, 120, 255), 1)
        cv2.putText(img, str(y), (2, Y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 2)
        cv2.putText(img, str(y), (2, Y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("box", nargs="*", type=int)
    ap.add_argument("--step", type=int, default=50)
    ap.add_argument("--zoom", type=float, default=1.0)
    a = ap.parse_args()
    grid(a.image, a.out, a.box or None, a.step, a.zoom)
