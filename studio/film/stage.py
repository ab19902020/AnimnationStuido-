"""Music videos: a band on a stage and a crowd, every one of them moving to the song (studio/film/song.py).

A stage shot (studio.film.shots.stage) is a camera in a plate, as a world shot is, with these layers in order:

  ("actors", [actor, ...])   drawings placed by their feet and height in plate px (or, screen=True, in 1920 x 1080
                             layout px: the crowd in close shots, the set blurred behind). An actor is a dict:
        who, draw            the performer (perf.py) and the drawing ("<character id>:<drawing>")
        feet, h              where the soles are and how tall the drawing stands
        mirror, clip         flipped; faded out below this y (plate px, or layout px when screen)
        inst                 "guitar", "bass" or "keys": a guitar or bass is hung on the drawing's own hands,
                             which are put back over it, the neck to the player's left (a right-handed player); the
                             arms are warped (never cut) so the strumming hand goes down through the strings on the
                             beat and up on the off-beat and the fretting hand slides along the neck. The keyboard is
                             seen as the audience sees it, from behind: its back panel stands on the stage in front
                             of the player's hands (on the keys behind it), the forearms dipping as he plays
        mic                  a mic stand at the mouth (True, or {"side": -1 / 1, "drop": eye distances below})
                             ("harmonica": in a neck rack, up at the lips while he plays, under the chin between)
        cloud                a little rain cloud over their head (the miserable)
        dance                scale of the groove (1 by default; 0: stands still)
        blur                 out of focus (px at 1920): the players the lens is not on
        eye, ed              (screen actors) placed by the point between the eyes and the eye distance (layout px)
                             instead of feet and height, so heads match whatever a drawing's proportions
        look_at              eyes on a point (layout px): the crowd watching the band (a three-quarter head's
                             pupils are turned back to where it looks, from how much narrower its far eye is)
  ("occl", mask)             the plate's own furniture in front (the drum kit, the monitors), sharp (or blurred
                             with the shot's "occl_blur" when the lens is on someone behind it)
  ("sticks", spec)           the drummer's sticks in his fists (spec: grips, drums (plate px), len, h, fist: a
                             drawing of his fist, blur), a rock beat as the song plays it: the right hand crosses to
                             the hi-hat on the eighth notes, the left cracks the snare on 2 and 4, fills go round
                             the toms and both go to the cymbals on a crash that opens a bar; accents from higher up
  ("fans", key)              a foreground crowd cut from a plate (props.fans_image(key)), jumping on the beat
  ("fg_fans", opt)           a front row of fans in silhouette between the lens and the people: heads, fists
                             pumping on the beat, a scarf held up (for a camera behind a crowd, never one on stage)
  ("stage_edge", opt)        a crowd shot taken from the stage: the stage floor across the bottom of the frame, its
                             lit front edge, a wedge monitor in a corner, out of focus (opt: y, monitor, mic, blur)
  ("props", fn)              an episode function fn(img, shot, t, M, scale) -> img (and the shot's "props":
                             overlays drawn over everything, like a title)

and, over the picture: the plate's lamps and beams pulsing with the kick (shot "lights": 0..1), beams swinging
through haze (LAMPS in direction.py; the haze glows with the lamps and beams, never the band), moving lights
sweeping a crowd shot ("sweep": n, amount, colors; a pass every two bars, flaring on the kick), a flash on the
crashes, a strobe in STROBE spans, a camera punch on the kick ("punch") and a shake ("shake"), a roll (the fourth
number of a camera key), the "stage" grade (the plate behind the band taken down, "plate_tone", so the band stands
out; bloom on the lights only; a vignette) or the "crowd" grade.

Dancing (perf.py's GROOVE = Groove({who: [(t0, t1, move, amount)]}, style={who: {...}})): bounce (a knee dip on
every beat), sway (side to side over two beats), headbang, jump (every beat), pogo (every beat, straight up and
hanging there), hop (every other beat, landing on 1 and 3) / hop2 (on 2 and 4), rock (a guitarist's lean on the
bar with a bounce), nod, bob (the head on the eighths), pump (an up-beat stretch), shuffle (a side step), skank (the
knees on the off-beat, the shoulders rocking), strut (weight from foot to foot), twist (shoulders and face turning
with the beat), wave (the terrace sway, over the bar, the whole room together), lean (degrees, held), awkward (a
stiff nod on the off-beat: someone who cannot dance). No two jumps are the same height or lean the same way.
style gives each performer their own feel: late (s behind the beat), lag (how far the head trails the body),
breathe (the idle rise and fall that keeps anyone standing still alive), lean; without one each is a few ms off the
grid. The head rides the body whole (rigid_head): the body squashes and stretches, the face never does.
perf.GLANCE = {who: [(t0, t1, target)]}: a look away and back (stage.glance): at someone in the shot, "up", "cam"
or ("dir", x, y, turn). perf.PLAYS = {who: [(t0, t1)]}: when a player plays (the rest of the time his instrument
rests). The singers' mouths: sing(PERF, ...) writes the lead vocal's mouth track into a performer's lip sync for
the spans they sing."""
import functools
import importlib
import math
import zlib

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
    return Song(ep.song_path())


