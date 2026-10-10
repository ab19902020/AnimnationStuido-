"""Render an episode (from All or Something): every frame is the shot at that time (the episode's direction.py)
-> the set, the characters with their face and body state (perf.py), their props and the furniture in front of
them -> grade -> captions -> vignette and grain. 1920 x 1080, 30 fps (EP_RES=960x540 for quick previews).

Kinds of shot (built with the helpers in studio.film.shots):
  single  one character close: the set behind (a plate view, blurred: shallow depth of field), the character
          (placed by the point between his eyes and his eye distance), the furniture edge in front
  world   characters placed in a plate at true scale (1x plate px) with the plate's own furniture in front
  group   several characters composited like a single (blurred set behind, furniture edge in front)
  insert  a full-frame close-up drawn by the episode's props.py (a screen, a sign, a document)
  black / title   black with closing captions / the title card
Any shot with `still=True` is a freeze frame: it holds its first frame (a comic freeze before the cut to black).
A world shot with `shakes=[(t0, t1, px)]` jolts on a shout; with `shadow={...}` it grounds its actors: contact
shadows on the furniture they sit in, pools under their shoes (see shadows())."""
import importlib
import math
import os
import subprocess
import sys

import cv2
import numpy as np

from studio.film import engine as E
from studio.film import graphics as G
from studio.film.cast import CAST
from studio.film.engine import FPS, OH, OW, RS
from studio.film.shots import ease

D = importlib.import_module("film.direction")
PERF = importlib.import_module("film.perf").PERF
try:
    X = importlib.import_module("film.props")
except ModuleNotFoundError:
    X = None

_PL = {}


def plate(k):
    if k not in _PL:
        img = X.plate_image(k) if X is not None and hasattr(X, "plate_image") else None
        if img is not None:
            _PL[k] = E.Plate(None, D.OCCL.get(k), image=img)
        else:
            from studio.episode.upscale import upscaled
            from studio.paths import BACKGROUNDS
            src = BACKGROUNDS / f"{D.PLATES[k]}.png"
            big = upscaled(src, 4.0)
            _PL[k] = E.Plate(None, D.OCCL.get(k), image=big[..., ::-1].copy())
    return _PL[k]


def drift(t, s, amt):
    """handheld documentary camera: slow, small wander (screen px)"""
    k = s["i"] * 1.37
    dx = (6.0 * math.sin(t * 0.9 + k) + 3.0 * math.sin(t * 2.1 + 2 * k)) * RS * amt
    dy = (4.0 * math.sin(t * 0.7 + 3 * k) + 2.0 * math.sin(t * 1.9 + k)) * RS * amt
    return dx, dy


def shake(t, amt):
    f = int(t * FPS)
    r0, r1 = np.random.default_rng(f), np.random.default_rng(f + 1)
    u = t * FPS - f
    a, b = r0.uniform(-1, 1, 2), r1.uniform(-1, 1, 2)
    v = a * (1 - u) + b * u
    return float(v[0] * amt * RS), float(v[1] * amt * RS)


def zoom_about(P, cx, cy, z, f, F):
    """the view (cx, cy, z) zoomed by f about screen point F"""
    s = P.scale(z)
    px, py = cx + (F[0] - OW / 2) / s, cy + (F[1] - OH / 2) / s
    s2 = s * f
    return px - (F[0] - OW / 2) / s2, py - (F[1] - OH / 2) / s2, z * f


def face_state(st, info, mirror):
    """perf state -> the drawing's own face parameters (look offset for the drawing, mirrored when flipped)"""
    l0 = info["look0"]
    sg = -1.0 if mirror else 1.0
    out = dict(st)
    out["lookx"] = max(-1.2, min(1.2, sg * st["lookx"] + l0[0]))
    out["looky"] = max(-0.8, min(1.0, st["looky"] + l0[1]))
    out["turn"] = max(-0.9, min(0.9, sg * st["turn"]))
    out["tilt"] = sg * st["tilt"]
    return out


