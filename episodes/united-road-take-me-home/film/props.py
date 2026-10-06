"""The pub stage for the video: the plates with their baked-in mic stand painted out (the band brings its own), the
crowd in the foreground of the front view cut out so it can jump on the beat, and the side view's fans."""
import functools

import cv2
import numpy as np

from studio.film import ep

STAGE = "pub-and-restaurant/united-pub-stage"
CROWD = "pub-and-restaurant/united-pub-stage-crowd"
SIDE = "pub-and-restaurant/united-pub-stage-side-crowd"

# the mic stand in the middle of the front view (1x plate px): its head, pole and base
MIC = [[(805, 256), (838, 256), (838, 304), (805, 304)],
       [(811, 298), (830, 298), (830, 541), (811, 541)]]
MIC_BASE = ((822, 547), (37, 12))
# the table with bottles and a candle among the fans of the crowd view: it stays put when the fans jump
TABLE = [(318, 752), (360, 728), (450, 716), (560, 706), (560, 660), (600, 660), (605, 700), (640, 706), (650, 712),
         (700, 704), (712, 710), (800, 742), (808, 790), (770, 820), (690, 836), (560, 842), (430, 838), (350, 822),
         (318, 795)]


def _x4(name):
    from studio.episode.upscale import upscaled
    from studio.paths import BACKGROUNDS
    return upscaled(BACKGROUNDS / f"{name}.png", 4.0)[..., ::-1].copy()          # RGB


def _mic_mask(shape, scale):
    m = np.zeros(shape[:2], np.uint8)
    for poly in MIC:
        cv2.fillPoly(m, [np.int32(np.float32(poly) * scale)], 255)
    (cx, cy), (rx, ry) = MIC_BASE
    cv2.ellipse(m, (int(cx * scale), int(cy * scale)), (int(rx * scale), int(ry * scale)), 0, 0, 360, 255, -1)
    return cv2.dilate(m, np.ones((int(3 * scale) | 1, int(3 * scale) | 1), np.uint8))


def _no_mic(big):
    """the mic stand painted out: inpainted from the curtain, the bass drum's head and the rug round it"""
    m = _mic_mask(big.shape, 4)
    x0, y0, x1, y1 = 760 * 4, 240 * 4, 880 * 4, 570 * 4
    sub = cv2.cvtColor(np.ascontiguousarray(big[y0:y1, x0:x1]), cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(sub, m[y0:y1, x0:x1], 9, cv2.INPAINT_TELEA)
    out = big.copy()
    out[y0:y1, x0:x1] = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)
    return out


@functools.lru_cache(maxsize=4)
def _plate(k):
    cache = ep.path(f"plate_{k}.png")
    if cache.exists():
        return cv2.cvtColor(cv2.imread(str(cache)), cv2.COLOR_BGR2RGB)
    big = _no_mic(_x4(STAGE if k == "F" else CROWD))
    cv2.imwrite(str(cache), cv2.cvtColor(big, cv2.COLOR_RGB2BGR))
    return big


# the back of the pub (what the crowd has behind them, seen from the stage): the windows' glass (1x px)
PUB = "pub-and-restaurant/pub"
WINDOWS = [[(1416, 158), (1492, 158), (1492, 382), (1416, 382)], [(1610, 92), (1672, 92), (1672, 384), (1610, 384)]]