def sm(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ramp(t, a, b, fin=0.25, fout=0.25):
    return sm((t - a) / max(1e-3, fin)) * (1 - sm((t - b) / max(1e-3, fout)))


# ---------------------------------------------------------------- dancing
def _h(i, k):
    """a repeatable random number in 0..1 for beat (or hop) i of performer k: no two jumps quite the same"""
    x = math.sin(i * 12.9898 + k * 78.233) * 43758.5453
    return x - math.floor(x)


class Groove:
    """spans of dance moves per performer: {who: [(t0, t1, move, amount)]} (a negative amount takes a move down).
    style: {who: dict(late, lag, breathe, lean, vary)}: how each one dances. late: seconds behind the beat (ahead
    of it if < 0), each their own feel; lag: how far the head trails the body (s); breathe: the rise and fall and
    the slow shift of weight that keeps anyone standing still alive (1 = normal); lean: degrees, how they stand;
    vary: how much one beat's move differs from the next (0.25 = a quarter either way)"""

    def __init__(self, spans, song=None, style=None):
        self.spans = spans
        self.song = song
        self.style = style or {}
        self.k = {w: i for i, w in enumerate(sorted(set(spans) | set(self.style)))}

    def at(self, who, t):
        S = self.song or SONG()
        out = dict(rot=0.0, sx=1.0, sy=1.0, jump=0.0, dx=0.0, nod=0.0, tilt=0.0, turn=0.0)
        st = self.style.get(who, {})
        if who not in self.spans and not st:
            return out
        k = self.k[who]
        late = st.get("late", 0.012 * ((k * 7) % 5 - 2))      # a few ms off the grid, each their own way
        tt = t - late
        p = S.phase(tt)
        bi = S.beat_index(tt)
        if p >= 1.0:                                         # past the last beat the beats run on
            bi, p = bi + int(p), p - int(p)
        pos = bi + p                                         # beats since the start
        vy = st.get("vary", 0.25)
        # this beat's size: a little bigger or smaller than the last, eased across the beat so nothing pops
        big = 1.0 + vy * (2 * (_h(bi, k) + (_h(bi + 1, k) - _h(bi, k)) * sm(p)) - 1)
        busy = 0.0
        for t0, t1, move, a in self.spans.get(who, ()):
            w = ramp(t, t0, t1, 0.3, 0.3) * a
            if abs(w) <= 1e-3:
                continue
            if move != "lean":
                busy += w
            beat = 0.5 + 0.5 * math.cos(2 * math.pi * p)    # 1 on the beat, 0 between
            hit = math.exp(-p * 7.0)                         # the instant of the beat
            if move == "bounce":
                out["sy"] -= 0.038 * w * beat * big
                out["sx"] += 0.016 * w * beat * big
                out["dx"] += 0.008 * w * math.sin(math.pi * pos + k)
                out["jump"] += 0.006 * w * hit
                out["rot"] += 0.8 * w * math.sin(math.pi * pos + k)
                out["nod"] += 4.0 * w * beat
            elif move == "sway":
                out["rot"] += 3.6 * w * math.sin(math.pi * pos + k)
                out["tilt"] += 2.4 * w * math.sin(math.pi * pos + k + 0.6)
                out["dx"] += 0.020 * w * math.sin(math.pi * pos + k)
                out["sy"] -= 0.010 * w * beat
            elif move == "headbang":
                d = max(0.0, math.cos(2 * math.pi * p)) ** 1.6
                out["nod"] += 8.0 * w * d
                out["sy"] -= 0.032 * w * d
                out["rot"] += 1.2 * w * d * (1 if bi % 2 else -1)
                out["tilt"] += 3.0 * w * math.sin(math.pi * pos)
            elif move in ("jump", "hop", "hop2", "pogo"):
                if move in ("jump", "pogo"):                # every beat
                    u, c, nb = p, bi, 1
                else:                                        # every other beat: hop lands on 1 and 3, hop2 on 2 and 4
                    o = bi + (move == "hop2")
                    u, c, nb = ((o % 2) + p) / 2, o // 2, 2
                dt = u * nb * S.period                       # seconds since they landed
                h = 1.0 + vy * (2 * _h(c, k + 11) - 1)       # this jump's height
                air = math.sin(math.pi * u)
                land = math.exp(-dt / (0.042 if move == "pogo" else 0.05))      # the squash as the feet land
                drop = dt / 0.07 * math.exp(1 - dt / 0.07)   # and the head carrying on down, a moment later
                if move == "pogo":                           # straight up, hanging at the top, stretched on the way
                    out["jump"] += 0.092 * w * h * air ** 0.55
                    up = max(0.0, math.cos(math.pi * u)) * (1 - land)
                    out["sy"] += 0.020 * w * up - 0.056 * w * land
                    out["sx"] += 0.024 * w * land - 0.008 * w * up
                    out["nod"] += 6.0 * w * drop - 1.6 * w * air
                else:
                    out["jump"] += 0.075 * w * h * air ** 0.8
                    out["sy"] -= 0.05 * w * land
                    out["sx"] += 0.02 * w * land
                    out["nod"] += 5.5 * w * drop
                # nobody goes up dead straight: each jump leans and tips the head its own way
                out["rot"] += 1.7 * w * (2 * _h(c, k + 7) - 1) * air
                out["tilt"] += 2.6 * w * (2 * _h(c, k + 3) - 1) * air
            elif move == "rock":
                out["sy"] -= 0.034 * w * beat
                out["sx"] += 0.012 * w * beat
                out["rot"] += 3.4 * w * math.sin(math.pi * pos / 2 + k)
                out["dx"] += 0.018 * w * math.sin(math.pi * pos + 0.7 * k)
                out["jump"] += 0.010 * w * hit
                out["nod"] += 5.5 * w * beat
                out["tilt"] += 3.0 * w * math.sin(math.pi * pos / 2 + k + 1.0)
            elif move == "nod":
                out["nod"] += 5.5 * w * beat
            elif move == "bob":                              # the head on every eighth note: can't keep still
                d = max(0.0, math.cos(4 * math.pi * p)) ** 2
                out["nod"] += 3.4 * w * d
                out["sy"] -= 0.010 * w * d
            elif move == "pump":
                out["sy"] += 0.022 * w * hit
                out["jump"] += 0.012 * w * hit
                out["nod"] -= 3.0 * w * hit
            elif move == "shuffle":
                out["dx"] += 0.035 * w * math.sin(math.pi * pos + k)
                out["sy"] -= 0.012 * w * beat
            elif move == "skank":                            # the knees on the off-beat, the shoulders rocking
                q = (p + 0.5) % 1.0
                d = (0.5 + 0.5 * math.cos(2 * math.pi * q)) ** 2
                sw = math.sin(math.pi * pos + k)
                out["sy"] -= 0.032 * w * d * big
                out["sx"] += 0.012 * w * d
                out["nod"] += 4.5 * w * d
                out["rot"] += 2.4 * w * sw
                out["dx"] += 0.012 * w * sw
                out["tilt"] -= 1.6 * w * sw
            elif move == "strut":                            # weight from foot to foot, a dip on every beat
                sw = math.sin(math.pi * pos + k)
                out["dx"] += 0.022 * w * sw
                out["rot"] -= 1.6 * w * sw
                out["sy"] -= 0.026 * w * beat * big
                out["tilt"] += 1.8 * w * sw
                out["turn"] += 0.12 * w * sw
            elif move == "twist":                            # the shoulders and the face turning with the beat
                sw = math.sin(math.pi * pos + k)
                out["turn"] += 0.30 * w * sw
                out["rot"] += 1.4 * w * sw
                out["sy"] -= 0.018 * w * beat
            elif move == "wave":                             # the terrace sway: the whole room together, over the bar
                sw = math.sin(math.pi * pos / 2)
                out["rot"] += 4.2 * w * sw
                out["dx"] += 0.028 * w * sw
                out["tilt"] -= 2.0 * w * sw
                out["sy"] -= 0.010 * w * beat
            elif move == "lean":
                out["rot"] += w
            elif move == "awkward":                         # out of time: a stiff nod on the off-beat
                q = (p + 0.5) % 1.0
                out["nod"] += 5.0 * w * max(0.0, math.cos(2 * math.pi * q)) ** 2
                out["rot"] += 0.8 * w * math.sin(math.pi * pos / 3)
        # standing still is never frozen: breathing, and the weight shifting from foot to foot
        br = st.get("breathe", 1.0) * max(0.0, 1.0 - 0.8 * min(1.0, busy))
        if br > 1e-3:
            out["sy"] += 0.006 * br * math.sin(2 * math.pi * t / (3.3 + 0.35 * (k % 4)) + k)
            out["rot"] += 0.5 * br * math.sin(2 * math.pi * t / (6.5 + 0.9 * (k % 3)) + 2.0 * k)
            out["tilt"] += 0.9 * br * math.sin(2 * math.pi * t / (5.1 + 0.7 * (k % 5)) + k)
        out["rot"] += st.get("lean", 0.0)
        out["sy"] = min(1.06, max(0.92, out["sy"]))          # however the moves stack, a body squashes only so far
        out["sx"] = min(1.05, max(0.96, out["sx"]))
        return out

    def head(self, who, t):
        """the head's share of the dance (nod, tilt, turn): the body's, a moment later, as a head trails the body"""
        g = self.at(who, t - self.style.get(who, {}).get("lag", 0.06))
        return g["nod"], g["tilt"], g["turn"]


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


def rigid_head(d, g, B, Ms, Hd):
    """the head rides the dancing body without its squash and stretch: carried by the neck, turned with the body
    (a face squashed on every beat looks like it is bubbling) -> E.place's head=(Mh, y0, y1) or None"""
    sp = d.spec
    if not (sp.get("neck") and sp.get("chin")) or abs(g["sy"] - 1) + abs(g["sx"] - 1) < 2e-3:
        return None
    nx, ny = sp["neck"]
    chin = sp["chin"]
    th = math.radians(g["rot"])
    c, s = math.cos(th), math.sin(th)
    bx, by = apply(B, nx, ny)
    Bh = np.array([[c, -s, bx - (c * nx - s * ny)], [s, c, by - (s * nx + c * ny)]])
    return compose(Ms, Bh), chin, max(ny, chin + 0.03 * Hd)


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
                   length=0.47, tilt=14.0, strum_amp=0.32, raise_body=0.10),
    "bass": dict(img="music/bass-guitar", tail=(128, 655), nut=(125, 128), strum=(126, 598), horn=(52, 415),
                 length=0.55, tilt=11.0, strum_amp=0.25, raise_body=0.08),
    "keys": dict(img="music/keyboard-on-stand"),              # the stand only: the audience sees the back
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
    strum = spec["strum_amp"] * r * math.sin(2 * math.pi * 2 * pos) * playing   # down through the strings on the beat
    slide = 0.25 * r * math.sin(2 * math.pi * pos / 8) * playing
    raise_px = spec.get("raise_body", 0.0) * H_screen
    out_R = -sgn                                             # the outside of the strumming arm
    move_hand(lay, hR[0], hR[1], r, 0.0, strum - raise_px, out_R)
    move_hand(lay, hL[0], hL[1], r, slide * sgn, -lift - raise_px, sgn)
    hR2 = (hR[0], hR[1] + strum - raise_px)
    hL2 = (hL[0] + slide * sgn, hL[1] - lift - raise_px)
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