def actor_matrix(info, ex, ey, k, mirror=False, lean=0.0, sink=0.0, ed=None):
    """sheet px -> screen px: the drawing's anchor (between the eyes) at (ex, ey), k screen px per sheet px"""
    ax, ay = info["anchor"]
    k2 = k * (1 + 0.07 * lean - 0.05 * sink)
    ed_s = ed if ed else info["ed"] * k
    ey = ey + ed_s * (0.25 * lean + 0.55 * sink)
    sx = -k2 if mirror else k2
    return np.float64([[sx, 0, ex - sx * ax], [0, k2, ey - k2 * ay]])


# ---------------------------------------------------------------- gaze resolution per shot
def single_resolver(s):
    who = s["who"]

    def res(g):
        if g == "cam":
            return (0.0, 0.0, 0.0)
        if g == "down":
            return (0.05, 0.85, 0.0)
        if isinstance(g, tuple) and g[0] == "dir":
            return g[1:]
        return D.EYES.get(who, {}).get(g, (0.0, 0.05, 0.0))
    return res


def world_resolver(s, who, pos):
    """inside a wide or a lineup: towards where the target is on screen (pos: who -> screen x)"""
    def res(g):
        if g == "cam":
            return (0.0, 0.0, 0.0)
        if g == "down":
            return (0.08, 0.85, 0.0)
        if isinstance(g, tuple) and g[0] == "dir":
            return g[1:]
        if g in pos and who in pos:
            dx = pos[g] - pos[who]
            if abs(dx) < 1:
                return (0.0, 0.05, 0.0)
            sgn = 1.0 if dx > 0 else -1.0
            return (0.9 * sgn, 0.05, 0.35 * sgn)
        return D.EYES.get(who, {}).get(g, (0.0, 0.05, 0.0))
    return res


# ---------------------------------------------------------------- shots
def render_single(s, t, extra_dx=0.0):
    u = (t - s["t"]) / max(1e-3, s["end"] - s["t"])
    p = s["push"][0] + (s["push"][1] - s["push"][0]) * ease(u)
    if s.get("punch") and t >= s["punch"][0]:          # a snap punch-in on the punchline (3 frames)
        p *= 1 + (s["punch"][1] - 1) * ease((t - s["punch"][0]) / 0.1)
    dx, dy = drift(t, s, s["drift"])
    if s.get("shake"):
        sx, sy = shake(t, 9.0)
        dx += sx
        dy += sy
    ex, ey = s["eye"][0] * RS, s["eye"][1] * RS
    EDS = s["ed"] * RS
    F = (ex, ey)
    pk, cx, cy, z, blur = s["bg"]
    P = plate(pk)
    cx, cy, z = zoom_about(P, cx, cy, z, p ** 0.35, F)      # the set behind zooms less (parallax)
    sc = P.scale(z)
    cx, cy = P.clamp(cx - dx * 0.6 / sc, cy - dy * 0.6 / sc, z)
    bg = P.render(cx, cy, z)
    if blur > 0:
        bg = cv2.GaussianBlur(bg, (0, 0), blur * RS)
    q = s.get("quiet", 0.0) * G.sm((t - s["t"] - 0.2) / 1.2)
    if q > 0:                                                # the button: the room goes quiet behind him
        l = bg.mean(2, keepdims=True)
        bg = (l + (bg - l) * (1 - 0.55 * q)) * (1 - 0.32 * q)
    d, info = CAST.get(s["draw"])
    mirror = s.get("mirror", False)
    st = PERF.state(s["who"], t, single_resolver(s), s["t"])
    k = EDS * p / info["ed"]
    ex2, ey2 = ex + dx + extra_dx, ey + dy
    Ms = actor_matrix(info, ex2, ey2, k, mirror, st["lean"], st["sink"])
    lay = np.zeros((OH, OW, 4), np.float32)
    for fn in s.get("behind", []):                           # props behind the character (his chair's mic...)
        getattr(X, fn)(lay, s, t, ex2, ey2, EDS * p, st)
    E.place(lay, d, face_state(st, info, mirror), Ms, clip=s.get("clip"))
    for fn in s.get("props", []):                            # props in his hands / in front of him
        getattr(X, fn)(lay, s, t, ex2, ey2, EDS * p, st)
    img = bg * (1 - lay[..., 3:4]) + lay[..., :3]
    if s["fg"] and s.get("table", 1) > 0:                     # the furniture edge in front of him
        fk, mname, fcx, edge, fz, fblur = s["fg"]
        P2 = plate(fk)
        fz2 = fz * p ** 1.1
        s2 = P2.scale(fz2)
        ty = ey + s["table"] * EDS * p + dy * 1.15
        bottom = Ms[1, 1] * (d.oy + d.size(1.0)[1] / d.S) + Ms[1, 2]
        ty = min(ty, bottom - 10 * RS)                        # never below the drawing's own bottom edge
        fcy = edge - (ty - OH / 2) / s2
        fcx2 = fcx - dx * 1.15 / s2
        fimg = P2.render(fcx2, fcy, fz2)
        msk = P2.mask(mname, fcx2, fcy, fz2)
        if fblur > 0:
            fimg = cv2.GaussianBlur(fimg, (0, 0), fblur * RS)
            msk = cv2.GaussianBlur(msk, (0, 0), max(0.8, fblur * 0.5) * RS)
        if q > 0:
            fimg = fimg * (1 - 0.25 * q)
        img = img * (1 - msk[..., None]) + fimg * msk[..., None]
    return G.grade(img, s.get("grade", "studio"), t)


