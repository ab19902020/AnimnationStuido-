"""Music videos: a band on a stage and a crowd, every one of them moving to the song (studio/film/song.py).

A stage shot (studio.film.shots.stage) is a camera in a plate, as a world shot is, with these layers in order:

  ("actors", [actor, ...])   drawings placed by their feet and height in plate px (or, screen=True, in 1920 x 1080
                             layout px: the crowd in close shots, the set blurred behind). An actor is a dict:
        who, draw            the performer (perf.py) and the drawing ("<character id>:<drawing>")
        feet, h              where the soles are and how tall the drawing stands
        mirror, clip         flipped; faded out below this y (plate px, or layout px when screen)
        inst                 "guitar", "bass" or "keys": the instrument is hung on the drawing's own hands, which
                             are put back over it; the arms are warped (never cut) so the strumming hand moves on
                             the eighth notes and the fretting hand slides up and down the neck
        mic                  a mic stand at the mouth (True, or {"side": -1 / 1, "drop": eye distances below})
        dance                scale of the groove (1 by default; 0: stands still)
        blur                 out of focus (px at 1920): the players the lens is not on
        eye, ed              (screen actors) placed by the point between the eyes and the eye distance (layout px)
                             instead of feet and height, so heads match whatever a drawing's proportions
  ("occl", mask)             the plate's own furniture in front (the drum kit, the monitors), sharp (or blurred
                             with the shot's "occl_blur" when the lens is on someone behind it)
  ("sticks", spec)           the drummer's sticks in his fists (spec: grips, drums (plate px), len, h, fist: a
                             drawing of his fist, blur): the left stick keeps the eighth notes on the hi-hat and
                             takes the snare on the strong backbeats, the right keeps time and takes the toms, both
                             go to the cymbals on the crashes; accents are played from higher up
  ("fans", key)              a foreground crowd cut from a plate (props.fans_image(key)), jumping on the beat
  ("fg_fans", opt)           a front row of fans in silhouette between the lens and a crowd shot's people: heads,
                             fists pumping on the beat, a scarf held up; out of focus, rimmed by the stage light
  ("props", fn)              an episode function fn(img, shot, t, M, scale) -> img (and the shot's "props":
                             overlays drawn over everything, like a title)

and, over the picture: the plate's lamps and beams pulsing with the kick (shot "lights": 0..1), beams swinging
through haze (LAMPS in direction.py), a flash on the crashes, a strobe in STROBE spans, a camera punch on the kick
("punch") and a shake ("shake"), a roll (the fourth number of a camera key), the "stage" grade with bloom.

Dancing (perf.py's GROOVE = Groove({who: [(t0, t1, move, amount)]})): bounce (a knee dip on every beat), sway
(side to side over two beats), headbang, jump (every beat) / hop (every other beat), rock (a guitarist's lean on
the bar with a bounce), nod, pump (an up-beat stretch), shuffle (a side step), lean (degrees, held). Each performer
is a few milliseconds off the grid, as people are. The singers' mouths: sing(PERF, ...) writes the lead vocal's
mouth track into a performer's lip sync for the spans they sing."""
import functools
import importlib
import math

import cv2
import numpy as np
from PIL import Image

from studio.film import engine as E
from studio.film.cast import CAST, feet as feet_of, hands as hands_of
from studio.film.engine import FPS, OH, OW, RS
from studio.paths import PROPS

INK = tuple(float(v) for v in np.float32([24, 20, 22]) / 255.0)


def _R():
    return importlib.import_module("studio.film.render")


@functools.lru_cache(maxsize=1)
def SONG():
    from studio.film import ep
    from studio.film.song import Song
    return Song(ep.path("song.json"))


def sm(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ramp(t, a, b, fin=0.25, fout=0.25):
    return sm((t - a) / max(1e-3, fin)) * (1 - sm((t - b) / max(1e-3, fout)))


# ---------------------------------------------------------------- dancing
class Groove:
    """spans of dance moves per performer: {who: [(t0, t1, move, amount)]}"""

    def __init__(self, spans, song=None):
        self.spans = spans
        self.song = song
        self.k = {w: i for i, w in enumerate(sorted(spans))}

    def at(self, who, t):
        S = self.song or SONG()
        out = dict(rot=0.0, sx=1.0, sy=1.0, jump=0.0, dx=0.0, nod=0.0, tilt=0.0)
        if who not in self.spans:
            return out
        k = self.k[who]
        tt = t - 0.012 * ((k * 7) % 5 - 2)                  # a few ms off the grid, each their own way
        p = S.phase(tt)
        bi = S.beat_index(tt)
        pos = bi + p                                         # beats since the start
        for t0, t1, move, a in self.spans[who]:
            w = ramp(t, t0, t1, 0.3, 0.3) * a
            if w <= 1e-3:
                continue
            beat = 0.5 + 0.5 * math.cos(2 * math.pi * p)    # 1 on the beat, 0 between
            hit = math.exp(-p * 7.0)                         # the instant of the beat
            if move == "bounce":
                out["sy"] -= 0.026 * w * beat
                out["sx"] += 0.010 * w * beat
                out["nod"] += 4.5 * w * beat
            elif move == "sway":
                out["rot"] += 2.8 * w * math.sin(math.pi * pos + k)
                out["tilt"] += 2.0 * w * math.sin(math.pi * pos + k + 0.6)
            elif move == "headbang":
                d = max(0.0, math.cos(2 * math.pi * p)) ** 1.6
                out["nod"] += 17.0 * w * d
                out["sy"] -= 0.014 * w * d
                out["tilt"] += 3.0 * w * math.sin(math.pi * pos)
            elif move in ("jump", "hop"):
                u = p if move == "jump" else ((bi % 2) + p) / 2
                out["jump"] += 0.075 * w * math.sin(math.pi * u) ** 0.8
                land = math.exp(-u * 10.0)
                out["sy"] -= 0.05 * w * land
                out["sx"] += 0.02 * w * land
                out["nod"] += 6.0 * w * land
            elif move == "rock":
                out["sy"] -= 0.020 * w * beat
                out["rot"] += 2.4 * w * math.sin(math.pi * pos / 2 + k)
                out["nod"] += 7.0 * w * beat
                out["tilt"] += 2.5 * w * math.sin(math.pi * pos / 2 + k + 1.0)
            elif move == "nod":
                out["nod"] += 5.5 * w * beat
            elif move == "pump":
                out["sy"] += 0.022 * w * hit
                out["jump"] += 0.012 * w * hit
                out["nod"] -= 3.0 * w * hit
            elif move == "shuffle":
                out["dx"] += 0.035 * w * math.sin(math.pi * pos + k)
                out["sy"] -= 0.012 * w * beat
            elif move == "lean":
                out["rot"] += w
        return out


def groove_matrix(g, foot, H):
    """the dance as a 2x3 sheet-px transform about the feet (H: the drawing's height, sheet px)"""
    fx, fy = foot
    th = math.radians(g["rot"])
    c, s = math.cos(th), math.sin(th)
    A = np.array([[c, -s], [s, c]]) @ np.diag([g["sx"], g["sy"]])
    B = np.zeros((2, 3))
    B[:, :2] = A
    B[:, 2] = np.array([fx, fy]) - A @ np.array([fx, fy]) + np.array([g["dx"] * H, -g["jump"] * H])
    return B


def compose(Ms, B):
    out = np.zeros((2, 3))
    out[:, :2] = Ms[:, :2] @ B[:, :2]
    out[:, 2] = Ms[:, :2] @ B[:, 2] + Ms[:, 2]
    return out


def apply(M, x, y):
    return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])


