"""Show effects for music videos, all keyed to the song so they land on the music (direction.py lists when):

  PYRO = [(t, length s, strength)]   spark fountains: gerbs at the front of the stage burst on the big hits (the lights
                                     coming up, a chorus dropping, the last chord). In the stage shots they stand on
                                     the stage (plate px, direction.FOUNTAINS); in the crowd shots, taken from the
                                     stage, they are beside the lens, close, out of focus, the sparks rising past it
  CONFETTI = (t0, t1)                red, white, gold and black paper tumbling down over everything (the finale)
  FLAGS = [(t0, t1)]                 United flags raised and waving at the back of the room in the crowd shots

Every particle's place is worked out from its own spawn time, so any frame renders on its own (the film is rendered
in parallel chunks)."""
import functools
import math

import cv2
import numpy as np

from studio.film.engine import OH, OW, RS

INK = (0.094, 0.078, 0.086)


def sm(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- sparks
def _fountain(t, t0, length, rate, seed):
    """the live sparks of one fountain at t: (age, vx, vy, life) per spark (plate units per second, up negative),
    spawned at `rate` a second from t0 for `length` s"""
    life_max = 1.1
    a0 = max(t0, t - life_max)
    a1 = min(t, t0 + length)
    if a1 <= a0:
        return None
    k0, k1 = int(math.floor((a0 - t0) * rate)), int(math.ceil((a1 - t0) * rate))
    k = np.arange(max(0, k0), max(0, k1))
    if len(k) == 0:
        return None
    r = np.random.default_rng(seed)
    n = int(rate * (length + life_max)) + 8
    ang = r.normal(0.0, 0.11, n)                        # the jet's spread (rad), a little wider at the edges
    spd = r.uniform(0.72, 1.0, n)
    life = r.uniform(0.55, 1.05, n)
    jit = r.uniform(0.0, 1.0, n)
    k = k[k < n]
    ts = t0 + (k + jit[k]) / rate
    age = t - ts
    ok = (age >= 0) & (age < life[k])
    k, age = k[ok], age[ok]
    return age, np.sin(ang[k]) * spd[k], -np.cos(ang[k]) * spd[k], life[k]


def _streaks(lay, glow, pts0, pts1, heat, width):
    """sparks as short bright streaks: the white-hot core into the sharp layer, a warm halo into the glow layer"""
    for (x0, y0), (x1, y1), h in zip(pts0, pts1, heat):
        c = (1.0, 0.86 + 0.14 * h, 0.55 + 0.45 * h)    # white-hot when new, gold, then orange as it cools
        c = tuple(float(v) * (0.5 + 0.5 * h) for v in c)
        p0, p1 = (int(x0 * 4), int(y0 * 4)), (int(x1 * 4), int(y1 * 4))
        cv2.line(lay, p0, p1, c, max(1, int(round(width * (0.6 + 0.4 * h)))), cv2.LINE_AA, 2)
        g = (1.0, 0.55 + 0.2 * h, 0.15)
        cv2.line(glow, (int(x0 / 2), int(y0 / 2)), (int(x1 / 2), int(y1 / 2)), tuple(float(v) * (0.35 + 0.5 * h) for v in g),
                 max(1, int(width * 1.5)), cv2.LINE_AA)


def sparks_plate(img, t, M, sc, bursts, fountains, height, dark=0.0, glow_k=1.0, rate=150.0):
    """fountains on the stage (plate px through M): bursts [(t0, length, strength)], fountains [(x, y)], height (plate
    px) the jets reach. Additive light: the sparks, their glow, and the fountains lighting the stage round them"""
    live = [(t0, ln, st) for t0, ln, st in bursts if t0 <= t < t0 + ln + 1.2]
    if not live:
        return img
    lay = np.zeros((OH, OW, 3), np.float32)
    glow = np.zeros((OH // 2, OW // 2, 3), np.float32)
    g = 2.0 * height / 0.62 ** 2                       # the jet tops out at `height` after 0.62 s
    v0 = 2.0 * height / 0.62
    base_glow = 0.0
    for bi, (t0, ln, st) in enumerate(live):
        for fi, (fx, fy) in enumerate(fountains):
            sp = _fountain(t, t0, ln, rate * st, seed=bi * 131 + fi * 17 + int(t0 * 10))
            if sp is None:
                continue
            age, ux, uy, life = sp
            def at(a):
                return fx + ux * v0 * a, fy + uy * v0 * a + 0.5 * g * a * a
            x1, y1 = at(age)
            x0, y0 = at(np.maximum(0.0, age - 0.035))
            sx1, sy1 = M[0, 0] * x1 + M[0, 2], M[1, 1] * y1 + M[1, 2]
            sx0, sy0 = M[0, 0] * x0 + M[0, 2], M[1, 1] * y0 + M[1, 2]
            heat = np.clip(1.0 - age / life, 0, 1) ** 0.7
            on = (sx1 > -50) & (sx1 < OW + 50) & (sy1 > -50) & (sy1 < OH + 50)
            _streaks(lay, glow, np.stack([sx0[on], sy0[on]], 1), np.stack([sx1[on], sy1[on]], 1), heat[on],
                     max(1.2, 0.0055 * height * sc))
            # the fountain's mouth burns bright and lights the stage round it
            u = sm((t - t0) / 0.08) * (1 - sm((t - t0 - ln) / 0.4)) * st
            if u > 0:
                bx, by = M[0, 0] * fx + M[0, 2], M[1, 1] * fy + M[1, 2]
                cv2.circle(glow, (int(bx / 2), int(by / 2)), max(2, int(0.06 * height * sc / 2)),
                           (1.0 * u, 0.7 * u, 0.3 * u), -1, cv2.LINE_AA)
                base_glow = max(base_glow, u)
    halo = cv2.GaussianBlur(glow, (0, 0), 7 * RS)
    halo = cv2.resize(halo, (OW, OH), interpolation=cv2.INTER_LINEAR)
    k = (1.0 - 0.6 * dark) * glow_k
    out = img + (lay * 1.2 + halo * 1.15) * k
    if base_glow > 0:                                   # warm light up from the stage over everything near it
        out = out + cv2.GaussianBlur(halo, (0, 0), 40 * RS) * 1.4 * base_glow * k
    return out


def _sparks_lay(t, bursts, bases, height, w=1.0):
    lay = np.zeros((OH, OW, 3), np.float32)
    glow = np.zeros((OH // 2, OW // 2, 3), np.float32)
    g = 2.0 * height / 0.7 ** 2
    v0 = 2.0 * height / 0.7
    for bi, (t0, ln, st) in enumerate(bursts):
        if not (t0 <= t < t0 + ln + 1.2):
            continue
        for fi, (fx, fy, lean) in enumerate(bases):
            sp = _fountain(t, t0, ln, 85.0 * st, seed=bi * 71 + fi * 29 + 5 + int(t0 * 10))
            if sp is None:
                continue
            age, ux, uy, life = sp
            ux = ux + lean
            x1, y1 = fx + ux * v0 * age, fy + uy * v0 * age + 0.5 * g * age * age
            a0 = np.maximum(0.0, age - 0.03)
            x0, y0 = fx + ux * v0 * a0, fy + uy * v0 * a0 + 0.5 * g * a0 * a0
            heat = np.clip(1.0 - age / life, 0, 1) ** 0.7
            _streaks(lay, glow, np.stack([x0, y0], 1), np.stack([x1, y1], 1), heat, w * 5.0 * RS)
    return lay, glow


def sparks_screen(img, t, bursts):
    """a crowd shot is taken from the stage: the fountains at the stage's edge are beside the lens, in the bottom
    corners, close and out of focus, their sparks rising past the crowd"""
    live = [b for b in bursts if b[0] <= t < b[0] + b[1] + 1.2]
    if not live:
        return img
    bases = [(0.015 * OW, 1.06 * OH, 0.06), (0.985 * OW, 1.06 * OH, -0.06)]
    lay, glow = _sparks_lay(t, live, bases, 0.92 * OH, w=1.5)
    lay = cv2.GaussianBlur(lay, (0, 0), 2.2 * RS)        # near the lens: soft
    halo = cv2.resize(cv2.GaussianBlur(glow, (0, 0), 10 * RS), (OW, OH))
    return img + lay * 1.1 + halo * 1.2


# ---------------------------------------------------------------- confetti
@functools.lru_cache(maxsize=4)
def _confetti_set(t0, t1, seed=11):
    """every piece of confetti that falls between t0 and t1: spawn time, x, size, depth, speed, sway, spin, colour"""
    rate = 240.0                                         # pieces a second
    n = int((t1 - t0 + 6.0) * rate)
    r = np.random.default_rng(seed)
    depth = r.choice([0, 1, 2], n, p=[0.55, 0.32, 0.13])            # far, mid, near
    cols = np.float32([[0.86, 0.06, 0.09], [0.97, 0.96, 0.94], [1.0, 0.80, 0.22], [0.08, 0.07, 0.08],
                       [0.86, 0.06, 0.09], [0.97, 0.96, 0.94]])
    return dict(ts=t0 + np.sort(r.uniform(-1.2, t1 - t0, n)), x=r.uniform(-0.05, 1.05, n), depth=depth,
                size=np.choose(depth, [r.uniform(5, 8, n), r.uniform(9, 14, n), r.uniform(17, 25, n)]),
                speed=np.choose(depth, [r.uniform(120, 170, n), r.uniform(170, 240, n), r.uniform(280, 380, n)]),
                sway=r.uniform(14, 40, n), sw_f=r.uniform(0.5, 1.4, n), ph=r.uniform(0, 6.28, n),
                spin=r.uniform(-4.0, 4.0, n), flip=r.uniform(2.0, 6.0, n), col=cols[r.integers(0, len(cols), n)],
                aspect=r.uniform(0.45, 0.75, n))


def confetti(img, t, t0, t1):
    """confetti tumbling down over the whole frame: three depths (the near pieces big and soft), each piece turning
    over as it falls so it flashes light and dark"""
    if not (t0 - 1.2 <= t < t1 + 6.0):
        return img
    c = _confetti_set(round(t0, 3), round(t1, 3))
    age = t - c["ts"]
    y = -40 + c["speed"] * age                           # layout px (1920 x 1080)
    live = (age > 0) & (y < 1120) & (c["ts"] < t1)
    if not live.any():
        return img
    out = img
    for depth, blur in ((0, 0.0), (1, 0.0), (2, 2.2)):
        sel = np.nonzero(live & (c["depth"] == depth))[0]
        if len(sel) == 0:
            continue
        lay = np.zeros((OH, OW, 4), np.float32)
        for i in sel:
            a = age[i]
            x = (c["x"][i] * 1920 + c["sway"][i] * math.sin(c["sw_f"][i] * a * 6.28 + c["ph"][i])) * RS
            yy = y[i] * RS
            s = c["size"][i] * RS
            th = c["spin"][i] * a + c["ph"][i]
            fl = math.cos(c["flip"][i] * a + c["ph"][i])          # turning over: the piece narrows and darkens
            w2, h2 = s * 0.5, max(0.6, s * c["aspect"][i] * 0.5 * abs(fl))
            ct, st_ = math.cos(th), math.sin(th)
            pts = np.float32([[-w2, -h2], [w2, -h2], [w2, h2], [-w2, h2]]) @ np.float32([[ct, st_], [-st_, ct]])
            pts += (x, yy)
            col = c["col"][i] * (0.55 + 0.45 * abs(fl))
            cv2.fillConvexPoly(lay, np.int32(pts * 4), (float(col[0]), float(col[1]), float(col[2]), 1.0),
                               cv2.LINE_AA, 2)
        if blur > 0:
            lay = cv2.GaussianBlur(lay, (0, 0), blur * RS)
        out = out * (1 - lay[..., 3:4]) + lay[..., :3]
    return out


# ---------------------------------------------------------------- flags
@functools.lru_cache(maxsize=2)
def _flag_cloth(kind, w, h):
    """a United flag as cloth, flat (RGB, h x w): a red field with a white and a black band, or red with UNITED"""
    from PIL import Image, ImageDraw, ImageFont
    from studio.film.graphics import BEBAS
    im = Image.new("RGB", (w, h), (205, 16, 24))
    d = ImageDraw.Draw(im)
    if kind == 0:                                        # the red, white and black bars
        d.rectangle([0, int(h * 0.36), w, int(h * 0.52)], fill=(245, 243, 238))
        d.rectangle([0, int(h * 0.52), w, int(h * 0.68)], fill=(22, 18, 20))
    else:
        f = ImageFont.truetype(BEBAS, int(h * 0.62))
        bx = d.textbbox((0, 0), "UNITED", font=f)
        d.text(((w - (bx[2] - bx[0])) / 2 - bx[0], (h - (bx[3] - bx[1])) / 2 - bx[1]), "UNITED", font=f,
               fill=(250, 248, 242))
        d.rectangle([0, 0, w, int(h * 0.07)], fill=(22, 18, 20))
        d.rectangle([0, h - int(h * 0.07), w, h], fill=(22, 18, 20))
    return np.asarray(im, np.float32) / 255.0


def flags(img, t, spans, beat_pos, seed=3):
    """flags raised at the back of the room in a crowd shot (drawn behind the people): each on a pole that goes down
    behind the heads, swung from side to side over two beats, the cloth rippling; out of focus, in the room's light"""
    up = max((sm((t - a) / 0.6) * (1 - sm((t - b) / 0.6)) for a, b in spans), default=0.0)
    if up <= 0.01:
        return img
    out = img
    lay = np.zeros((OH, OW, 4), np.float32)
    for k, (fx, kind) in enumerate(((0.16, 0), (0.39, 1), (0.63, 0), (0.85, 1))):
        W, H = int(0.17 * OW), int(0.105 * OW)
        cloth = _flag_cloth(kind, W, H)
        rise = (1 - up) * 0.55 * OH
        sw = math.radians(9.0 * math.sin(math.pi * (beat_pos / 2.0) + k * 1.3))
        px, py = fx * OW, 0.035 * OH + rise + 0.025 * OH * math.sin(k * 2.1)     # the pole's top
        # the cloth: each column displaced by a travelling wave, stronger away from the pole
        side = 1.0 if kind == 0 else -1.0                    # which side of the pole it flies
        xs = np.arange(W, dtype=np.float32)
        u = xs / W if side > 0 else 1.0 - xs / W             # from the pole out to the free end
        wave = np.sin(6.28 * (u * 1.3 - 1.4 * t - 0.2 * k)) * (0.10 * H) * u
        shade = 0.82 + 0.18 * np.cos(6.28 * (u * 1.3 - 1.4 * t - 0.2 * k))
        Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
        mapy = (Y - wave[None, :]).astype(np.float32)
        warped = cv2.remap(cloth, X, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        alpha = cv2.remap(np.ones((H, W), np.float32), X, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=0)
        warped = warped * shade[None, :, None]               # (never mirrored: the lettering reads the right way)
        rgba = np.dstack([warped * alpha[..., None], alpha])
        # outline: the house look
        edge = cv2.dilate((alpha > 0.5).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
        ring = np.clip(edge - alpha, 0, 1)
        rgba[..., :3] += ring[..., None] * np.float32(INK)
        rgba[..., 3] = np.maximum(rgba[..., 3], ring)
        c, s = math.cos(sw), math.sin(sw)
        ox = 0.0 if side > 0 else -W
        A = np.float32([[c, -s, px + c * ox], [s, c, py + s * ox]])
        cv2.line(lay, (int(px * 4), int(py * 4)), (int((px - math.sin(sw) * OH) * 4), int((py + math.cos(sw) * OH) * 4)),
                 (*INK, 1.0), max(2, int(round(7 * RS))), cv2.LINE_AA, 2)
        cv2.line(lay, (int(px * 4), int(py * 4)), (int((px - math.sin(sw) * OH) * 4), int((py + math.cos(sw) * OH) * 4)),
                 (0.55, 0.42, 0.28, 1.0), max(1, int(round(4 * RS))), cv2.LINE_AA, 2)
        warped_full = cv2.warpAffine(rgba, A, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        lay = warped_full + lay * (1 - warped_full[..., 3:4])
    lay = cv2.GaussianBlur(lay, (0, 0), 2.6 * RS)            # at the back of the room: out of focus
    lay[..., :3] *= 0.78                                     # in the room's light, not the stage's
    return out * (1 - lay[..., 3:4]) + lay[..., :3]