def cam_at(s, t):
    if s.get("cams"):
        ks = s["cams"]
        k = max([i for i, (tk, _) in enumerate(ks) if tk <= t] or [0])
        if k == 0 and t < ks[0][0]:
            return ks[0][1]
        if k + 1 < len(ks):
            u = ease((t - ks[k][0]) / max(1e-3, ks[k + 1][0] - ks[k][0]))
            return tuple(a + (b - a) * u for a, b in zip(ks[k][1], ks[k + 1][1]))
        return ks[k][1]
    u = ease((t - s["t"]) / max(1e-3, s["end"] - s["t"]), s.get("ease", "inout"))
    return tuple(a + (b - a) * u for a, b in zip(s["cam0"], s["cam1"]))


def render_world(s, t):
    """the set at true scale; with `blur` the far wall is out of focus while the furniture named in ("near", mask)
    layers (behind the actors) and ("occl", mask) layers (in front of them) stays sharp, at the actors' depth"""
    P = plate(s["plate"])
    cx, cy, z = cam_at(s, t)
    dx, dy = drift(t, s, s["drift"])
    for t0, t1, amt in s.get("shakes", []):                 # a jolt on a shout, dying away over (t0, t1)
        if t0 <= t < t1:
            sx, sy = shake(t, amt * (1 - (t - t0) / (t1 - t0)) ** 1.5)
            dx += sx
            dy += sy
    sc = P.scale(z)
    cx, cy = P.clamp(cx - dx / sc, cy - dy / sc, z)
    sharp = P.render(cx, cy, z)
    bg = cv2.GaussianBlur(sharp, (0, 0), s["blur"] * RS) if s.get("blur", 0) > 0 else sharp
    M = P.M(cx, cy, z)
    img = bg.copy()
    pos = {}
    for kind, val in s["layers"]:
        if kind == "actors":
            for a in val:
                pos[a[0]] = M[0, 0] * a[2][0] + M[0, 2]
    for kind, val in s["layers"]:
        if kind in ("occl", "near"):
            msk = P.mask(val, cx, cy, z)[..., None]
            img = img * (1 - msk) + sharp * msk
            continue
        if kind == "props":
            img = getattr(X, val)(img, s, t, M, sc)
            continue
        lay = np.zeros((OH, OW, 4), np.float32)
        soles = []
        for a in val:
            who, draw, (px, py), ed_p, mirror = a[:5]
            opt = a[5] if len(a) > 5 else {}
            d, info = CAST.get(draw)
            ex, ey = M[0, 0] * px + M[0, 2], M[1, 1] * py + M[1, 2]
            k = ed_p * sc / info["ed"]
            st = PERF.state(who, t, world_resolver(s, who, pos), s["t"]) if d.has_face else {}
            Ms = actor_matrix(info, ex, ey, k, mirror, st.get("lean", 0.0), st.get("sink", 0.0))
            E.place(lay, d, face_state(st, info, mirror) if st else {}, Ms, clip=opt.get("clip"))
            if s.get("shadow"):
                from studio.film.cast import feet
                fx, fy = feet(draw)
                soles.append((Ms[0, 0] * fx + Ms[0, 2], Ms[1, 1] * fy + Ms[1, 2], ed_p * sc))
        if s.get("shadow"):
            img = shadows(img, s["shadow"], lay[..., 3], soles, P, cx, cy, z)
        img = img * (1 - lay[..., 3:4]) + lay[..., :3]
    return G.grade(img, s.get("grade", "studio"), t)