@functools.lru_cache(maxsize=None)
def top_of(key):
    d, _ = CAST.get(key)
    a = d.u8[1.0][..., 3] > 128
    ys = np.nonzero(a.any(1))[0]
    return float(ys.min() / d.S + d.oy)


# ---------------------------------------------------------------- singing
def sing(perf, who, spans, track="lead", gain=1.0, lag=0):
    """the song's mouth track into a performer's lip sync for the spans they sing: [(t0, t1)] (seconds);
    gain scales how wide the mouth opens (a crowd singing along opens less than the singer), lag in frames"""
    S = SONG()
    tr = getattr(S, track)
    for t0, t1 in spans:
        f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
        for f in range(max(0, f0), min(perf.N, f1)):
            v, a = tr[min(len(tr) - 1, max(0, f - lag))]
            e = ramp(f / FPS, t0, t1, 0.12, 0.12)
            if e < 0.3:
                v = "REST"
            perf.VIS[who][f] = v
            perf.AMP[who][f] = max(0.35, a * gain * (0.4 + 0.6 * e))
            perf.TALK[who][f] = v != "REST"


# ---------------------------------------------------------------- props: instruments, mic stands, sticks
INSTRUMENTS = {
    # image (library/props), the strings' axis (tail -> nut), where the strumming hand sits, the strap button on
    # the upper horn, the instrument's length as a share of the player's height, the neck's rise (deg)
    "guitar": dict(img="music/electric-guitar", tail=(128, 640), nut=(125, 75), strum=(128, 552), horn=(205, 400),
                   length=0.50, tilt=9.0, strum_amp=0.45),
    "bass": dict(img="music/bass-guitar", tail=(128, 655), nut=(125, 128), strum=(126, 598), horn=(52, 415),
                 length=0.60, tilt=9.0, strum_amp=0.30),
    "keys": dict(img="music/keyboard-on-stand", keys_y=108, x0=48, x1=668, width=0.62),
    "mic": dict(img="music/microphone-stand", grille=(55, 32), base=(87, 543)),
}


@functools.lru_cache(maxsize=None)
def prop_image(name, mirror=False):
    im = np.asarray(Image.open(PROPS / f"{name}.png").convert("RGBA")).astype(np.float32) / 255.0
    if mirror:
        im = im[:, ::-1].copy()
    im[..., :3] *= im[..., 3:4]
    return im


