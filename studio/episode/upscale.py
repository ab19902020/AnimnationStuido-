"""Sharpen a background for camera moves: Real-ESRGAN x4 (anime 6B, models/realesrgan_x4_anime6b.onnx, committed),
run in overlapping tiles on the CPU, then brought down to the size the shots need.

    from studio.episode.upscale import upscaled
    img = upscaled(path, factor=2.0)        # BGR uint8, cached in build/upscaled/"""
import hashlib

import cv2
import numpy as np

from studio.paths import MODELS, build_dir

TILE, PAD = 128, 12
_session = None


def session():
    global _session
    if _session is None:
        import onnxruntime as ort
        _session = ort.InferenceSession(str(MODELS / "realesrgan_x4_anime6b.onnx"), providers=["CPUExecutionProvider"])
    return _session


def x4(bgr):
    """the image at 4x, tile by tile with PAD pixels of overlap thrown away at each seam"""
    s = session()
    name = s.get_inputs()[0].name
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    padded = cv2.copyMakeBorder(rgb, PAD, PAD, PAD, PAD, cv2.BORDER_REFLECT)
    out = np.zeros((h * 4, w * 4, 3), np.float32)
    for y in range(0, h, TILE):
        for x in range(0, w, TILE):
            tile = padded[y:y + TILE + 2 * PAD, x:x + TILE + 2 * PAD]
            r = s.run(None, {name: np.ascontiguousarray(tile.transpose(2, 0, 1)[None])})[0][0].transpose(1, 2, 0)
            th, tw = min(TILE, h - y), min(TILE, w - x)
            out[y * 4:(y + th) * 4, x * 4:(x + tw) * 4] = r[PAD * 4:(PAD + th) * 4, PAD * 4:(PAD + tw) * 4]
    return cv2.cvtColor(np.clip(out * 255, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)


def upscaled(path, factor=2.0):
    """`path` at `factor` times its size, sharpened; cached"""
    key = hashlib.sha1(f"{path}:{factor}".encode()).hexdigest()[:10]
    f = build_dir("upscaled") / f"{path.stem}_{factor:g}x_{key}.png"
    if f.exists():
        return cv2.imread(str(f))
    img = cv2.imread(str(path))
    big = x4(img)
    out = cv2.resize(big, (int(img.shape[1] * factor), int(img.shape[0] * factor)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(f), out)
    return out