def shadows(img, sh, alpha, soles, P, cx, cy, z):
    """the actors grounded in a world shot: their silhouettes darken the furniture they sit in (a soft contact
    shadow, cast a little down and to one side, only on the plate's `on` mask), and a soft pool on the floor under
    each one's shoes. sh: {on: mask, k, blur, dx, dy (eye distances), floor: strength, spread: half-width in eye
    distances}"""
    if not soles:
        return img
    ed = float(np.mean([e for _, _, e in soles]))
    k = sh.get("k", 0.4)
    if k > 0:
        dx, dy = sh.get("dx", 0.1) * ed, sh.get("dy", 0.2) * ed
        a = cv2.warpAffine(alpha, np.float32([[1, 0, dx], [0, 1, dy]]), (OW, OH))
        a = cv2.GaussianBlur(a, (0, 0), max(1.0, sh.get("blur", 0.35) * ed))
        recv = P.mask(sh["on"], cx, cy, z) if sh.get("on") else 1.0
        img = img * (1 - k * np.clip(a * 1.3, 0, 1) * recv)[..., None]
    fk = sh.get("floor", 0.0)
    if fk > 0:
        pool = np.zeros((OH, OW), np.float32)
        for x, y, e in soles:
            rx, ry = sh.get("spread", 2.3) * e, 0.32 * e
            cv2.ellipse(pool, (int(x * 4), int((y - 0.08 * e) * 4)), (int(rx * 4), int(ry * 4)), 0, 0, 360, 1.0, -1,
                        cv2.LINE_AA, 2)
        pool = cv2.GaussianBlur(pool, (0, 0), max(1.0, 0.22 * ed))
        img = img * (1 - fk * pool)[..., None]
    return img


