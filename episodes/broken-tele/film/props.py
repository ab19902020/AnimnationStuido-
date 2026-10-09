"""The sets and the action: the telly's screen cracking and smashing (the drawn cracked and smashed screens from the
household props sheet, warped onto the telly in the plate and revealed outwards from where the toy hits), the toys
in the air, the glass, the flash and the shake; the new telly's shine, the projector; and the inserts (the card
reader, the time cards). Drawn in the house look: flat colours, a dark ink outline."""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from studio.film import graphics as G
from studio.film.cast import CAST
from studio.film.engine import FPS, OH, OW, RS
from studio.film.shots import ease
from studio.paths import BACKGROUNDS, PROPS
from film.timeline import TL

INK = (30, 24, 26)
GLASS = (178, 204, 224)


def m(k):
    return TL["marks"][k]


def sm(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- props as pictures
@functools.lru_cache(None)
def prop(name):
    """a household prop, RGBA uint8 (RGB order), 4 px per sheet px"""
    im = cv2.imread(str(PROPS / "household" / f"{name}.png"), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


@functools.lru_cache(maxsize=64)
def prop_at(name, w):
    """the prop resized to about w px wide (area-averaged, so it never aliases)"""
    im = prop(name)
    k = max(8, w) / im.shape[1]
    return cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)


def sprite(img, name, X, Y, w, ang=0.0, alpha=1.0, flip=False, blur=0.0):
    """composite a prop centred on screen px (X, Y), w screen px wide, rotated ang degrees"""
    wq = int(max(8, round(w / 8) * 8))
    im = prop_at(name, wq)
    if flip:
        im = im[:, ::-1]
    h0, w0 = im.shape[:2]
    R = cv2.getRotationMatrix2D((w0 / 2, h0 / 2), ang, w / w0)
    R[:, 2] += (X - w0 / 2, Y - h0 / 2)
    lay = cv2.warpAffine(im, R, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(0, 0, 0, 0)).astype(np.float32) / 255.0
    if blur > 0:
        lay = cv2.GaussianBlur(lay, (0, 0), blur)
    a = lay[..., 3:4] * alpha
    return img * (1 - a) + lay[..., :3] * a


def P(M, x, y):
    return M[0, 0] * x + M[0, 2], M[1, 1] * y + M[1, 2]


# ---------------------------------------------------------------- the telly's screen
# the screen of the telly on the wall plate (1x plate px, inner edge of the bezel: TL, TR, BR, BL)
SCREEN = np.float32([(520, 336), (892, 268), (895, 554), (521, 561)])
# the drawn screens (prop px): the inner edge of their bezels, and where the hit is
TEX = {"cracked": ("tv-cracked", np.float32([(50, 100), (1744, 50), (1736, 1010), (56, 990)]), (830, 630)),
       "smashed": ("tv-smashed", np.float32([(80, 50), (1724, 90), (1716, 1000), (84, 1010)]), (900, 600))}


def tex_to(kind, quad):
    """the homography from a drawn screen onto a screen quad"""
    return cv2.getPerspectiveTransform(TEX[kind][1], np.float32(quad))


def hit_point(kind, quad=SCREEN):
    """where the drawn screen's impact lands on the plate (1x plate px)"""
    Hm = tex_to(kind, quad)
    p = cv2.perspectiveTransform(np.float32([[TEX[kind][2]]]), Hm)[0, 0]
    return float(p[0]), float(p[1])


def screen_layer(img, kind, M, reveal=1.0):
    """the drawn cracked / smashed screen over the telly in a shot (M: plate -> screen), revealed outwards from the
    hit point to `reveal` (0..1)"""
    quad = np.float32([P(M, x, y) for x, y in SCREEN])
    Hm = tex_to(kind, quad)
    tex = prop(TEX[kind][0])
    warped = cv2.warpPerspective(tex[..., :3], Hm, (OW, OH), flags=cv2.INTER_AREA if M[0, 0] < 2 else cv2.INTER_LINEAR)
    inside = np.zeros((OH, OW), np.float32)
    cv2.fillConvexPoly(inside, np.int32(np.round(quad * 8)), 1.0, cv2.LINE_AA, 3)
    hx, hy = cv2.perspectiveTransform(np.float32([[TEX[kind][2]]]), Hm)[0, 0]
    if reveal < 1.0:
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        d = np.sqrt((xx - hx) ** 2 + (yy - hy) ** 2)
        span = float(np.max(np.linalg.norm(quad - [hx, hy], axis=1)))
        r = reveal * span * 1.05
        feather = 18 * RS * M[0, 0] / 2
        inside *= np.clip((r - d) / feather, 0, 1)
    a = inside[..., None]
    return img * (1 - a) + warped.astype(np.float32) / 255.0 * a


def bake_screen(big, kind):
    """the drawn screen warped onto a 4x plate, the plant in front of it kept"""
    from film.direction import PLANT
    quad = SCREEN * 4
    Hm = tex_to(kind, quad)
    tex = prop(TEX[kind][0])
    H, W = big.shape[:2]
    warped = cv2.warpPerspective(tex[..., :3], Hm, (W, H), flags=cv2.INTER_CUBIC)
    msk = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(msk, np.int32(np.round(quad * 8)), 255, cv2.LINE_AA, 3)
    cv2.fillPoly(msk, [np.int32(np.round(np.float32(PLANT) * 4 * 8))], 0, cv2.LINE_AA, 3)
    a = (msk.astype(np.float32) / 255)[..., None]
    return (big * (1 - a) + warped * a).astype(np.uint8)


# ---------------------------------------------------------------- the plates
def _base(key):
    from studio.episode.upscale import upscaled
    return upscaled(BACKGROUNDS / f"{key}.png", 4.0)[..., ::-1].copy()


# the telly, its bezel and its feet on the wall plate (1x px): what the projector replaced
TV_OUTER = [(503, 322), (903, 248), (906, 584), (884, 590), (880, 598), (556, 600), (548, 592), (503, 590)]


def projected_picture(w=1600, h=900):
    """what the projector shows: a sunny cartoon with the dinosaur, in the house look"""
    im = Image.new("RGB", (w, h), (0, 0, 0))
    dr = ImageDraw.Draw(im)
    for y in range(h):                                   # sky
        u = y / h
        dr.line([(0, y), (w, y)], fill=(int(110 + 90 * u), int(185 + 50 * u), int(240 + 10 * u)))
    dr.ellipse((w * 0.78, h * 0.08, w * 0.92, h * 0.33), fill=(255, 226, 92), outline=INK, width=8)
    for cx, cy, s in ((0.2, 0.18, 1.0), (0.5, 0.12, 0.8)):
        for dx, dy, r in ((-0.06, 0.02, 0.06), (0.0, -0.01, 0.08), (0.07, 0.02, 0.06)):
            x, y, rr = (cx + dx * s) * w, (cy + dy * s) * h, r * s * w
            dr.ellipse((x - rr, y - rr * 0.7, x + rr, y + rr * 0.7), fill=(255, 255, 255))
    dr.polygon([(0, h * 0.72), (w * 0.35, h * 0.55), (w * 0.7, h * 0.66), (w, h * 0.58), (w, h), (0, h)],
               fill=(118, 196, 84), outline=INK)
    dr.polygon([(0, h * 0.85), (w * 0.5, h * 0.76), (w, h * 0.86), (w, h), (0, h)], fill=(92, 168, 66))
    dino = Image.fromarray(prop_at("toy-dinosaur", int(w * 0.42)))
    im.paste(dino, (int(w * 0.29), int(h * 0.92 - dino.height)), dino)
    return np.asarray(im)


def plate_image(k):
    """the telly wall after the first smash (TWc: the cracked screen), after the second (TWs: the smashed one), and
    without its telly (TWp: the wall painted over where it hung, the projector's picture on it)"""
    if k == "TWc":
        return bake_screen(_base("home/family-living-room-tv-wall"), "cracked")
    if k == "TWs":
        return bake_screen(_base("home/family-living-room-tv-wall"), "smashed")
    if k == "LRs":                                   # the living room after the second telly: its screen (seen at an
        big = _base("home/family-living-room")       # angle, running off the plate) smashed through too
        tex = prop(TEX["smashed"][0])
        src = TEX["smashed"][1]
        u = 0.36                                      # the share of the screen's width the plate shows
        s0 = np.float32([src[0], src[0] + (src[1] - src[0]) * u, src[3] + (src[2] - src[3]) * u, src[3]])
        dst = np.float32([(798, 396), (941, 382), (941, 650), (798, 645)]) * 4
        Hm = cv2.getPerspectiveTransform(s0, dst)
        H, W = big.shape[:2]
        warped = cv2.warpPerspective(tex[..., :3], Hm, (W, H), flags=cv2.INTER_CUBIC)
        msk = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(msk, np.int32(np.round(dst * 8)), 255, cv2.LINE_AA, 3)
        hsv = cv2.cvtColor(big[..., ::-1].copy(), cv2.COLOR_BGR2HSV)
        leaves = ((hsv[..., 0] > 25) & (hsv[..., 0] < 90) & (hsv[..., 1] > 60)).astype(np.uint8)
        leaves = cv2.dilate(leaves, np.ones((5, 5), np.uint8))
        msk[leaves > 0] = 0
        a = (msk.astype(np.float32) / 255)[..., None]
        return (big * (1 - a) + warped * a).astype(np.uint8)
    if k == "TWp":
        big = _base("home/family-living-room-tv-wall")
        src = cv2.imread(str(BACKGROUNDS / "home/family-living-room-tv-wall.png"))
        hole = np.zeros(src.shape[:2], np.uint8)
        cv2.fillPoly(hole, [np.int32(TV_OUTER)], 255)
        hole = cv2.dilate(hole, np.ones((7, 7), np.uint8))
        # the wall continued over the telly (the unit below it stays): rebuilt at 1x, then brought up to 4x
        fixed = cv2.inpaint(src, hole, 9, cv2.INPAINT_TELEA)[..., ::-1]
        x0, y0, x1, y1 = 480, 230, 941, 620
        patch = cv2.resize(fixed[y0:y1, x0:x1], ((x1 - x0) * 4, (y1 - y0) * 4), interpolation=cv2.INTER_CUBIC)
        patch = cv2.GaussianBlur(patch, (0, 0), 3)
        a = cv2.GaussianBlur(cv2.resize(hole[y0:y1, x0:x1], ((x1 - x0) * 4, (y1 - y0) * 4)), (0, 0), 4)
        a = (a.astype(np.float32) / 255)[..., None]
        reg = big[y0 * 4:y1 * 4, x0 * 4:x1 * 4].astype(np.float32)
        big[y0 * 4:y1 * 4, x0 * 4:x1 * 4] = (reg * (1 - a) + patch * a).astype(np.uint8)
        # the picture, a little bigger than the telly was, soft at its edges
        c = SCREEN.mean(0)
        quad = (c + (SCREEN - c) * np.float32([1.22, 1.18])) * 4
        pic = projected_picture()
        Hm = cv2.getPerspectiveTransform(np.float32([(0, 0), (1600, 0), (1600, 900), (0, 900)]), quad)
        H, W = big.shape[:2]
        warped = cv2.warpPerspective(pic, Hm, (W, H), flags=cv2.INTER_CUBIC).astype(np.float32)
        msk = cv2.warpPerspective(np.full((900, 1600), 255, np.uint8), Hm, (W, H))
        msk = cv2.GaussianBlur(msk, (0, 0), 6).astype(np.float32)[..., None] / 255
        wall = big.astype(np.float32)
        lit = wall * 0.18 + warped * 0.92
        big = np.clip(wall * (1 - msk) + lit * msk, 0, 255).astype(np.uint8)
        return big
    return None


# ---------------------------------------------------------------- the boy's throws
def _point_on(draw, fx, fy, ppm, sx, sy):
    """a point of a drawing (sheet px) in plate px, for a world actor stood at (fx, fy)"""
    from film.direction import actor
    _, _, (ex, ey), ed_p, mirror, _ = actor(*draw.split(":")[0].split("-")[1:], draw.split(":")[1], fx, fy, ppm)
    d, info = CAST.get(draw)
    k = ed_p / info["ed"]
    return ex + (sx - info["anchor"][0]) * k, ey + (sy - info["anchor"][1]) * k


@functools.lru_cache(None)
def red_ball(draw):
    """the centre and radius of the red ball drawn in a pose (sheet px)"""
    d, info = CAST.get(draw)
    im = d.u8[1.0]
    r, g, b, a = (im[..., i].astype(int) for i in range(4))
    red = (r > 170) & (g < 90) & (b < 90) & (a > 200)
    ys, xs = np.nonzero(red)
    return (xs.mean() / d.S + d.ox, ys.mean() / d.S + d.oy, 0.5 * (xs.max() - xs.min()) / d.S)


@functools.lru_cache(None)
def throw_hand(draw):
    """the throwing hand of the throw pose: the skin furthest out on the right (sheet px)"""
    d, info = CAST.get(draw)
    im = d.u8[1.0]
    r, g, b, a = (im[..., i].astype(int) for i in range(4))
    skin = (r > 200) & (g > 140) & (g < 215) & (b > 100) & (b < 190) & (a > 200)
    ys, xs = np.nonzero(skin)
    k = xs > xs.max() - 0.04 * im.shape[1]
    return (xs[k].mean() / d.S + d.ox, ys[k].mean() / d.S + d.oy)


def _throw(n):
    from film.direction import BOY_X, BOY_Y, PPM_NEAR
    wind = "family-boy:wind"
    bx, by, br = red_ball(wind)
    hold = _point_on(wind, BOY_X, BOY_Y, PPM_NEAR, bx, by)
    rel = _point_on("family-boy:throw", BOY_X + 25, BOY_Y, PPM_NEAR, *throw_hand("family-boy:throw"))
    return hold, rel, br


def held_car(img, s, t, M, sc):
    """the toy car in his raised hand, over the ball the pose was drawn with"""
    if t >= m("throw1"):
        return img
    (hx, hy), _, br = _throw(1)
    X, Y = P(M, hx, hy - 4)
    return sprite(img, "toy-car", X, Y, 0.24 * PPM_SCALE() * sc, ang=-12 + 6 * math.sin(t * 9))


def _ppm(y):
    """the telly wall's floor scale at floor row y (plate px to the metre)"""
    from film.direction import ppm_at
    return ppm_at("TW", y)


def PPM_SCALE():
    from film.direction import PPM_NEAR
    return PPM_NEAR


def _flight(img, t, t0, t1, M, sc, toy, kind):
    if not t0 <= t < t1:
        return img
    _, (rx, ry), _ = _throw(1)
    hx, hy = hit_point(kind)
    u = (t - t0) / (t1 - t0)
    x = rx + (hx - rx) * u
    y = ry + (hy - ry) * u - 70 * math.sin(math.pi * u)
    w0 = 0.24 * PPM_SCALE() if toy == "toy-car" else 0.2 * PPM_SCALE()
    w = w0 * (1 - 0.45 * u) * sc
    for g, back in ((0.18, 0.12), (0.32, 0.06)):            # a little smear behind it
        ug = max(0.0, u - back)
        xg = rx + (hx - rx) * ug
        yg = ry + (hy - ry) * ug - 70 * math.sin(math.pi * ug)
        img = _toy(img, toy, *P(M, xg, yg), w, -360 * ug * 1.3, g)
    return _toy(img, toy, *P(M, x, y), w, -360 * u * 1.3, 1.0)


def _toy(img, toy, X, Y, w, ang, alpha):
    if toy == "ball":
        return ball(img, X, Y, w / 2, ang, alpha)
    return sprite(img, toy, X, Y, w, ang, alpha)


def ball(img, X, Y, r, ang=0.0, alpha=1.0):
    """the boy's soft red ball, as drawn on his sheet: red, a highlight, the ink outline"""
    lay = np.zeros((OH, OW, 4), np.float32)
    c = (int(X * 8), int(Y * 8))
    R = int(r * 8)
    cv2.circle(lay, c, R, (INK[0] / 255, INK[1] / 255, INK[2] / 255, 1.0), -1, cv2.LINE_AA, 3)
    cv2.circle(lay, c, int(R * 0.86), (0.86, 0.13, 0.12, 1.0), -1, cv2.LINE_AA, 3)
    hx, hy = X - 0.32 * r * math.cos(math.radians(ang) + 0.8), Y - 0.32 * r * math.sin(math.radians(ang) + 0.8)
    cv2.ellipse(lay, (int(hx * 8), int(hy * 8)), (int(R * 0.26), int(R * 0.16)), ang - 40, 0, 360,
                (1.0, 0.75, 0.72, 1.0), -1, cv2.LINE_AA, 3)
    a = lay[..., 3:4] * alpha
    return img * (1 - a) + lay[..., :3] * a


def flight1(img, s, t, M, sc):
    return _flight(img, t, m("throw1"), m("smash1"), M, sc, "toy-car", "cracked")


def flight2(img, s, t, M, sc):
    return _flight(img, t, m("throw2"), m("smash2"), M, sc, "ball", "smashed")


# ---------------------------------------------------------------- the smash
def screen1(img, s, t, M, sc):
    return screen_layer(img, "cracked", M, sm((t - m("smash1")) / 0.9) if t < m("smash1") + 0.9 else 1.0)


def screen2(img, s, t, M, sc):
    return screen_layer(img, "smashed", M, sm((t - m("smash2")) / 0.14) if t < m("smash2") + 0.14 else 1.0)


def shards(img, t, t0, X, Y, scale, n, seed, spread=1.0, life=1.1):
    """glass flying out from (X, Y) screen px at t0 and falling: light glass triangles with an ink edge"""
    u = t - t0
    if not 0 <= u < life:
        return img
    rng = np.random.default_rng(seed)
    lay = np.zeros((OH, OW, 4), np.float32)
    for i in range(n):
        ang = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(250, 900) * spread * scale
        vx, vy = v * math.cos(ang), v * math.sin(ang) * 0.7 - rng.uniform(100, 400) * scale
        x = X + vx * u
        y = Y + vy * u + 1500 * scale * u * u
        sz = rng.uniform(5, 16) * scale
        rot = rng.uniform(0, 6.3) + u * rng.uniform(-12, 12)
        pts = np.float32([[math.cos(rot + k * 2.1 + rng.uniform(-0.3, 0.3)), math.sin(rot + k * 2.1)] for k in range(3)])
        pts = pts * sz + [x, y]
        q = np.int32(np.round(pts * 8))
        cv2.fillConvexPoly(lay, q, (INK[0] / 255, INK[1] / 255, INK[2] / 255, 1.0), cv2.LINE_AA, 3)
        inner = (pts - [x, y]) * 0.7 + [x, y]
        cv2.fillConvexPoly(lay, np.int32(np.round(inner * 8)), (GLASS[0] / 255, GLASS[1] / 255, GLASS[2] / 255, 1.0),
                           cv2.LINE_AA, 3)
    a = lay[..., 3:4] * (1 - sm((u - life + 0.3) / 0.3))
    return img * (1 - a) + lay[..., :3] * a


def impact(img, t, t0, M, sc, kind, big):
    u = t - t0
    hx, hy = hit_point(kind)
    X, Y = P(M, hx, hy)
    img = shards(img, t, t0, X, Y, sc * 1.1, 34 if big else 22, 7 if big else 3, 1.4 if big else 1.0)
    if kind == "cracked":                                   # the car bounces off and drops onto the unit
        img = car_after(img, t, M, sc)
    if 0 <= u < 0.45:                                       # the shake, dying away
        k = math.exp(-u * 9) * (26 if big else 16) * RS
        rng = np.random.default_rng(int(t * FPS))
        dx, dy = rng.uniform(-1, 1, 2) * k
        z = 1 + 0.035 * math.exp(-u * 10)
        A = np.float32([[z, 0, OW / 2 * (1 - z) + dx], [0, z, OH / 2 * (1 - z) + dy]])
        img = cv2.warpAffine(img, A, (OW, OH), borderMode=cv2.BORDER_REFLECT)
    if 0 <= u < 2.5 / FPS:                                  # the flash: two frames
        img = img * 0.15 + 0.85 * (1.0 if u < 1 / FPS else 0.55)
    return img


CAR_REST = (668, 586)                                       # the car where it lands, on the unit under the screen


def car_after(img, t, M, sc):
    u = t - m("smash1")
    if u < 0:
        return img
    hx, hy = hit_point("cracked")
    w = 0.24 * _ppm(CAR_REST[1] + 170)
    if u < 0.55:
        q = u / 0.55
        x = hx + (CAR_REST[0] - hx) * q
        y = hy + (CAR_REST[1] - 12 - hy) * q * q - 30 * math.sin(math.pi * q) * (1 - q)
        ang = 200 * q
    else:
        b = u - 0.55
        x, y = CAR_REST[0], CAR_REST[1] - 12 - 14 * abs(math.sin(b * 9)) * math.exp(-b * 6)
        ang = 180 + 8 * math.exp(-b * 5) * math.sin(b * 14)
    return sprite(img, "toy-car", *P(M, x, y), w * sc, ang)


def fallen_car(img, s, t, M, sc):
    return sprite(img, "toy-car", *P(M, CAR_REST[0], CAR_REST[1] - 12), 0.24 * _ppm(CAR_REST[1] + 170) * sc, 180)


def impact1(img, s, t, M, sc):
    return impact(img, t, m("smash1"), M, sc, "cracked", False)


def impact2(img, s, t, M, sc):
    return impact(img, t, m("smash2"), M, sc, "smashed", True)


def falling1(img, s, t, M, sc):
    """the close-up after the first smash: the car settles on the unit, one shard drops out of the crack"""
    img = car_after(img, t, M, sc)
    t0 = m("cut_crack1") + 0.45
    u = t - t0
    hx, hy = hit_point("cracked")
    if u < 0:
        x, y, ang = hx + 6, hy + 4, 0
    else:
        x, y, ang = hx + 6 + 10 * u, hy + 4 + 600 * u * u, 260 * u
    if y > 640:
        return img
    X, Y = P(M, x, y)
    pts = np.float32([(-1, -0.6), (1.1, -0.2), (-0.1, 1.0)]) * 7 * sc / 2
    c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = pts @ np.float32([[c, s_], [-s_, c]]) + [X, Y]
    lay = np.zeros((OH, OW, 4), np.float32)
    cv2.fillConvexPoly(lay, np.int32(np.round(pts * 8)), (INK[0] / 255, INK[1] / 255, INK[2] / 255, 1), cv2.LINE_AA, 3)
    inner = (pts - [X, Y]) * 0.68 + [X, Y]
    cv2.fillConvexPoly(lay, np.int32(np.round(inner * 8)), (0.75, 0.84, 0.92, 1), cv2.LINE_AA, 3)
    a = lay[..., 3:4]
    return img * (1 - a) + lay[..., :3] * a


def falling2(img, s, t, M, sc):
    """the close-up after the second smash: glass still raining out of the hole"""
    hx, hy = hit_point("smashed")
    X, Y = P(M, hx, hy)
    for k, dt in enumerate((0.0, 0.35, 0.7)):
        img = shards(img, t, m("cut_crack2") + dt - 0.2, X + (k - 1) * 60 * RS, Y + 80 * RS, sc / 3.0, 9, 20 + k,
                     0.35, 1.2)
    return img


# ---------------------------------------------------------------- the rest of the props
def vroom(img, s, t, M, sc):
    """the toy car rolling across the floor to the foot of the telly unit, a wobble on the bumps in the rug"""
    u = (t - s["t"]) / (s["end"] - s["t"])
    q = 1 - (1 - min(1.0, u * 1.25)) ** 2
    x = 400 + (640 - 400) * q
    y = 708 - 4 * abs(math.sin(u * 22)) * (1 - q)
    return sprite(img, "toy-car", *P(M, x, y), 0.24 * _ppm(780) * sc, 2 * math.sin(u * 30) * (1 - q), flip=True)


def toy_box(img, s, t, M, sc):
    from film.direction import ppm_at
    return sprite(img, "toy-box", *P(M, 570, 770 - 0.15 * ppm_at("TW", 770)), 0.5 * ppm_at("TW", 770) * sc)


def sparkle(img, s, t, M, sc):
    """the new telly: a shine sweeps across the screen and a few twinkles"""
    u = t - s["t"]
    quad = np.float32([P(M, x, y) for x, y in SCREEN])
    inside = np.zeros((OH, OW), np.float32)
    cv2.fillConvexPoly(inside, np.int32(np.round(quad * 8)), 1.0, cv2.LINE_AA, 3)
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    x0 = quad[:, 0].min() - 300 * RS + (quad[:, 0].max() - quad[:, 0].min() + 600 * RS) * sm((u - 0.2) / 1.0)
    band = np.exp(-(((xx + (yy - quad[:, 1].mean()) * 0.6) - x0) / (60 * RS)) ** 2)
    img = img + (band * inside)[..., None] * 0.35
    lay = np.zeros((OH, OW, 4), np.float32)
    for k, (fx, fy, t0) in enumerate(((0.2, 0.25, 0.5), (0.8, 0.2, 0.9), (0.62, 0.7, 1.3), (0.3, 0.66, 1.7))):
        v = u - t0
        if 0 <= v < 0.6:
            p = quad[0] * (1 - fx) * (1 - fy) + quad[1] * fx * (1 - fy) + quad[2] * fx * fy + quad[3] * (1 - fx) * fy
            r = 22 * RS * math.sin(math.pi * v / 0.6)
            for ang in (0, 90):
                c, s_ = math.cos(math.radians(ang + 45 * v)), math.sin(math.radians(ang + 45 * v))
                pts = np.float32([(r, 0), (0, r * 0.18), (-r, 0), (0, -r * 0.18)]) @ np.float32([[c, s_], [-s_, c]])
                cv2.fillConvexPoly(lay, np.int32(np.round((pts + p) * 8)), (1, 1, 0.92, 1), cv2.LINE_AA, 3)
    return img * (1 - lay[..., 3:4]) + lay[..., :3]


PROJECTOR = (330, 58)                                      # the projector on the ceiling (1x plate px)


def projection(img, s, t, M, sc):
    """the projector hung from the ceiling and its beam to the picture on the wall"""
    c = SCREEN.mean(0)
    quad = c + (SCREEN - c) * np.float32([1.22, 1.18])
    lx, ly = P(M, PROJECTOR[0] + 26, PROJECTOR[1] + 8)
    q = [P(M, x, y) for x, y in quad]
    beam = np.zeros((OH, OW), np.float32)
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        cv2.fillConvexPoly(beam, np.int32(np.round(np.float32([(lx, ly), q[a], q[b]]) * 8)), 1.0, cv2.LINE_AA, 3)
    beam = cv2.GaussianBlur(beam, (0, 0), 6 * RS)
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    fall = np.clip(1 - np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / (900 * RS * sc / 2), 0.25, 1)
    img = img + (beam * fall)[..., None] * np.float32([0.16, 0.15, 0.12])
    # the projector: a white box on a pole from the ceiling, a dark lens, the ink outline
    pil = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(pil)
    X, Y = P(M, *PROJECTOR)
    k = sc / 2.0
    lw = max(2, int(5 * k))
    dr.rectangle((X - 4 * k, Y - 80 * k, X + 4 * k, Y - 18 * k), fill=(70, 70, 76), outline=INK, width=lw)
    dr.rounded_rectangle((X - 34 * k, Y - 20 * k, X + 30 * k, Y + 14 * k), radius=int(8 * k), fill=(236, 236, 232),
                         outline=INK, width=lw)
    dr.ellipse((X + 14 * k, Y - 13 * k, X + 40 * k, Y + 9 * k), fill=(40, 44, 54), outline=INK, width=lw)
    dr.ellipse((X + 22 * k, Y - 7 * k, X + 30 * k, Y + 1 * k), fill=(250, 250, 220))
    return G.over(img, G.premult(pil))


def wheel(lay, s, t, ex, ey, ed, st):
    """the steering wheel in front of Dad, low in the frame, turning a little with the road"""
    ang = 6 * math.sin(t * 0.9) + 3 * math.sin(t * 2.3)
    cx, cy = ex + 0.25 * ed, ey + 3.5 * ed
    R = 2.0 * ed
    pil = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(pil)
    w = int(0.3 * ed)
    dr.ellipse((cx - R, cy - R, cx + R, cy + R), outline=INK, width=w + int(0.12 * ed))
    dr.ellipse((cx - R + 0.06 * ed, cy - R + 0.06 * ed, cx + R - 0.06 * ed, cy + R - 0.06 * ed), outline=(52, 52, 58),
               width=w)
    for a in (ang - 90, ang + 30, ang + 150):
        x2, y2 = cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))
        dr.line((cx, cy, x2, y2), fill=INK, width=int(0.36 * ed))
        dr.line((cx, cy, x2, y2), fill=(60, 60, 66), width=int(0.22 * ed))
    lay[:] = G.premult(pil) + lay * (1 - G.premult(pil)[..., 3:4])