def warp_region(lay, x0, y0, x1, y1, fx, fy):
    """move pixels of a layer inside a box by a displacement field (fx, fy: arrays the box's size): output pixel
    p takes the pixel at p - d(p)"""
    H, W = lay.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    sub = lay[y0:y1, x0:x1]
    Y, X = np.mgrid[0:y1 - y0, 0:x1 - x0].astype(np.float32)
    mx = X - fx[:y1 - y0, :x1 - x0]
    my = Y - fy[:y1 - y0, :x1 - x0]
    lay[y0:y1, x0:x1] = cv2.remap(sub, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def move_hand(lay, hx, hy, r, dx, dy, out_sign):
    """move a hanging hand (screen px) by (dx, dy), its forearm bending with it: the displacement is whole at the
    hand and fades up the arm (to the elbow) and fast towards the body (out_sign: +1 if the outside of the arm is
    to the right)"""
    if abs(dx) + abs(dy) < 0.3:
        return
    m = int(r * 4.5 + abs(dx) + abs(dy))
    x0, y0, x1, y1 = int(hx - m), int(hy - m * 1.6), int(hx + m), int(hy + m * 0.8)
    Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    u = (X - hx) / (1.25 * r)
    v = np.where(Y < hy, (Y - hy) / (3.2 * r), (Y - hy) / (1.1 * r))
    w = np.exp(-(u * u + v * v))
    inward = (hx - X) * out_sign                             # > 0 towards the body
    w *= np.clip(1 - (inward - 0.55 * r) / (0.6 * r), 0, 1)
    warp_region(lay, x0, y0, x1, y1, (w * dx).astype(np.float32), (w * dy).astype(np.float32))


def hand_cover(lay, dst, hx, hy, r, up=2.4):
    """the hand (and the forearm above it) from the performer's own layer, put over what was drawn on top of it
    (the instrument): a feathered capsule from the hand up the arm"""
    m = int(r * 1.6)
    x0, y0, x1, y1 = int(hx - m), int(hy - r * up - m * 0.3), int(hx + m), int(hy + m)
    H, W = lay.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    cy = np.clip(Y, hy - r * up, hy)
    d = np.sqrt((X - hx) ** 2 + (Y - cy) ** 2) / (1.08 * r)
    w = np.clip((1.0 - d) / 0.18, 0, 1)
    w *= np.clip((Y - (hy - r * up)) / (0.9 * r), 0, 1)       # fades out up the arm: no seam where it leaves
    src = lay[y0:y1, x0:x1] * w[..., None]
    reg = dst[y0:y1, x0:x1]
    dst[y0:y1, x0:x1] = src + reg * (1 - src[..., 3:4])


def strap(dst, p0, p1, width):
    """a guitar strap from the strap button over the shoulder (screen px)"""
    H, W = dst.shape[:2]
    x0, y0 = int(min(p0[0], p1[0]) - 2 * width), int(min(p0[1], p1[1]) - 2 * width)
    x1, y1 = int(max(p0[0], p1[0]) + 2 * width), int(max(p0[1], p1[1]) + 2 * width)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    S = 4
    im = np.zeros(((y1 - y0) * S, (x1 - x0) * S, 4), np.float32)
    a = (int((p0[0] - x0) * S), int((p0[1] - y0) * S))
    b = (int((p1[0] - x0) * S), int((p1[1] - y0) * S))
    cv2.line(im, a, b, (*INK, 1.0), int(width * S + 3 * RS * S), cv2.LINE_AA)
    cv2.line(im, a, b, (0.12, 0.11, 0.12, 1.0), int(width * S), cv2.LINE_AA)
    cv2.line(im, a, b, (0.55, 0.06, 0.08, 1.0), max(1, int(width * S * 0.25)), cv2.LINE_AA)   # a red stitch line
    im = cv2.resize(im, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    reg = dst[y0:y1, x0:x1]
    dst[y0:y1, x0:x1] = im + reg * (1 - im[..., 3:4])


def place_prop(dst, name, A, mirror=False):
    E.warp_into(dst, prop_image(name, mirror), A.astype(np.float32))


def similarity(src_a, src_b, dst_a, dst_b):
    """the 2x3 rotation + uniform scale + shift taking points src_a, src_b to dst_a, dst_b"""
    sa, sb, da, db = (np.array(v, np.float64) for v in (src_a, src_b, dst_a, dst_b))
    vs, vd = sb - sa, db - da
    k = np.linalg.norm(vd) / max(1e-6, np.linalg.norm(vs))
    r = math.atan2(vd[1], vd[0]) - math.atan2(vs[1], vs[0])
    c, s = math.cos(r) * k, math.sin(r) * k
    A = np.array([[c, -s, 0.0], [s, c, 0.0]])
    A[:, 2] = da - A[:, :2] @ sa
    return A


def play_strings(lay, inst, Ms2, key, t, mirror, H_screen, playing):
    """a guitar or bass hung on the drawing's hands -> (the layer with the instrument and the hands over it)"""
    spec = INSTRUMENTS[inst]
    S = SONG()
    hs = hands_of(key)
    if "R" not in hs or "L" not in hs:
        return lay
    d, _ = CAST.get(key)
    kscr = math.sqrt(abs(np.linalg.det(Ms2[:, :2])))
    hR = apply(Ms2, hs["R"][0], hs["R"][1])
    hL = apply(Ms2, hs["L"][0], hs["L"][1])
    r = hs["R"][2] * kscr
    # the neck rises towards the fretting hand, which is lifted onto it; the strumming hand strums on the eighths
    span = hL[0] - hR[0]
    sgn = 1.0 if span > 0 else -1.0
    lift = abs(span) * math.tan(math.radians(spec["tilt"]))
    pos = S.beat_index(t) + S.phase(t)
    strum = -spec["strum_amp"] * r * math.cos(2 * math.pi * 2 * pos) * playing
    slide = 0.25 * r * math.sin(2 * math.pi * pos / 8) * playing
    out_R = -sgn                                             # the outside of the strumming arm
    move_hand(lay, hR[0], hR[1], r, 0.0, strum, out_R)
    move_hand(lay, hL[0], hL[1], r, slide * sgn, -lift, sgn)
    hR2 = (hR[0], hR[1] + strum)
    hL2 = (hL[0] + slide * sgn, hL[1] - lift)
    # the instrument: its strum point under the strumming hand, its strings along the line to the fretting hand
    tail, nut, st = np.array(spec["tail"], float), np.array(spec["nut"], float), np.array(spec["strum"], float)
    img = prop_image(spec["img"], mirror=False)
    Lpx = img.shape[0]
    scale = spec["length"] * H_screen / Lpx
    direction = np.array([hL2[0] - hR[0], hL[1] - lift - hR[1]])
    direction /= max(1e-6, np.linalg.norm(direction))
    # the strings run from the strum point towards the nut: map (strum -> hand R) and (strum + axis -> along dir)
    axis = (nut - tail) / np.linalg.norm(nut - tail)
    A = similarity(st, st + axis * 100.0, (hR[0], hR[1] + 0.25 * r), (hR[0] + direction[0] * 100 * scale,
                                                                       hR[1] + 0.25 * r + direction[1] * 100 * scale))
    if sgn < 0:                                              # neck to the left: the guitar seen from its other side
        flipx = np.array([[-1.0, 0, img.shape[1]], [0, 1.0, 0], [0, 0, 1.0]])
        A = (np.vstack([A, [0, 0, 1]]) @ flipx)[:2]
        A = similarity((img.shape[1] - st[0], st[1]), (img.shape[1] - st[0] - axis[0] * 100, st[1] + axis[1] * 100),
                       (hR[0], hR[1] + 0.25 * r), (hR[0] + direction[0] * 100 * scale, hR[1] + 0.25 * r + direction[1] * 100 * scale))
        name_mirror = True
    else:
        name_mirror = False
    out = lay.copy()
    # the strap: from the horn's strap button up over the far shoulder
    horn = np.array(spec["horn"], float)
    if name_mirror:
        horn = np.array([img.shape[1] - horn[0], horn[1]])
    hb = apply(A, horn[0], horn[1])
    top = top_of(key)
    sh_y = top + 0.42 * (feet_of(key)[1] - top)
    shoulder = apply(Ms2, hs["L"][0] - 0.25 * (hs["L"][0] - hs["R"][0]), sh_y)
    strap(out, hb, shoulder, max(2.0, 0.22 * r))
    place_prop(out, spec["img"], A, mirror=name_mirror)
    hand_cover(lay, out, hR2[0], hR2[1], r)
    hand_cover(lay, out, hL2[0], hL2[1], r)
    return out


def play_keys(lay, Ms2, key, t, playing):
    spec = INSTRUMENTS["keys"]
    S = SONG()
    hs = hands_of(key)
    if "R" not in hs or "L" not in hs:
        return lay
    kscr = math.sqrt(abs(np.linalg.det(Ms2[:, :2])))
    hR = apply(Ms2, hs["R"][0], hs["R"][1])
    hL = apply(Ms2, hs["L"][0], hs["L"][1])
    r = hs["R"][2] * kscr
    pos = S.beat_index(t) + S.phase(t)
    out = lay.copy()
    for (hx, hy), ph, sg in ((hR, 0.0, -1.0), (hL, 0.5, 1.0)):
        press = 0.16 * r * max(0.0, math.cos(2 * math.pi * (2 * pos + ph))) ** 2 * playing
        reach = -0.35 * r * sg                                # hands reach in a little, over the keys
        move_hand(lay, hx, hy, r, reach, press - 0.15 * r, sg)
    img = prop_image(spec["img"])
    width = abs(hL[0] - hR[0]) * 1.9
    scale = width / (spec["x1"] - spec["x0"])
    cxm = (hR[0] + hL[0]) / 2
    keys_y = (hR[1] + hL[1]) / 2 + 0.55 * r
    A = np.array([[scale, 0, cxm - scale * (spec["x0"] + spec["x1"]) / 2], [0, scale, keys_y - scale * spec["keys_y"]]])
    place_prop(out, spec["img"], A)
    hand_cover(lay, out, hR[0] - 0.35 * r * -1, hR[1] - 0.15 * r, r, up=1.8)
    hand_cover(lay, out, hL[0] - 0.35 * r, hL[1] - 0.15 * r, r, up=1.8)
    return out


def mic_stand(dst, Ms2, key, foot_screen, opt):
    """a mic stand in front of a singer, its grille at the mouth (a little to one side and below, so the mouth
    shows)"""
    d, info = CAST.get(key)
    spec = INSTRUMENTS["mic"]
    mo = d.spec.get("mouth")
    if not mo:
        return
    kscr = math.sqrt(abs(np.linalg.det(Ms2[:, :2])))
    side = opt.get("side", -1.0) if isinstance(opt, dict) else -1.0
    drop = opt.get("drop", 0.55) if isinstance(opt, dict) else 0.55
    mx, my = apply(Ms2, mo[4], mo[5])
    ed = info["ed"] * kscr
    gx, gy = mx + side * 0.62 * ed, my + drop * ed
    fx, fy = foot_screen
    scale = (fy + 0.02 * ed - gy) / (spec["base"][1] - spec["grille"][1])
    mirror = side > 0
    img = prop_image(spec["img"], mirror)
    gsx = img.shape[1] - spec["grille"][0] if mirror else spec["grille"][0]
    A = np.array([[scale, 0, gx - scale * gsx], [0, scale, gy - scale * spec["grille"][1]]])
    place_prop(dst, spec["img"], A, mirror=mirror)


def drumsticks(dst, t, M, spec, H_screen):
    """two sticks played from the song's hits (plate px positions through M), each in a fist (spec["fist"]: a
    drawing of the drummer's fist) whose forearm drops behind the drums: the left stick keeps the eighth notes on
    the hi-hat and takes the snare on strong backbeats, the right stick the toms; both go to the cymbals on the
    crashes"""
    S = SONG()
    L = spec.get("len", 0.33) * H_screen
    dr = {k: apply(M, *v) for k, v in spec["drums"].items()}
    grips = {k: apply(M, *v) for k, v in spec["grips"].items()}
    per = S.period
    plan = {"L": [], "R": []}
    lo, hi = t - 1.0, t + 1.0
    b = S.B
    for i in range(max(0, int(np.searchsorted(b, lo)) - 1), min(len(b), int(np.searchsorted(b, hi)) + 1)):
        for half in (0.0, 0.5):
            plan["L"].append((b[i] + half * per, "hat"))
            plan["R"].append((b[i] + half * per + 0.25 * per, "ride"))       # the right hand keeps time too
    for kind, who, tgt, th in (("snare", "L", "snare", 0.45), ("snare", "R", "tom", 0.75), ("crash", "R", "crash_l", 0.7),
                               ("crash", "L", "crash_r", 0.7), ("kick", "R", "tom", 0.95)):
        h, hs = S.H[kind], S.HS[kind]
        j0, j1 = int(np.searchsorted(h, lo)), int(np.searchsorted(h, hi))
        for j in range(j0, j1):
            if hs[j] >= th:
                plan[who].append((float(h[j]), tgt))
    fist = spec.get("fist")
    for side in ("L", "R"):
        ev = sorted(plan[side])
        clean = []                                       # an accent replaces a time-keeping note near it
        for te, tg in ev:
            if clean and te - clean[-1][0] < 0.08:
                if tg not in ("hat", "ride"):
                    clean[-1] = (te, tg)
                continue
            clean.append((te, tg))
        prev = max([e for e in clean if e[0] <= t] or [(t - 9, "hat")])
        nxt = min([e for e in clean if e[0] > t] or [(t + 9, "hat")])
        g = grips[side]

        def ang(tg):
            p = dr.get(tg) or dr.get("snare")
            if tg == "ride":
                p = dr.get("tom") if side == "R" else dr.get("hat")
            return math.atan2(p[1] - g[1], p[0] - g[0])

        def raised(a, amt):
            up = -math.pi / 2
            dlt = (up - a + math.pi) % (2 * math.pi) - math.pi
            return a + amt * dlt

        accent = nxt[1] not in ("hat", "ride")
        lift = 0.75 if accent else 0.45                  # accents are played from higher up
        after = math.exp(-(t - prev[0]) / 0.055)
        before = sm(1 - (nxt[0] - t) / (0.11 if accent else 0.07))
        a_prev, a_next = ang(prev[1]), ang(nxt[1])
        if before > after:
            a = raised(a_next, lift) + (a_next - raised(a_next, lift)) * before
            up = 1 - before
        else:
            a = raised(a_prev, lift) + (a_prev - raised(a_prev, lift)) * after
            up = 1 - after
        hand = (g[0], g[1] - 0.035 * H_screen * up * (1.4 if accent else 1.0))
        dx, dy = math.cos(a), math.sin(a)
        tip = (hand[0] + L * dx, hand[1] + L * dy)
        butt = (hand[0] - 0.12 * L * dx, hand[1] - 0.12 * L * dy)
        stick(dst, butt, tip, max(2.0, 0.014 * H_screen))
        if fist:
            draw_fist(dst, fist, hand, side, 0.085 * H_screen)


def draw_fist(dst, key, at, side, width):
    """the drummer's fist round the stick at `at` (screen px), its forearm dropping inward behind the drums;
    side R is the drummer's right (the viewer's left): the fist mirrored"""
    d, _ = CAST.get(key)
    im = _fist_pm(key)
    mirror = side == "R"
    if mirror:
        im = im[:, ::-1]
    h, w = im.shape[:2]
    cx, cy = (w - 0.50 * w) if mirror else 0.50 * w, 0.66 * h          # where the stick passes through
    fx, fy = ((w - 0.38 * w) if mirror else 0.38 * w) - cx, 0.10 * h - cy   # towards the wrist
    cur = math.atan2(fy, fx)
    target = math.radians(55.0 if mirror else 125.0)                   # down and in, to the drummer's body
    phi = target - cur
    k = width / w
    c, sn = math.cos(phi) * k, math.sin(phi) * k
    A = np.array([[c, -sn, 0.0], [sn, c, 0.0]])
    A[:, 2] = np.array(at) - A[:, :2] @ np.array([cx, cy])
    E.warp_into(dst, np.ascontiguousarray(im), A.astype(np.float32))


@functools.lru_cache(maxsize=4)
def _fist_pm(key):
    d, _ = CAST.get(key)
    return d.base(1.0)


def stick(dst, p0, p1, width):
    H, W = dst.shape[:2]
    m = int(width * 3)
    x0, y0 = int(min(p0[0], p1[0]) - m), int(min(p0[1], p1[1]) - m)
    x1, y1 = int(max(p0[0], p1[0]) + m), int(max(p0[1], p1[1]) + m)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    S = 4
    im = np.zeros(((y1 - y0) * S, (x1 - x0) * S, 4), np.float32)
    a = (int((p0[0] - x0) * S), int((p0[1] - y0) * S))
    b = (int((p1[0] - x0) * S), int((p1[1] - y0) * S))
    ink = max(2, int(2.6 * RS * S))
    cv2.line(im, a, b, (*INK, 1.0), int(width * S) + 2 * ink, cv2.LINE_AA)
    cv2.circle(im, b, int(width * S * 0.55) + ink, (*INK, 1.0), -1, cv2.LINE_AA)
    cv2.line(im, a, b, (0.87, 0.70, 0.44, 1.0), int(width * S), cv2.LINE_AA)
    cv2.circle(im, b, int(width * S * 0.55), (0.93, 0.80, 0.56, 1.0), -1, cv2.LINE_AA)
    im = cv2.resize(im, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    reg = dst[y0:y1, x0:x1]
    dst[y0:y1, x0:x1] = im + reg * (1 - im[..., 3:4])


# ---------------------------------------------------------------- the performers
def draw_actor(shared, a, t, s, M, sc, pos):
    R = _R()
    key, who = a["draw"], a["who"]
    d, info = CAST.get(key)
    fx, fy = feet_of(key)
    Hd = fy - top_of(key)
    mirror = a.get("mirror", False)
    if a.get("eye") is not None:                         # placed by the point between the eyes and eye distance
        ax, ay = info["anchor"]
        k = a["ed"] * RS / info["ed"]
        sx = -k if mirror else k
        Ex, Ey = a["eye"][0] * RS, a["eye"][1] * RS
        Ms = np.array([[sx, 0.0, Ex - sx * ax], [0.0, k, Ey - k * ay]])
        Fx, Fy = apply(Ms, fx, fy)
    else:
        if a.get("screen"):
            Fx, Fy = a["feet"][0] * RS, a["feet"][1] * RS
            k = a["h"] * RS / Hd
        else:
            Fx, Fy = apply(M, *a["feet"])
            k = a["h"] * sc / Hd
        sx = -k if mirror else k
        Ms = np.array([[sx, 0.0, Fx - sx * fx], [0.0, k, Fy - k * fy]])
    perf = importlib.import_module("film.perf")
    gv = getattr(perf, "GROOVE", None)
    g = gv.at(who, t) if gv is not None else dict(rot=0.0, sx=1.0, sy=1.0, jump=0.0, dx=0.0, nod=0.0, tilt=0.0)
    amt = a.get("dance", 1.0)
    if amt != 1.0:
        g = dict(rot=g["rot"] * amt, sx=1 + (g["sx"] - 1) * amt, sy=1 + (g["sy"] - 1) * amt, jump=g["jump"] * amt,
                 dx=g["dx"] * amt, nod=g["nod"] * amt, tilt=g["tilt"] * amt)
    Ms2 = compose(Ms, groove_matrix(g, (fx, fy), Hd))
    st = R.PERF.state(who, t, R.world_resolver(s, who, pos), s["t"]) if d.has_face else {}
    if st:
        st = dict(st)
        st["nod"] = st["nod"] + g["nod"]
        st["tilt"] = st["tilt"] + g["tilt"]
        fst = R.face_state(st, info, mirror)
    else:
        fst = {}
    clip = None
    if a.get("clip") is not None:
        cy_scr = a["clip"] * RS if a.get("screen") else apply(M, 0.0, a["clip"])[1]
        clip = (cy_scr - Ms2[1, 2]) / Ms2[1, 1]
    H_screen = Hd * k
    inst = a.get("inst")
    playing = a.get("playing", 1.0)
    if inst or a.get("blur"):
        lay = np.zeros((OH, OW, 4), np.float32)
        E.place(lay, d, fst, Ms2, clip=clip)
        if inst in ("guitar", "bass"):
            lay = play_strings(lay, inst, Ms2, key, t, mirror, H_screen, playing)
        elif inst == "keys":
            lay = play_keys(lay, Ms2, key, t, playing)
        if a.get("blur"):
            lay = cv2.GaussianBlur(lay, (0, 0), a["blur"] * RS)
        shared[:] = lay + shared * (1 - lay[..., 3:4])
    else:
        E.place(shared, d, fst, Ms2, clip=clip)
    if a.get("mic"):
        mic_stand(shared, Ms2, key, (Fx, Fy), a["mic"])


# ---------------------------------------------------------------- lights
@functools.lru_cache(maxsize=8)
def light_mask(pk):
    """where the plate's lamps and beams are: its bright, warm-or-white parts in the upper half (uint8 mask at the
    plate's 4x / 2x / 1x levels, registered as the occluder "_lights")"""
    P = _R().plate(pk)
    im = P.lv[1].astype(np.float32) / 255.0
    lum = im.max(2)
    m = np.clip((lum - 0.72) / 0.22, 0, 1)
    H = m.shape[0]
    yy = np.arange(H, dtype=np.float32)[:, None] / H
    m *= np.clip((0.62 - yy) / 0.2, 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 2.0)
    m1 = (m * 255).astype(np.uint8)
    lv = {1: m1, 2: cv2.resize(m1, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR),
          4: cv2.resize(m1, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)}
    P.occl["_lights"] = lv
    return True


def beams(t, M, sc, lamps, energy):
    """soft light beams from the lamps (plate px), swinging with the bars, through haze -> additive RGB (screen)"""
    S = SONG()
    q = 4
    w, h = OW // q, OH // q
    acc = np.zeros((h, w, 3), np.float32)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    bar = S.bar_phase(t)
    bi = S.beat_index(t)
    for i, lp in enumerate(lamps):
        x0, y0 = apply(M, lp["at"][0], lp["at"][1])
        x0, y0 = x0 / q, y0 / q
        swing = lp.get("swing", 18.0) * math.sin(2 * math.pi * (bar / 4.0) + i * 1.3)
        ang = math.radians(lp.get("aim", 90.0) + swing)
        dx, dy = math.cos(ang), math.sin(ang)
        vx, vy = X - x0, Y - y0
        along = vx * dx + vy * dy
        across = -vx * dy + vy * dx
        spread = math.tan(math.radians(lp.get("spread", 9.0))) * np.maximum(along, 1.0) + 2.0
        b = np.exp(-(across / spread) ** 2) * (along > 0) * np.exp(-along / (h * 1.4))
        col = lp["colors"][(bi // 4 + i) % len(lp["colors"])]
        pulse = 0.55 + 0.45 * math.exp(-S.phase(t) * 4.0)
        acc += b[..., None] * np.float32(col) * pulse * lp.get("power", 0.18)
    acc *= energy
    return cv2.resize(acc, (OW, OH), interpolation=cv2.INTER_LINEAR)


def in_spans(t, spans):
    return any(a <= t < b for a, b in spans)


# ---------------------------------------------------------------- fans
@functools.lru_cache(maxsize=4)
def fans_layer(key):
    """the foreground crowd (props.fans_image) as premultiplied levels, like a plate's"""
    X = _R().X
    rgba = X.fans_image(key)                                 # 4x plate px, RGBA uint8
    f = rgba.astype(np.float32) / 255.0
    f[..., :3] *= f[..., 3:4]
    return {4: f, 2: cv2.resize(f, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
            1: cv2.resize(f, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)}


def draw_fg_fans(img, opt, t, energy):
    """the front row of the crowd between the lens and the people in a crowd shot: dark heads and shoulders, fists
    pumping on the beat, a scarf held up between two of them; out of focus, rimmed by the stage light behind the
    camera. opt: seed, n (people), y (top of the heads, share of the frame), blur, scarf"""
    S = SONG()
    rng = np.random.default_rng(opt.get("seed", 1))
    n = opt.get("n", 9)
    lay = np.zeros((OH, OW, 4), np.float32)
    top = opt.get("y", 0.70) * OH
    col = (0.035, 0.018, 0.022, 1.0)
    p0 = S.phase(t)
    xs = (np.linspace(-0.04, 1.04, n) + rng.uniform(-0.025, 0.025, n)) * OW
    rs = rng.uniform(0.072, 0.094, n) * OH
    arms = rng.random(n) < opt.get("arms", 0.45)
    side = rng.choice([-1.0, 1.0], n)
    fists = []
    for i in range(n):
        x, r = xs[i], rs[i]
        p = (p0 + 0.5 * (i % 2) + 0.07 * rng.random()) % 1.0
        jump = energy * 0.034 * OH * math.sin(math.pi * p) ** 1.2
        cy = top + r - jump + rng.uniform(-0.2, 0.25) * r
        cv2.ellipse(lay, (int(x), int(cy)), (int(0.86 * r), int(r)), 0, 0, 360, col, -1, cv2.LINE_AA)
        cv2.ellipse(lay, (int(x), int(cy + 1.95 * r)), (int(1.55 * r), int(1.15 * r)), 0, 0, 360, col, -1, cv2.LINE_AA)
        cv2.rectangle(lay, (int(x - 1.5 * r), int(cy + 1.95 * r)), (int(x + 1.5 * r), OH), col, -1)
        if arms[i]:                                      # an arm up: shoulder, elbow out, fist pumping
            pump = 0.4 * r * max(0.0, math.cos(2 * math.pi * p)) ** 2 * energy
            sd = side[i]
            sh = (x + sd * 1.25 * r, cy + 1.55 * r)
            el = (x + sd * 1.95 * r, cy + 0.15 * r - 0.5 * pump)
            fist = (x + sd * 1.45 * r, cy - 1.45 * r - pump)
            for q0, q1, wd in ((sh, el, 0.82), (el, fist, 0.72)):
                cv2.line(lay, (int(q0[0]), int(q0[1])), (int(q1[0]), int(q1[1])), col, int(wd * r), cv2.LINE_AA)
            cv2.circle(lay, (int(el[0]), int(el[1])), int(0.4 * r), col, -1, cv2.LINE_AA)
            cv2.ellipse(lay, (int(fist[0]), int(fist[1])), (int(0.55 * r), int(0.62 * r)), 0, 0, 360, col, -1,
                        cv2.LINE_AA)
            fists.append((fist, i))
    if opt.get("scarf", True) and len(fists) >= 2:          # a scarf held up between two raised fists
        (f1, i1), (f2, i2) = fists[0], fists[1]
        if abs(f2[0] - f1[0]) < 0.45 * OW:
            L = math.hypot(f2[0] - f1[0], f2[1] - f1[1])
            th = 0.36 * rs[i1]
            m = 10
            for k in range(m):
                a0 = (f1[0] + (f2[0] - f1[0]) * k / m, f1[1] + (f2[1] - f1[1]) * k / m + 0.25 * th * math.sin(k))
                a1 = (f1[0] + (f2[0] - f1[0]) * (k + 1) / m, f1[1] + (f2[1] - f1[1]) * (k + 1) / m)
                c = (0.42, 0.04, 0.05, 1.0) if k % 2 == 0 else (0.62, 0.58, 0.56, 1.0)
                cv2.line(lay, (int(a0[0]), int(a0[1])), (int(a1[0]), int(a1[1])), c, int(th), cv2.LINE_AA)
    lay = E.rim(lay, 0.0, 1.0, opt.get("rim", 0.6), (1.0, 0.32, 0.26), 5 * RS)
    if opt.get("blur", 6.0) > 0:
        lay = cv2.GaussianBlur(lay, (0, 0), opt.get("blur", 6.0) * RS)
    return img * (1 - lay[..., 3:4]) + lay[..., :3]


def draw_fans(img, key, P, cx, cy, z, t, amt):
    S = SONG()
    lv = fans_layer(key)
    s = P.scale(z)
    L = next((l for l in (1, 2, 4) if l >= s * 0.95), 4)
    out = img
    W1 = P.W1
    for half, ph in ((0, 0.0), (1, 0.5)):                    # two halves of the crowd, jumping a half beat apart
        p = (S.phase(t) + ph) % 1.0
        jump = amt * 0.035 * OH * math.sin(math.pi * p) ** 1.2
        A = np.float32([[s / L, 0, OW / 2 - s * cx], [0, s / L, OH / 2 - s * cy - jump]])
        lay = cv2.warpAffine(lv[L], A, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        xs = (np.arange(OW, dtype=np.float32) - (OW / 2 - s * cx)) / s       # plate x of each column
        m = np.clip((xs - W1 * 0.5) / (W1 * 0.08) + 0.5, 0, 1)
        m = m if half else 1 - m
        lay = lay * m[None, :, None]
        out = lay[..., :3] + out * (1 - lay[..., 3:4])
    return out


# ---------------------------------------------------------------- the shot
def render(s, t):
    R = _R()
    S = SONG()
    P = R.plate(s["plate"])
    cam = R.cam_at(s, t)
    cx, cy, z = cam[:3]
    roll = cam[3] if len(cam) > 3 else 0.0
    kick = S.hit("kick", t, 0.11)
    crash = S.hit("crash", t, 0.16)
    z = z * (1 + s.get("punch", 0.0) * 0.022 * kick)
    dx, dy = R.drift(t, s, s.get("drift", 0.5))
    if s.get("shake"):
        a = s["shake"] * (0.5 * kick + crash)
        dx += a * 9 * RS * math.sin(t * 61.0)
        dy += a * 7 * RS * math.sin(t * 47.0 + 1.0)
    sc = P.scale(z)
    cx, cy = P.clamp(cx - dx / sc, cy - dy / sc, z)
    sharp = P.render(cx, cy, z)
    img = cv2.GaussianBlur(sharp, (0, 0), s["blur"] * RS) if s.get("blur", 0) > 0 else sharp.copy()
    M = P.M(cx, cy, z)
    energy = s.get("energy", S.energy(t))
    dark = s.get("dark", 0.0)
    if callable(dark):
        dark = dark(t)
    # the house lights: the plate's lamps pulse with the kick, flare on a crash
    if s.get("lights", 1.0) > 0:
        light_mask(s["plate"])
        lm = P.mask("_lights", cx, cy, z)[..., None]
        k = s.get("lights", 1.0) * (0.10 + 0.32 * kick * energy + 0.5 * crash * energy)
        img = img + lm * k * np.float32([1.0, 0.82, 0.70])
    if dark > 0:
        img = img * (1 - 0.82 * dark)
    pos = {}
    for kind, val in s["layers"]:
        if kind == "actors":
            for a in val:
                if a.get("eye") is not None:
                    pos[a["who"]] = a["eye"][0] * RS
                elif not a.get("screen"):
                    pos[a["who"]] = apply(M, *a["feet"])[0]
                else:
                    pos[a["who"]] = a["feet"][0] * RS
    for kind, val in s["layers"]:
        if kind == "occl":
            msk = P.mask(val, cx, cy, z)
            src = sharp
            ob = s.get("occl_blur", 0.0)
            if ob > 0:
                src = cv2.GaussianBlur(sharp, (0, 0), ob * RS)
                msk = cv2.GaussianBlur(msk, (0, 0), ob * 0.8 * RS)
            if dark > 0:
                src = src * (1 - 0.82 * dark)
            msk = msk[..., None]
            img = img * (1 - msk) + src * msk
        elif kind == "fans":
            img = draw_fans(img, val, P, cx, cy, z, t, s.get("fans_jump", 1.0) * energy)
        elif kind == "fg_fans":
            img = draw_fg_fans(img, val, t, s.get("fans_jump", 1.0) * (0.4 + 0.6 * energy))
        elif kind == "props":
            img = getattr(R.X, val)(img, s, t, M, sc)
        elif kind == "sticks":                           # the drummer's sticks and fists, in front of the kit
            lay = np.zeros((OH, OW, 4), np.float32)
            drumsticks(lay, t, M, val, val["h"] * sc)
            if val.get("blur"):
                lay = cv2.GaussianBlur(lay, (0, 0), val["blur"] * RS)
            if dark > 0:
                lay[..., :3] *= 1 - 0.85 * dark
            img = img * (1 - lay[..., 3:4]) + lay[..., :3]
        elif kind == "actors":
            lay = np.zeros((OH, OW, 4), np.float32)
            for a in val:
                draw_actor(lay, a, t, s, M, sc, pos)
            if dark > 0:                                      # backlit: dark, with a rim of stage light
                lay[..., :3] *= 1 - 0.85 * dark
                lay = E.rim(lay, 0.0, 1.0, 0.9 * dark, (1.0, 0.35, 0.3), 5 * RS)
            elif s.get("rim", 0.0) > 0:                      # the truss behind them: a warm backlight
                lay = E.rim(lay, 0.0, 1.0, s["rim"] * (0.55 + 0.45 * kick), (1.0, 0.86, 0.70), 5 * RS)
            img = img * (1 - lay[..., 3:4]) + lay[..., :3]
    for fn in ([s["props"]] if isinstance(s.get("props"), str) else s.get("props", [])):   # overlays on top
        img = getattr(R.X, fn)(img, s, t, M, sc)
    spot = s.get("spot")
    if spot:                                             # a follow spot: everything else falls away
        at = pos_of(spot["at"], s, M, pos)
        rr = spot.get("r", 150) * sc
        Y, X = np.ogrid[0:OH, 0:OW]
        d2 = ((X - at[0]) / rr) ** 2 + ((Y - at[1]) / (rr * spot.get("tall", 1.5))) ** 2
        m = np.clip(1.25 - d2, 0, 1) ** 1.5
        k = spot.get("dark", 0.72) * ramp(t, s["t"], s["end"], spot.get("fin", 0.4), 0.2)
        img = img * (1 - k * (1 - m[..., None])) + m[..., None] * k * 0.06 * np.float32([1.0, 0.9, 0.8])
    D = R.D
    lamps = s.get("lamps", getattr(D, "LAMPS", {}).get(s["plate"]))
    if lamps and s.get("beams", 1.0) > 0:
        img = img + beams(t, M, sc, lamps, s.get("beams", 1.0) * (0.35 + 0.65 * energy))
    # haze: the air glows with the light
    if s.get("haze", 0.0) > 0:
        img = img + cv2.GaussianBlur(np.clip(img - 0.55, 0, 1), (0, 0), 30 * RS) * s["haze"]
    if crash > 0.02 and s.get("flash", 1.0) > 0:
        f = s.get("flash", 1.0) * 0.30 * crash * energy
        img = img + (1 - img) * f * np.float32([1.0, 0.95, 0.88])
    for a, b in getattr(D, "STROBE", []):
        if a <= t < b and s.get("strobe", 1.0) > 0:
            q = (S.beat_index(t) + S.phase(t)) * 4
            if (q % 1.0) < 0.35:
                img = img + (1 - img) * 0.35
            else:
                img = img * 0.82
    img = grade_stage(img, s.get("grade", "stage"))
    if abs(roll) > 0.01:
        Mr = cv2.getRotationMatrix2D((OW / 2, OH / 2), roll, 1.0 + abs(math.radians(roll)) * 0.9)
        img = cv2.warpAffine(img, Mr, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return img


def pos_of(at, s, M, pos):
    """a spot's target: plate px, or a performer (their upper body)"""
    if isinstance(at, str):
        for kind, val in s["layers"]:
            if kind == "actors":
                for a in val:
                    if a["who"] == at:
                        if a.get("eye") is not None:
                            return (a["eye"][0] * RS, (a["eye"][1] + 1.6 * a["ed"]) * RS)
                        if a.get("screen"):
                            return (a["feet"][0] * RS, (a["feet"][1] - 0.75 * a["h"]) * RS)
                        return apply(M, a["feet"][0], a["feet"][1] - 0.62 * a["h"])
        return (OW / 2, OH / 2)
    return apply(M, *at)


def grade_stage(img, kind):
    if kind == "stage":                                      # gig: contrast, saturated reds, bloom on the lights
        bloom = cv2.GaussianBlur(np.clip(img - 0.62, 0, 1), (0, 0), 14 * RS)
        l = img.mean(2, keepdims=True)
        img = l + (img - l) * 1.10
        img = (img - 0.5) * 1.08 + 0.5
        img = img * np.float32([1.03, 0.98, 0.95]) + bloom * np.float32([0.9, 0.55, 0.45])
    elif kind == "crowd":                                    # the room: warm, a little softer
        bloom = cv2.GaussianBlur(np.clip(img - 0.65, 0, 1), (0, 0), 18 * RS)
        img = (img - 0.5) * 1.04 + 0.5
        img = img * np.float32([1.04, 0.99, 0.94]) + bloom * 0.6
    return img