def render_group(s, t):
    fx, fy, z = cam_at(s, t)
    dx, dy = drift(t, s, s["drift"])

    def S(x, y):
        return ((x - fx) * z * RS + OW / 2 + dx, (y - fy) * z * RS + OH / 2 + dy)

    pk, cx, cy, zz, blur = s["bg"]
    P = plate(pk)
    s0 = P.scale(zz) / RS
    zb = zz * z ** 0.35
    cxb = cx + (fx - 960) * 0.35 / s0 - dx * 0.6 / P.scale(zb)
    cyb = cy + (fy - 540) * 0.35 / s0 - dy * 0.6 / P.scale(zb)
    cxb, cyb = P.clamp(cxb, cyb, zb)
    img = P.render(cxb, cyb, zb)
    if blur > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur * RS)
    pos = {a[0]: S(*a[2])[0] for a in s["actors"]}
    lay = np.zeros((OH, OW, 4), np.float32)
    for a in s["actors"]:
        who, draw, (px, py), ed, mirror = a[:5]
        opt = a[5] if len(a) > 5 else {}
        d, info = CAST.get(draw)
        ex, ey = S(px, py)
        st = PERF.state(who, t, world_resolver(s, who, pos), s["t"])
        Ms = actor_matrix(info, ex, ey, ed * z * RS / info["ed"], mirror, st["lean"], st["sink"])
        E.place(lay, d, face_state(st, info, mirror), Ms, clip=opt.get("clip"))
    img = img * (1 - lay[..., 3:4]) + lay[..., :3]
    if s.get("fg"):
        fk, mname, fcx, edge, fz, fblur = s["fg"]
        P2 = plate(fk)
        fz2 = fz * z ** 1.1
        s2 = P2.scale(fz2)
        ty = S(0, s["table_y"])[1] + dy * 0.15
        fcy = edge - (ty - OH / 2) / s2
        fcx2 = fcx + (fx - 960) * RS * 1.1 / P2.scale(fz) - dx * 1.15 / s2
        fimg = P2.render(fcx2, fcy, fz2)
        msk = P2.mask(mname, fcx2, fcy, fz2)
        if fblur > 0:
            fimg = cv2.GaussianBlur(fimg, (0, 0), fblur * RS)
            msk = cv2.GaussianBlur(msk, (0, 0), max(0.8, fblur * 0.5) * RS)
        img = img * (1 - msk[..., None]) + fimg * msk[..., None]
    return G.grade(img, s.get("grade", "studio"), t)


def render_frame(f):
    t = f / FPS
    s = D.shot_at(t)
    kind = s["kind"]
    if s.get("still"):                                        # a freeze frame: the shot holds its first frame
        t = s["t"]
    if kind == "black":
        img = np.zeros((OH, OW, 3), np.float32)
    elif kind == "title":
        img = G.title_card(t, s["t"], D.TITLE, D.TAGLINE)
    elif kind == "insert":
        img = getattr(X, s["draw"])(s, t)
    elif kind == "single":
        img = render_single(s, t)
    elif kind == "group":
        img = render_group(s, t)
    elif kind == "stage":                                     # a music video's stage (studio/film/stage.py)
        from studio.film import stage
        img = stage.render(s, t)
    else:
        img = render_world(s, t)
    # whip pan: the camera swings across the cut with a directional motion blur
    for tw in getattr(D, "WHIPS", []):
        a = 1 - abs(t - tw) * FPS / 3.0
        if a > 0:
            n = max(3, int(110 * RS * a)) | 1
            img = cv2.filter2D(img, -1, np.ones((1, n), np.float32) / n, borderType=cv2.BORDER_REFLECT)
            sh = (t - tw) * FPS * 70 * RS
            z = 1 + 2.2 * abs(sh) / OW
            img = cv2.warpAffine(img, np.float32([[z, 0, OW / 2 * (1 - z) + sh], [0, z, OH / 2 * (1 - z)]]),
                                 (OW, OH), borderMode=cv2.BORDER_REPLICATE)
    img = G.captions(img, t, getattr(D, "CAPTIONS", []))
    if kind not in ("black", "title"):
        img = G.finish(img, f)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def still(ts, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in ts:
        img = render_frame(int(round(t * FPS)))
        p = out_dir / f"still_{t:06.2f}.jpg"
        cv2.imwrite(str(p), img[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])
        paths.append(p)
    return paths


def chunk(a, b, out):
    if os.environ.get("FILM_THREADS"):
        cv2.setNumThreads(int(os.environ["FILM_THREADS"]))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{OW}x{OH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                          "-threads", "1", "-rc-lookahead", "10",          # lean: four chunks share the machine's memory
                          "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for f in range(a, b):
        p.stdin.write(render_frame(f).tobytes())
        if (f - a) % 60 == 0:
            print(f"frame {f}/{b}", flush=True)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    # python3 -m studio.film.render chunk A B OUT   (run by studio.film's `render` step, one per core)
    if sys.argv[1] == "chunk":
        chunk(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