def _pub():
    """the pub at night, the gig on: the windows dark (lit windows across the street), the room dim and warm with
    its own lamps glowing, the stage's red light spilling over the floor and the booths"""
    big = _x4(PUB).astype(np.float32) / 255.0
    H, W = big.shape[:2]
    s1 = cv2.resize(big, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    lum = s1.max(2)
    # the room's own lights: its brightest warm parts (the lamps, the sconces, the fire)
    warm = ((s1[..., 0] > s1[..., 2] + 0.10) & (lum > 0.80)) | (s1.min(2) > 0.93)     # the bulbs burn white
    warm[540:] = False                                       # the floor's sunlight is not a lamp
    warm = cv2.morphologyEx(warm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    lamps = cv2.GaussianBlur(cv2.dilate(warm.astype(np.float32), np.ones((3, 3), np.uint8)), (0, 0), 1.5)
    win = np.zeros((H // 4, W // 4), np.float32)
    for poly in WINDOWS:
        cv2.fillPoly(win, [np.int32(poly)], 1.0)
    win = cv2.GaussianBlur(win, (0, 0), 1.0)
    up = lambda m: cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]   # noqa: E731
    lamps, win = up(lamps), up(win)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    # no sun on the floor at night: the floor's patches of light flattened into the boards around them
    fl = np.clip((yy - 0.55) / 0.05, 0, 1)
    soft = cv2.resize(cv2.GaussianBlur(s1, (0, 0), 15), (W, H), interpolation=cv2.INTER_LINEAR)
    big = big * (1 - fl) + (soft + 0.35 * (big - soft)) * fl
    # dim and warm, a little brighter low down where the stage light reaches
    room = big * (0.30 + 0.16 * yy) * np.float32([1.0, 0.80, 0.72])
    room += (0.10 * yy ** 1.5) * np.float32([0.85, 0.12, 0.08])                    # the stage's red spill
    out = room * (1 - lamps) + big * np.float32([1.0, 0.93, 0.82]) * lamps
    # night outside: the street dark blue, its white window frames lit warm
    L = big.mean(2, keepdims=True)
    night = L * np.float32([0.10, 0.13, 0.28]) + np.clip(L - 0.82, 0, 1) * 4.0 * np.float32([0.95, 0.70, 0.30])
    out = out * (1 - win) + night * win
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def plate_image(k):
    """F: the front view, empty; FC: the same with the fans in the foreground (both without the mic stand); PUB:
    the back of the pub at night, behind the crowd"""
    if k in ("F", "FC"):
        return _plate(k)
    if k == "PUB":
        cache = ep.path("plate_PUB.png")
        if cache.exists():
            return cv2.cvtColor(cv2.imread(str(cache)), cv2.COLOR_BGR2RGB)
        img = _pub()
        cv2.imwrite(str(cache), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        return img
    return None


@functools.lru_cache(maxsize=2)
def fans_image(k="FC"):
    """the fans in the front of the crowd view (where it differs from the empty view, below the stage), without
    the table among them -> RGBA uint8 at 4x"""
    cache = ep.path("fans_FC.png")
    big = _plate("FC")
    if cache.exists():
        a4 = cv2.imread(str(cache), cv2.IMREAD_GRAYSCALE)
    else:
        f1 = cv2.resize(_plate("F"), None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA).astype(np.float32)
        c1 = cv2.resize(big, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA).astype(np.float32)
        d = np.abs(c1 - f1).max(2)
        d = cv2.GaussianBlur(d, (0, 0), 2.0)
        m = (d > 38).astype(np.uint8)
        H, W = m.shape
        zone = np.zeros_like(m)
        cv2.fillPoly(zone, [np.int32([(0, 640), (300, 655), (560, 650), (560, 941), (0, 941)])], 1)
        cv2.fillPoly(zone, [np.int32([(560, 700), (1100, 690), (1250, 640), (1540, 600), (1540, 505), (1672, 505),
                                      (1672, 941), (560, 941)])], 1)
        m &= zone
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        keep = np.zeros_like(m)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] > 1500 and st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT] >= H - 3:
                keep[lab == i] = 1                               # only what reaches the bottom of the frame: people
        # fill holes (between arms and heads)
        inv = 1 - keep
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
        for i in range(1, n2):
            x, y, w, h, a = st2[i]
            if a < 6000 and y > 0 and x > 0 and x + w < W:
                keep[lab2 == i] = 1
        t = np.zeros_like(keep)
        cv2.fillPoly(t, [np.int32(TABLE)], 1)
        keep[t > 0] = 0
        a1 = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 1.6)
        a4 = (cv2.resize(a1, (big.shape[1], big.shape[0]), interpolation=cv2.INTER_LINEAR) * 255).astype(np.uint8)
        cv2.imwrite(str(cache), a4)
    return np.dstack([big, a4])


# ---------------------------------------------------------------- the opening title, over the room in the dark
def title_over(img, s, t, M, sc):
    """UNITED ROAD / TAKE ME HOME over the dark room, gone as the lights come up"""
    from studio.film import graphics as G
    from film.direction import TITLE, b
    u = t - s["t"]
    k = G.sm((u - 0.4) / 0.6) * (1 - G.sm((t - (b(1, 0.75))) / 0.35))
    if k <= 0:
        return img
    lay = G.text_layer(TITLE)
    sh = G.shadow_of(lay, 14, (0, 6), 0.6)
    img = img * (1 - sh[..., None] * k)
    return G.over(img, lay, k)