@functools.lru_cache(maxsize=1)
def keys_back():
    """the keyboard as the audience sees it: its back panel (black, the red end cheeks, a sliver of the top, the jack
    sockets, a vent, a sticker) -> (RGBA premultiplied, 2 px per prop px, with a 4 prop px margin; the jacks in prop
    px from the panel's top left)"""
    from PIL import ImageDraw, ImageFont
    from studio.film.graphics import BEBAS
    W, H, m, c = 716, 86, 4, 8                               # prop px; margin; canvas px per prop px (4x over 2x)
    CW, CH = (W + 2 * m) * c, (H + 2 * m) * c
    yy = (np.arange(CH, dtype=np.float32)[:, None] / c - m) / H   # 0 at the panel's top .. 1 at its bottom
    xx = np.arange(CW, dtype=np.float32)[None, :] / c - m

    def rrect(x0, y0, x1, y1, rad):
        msk = np.zeros((CH, CW), np.uint8)
        x0, y0, x1, y1, rad = (int((v + m) * c) if i < 4 else int(v * c) for i, v in enumerate((x0, y0, x1, y1, rad)))
        cv2.rectangle(msk, (x0 + rad, y0), (x1 - rad, y1), 255, -1)
        cv2.rectangle(msk, (x0, y0 + rad), (x1, y1 - rad), 255, -1)
        for cx, cy in ((x0 + rad, y0 + rad), (x1 - rad, y0 + rad), (x0 + rad, y1 - rad), (x1 - rad, y1 - rad)):
            cv2.circle(msk, (cx, cy), rad, 255, -1, cv2.LINE_AA)
        return msk.astype(np.float32) / 255.0

    def paint(img, msk, col):
        col = np.broadcast_to(np.asarray(col, np.float32), img[..., :3].shape) if np.ndim(col) == 1 else col
        img[..., :3] = img[..., :3] * (1 - msk[..., None]) + col * msk[..., None]
        img[..., 3] = np.maximum(img[..., 3], msk)

    img = np.zeros((CH, CW, 4), np.float32)
    paint(img, rrect(-4, -4, W + 4, H + 4, 15), INK)                                   # the outline
    body = rrect(0, 0, W, H, 11)
    shade = (0.17 - 0.09 * np.clip(yy, 0, 1))[..., None] * np.float32([1.0, 0.98, 1.04])
    paint(img, body, np.broadcast_to(shade, (CH, CW, 3)))
    cheek = body * ((xx < 40) | (xx > W - 40)).astype(np.float32)
    red = (np.float32([0.80, 0.09, 0.11]) * (1.0 - 0.32 * np.clip(yy, 0, 1))[..., None])
    paint(img, cheek, np.broadcast_to(red, (CH, CW, 3)))
    for x in (40, W - 40):                                                              # the cheeks' seams
        paint(img, body * (np.abs(xx - x) < 1.8).astype(np.float32), INK)
    top = body * (yy < 0.10).astype(np.float32)                                         # the top, edge on
    paint(img, top * ((xx > 40) & (xx < W - 40)).astype(np.float32), (0.30, 0.30, 0.33))
    paint(img, body * (np.abs(yy - 0.10) < 0.012).astype(np.float32), INK)
    paint(img, body * (np.abs(yy - 0.94) < 0.03).astype(np.float32), (0.05, 0.05, 0.06))   # the base's lip
    # the connector bay with five jacks and the power inlet
    paint(img, rrect(424, 24, 664, 70, 5), (0.05, 0.05, 0.06))
    paint(img, rrect(424, 24, 664, 26, 1), (0.24, 0.24, 0.26))
    jacks = [(448 + 30 * i, 47) for i in range(5)]
    for jx, jy in jacks:
        for rad, col in ((9.5, INK), (8.0, (0.66, 0.66, 0.70)), (5.0, (0.20, 0.20, 0.22)), (3.4, (0.01, 0.01, 0.01))):
            msk = np.zeros((CH, CW), np.uint8)
            cv2.circle(msk, (int((jx + m) * c), int((jy + m) * c)), int(rad * c), 255, -1, cv2.LINE_AA)
            paint(img, msk.astype(np.float32) / 255.0, col)
    paint(img, rrect(608, 34, 646, 60, 4), (0.13, 0.13, 0.14))
    for px in (618, 627, 636):
        paint(img, rrect(px - 1.6, 42, px + 1.6, 52, 1), (0.01, 0.01, 0.01))
    for vx in range(352, 404, 9):                                                       # the vent
        paint(img, rrect(vx, 30, vx + 4, 66, 2), (0.03, 0.03, 0.035))
    # the sticker: UNITED ROAD in white on red
    paint(img, rrect(98, 26, 318, 68, 6), (0.96, 0.95, 0.93))
    paint(img, rrect(102, 30, 314, 64, 5), (0.80, 0.07, 0.10))
    txt = Image.new("L", (CW, CH), 0)
    dr = ImageDraw.Draw(txt)
    f = ImageFont.truetype(BEBAS, int(30 * c))
    bx = dr.textbbox((0, 0), "UNITED ROAD", font=f)
    tx = int((208 + m) * c - (bx[2] - bx[0]) / 2 - bx[0])
    ty = int((47 + m) * c - (bx[3] - bx[1]) / 2 - bx[1])
    dr.text((tx, ty), "UNITED ROAD", fill=255, font=f)
    paint(img, np.asarray(txt, np.float32) / 255.0, (0.98, 0.97, 0.95))
    img = cv2.resize(img, (CW // 4, CH // 4), interpolation=cv2.INTER_AREA)
    img[..., :3] *= img[..., 3:4]
    return img, jacks


def cable(dst, pts, width):
    """a cable through screen points (a smooth curve), dark with the house outline"""
    pts = np.float32(pts)
    H, W = dst.shape[:2]
    x0, y0 = int(pts[:, 0].min() - 3 * width), int(pts[:, 1].min() - 3 * width)
    x1, y1 = int(pts[:, 0].max() + 3 * width), int(pts[:, 1].max() + 3 * width)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    S = 4
    im = np.zeros(((y1 - y0) * S, (x1 - x0) * S, 4), np.float32)
    p = np.int32((pts - (x0, y0)) * S)
    cv2.polylines(im, [p], False, (*INK, 1.0), int(width * S + 2.5 * RS * S), cv2.LINE_AA)
    cv2.polylines(im, [p], False, (0.07, 0.07, 0.08, 1.0), max(1, int(width * S)), cv2.LINE_AA)
    im = cv2.resize(im, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    reg = dst[y0:y1, x0:x1]
    dst[y0:y1, x0:x1] = im + reg * (1 - im[..., 3:4])


def bezier(p0, p1, p2, n=24):
    u = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = (np.float32(v) for v in (p0, p1, p2))
    return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * p1 + u * u * p2


def play_keys(lay, Ms, Ms2, key, t, playing):
    """a keyboard on its stand in front of the player, seen from the audience: its back panel hides his hands (on the
    keys behind it) and the forearms dip as he plays (the right hand on the beat, the left on the off-beat). The
    keyboard stands on the stage: it is placed from where the hands rest (Ms, no dancing), so the player dances
    behind it"""
    S = SONG()
    hs = hands_of(key)
    if "R" not in hs or "L" not in hs:
        return lay
    kscr = math.sqrt(abs(np.linalg.det(Ms[:, :2])))
    r = hs["R"][2] * kscr
    hR0, hL0 = apply(Ms, *hs["R"][:2]), apply(Ms, *hs["L"][:2])
    hR, hL = apply(Ms2, *hs["R"][:2]), apply(Ms2, *hs["L"][:2])
    fx, fy = feet_of(key)
    floor = apply(Ms, fx, fy)[1]
    H_screen = (fy - top_of(key)) * kscr
    out_R = -1.0 if hR0[0] < hL0[0] else 1.0                # the outside of the right arm, on screen
    i, ph = S.beat_index(t), S.phase(t)
    lift = 0.35 * r
    for (hx, hy), off, sg in ((hR, 0.0, out_R), (hL, 0.5, -out_R)):
        p = (ph - off) % 1.0
        press = 0.22 * r * (math.exp(-p / 0.16) - 0.3 * math.exp(-(1 - p) / 0.07)) * playing
        move_hand(lay, hx, hy, r, 0.35 * r * sg * -1, press - lift, sg)          # in, over the keys; press
    out = lay.copy()
    img, jacks = keys_back()
    W, Hp0, m = 716, 86, 4
    span = abs(hL0[0] - hR0[0])
    sc = 1.9 * span / W                                      # screen px per prop px
    cxm = (hR0[0] + hL0[0]) / 2
    hy = (hR0[1] + hL0[1]) / 2 - lift
    top = hy - 1.2 * r
    Hp = max(Hp0 * sc, hy + 1.25 * r - top)
    ky = Hp / Hp0
    # the stand under it: the prop's X-stand, from the panel's underside to the stage
    st_img = prop_image(INSTRUMENTS["keys"]["img"])[136:]
    s0 = top + Hp - 4 * sc
    s1 = floor + 0.012 * H_screen
    As = np.array([[sc, 0, cxm - 358 * sc], [0, (s1 - s0) / st_img.shape[0], s0]])
    E.warp_into(out, st_img, As.astype(np.float32))
    # two cables from the jacks, down to the stage and off to the side
    for jx, jy in (jacks[1], jacks[3]):
        J = (cxm + (jx - W / 2) * sc, top + jy * ky)
        far = J[0] + (0.28 if jx > W / 2 else 0.18) * W * sc
        pts = np.vstack([bezier(J, (J[0] + 0.02 * W * sc, (J[1] + s1) / 2), (J[0] + 0.07 * W * sc, s1 + 2 * sc)),
                         bezier((J[0] + 0.07 * W * sc, s1 + 2 * sc), (J[0] + 0.12 * W * sc, s1 + 5 * sc), (far, s1 + 4 * sc))])
        cable(out, pts, max(1.5, 3.2 * sc))
    Ap = np.array([[sc / 2, 0, cxm - (m + W / 2) * sc], [0, ky / 2, top - m * ky]])
    E.warp_into(out, img, Ap.astype(np.float32))
    return out


def _canvas(dst, x0, y0, x1, y1, S=4):
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1, np.zeros(((y1 - y0) * S, (x1 - x0) * S, 4), np.float32)


def _commit(dst, box, im):
    x0, y0, x1, y1 = box
    im = cv2.resize(im, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    reg = dst[y0:y1, x0:x1]
    dst[y0:y1, x0:x1] = im + reg * (1 - im[..., 3:4])


def harmonica(dst, Ms2, key, t, on):
    """a harmonica in a neck rack, so a whole drawing plays it with its hands down: chrome covers, a red comb with
    its holes, the wire up from the collar. on (0..1): up at the lips (playing; the mouth is behind it) or resting
    under the chin; while he plays his head works along it, two beats across and back"""
    d, info = CAST.get(key)
    mo = d.spec.get("mouth")
    if not mo:
        return
    kscr = math.sqrt(abs(np.linalg.det(Ms2[:, :2])))
    xl, yl, xr, yr, xc, yc = mo
    ed = info["ed"] * kscr
    W = max(2.7 * abs(xr - xl) * kscr, 1.5 * ed)
    Hh = 0.32 * W
    mx, my = apply(Ms2, xc, yc)
    S_ = SONG()
    pos = S_.beat_index(t) + S_.phase(t)
    cx = mx + on * 0.16 * W * math.sin(math.pi * pos / 2)
    cy = my + 0.30 * Hh + (1 - on) * 0.75 * ed
    nk = d.spec.get("neck") or (xc, yc + 0.8 * info["ed"])
    nx, ny = apply(Ms2, nk[0], nk[1])
    ny += 0.30 * ed
    m = 0.4 * W
    box = _canvas(dst, min(cx - W / 2, nx - 1.2 * W) - m, cy - Hh - m, max(cx + W / 2, nx + 1.2 * W) + m,
                  ny + 0.3 * ed + m)
    if box is None:
        return
    x0, y0, x1, y1, im = box
    S = 4

    def P(x, y):
        return int((x - x0) * S), int((y - y0) * S)
    ink = (*INK, 1.0)
    lw = max(1, int(0.045 * ed * S))
    # the rack: a wire from each end of the harmonica down to the collar
    for sg in (-1, 1):                                   # each wire bows out and down to the collarbone
        a = (cx + sg * 0.47 * W, cy + 0.15 * Hh)
        b = (nx + sg * 0.95 * W, ny + 0.15 * ed)
        c = (cx + sg * 0.95 * W, cy + 0.2 * (ny - cy))
        pts = np.int32([P(*q) for q in bezier(a, c, b, 12)])
        cv2.polylines(im, [pts], False, ink, lw + int(2.0 * RS * S), cv2.LINE_AA)
        cv2.polylines(im, [pts], False, (0.62, 0.63, 0.67, 1.0), lw, cv2.LINE_AA)
    # the harmonica: outline, the covers top and bottom, the comb between with its ten holes
    X0, Y0, X1, Y1 = cx - W / 2, cy - Hh / 2, cx + W / 2, cy + Hh / 2
    o = 0.07 * Hh

    def rounded(a, b, c, d, r, col):
        cv2.rectangle(im, P(a + r, b), P(c - r, d), col, -1, cv2.LINE_AA)
        cv2.rectangle(im, P(a, b + r), P(c, d - r), col, -1, cv2.LINE_AA)
        for qx, qy in ((a + r, b + r), (c - r, b + r), (a + r, d - r), (c - r, d - r)):
            cv2.circle(im, P(qx, qy), max(1, int(r * S)), col, -1, cv2.LINE_AA)
    r = 0.22 * Hh
    rounded(X0 - o, Y0 - o, X1 + o, Y1 + o, r + o, ink)
    # the comb runs the full length; the covers, top and bottom, stop short of its ends
    rounded(X0, Y0 + 0.30 * Hh, X1, Y1 - 0.30 * Hh, 0.08 * Hh, (0.74, 0.07, 0.09, 1.0))
    for k in range(10):
        hx = X0 + 0.06 * W + (k + 0.5) * 0.88 * W / 10
        cv2.rectangle(im, P(hx - 0.024 * W, Y0 + 0.38 * Hh), P(hx + 0.024 * W, Y1 - 0.38 * Hh), (0.04, 0.02, 0.02, 1.0),
                      -1, cv2.LINE_AA)
    for top in (True, False):
        a, b = (Y0, Y0 + 0.32 * Hh) if top else (Y1 - 0.32 * Hh, Y1)
        rounded(X0 + 0.03 * W - 0.5 * o, a - 0.5 * o, X1 - 0.03 * W + 0.5 * o, b + 0.5 * o, r, ink)
        rounded(X0 + 0.03 * W, a, X1 - 0.03 * W, b, r * 0.8, (0.88, 0.89, 0.92, 1.0) if top else (0.66, 0.67, 0.71, 1.0))
        cv2.line(im, P(X0 + 0.09 * W, a + 0.32 * (b - a)), P(X1 - 0.09 * W, a + 0.32 * (b - a)),
                 (1.0, 1.0, 1.0, 1.0) if top else (0.82, 0.83, 0.86, 1.0), max(1, int(0.05 * Hh * S)), cv2.LINE_AA)
        for sx in (X0 + 0.07 * W, X1 - 0.07 * W):            # the screws
            cv2.circle(im, P(sx, (a + b) / 2), max(1, int(0.045 * Hh * S)), (0.35, 0.35, 0.38, 1.0), -1, cv2.LINE_AA)
    _commit(dst, (x0, y0, x1, y1), im)


def rain_cloud(dst, Ms2, key, t):
    """a little grey cloud raining on someone's head (the miserable)"""
    d, info = CAST.get(key)
    kscr = math.sqrt(abs(np.linalg.det(Ms2[:, :2])))
    ed = info["ed"] * kscr
    hd = d.spec.get("head")
    if hd:
        hx, hy = apply(Ms2, (hd[0] + hd[2]) / 2, hd[1])
    else:
        hx, hy = apply(Ms2, *info["anchor"])
        hy -= 2.0 * ed
    cw = 2.3 * ed
    cy = hy - 0.75 * ed + 0.06 * ed * math.sin(t * 1.3)
    cx = hx + 0.1 * ed * math.sin(t * 0.7)
    box = _canvas(dst, cx - cw, cy - 0.7 * cw, cx + cw, hy + 0.6 * ed)
    if box is None:
        return
    x0, y0, x1, y1, im = box
    S = 4

    def P(x, y):
        return int((x - x0) * S), int((y - y0) * S)
    # rain first, under the cloud: streaks falling to the head
    rng = np.random.default_rng(7)
    for k in range(18):
        rx = cx + (rng.random() - 0.5) * 1.4 * cw
        ph = (t * 1.8 + rng.random()) % 1.0
        ry = cy + 0.2 * cw + ph * (hy + 0.4 * ed - cy - 0.2 * cw)
        cv2.line(im, P(rx, ry), P(rx - 0.05 * ed, ry + 0.38 * ed), (*INK, 1.0), max(2, int(0.16 * ed * S)), cv2.LINE_AA)
        cv2.line(im, P(rx, ry), P(rx - 0.05 * ed, ry + 0.38 * ed), (0.55, 0.72, 1.0, 1.0), max(1, int(0.09 * ed * S)),
                 cv2.LINE_AA)
    puffs = [(-0.55, 0.05, 0.36), (-0.2, -0.18, 0.46), (0.22, -0.12, 0.42), (0.58, 0.06, 0.32), (0.0, 0.12, 0.40)]
    for dx, dy, r in puffs:
        cv2.circle(im, P(cx + dx * cw, cy + dy * cw), int((r * cw + 0.10 * ed) * S), (*INK, 1.0), -1, cv2.LINE_AA)
    for dx, dy, r in puffs:
        cv2.circle(im, P(cx + dx * cw, cy + dy * cw), int(r * cw * S), (0.50, 0.52, 0.56, 1.0), -1, cv2.LINE_AA)
    cv2.ellipse(im, P(cx, cy + 0.22 * cw), (int(0.75 * cw * S), int(0.12 * cw * S)), 0, 0, 180, (0.38, 0.40, 0.44, 1.0),
                -1, cv2.LINE_AA)
    for dx, dy, r in puffs[1:3]:
        cv2.circle(im, P(cx + dx * cw - 0.08 * cw, cy + dy * cw - 0.10 * cw), int(0.45 * r * cw * S),
                   (0.66, 0.68, 0.72, 1.0), -1, cv2.LINE_AA)
    _commit(dst, (x0, y0, x1, y1), im)


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
    """two sticks played as the song's drummer plays (plate px positions through M), each in a fist (spec["fist"]:
    a drawing of the drummer's fist) whose forearm drops behind the drums. A rock beat: the right hand crosses over
    to the hi-hat on the eighth notes, the left cracks the snare on 2 and 4 (where the song's snare is); fills (a
    strong snare off the beat, late in a bar) go round the toms, and both hands go to the cymbals on the crashes
    that open a bar"""
    S = SONG()
    L = spec.get("len", 0.33) * H_screen
    dr = {k: apply(M, *v) for k, v in spec["drums"].items()}
    grips = {k: apply(M, *v) for k, v in spec["grips"].items()}
    per = S.period
    plan = {"L": [], "R": []}
    lo, hi = t - 1.0, t + 1.0
    b = S.B

    def near(kind, te, win=0.05):
        h = S.H[kind]
        j = int(np.searchsorted(h, te))
        best = 0.0
        for q in (j - 1, j):
            if 0 <= q < len(h) and abs(h[q] - te) < win:
                best = max(best, float(S.HS[kind][q]))
        return best

    playing = lambda te: S.energy(te, 2.0) > 0.18           # noqa: E731  the drums are in
    for i in range(max(0, int(np.searchsorted(b, lo)) - 1), min(len(b), int(np.searchsorted(b, hi)) + 1)):
        if not playing(b[i]):
            continue
        for half in (0.0, 0.5):
            plan["R"].append((b[i] + half * per, "hat"))
        bp = int(round(S.bar_phase(b[i] + 0.02))) % 4
        if bp in (1, 3) and near("snare", b[i]) > 0.25:      # the backbeat
            plan["L"].append((float(b[i]), "snare"))
    h, hs = S.H["snare"], S.HS["snare"]
    for j in range(int(np.searchsorted(h, lo)), int(np.searchsorted(h, hi))):
        te = float(h[j])
        if hs[j] < 0.6 or S.bar_phase(te) < 3.0 or not playing(te):
            continue
        k = int(np.argmin(np.abs(b - te)))
        if abs(b[k] - te) < 0.06:                            # on a beat: that is the backbeat, not a fill
            continue
        side = "L" if (j % 2) else "R"
        plan[side].append((te, "snare" if side == "L" else "tom"))
    h, hs = S.H["crash"], S.HS["crash"]
    for j in range(int(np.searchsorted(h, lo)), int(np.searchsorted(h, hi))):
        te = float(h[j])
        if hs[j] >= 0.7 and S.bar_phase(te + 0.03) < 0.15:  # a crash opening a bar
            plan["R"].append((te, "crash_l"))
            plan["L"].append((te, "crash_r"))
    fist = spec.get("fist")
    motion = {}
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
        # A real stroke ends on the selected drum, even when the two grips
        # are different distances from it. The stick length stays rigid.
        target = dr.get(prev[1], dr["snare"])
        reach = math.hypot(target[0] - g[0], target[1] - g[1]) if spec.get("connected") else L
        tip = (hand[0] + reach * dx, hand[1] + reach * dy)
        butt = (hand[0] - 0.12 * L * dx, hand[1] - 0.12 * L * dy)
        motion[side] = dict(hand=hand, tip=tip, butt=butt)
        if dst is not None:
            stick(dst, butt, tip, max(2.0, 0.014 * H_screen))
        if fist and dst is not None:
            draw_fist(dst, fist, hand, side, 0.085 * H_screen)
    return motion


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
@functools.lru_cache(maxsize=None)
def turn_look(key):
    """a three-quarter head looks along its turn with its pupils centred: this is the pupils' offset (drawing x) that
    turns its eyes back to the lens, from how much narrower the far eye is (film.yaml look0 overrides it)"""
    d, info = CAST.get(key)
    eyes = d.spec.get("eyes") or []
    if len(eyes) != 2:
        return 0.0
    l, r = sorted(eyes, key=lambda e: e[0])
    asym = (l[2] - r[2]) / max(1e-6, l[2] + r[2])            # > 0: the face turned to the drawing's right
    return float(np.clip(-2.0 * asym, -0.7, 0.7)) if abs(asym) > 0.06 else 0.0


@functools.lru_cache(maxsize=None)
def _sung_lines(who):
    """which of the song's lyric lines this performer sings (any mouth shape inside the line)"""
    vis = _R().PERF.VIS.get(who)
    if vis is None:
        return ()
    return tuple(any(v != "REST" for v in vis[int(a * FPS):int(b * FPS)]) for a, b, _ in SONG().lines)


@functools.lru_cache(maxsize=1)
def _vocal_push():
    """how hard the lead vocal is pushing, 0..1 per frame, over a quarter of a second"""
    v = np.clip((np.asarray(SONG().vocal, np.float32) + 30.0) / 12.0, 0, 1)
    return np.convolve(v, np.ones(8, np.float32) / 8, mode="same")


def life(st, who, t, cam=False, opt=None):
    """a face is never quite still: the eyes dart a little every second or so and come back, the head finds its
    own angle for every line it sings, the brows lift as the voice pushes. cam: playing to the lens (darts smaller
    and rarer). opt (perf.LIFE[who]): eyes, head, brows, multipliers (0 turns one off)"""
    opt = opt or {}
    k = zlib.crc32(who.encode()) % 9973
    ke, kh, kb = opt.get("eyes", 1.0), opt.get("head", 1.0), opt.get("brows", 1.0)
    if ke > 0:
        L = 1.1 + 0.7 * _h(k, 3)                             # each their own rhythm
        i = math.floor(t / L)

        def when(j):
            return (j + 0.15 + 0.7 * _h(j, k + 5)) * L

        def aim(j):
            if _h(j, k + 9) < (0.65 if cam else 0.35):       # back to where they were looking
                return 0.0, 0.0
            s = ke * (0.35 if cam else 1.0)
            return s * 0.22 * (2 * _h(j, k + 1) - 1), s * 0.09 * (2 * _h(j, k + 2) - 1)

        j = i if t >= when(i) else i - 1
        (x0, y0), (x1, y1) = aim(j - 1), aim(j)
        u = sm((t - when(j)) / 0.07)                         # a dart takes two frames
        st["lookx"] += x0 + (x1 - x0) * u
        st["looky"] += y0 + (y1 - y0) * u
    sung = _sung_lines(who)
    if not sung:
        return
    lines = SONG().lines
    n = 0
    while n + 1 < len(lines) and lines[n + 1][0] - 0.1 <= t:
        n += 1
    for m in (n - 1, n):                                     # (the last line's angle easing out under the new one)
        if m < 0 or not sung[m]:
            continue
        a, b = lines[m][0], lines[m][1]
        w = ramp(t, a - 0.1, b, 0.35, 0.5)
        if w > 1e-3 and kh > 0:
            st["tilt"] += kh * 4.0 * (2 * _h(m, k + 11) - 1) * w
            st["turn"] += kh * 0.14 * (2 * _h(m, k + 12) - 1) * w
        if kb > 0 and a <= t <= b + 0.2:
            push = float(_vocal_push()[min(len(SONG().vocal) - 1, int(t * FPS))])
            st["brow"] += kb * (0.15 + 0.3 * _h(k, 13)) * push * ramp(t, a, b, 0.2, 0.2)


def glance(st, who, t, pos, spans):
    """looks away from where they were looking and back: spans [(t0, t1, target)], target a performer in the shot
    (turning to them; skipped if they are not in it), "up" (the sky, the flags), "cam" (into the lens), or
    ("dir", lookx, looky, turn). The eyes get there in a few frames, the head follows"""
    for t0, t1, tg in spans:
        we = ramp(t, t0, t1, 0.12, 0.16)
        if we <= 1e-3:
            continue
        if tg == "up":
            gx, gy, gt = 0.0, -0.7, 0.0
        elif tg == "cam":
            gx, gy, gt = 0.0, -0.02, 0.0
        elif isinstance(tg, tuple):
            gx, gy, gt = tg[1:]
        elif tg in pos and who in pos and abs(pos[tg] - pos[who]) > 1:
            sg = 1.0 if pos[tg] > pos[who] else -1.0
            gx, gy, gt = 0.8 * sg, 0.06, 0.3 * sg
        else:
            continue
        wh = ramp(t, t0, t1, 0.28, 0.3)
        st["lookx"] += (gx - st["lookx"]) * we
        st["looky"] += (gy - st["looky"]) * we
        st["turn"] += gt * wh
        if tg == "up":
            st["nod"] -= 3.0 * wh                        # the chin up


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
    if hasattr(gv, "head"):                              # the head trails the body
        g["nod"], g["tilt"], g["turn"] = gv.head(who, t)
    amt = a.get("dance", 1.0)
    if amt != 1.0:
        g = dict(rot=g["rot"] * amt, sx=1 + (g["sx"] - 1) * amt, sy=1 + (g["sy"] - 1) * amt, jump=g["jump"] * amt,
                 dx=g["dx"] * amt, nod=g["nod"] * amt, tilt=g["tilt"] * amt, turn=g.get("turn", 0.0) * amt)
    st = R.PERF.state(who, t, R.world_resolver(s, who, pos), s["t"]) if d.has_face else {}
    native = CAST.spec(key.split(":")[0])["drawings"][key.split(":")[1]].get("native_inst")
    if native == "drumming":
        # The kit is fixed on the stage; keep the seated player's wrists
        # registered to it, with the connected forearms doing the strokes.
        g = dict(g, rot=0.0, sx=1.0, sy=1.0, jump=0.0, dx=0.0, nod=0.0)
    if st:
        st = dict(st)
        # the face warp drops the face by a share of its height into the chin and the neck below it: past ~4 % that
        # visibly squashes them (a big face seems to bubble on every beat), so the rest of a nod's depth goes into
        # the body, which carries the head down whole (rigid_head)
        nod = st["nod"] + g["nod"]
        st["nod"] = 0.0  # rigid head travel carries the beat without compressing the face
        st["tilt"] = st["tilt"] + g["tilt"]
        st["turn"] = st["turn"] + g.get("turn", 0.0)
        if a.get("look_at") is not None:                 # eyes on a point (layout px): the crowd on the band
            ex, ey = a["eye"] if a.get("eye") is not None else (a["feet"][0], a["feet"][1] - a["h"])
            tx, ty = a["look_at"]
            wob = 0.04 * math.sin(t * 0.83 + (zlib.crc32(who.encode()) % 17))
            st["lookx"] = float(np.clip((tx - ex) / 2400.0, -0.4, 0.4)) + wob
            st["looky"] = float(np.clip((ty - ey) / 2600.0, -0.24, 0.2))
        elif a.get("look_cam"):
            st["lookx"] = 0.0
            st["looky"] = -0.02
        life(st, who, t, bool(a.get("look_cam")), getattr(perf, "LIFE", {}).get(who))
        glance(st, who, t, pos, getattr(perf, "GLANCE", {}).get(who, ()))
        fst = R.face_state(st, info, mirror)
        if not a.get("look_cam") and "look0" not in CAST.spec(key.split(":")[0])["drawings"][key.split(":")[1]]:
            fst["lookx"] = float(np.clip(fst["lookx"] + turn_look(key), -1.2, 1.2))
    else:
        fst = {}
    B = groove_matrix(g, (fx, fy), Hd)
    Ms2 = compose(Ms, B)
    head = rigid_head(d, g, B, Ms, Hd)
    clip = None
    if a.get("clip") is not None:
        cy_scr = a["clip"] * RS if a.get("screen") else apply(M, 0.0, a["clip"])[1]
        clip = (cy_scr - Ms2[1, 2]) / Ms2[1, 1]
    H_screen = Hd * k
    inst = a.get("inst")
    playing = a.get("playing", 1.0)
    plays = getattr(perf, "PLAYS", {}).get(who)             # spans when this player plays (perf.PLAYS)
    if plays is not None:
        playing = max([ramp(t, t0, t1, 0.2, 0.25) for t0, t1 in plays] or [0.0])
    if inst or a.get("blur") or a.get("cloud"):
        lay = np.zeros((OH, OW, 4), np.float32)
        E.place(lay, d, fst, Ms2, clip=clip, head=head)
        if native:
            from studio.film.concert import play_native
            lay = play_native(lay, native, Ms2, key, t, H_screen, playing, M, R.D)
        elif inst in ("guitar", "bass"):
            lay = play_strings(lay, inst, Ms2, key, t, mirror, H_screen, playing)
        elif inst == "keys":
            lay = play_keys(lay, Ms, Ms2, key, t, playing)
        elif inst == "harmonica":
            harmonica(lay, Ms2, key, t, playing)
        if a.get("cloud"):
            rain_cloud(lay, Ms2, key, t)
        E.over_sparse(shared, lay, a.get("blur", 0.0) * RS)
    else:
        E.place(shared, d, fst, Ms2, clip=clip, head=head)
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
    rs = rng.uniform(0.072, 0.094, n) * OH * opt.get("scale", 1.0)
    arms = rng.random(n) < opt.get("arms", 0.45)
    side = rng.choice([-1.0, 1.0], n)
    jit = rng.random(n)
    rise = rng.uniform(-0.2, 0.25, n)
    kind = rng.integers(0, 4, n)                         # each their own: a jump every beat, a hop every other, a
    off = rng.uniform(-0.14, 0.14, n)                    # bounce, a sway; and a little ahead or behind the beat
    bi0 = S.beat_index(t)
    fists = []
    for i in range(n):
        x, r = xs[i], rs[i]
        q = p0 + 0.5 * (i % 2) + 0.07 * jit[i] + off[i]
        bi, p = bi0 + math.floor(q), q % 1.0
        hh = 0.8 + 0.4 * _h(bi, i + 31)                  # no two jumps the same height
        if kind[i] == 1:                                 # a hop every other beat
            u = ((bi % 2) + p) / 2
            jump = energy * 0.040 * OH * hh * math.sin(math.pi * u) ** 1.1
        elif kind[i] == 2:                               # knees on the beat
            jump = -energy * 0.012 * OH * (0.5 + 0.5 * math.cos(2 * math.pi * p))
        elif kind[i] == 3:                               # swaying, bobbing
            jump = energy * 0.010 * OH * math.sin(math.pi * p)
            x = x + energy * 0.25 * r * math.sin(math.pi * (bi + p) + i)
        else:
            jump = energy * 0.034 * OH * hh * math.sin(math.pi * p) ** 1.2
        cy = top + r - jump + rise[i] * r
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


def draw_stage_edge(img, opt, t, energy):
    """a crowd shot is taken from the stage: its floor across the bottom of the frame (out of focus, red with the
    lights), its front edge catching the light, a wedge monitor in one corner and a mic stand at the side, all close
    to the lens. opt: y (the edge, share of the frame), monitor (-1 / 1: which corner, 0: none), mic (x share of the
    frame, or None), blur"""
    S = SONG()
    kick = S.hit("kick", t, 0.12)
    lay = np.zeros((OH, OW, 4), np.float32)
    ey = opt.get("y", 0.9) * OH
    Y = np.arange(OH, dtype=np.float32)[:, None]
    u = np.clip((Y - ey) / max(1.0, OH - ey), 0, 1)
    floor = (Y >= ey).astype(np.float32)
    shade = (1 - 0.65 * u)
    lay[..., 0] = floor * 0.26 * shade
    lay[..., 1] = floor * 0.040 * shade
    lay[..., 2] = floor * 0.036 * shade
    lay[..., 3] = floor
    lip = np.exp(-((Y - ey) / (0.006 * OH)) ** 2) * (Y > ey - 0.004 * OH)
    lay[..., 0] += lip[:, 0:1] * (0.55 + 0.35 * kick)
    lay[..., 1] += lip[:, 0:1] * 0.12
    lay[..., 2] += lip[:, 0:1] * 0.08
    lay[..., 3] = np.maximum(lay[..., 3], np.clip(lip[:, 0:1] * 1.5, 0, 1))
    side = opt.get("monitor", 1)
    if side:                                                 # a wedge monitor on the stage floor
        w, h = 0.25 * OW, 0.20 * OH
        x0 = OW - w * 0.85 if side > 0 else -0.15 * w
        base = OH + 0.02 * OH
        poly = np.float32([(x0, base), (x0 + w, base), (x0 + w * 0.94, ey - 0.55 * h), (x0 + w * 0.10, ey - 0.42 * h)])
        cv2.fillPoly(lay, [np.int32(poly)], (0.025, 0.022, 0.026, 1.0), cv2.LINE_AA)
        g = np.float32([(x0 + w * 0.16, ey - 0.30 * h), (x0 + w * 0.86, ey - 0.40 * h), (x0 + w * 0.90, base - 0.06 * h),
                        (x0 + w * 0.12, base - 0.06 * h)])
        cv2.fillPoly(lay, [np.int32(g)], (0.055, 0.05, 0.058, 1.0), cv2.LINE_AA)
        cv2.line(lay, tuple(np.int32(poly[3])), tuple(np.int32(poly[2])), (0.60 + 0.3 * kick, 0.12, 0.09, 1.0),
                 max(2, int(0.006 * OH)), cv2.LINE_AA)
    mx = opt.get("mic")
    if mx is not None:                                       # the singer's mic stand, beside the lens
        spec = INSTRUMENTS["mic"]
        im = prop_image(spec["img"])
        scale = 1.6 * OH / im.shape[0]
        gx = mx * OW
        A = np.array([[scale, 0, gx - scale * spec["base"][0]], [0, scale, OH * 1.18 - scale * spec["base"][1]]])
        E.warp_into(lay, im, A.astype(np.float32))
    if opt.get("blur", 9.0) > 0:
        lay = cv2.GaussianBlur(lay, (0, 0), opt.get("blur", 9.0) * RS)
    return img * (1 - lay[..., 3:4]) + lay[..., :3]


def sweep_layer(t, opt, energy):
    """moving lights from the stage sweeping over the crowd and the room: soft coloured spots crossing the frame,
    one pass every two bars, flaring on the kick -> RGB to add (screen size)"""
    S = SONG()
    i = int(np.searchsorted(S.D, t, side="right")) - 1
    pos = max(0, i) + S.bar_phase(t) / 4.0
    kick = S.hit("kick", t, 0.14)
    cols = opt.get("colors", [(1.0, 0.18, 0.12), (1.0, 0.85, 0.65), (1.0, 0.45, 0.12)])
    n = opt.get("n", 3)
    sm_w, sm_h = OW // 8, OH // 8
    Y, X = np.mgrid[0:sm_h, 0:sm_w].astype(np.float32)
    out = np.zeros((sm_h, sm_w, 3), np.float32)
    for k in range(n):
        ph = k / n + opt.get("phase", 0.0)
        cx = sm_w * (0.5 + 0.55 * math.sin(2 * math.pi * (pos / 2.0 + ph)))
        cy = sm_h * (0.38 + 0.20 * math.sin(2 * math.pi * (pos / 4.0 + 0.37 * k + ph)))
        rx, ry = 0.13 * sm_w, 0.22 * sm_h
        d2 = ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2
        out += np.exp(-d2 ** 1.4)[..., None] * np.float32(cols[k % len(cols)])
    out = cv2.resize(out, (OW, OH), interpolation=cv2.INTER_LINEAR)
    return out * opt.get("amount", 0.22) * (0.45 + 0.55 * energy) * (0.7 + 0.6 * kick)


def draw_fans(img, key, P, cx, cy, z, t, amt):
    S = SONG()
    lv = fans_layer(key)
    s = P.scale(z)
    L = next((l for l in (1, 2, 4) if l >= s * 0.95), 4)
    W1 = P.W1
    A = np.float32([[s / L, 0, OW / 2 - s * cx], [0, s / L, OH / 2 - s * cy]])
    lay = cv2.warpAffine(lv[L], A, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # everyone jumping in their own time: a jump of its own every head's width across the crowd (alternate ones a
    # half beat apart, each a little ahead of or behind the beat, no two the same height), blended smoothly between
    xs = (np.arange(OW, dtype=np.float32) - (OW / 2 - s * cx)) / s           # plate x of each column
    n = 11
    cxs = np.linspace(0, W1, n)
    num = np.zeros(OW, np.float32)
    den = np.zeros(OW, np.float32)
    for j in range(n):
        q = S.beat_index(t) + S.phase(t) + 0.5 * (j % 2) + 0.12 * (2 * _h(j, 5) - 1)
        bi, p = math.floor(q), q % 1.0
        hop = (j % 3 == 2)                                   # some only every other beat
        u = ((bi % 2) + p) / 2 if hop else p
        up = (0.8 + 0.4 * _h(bi // (2 if hop else 1), j + 17)) * math.sin(math.pi * u) ** 1.2
        g = np.exp(-((xs - cxs[j]) / (0.5 * W1 / (n - 1))) ** 2)
        num += g * up
        den += g
    jump = amt * 0.035 * OH * num / np.maximum(den, 1e-6)
    my = np.arange(OH, dtype=np.float32)[:, None] + jump[None, :]
    mx = np.broadcast_to(np.arange(OW, dtype=np.float32)[None, :], (OH, OW))
    lay = cv2.remap(lay, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return lay[..., :3] + img * (1 - lay[..., 3:4])


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
    if s.get("grade", "stage") == "stage":
        sharp = plate_tone(sharp, s.get("plate_tone", 0.72))
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
        wash = [(1.0, 0.34, 0.22), (0.28, 0.48, 1.0), (1.0, 0.24, 0.70),
                (0.18, 0.95, 1.0), (1.0, 0.82, 0.54)]
        bi = max(0, S.beat_index(t))
        col = np.float32(wash[(bi // 4) % len(wash)])
        img = img + lm * k * col
    if dark > 0:
        img = img * (1 - 0.82 * dark)
    sweep = sweep_layer(t, s["sweep"], energy) if s.get("sweep") else None
    if sweep is not None:
        img = img + sweep
    room = img                                           # what the haze glows with: the room's lights, not the band
    D_ = R.D
    if s["plate"] == "PUB" and getattr(D_, "FLAGS", None) and s.get("flags", True):
        from studio.film import fx                       # flags raised at the back of the room, behind everyone
        img = fx.flags(img, t, D_.FLAGS, S.beat_index(t) + S.phase(t))
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
        elif kind == "stage_edge":
            img = draw_stage_edge(img, val, t, energy)
        elif kind == "pyro":                             # spark fountains on the stage's front edge
            from studio.film import fx
            bursts = getattr(D_, "PYRO", [])
            big = [b for b in bursts if b[2] >= 1.2]
            img = fx.sparks_plate(img, t, M, sc, bursts, getattr(D_, "FOUNTAINS", []), getattr(D_, "PYRO_H", 280),
                                  dark=dark)
            if big and getattr(D_, "FOUNTAINS_BIG", None):          # in front of the band: lower, gentler
                img = fx.sparks_plate(img, t, M, sc, big, D_.FOUNTAINS_BIG, 0.7 * getattr(D_, "PYRO_H", 280), dark=dark,
                                      glow_k=0.6, rate=110.0)
        elif kind == "pyro_near":                        # the same fountains seen from the stage: beside the lens
            from studio.film import fx
            img = fx.sparks_screen(img, t, getattr(D_, "PYRO", []))
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
                lay = E.rim(lay, 0.0, 1.0, s["rim"] * (0.55 + 0.45 * kick), s.get("rim_color", (1.0, 0.86, 0.70)),
                            5 * RS)
            if sweep is not None:                             # the moving lights pass over them too
                lay[..., :3] += sweep * lay[..., 3:4] * 0.45
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
    bl = None
    if lamps and s.get("beams", 1.0) > 0:
        bl = beams(t, M, sc, lamps, s.get("beams", 1.0) * (0.35 + 0.65 * energy))
        img = img + bl
    # haze: the air glows with the lamps and the beams
    if s.get("haze", 0.0) > 0:
        src = room + bl if bl is not None else room
        glow = cv2.resize(np.clip(src - 0.55, 0, 1), (OW // 4, OH // 4), interpolation=cv2.INTER_AREA)
        glow = cv2.GaussianBlur(glow, (0, 0), 7.5 * RS)
        img = img + cv2.resize(glow, (OW, OH), interpolation=cv2.INTER_LINEAR) * s["haze"]
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
    cf = getattr(D_, "CONFETTI", None)
    if cf and s.get("confetti", True):
        from studio.film import fx
        img = fx.confetti(img, t, *cf)
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


def plate_tone(img, k):
    """the stage behind the band taken down: its mid-tones darker (k), its lamps and their glow kept, so the band
    stands out against it"""
    if k >= 1.0:
        return img
    lum = img.max(2, keepdims=True)
    return img * (k + (1 - k) * np.clip((lum - 0.70) / 0.25, 0, 1))


@functools.lru_cache(maxsize=2)
def vignette(h, w, amt):
    Y, X = np.ogrid[0:h, 0:w]
    r2 = ((X - w / 2) / (w / 2)) ** 2 * 0.6 + ((Y - h / 2) / (h / 2)) ** 2 * 0.4
    return (1 - amt * np.clip(r2, 0, 1.5) ** 1.3).astype(np.float32)[..., None]


def grade_stage(img, kind):
    if kind == "stage":                                      # gig: contrast, bloom on the lights only, a vignette
        bloom = cv2.GaussianBlur(np.clip(img - 0.82, 0, 1), (0, 0), 14 * RS)
        img = (img - 0.5) * 1.10 + 0.5
        img = img + bloom * np.float32([0.8, 0.5, 0.4])
        img = img * vignette(img.shape[0], img.shape[1], 0.22)
    elif kind == "crowd":                                    # the room: warm, a little softer
        bloom = cv2.GaussianBlur(np.clip(img - 0.70, 0, 1), (0, 0), 18 * RS)
        img = (img - 0.5) * 1.06 + 0.5
        img = img * np.float32([1.03, 0.99, 0.95]) + bloom * 0.5
        img = img * vignette(img.shape[0], img.shape[1], 0.25)
    return img