# ---------------------------------------------------------------- inserts
@functools.lru_cache(maxsize=4)
def _shop_bg():
    big = _base("street/electronics-shop-tv-aisle")
    h, w = big.shape[:2]
    crop = big[int(h * 0.42):int(h * 0.42) + int(w * 9 / 16), :]
    crop = cv2.resize(crop, (OW, OH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return cv2.GaussianBlur(crop, (0, 0), 14 * RS) * 0.85


def reader(s, t):
    """the card reader on the shop counter: £799.00... a card taps... beep: APPROVED"""
    u = t - s["t"]
    tb = m("beep") - s["t"]
    img = _shop_bg().copy()
    k = RS * (1 + 0.03 * sm(u / 2.4))
    pil = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(pil)
    cx, cy = OW / 2 - 40 * k, OH / 2 + 30 * k
    W2, H2 = 300 * k, 430 * k
    lw = int(9 * k)
    dr.rounded_rectangle((cx - W2, cy - H2, cx + W2, cy + H2), radius=int(60 * k), fill=(58, 62, 70), outline=INK,
                         width=lw)
    sx0, sy0, sx1, sy1 = cx - W2 + 50 * k, cy - H2 + 60 * k, cx + W2 - 50 * k, cy - 40 * k
    ok = u >= tb
    dr.rounded_rectangle((sx0, sy0, sx1, sy1), radius=int(22 * k), fill=(196, 236, 196) if ok else (206, 222, 214),
                         outline=INK, width=int(6 * k))
    f_big = G.font(G.BEBAS, 150 * k)
    f_small = G.font(G.BEBAS, 62 * k)

    def ctext(txt, f, y, col):
        tw = dr.textlength(txt, font=f)
        dr.text(((sx0 + sx1) / 2 - tw / 2, y), txt, font=f, fill=col)

    if not ok:
        ctext("TOTAL", f_small, sy0 + 30 * k, (60, 70, 66))
        ctext("£799.00", f_big, sy0 + 100 * k, INK)
    else:
        ctext("£799.00", f_small, sy0 + 26 * k, (60, 90, 66))
        ctext("APPROVED", G.font(G.BEBAS, 128 * k), sy0 + 110 * k, (24, 120, 52))
    for r in range(3):
        for c in range(3):
            bx, by = cx - 150 * k + c * 150 * k, cy + 70 * k + r * 95 * k
            dr.rounded_rectangle((bx - 52 * k, by - 32 * k, bx + 52 * k, by + 32 * k), radius=int(14 * k),
                                 fill=(222, 224, 228), outline=INK, width=int(5 * k))
    img = G.over(img, G.premult(pil))
    # the card comes in from the right, taps the screen on the beep, and goes
    v = sm((u - (tb - 0.75)) / 0.55) - sm((u - (tb + 0.35)) / 0.5)
    if v > 0:
        pil = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        dr = ImageDraw.Draw(pil)
        x = OW + 200 * k - (OW + 200 * k - (cx + W2 + 150 * k)) * v
        y = cy - H2 + 60 * k
        dr.rounded_rectangle((x - 210 * k, y - 130 * k, x + 210 * k, y + 130 * k), radius=int(24 * k),
                             fill=(40, 92, 190), outline=INK, width=int(8 * k))
        dr.rounded_rectangle((x - 150 * k, y - 50 * k, x - 70 * k, y + 10 * k), radius=int(8 * k), fill=(232, 196, 92),
                             outline=INK, width=int(4 * k))
        dr.text((x - 150 * k, y + 40 * k), "DAD", font=G.font(G.BEBAS, 60 * k), fill=(230, 236, 250))
        lay = G.premult(pil)
        img = G.over(img, lay)
    if ok and u - tb < 0.25:                                # the beep: a flash on the screen
        img = img + 0.12 * (1 - (u - tb) / 0.25)
    return img


def _card(s, t, text, sub, c0, c1):
    """a time card: a slowly turning sunburst, the words slammed in with the ink outline"""
    u = t - s["t"]
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    ang = np.arctan2(yy - OH / 2, xx - OW / 2) + u * 0.25
    rays = (np.sin(ang * 14) > 0).astype(np.float32)[..., None]
    img = np.float32(c0) / 255 * (1 - rays) + np.float32(c1) / 255 * rays
    r = np.sqrt(((xx - OW / 2) / OW) ** 2 + ((yy - OH / 2) / OH) ** 2)[..., None]
    img = img * (1 - 0.5 * np.clip(r - 0.15, 0, 1))
    pil = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(pil)
    f = G.font(G.BEBAS, 190 * RS)
    tw = dr.textlength(text, font=f)
    dr.text((OW / 2 - tw / 2, OH / 2 - 150 * RS), text, font=f, fill=(255, 255, 255), stroke_width=int(12 * RS),
            stroke_fill=INK)
    if sub:
        f2 = G.font(G.BEBAS, 70 * RS)
        tw = dr.textlength(sub, font=f2)
        dr.text((OW / 2 - tw / 2, OH / 2 + 70 * RS), sub, font=f2, fill=(255, 240, 200), stroke_width=int(6 * RS),
                stroke_fill=INK)
    lay = G.premult(pil)
    sc = 1 + 0.6 * (1 - sm(u / 0.16)) + 0.03 * u
    sh = G.shadow_of(lay, 10, (8, 12), 0.5)[..., None]
    img = img * (1 - sh)
    return G.over(img, G.scaled(lay, sc, OW / 2, OH / 2))


def card_weeks(s, t):
    return _card(s, t, "TWO WEEKS LATER", "THE TELLY IS STILL ALIVE", (246, 170, 60), (240, 150, 44))


def card_minutes(s, t):
    return _card(s, t, "TWO MINUTES LATER", "", (90, 150, 230), (70, 130, 214))
