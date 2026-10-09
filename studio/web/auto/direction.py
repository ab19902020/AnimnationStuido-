"""A web episode's shot list, worked out the All or Something way from where everyone stands and who talks to whom.

Each scene is one background with its cast standing in it at true scale (studio.json scenes[k].stage). From that:

  * each scene opens on its whole set, easing in on the cast while the place caption is up
  * close singles on whoever is talking: the set behind them out of focus at the same scale it has in the wide
    (so the room stays the same room), the character placed on the side of the frame away from who they talk to,
    turned towards them, with a slow push in, framed so the hanging hands stay out of shot; the last line of a
    scene gets a stronger push
  * a cut on every change of speaker (on the gap before the line); a speaker who carries on for a long time gets a
    two-shot with whoever they are talking to; every few changes the scene opens out to a two-shot or the wide
  * a reaction: in a long line answered by the person it is said to, the cut to them comes early, on a word, so we
    see the line land before they answer
  * name captions on each character's first single, then the title card

The geometry is in 1x background px (`plate px`) and 1920 x 1080 screen px, as in studio/film/shots.py. Eyelines
differ from scene to scene, so EYES follows the scene of the frame being rendered (set by shot_at)."""
import json

from studio.film import ep
from studio.film.shots import Marks, card, finish, shot_at as _shot_at, single, world
from studio.web.auto import spec as S
from studio.web.auto.timeline import OPEN, TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le = T.m, T.ls, T.le

PLATES = {k: b for b, k in S.PLATE.items()}
OCCL = {}
WHIPS = []
DRAW = {cid: S.draw(cid) for cid in S.WHO}


def _ensure_built():
    """the drawings must be cut and measured before the staging can be worked out (studio.film.art)"""
    from studio.paths import BUILD
    for cid, key in DRAW.items():
        name = key.split(":")[1]
        mf = BUILD / "film" / cid / "meta.json"
        if not (BUILD / "film" / cid / f"{name}.png").exists() or name not in (json.loads(mf.read_text()) if mf.exists() else {}):
            from studio.film import art
            art.build(cid, [name])


_ensure_built()
from studio.film.cast import CAST, feet, hands  # noqa: E402  (after the drawings exist)


# ---------------------------------------------------------------- where everyone stands
def _faces_towards(cid, sgn):
    """mirror the drawing so it faces screen direction sgn (+1 right, -1 left, 0 the lens)?"""
    f = CAST.get(DRAW[cid])[1]["faces"]
    return (f == "R" and sgn < 0) or (f == "L" and sgn > 0)


def _stand(k, cid):
    """-> dict(x, eye (plate px), ed (plate px), mirror) for the character standing on scene k's set"""
    sc = S.SCENES[k]
    W1, H1 = S.SIZE[sc["background"]]
    c = sc["stage"][cid]
    d, info = CAST.get(DRAW[cid])
    top = d.oy
    bottom = d.oy + d.size(1.0)[1] / d.S
    fx, fy = feet(DRAW[cid])
    kk = float(c["height"]) * H1 / max(1.0, bottom - top)             # plate px per sheet px
    x, floor = float(c["x"]) * W1, float(c["floor"]) * H1
    xs = [v["x"] for o, v in sc["stage"].items() if o != cid]
    mid = sum(xs) / len(xs) if xs else c["x"]
    mirror = _faces_towards(cid, 0 if abs(mid - c["x"]) < 1e-6 else (1 if mid > c["x"] else -1))
    ax, ay = info["anchor"]
    sg = -1.0 if mirror else 1.0
    return dict(x=x, eye=(x + sg * (ax - fx) * kk, floor - (fy - ay) * kk), ed=info["ed"] * kk, mirror=mirror)


STAND = [{cid: _stand(k, cid) for cid in sc["stage"] if cid in S.CAST} for k, sc in enumerate(S.SCENES)]


def _hands_clear(cid, ey=400):
    """the smallest eye distance (screen px) at which a single with the eyes at ey has the hanging hands below the
    frame: the house singles never show them (in a seated set a table edge would hide them)"""
    _, info = CAST.get(DRAW[cid])
    try:
        hs = hands(DRAW[cid])
    except Exception:  # noqa: BLE001  (no hands found: no limit)
        hs = {}
    if not hs:
        return 0.0
    top = min(h[1] - h[2] for h in hs.values())
    below = (top - info["anchor"][1]) / info["ed"]       # eye distances from the eyes down to the hands
    return (1080 + 30 - ey) / below if below > 0.5 else 0.0


HANDS = {cid: _hands_clear(cid) for cid in S.WHO}


def side(k, a, b):
    """screen direction from a to b in scene k: +1 right, -1 left, 0 (the lens, or not in the scene)"""
    st = STAND[k]
    if a not in st or b not in st:
        return 0
    dx = st[b]["eye"][0] - st[a]["eye"][0]
    return 0 if abs(dx) < 1 else (1 if dx > 0 else -1)


# gaze towards characters out of frame in a single, per scene: screen direction (x, y) and head turn
SCENE_EYES = [{a: {b: (0.75 * side(k, a, b), 0.04, 0.28 * side(k, a, b)) for b in STAND[k] if b != a} for a in STAND[k]}
              for k in range(len(S.SCENES))]


class _Eyes(dict):
    """the eyelines of the scene being rendered (studio/film/render.py reads D.EYES.get(who))"""
    scene = 0

    def get(self, who, default=None):
        return SCENE_EYES[self.scene].get(who, default if default is not None else {})


EYES = _Eyes()


def actors(k):
    return [(cid, DRAW[cid], st["eye"], st["ed"], st["mirror"]) for cid, st in STAND[k].items()]


def plate_of(k):
    b = S.SCENES[k]["background"]
    return S.PLATE[b], S.SIZE[b]


# ---------------------------------------------------------------- the kinds of shot
def wide(t, k, push=1.12, z0=1.0, blur=0.0, **extra):
    """scene k's set with its cast in it, easing in on them"""
    pk, (W1, H1) = plate_of(k)
    st = STAND[k]
    c0 = (W1 / 2, H1 / 2, z0)
    if st:
        cx = sum(v["eye"][0] for v in st.values()) / len(st)
        cy = sum(v["eye"][1] for v in st.values()) / len(st)
        c1 = (W1 / 2 + (cx - W1 / 2) * 0.5, H1 / 2 + (cy - H1 / 2) * 0.35, z0 * push)
    else:
        c1 = (W1 / 2, H1 / 2, z0 * push)
    return world(t, pk, c0, c1, layers=[("actors", actors(k))], drift=0.35, blur=blur, scene=k, **extra)


def two(t, k, a, b, push=1.05):
    """a pair at true scale, framed so their eyes are about 520 px apart on screen"""
    pk, (W1, H1) = plate_of(k)
    SX = 1920.0 / W1
    ea, eb = STAND[k][a]["eye"], STAND[k][b]["eye"]
    gap = max(abs(ea[0] - eb[0]), 2.5 * max(STAND[k][a]["ed"], STAND[k][b]["ed"]))
    z = min(3.2, max(1.15, 520.0 / (gap * SX)))
    sc = SX * z
    cx, cy = (ea[0] + eb[0]) / 2, (ea[1] + eb[1]) / 2 + (540 - 430) / sc
    return world(t, pk, (cx, cy, z), (cx, cy, z * push), layers=[("actors", actors(k))], drift=0.5, blur=1.6, scene=k)


def close(t, k, who, to=None, ed=110.0, push=(1.0, 1.04)):
    """a close single: the character on the side of the frame away from who they look at, the set behind them at
    the scale it has in the wide (out of focus)"""
    pk, (W1, H1) = plate_of(k)
    SX = 1920.0 / W1
    st = STAND[k][who]
    sgn = side(k, who, to) if to else 0
    ex, ey = 960 - 190 * sgn, 400
    ed = max(ed, min(175.0, HANDS[who]))                 # tight enough that the hands are out of the frame
    z = min(4.0, max(1.2, ed / (st["ed"] * SX)))        # the set at the character's own scale
    sc = SX * z
    bg = (pk, st["eye"][0] + (960 - ex) / sc, st["eye"][1] + (540 - ey) / sc, z, 4.5)
    mirror = _faces_towards(who, sgn) if sgn else st["mirror"]
    return single(t, who, DRAW[who], bg, None, ed=ed, eye=(ex, ey), push=push, drift=0.8, mirror=mirror, scene=k)


# ---------------------------------------------------------------- who each line is said to
def _to(i):
    ln = S.LINES[i]
    k = ln["scene"]
    if ln.get("to") == "cam" or (ln.get("to") in STAND[k] and ln["to"] != ln["who"]):
        return ln["to"]
    for j in (i - 1, i + 1, i - 2, i + 2):            # the one they are answering, or the one who answers them
        if 0 <= j < len(S.LINES) and S.LINES[j]["scene"] == k and S.LINES[j]["who"] != ln["who"]:
            return S.LINES[j]["who"]
    others = [o for o in STAND[k] if o != ln["who"]]
    if others:
        return min(others, key=lambda o: abs(STAND[k][o]["x"] - STAND[k][ln["who"]]["x"]))
    return "cam"


TO = {ln["id"]: _to(i) for i, ln in enumerate(S.LINES)}


# ---------------------------------------------------------------- the edit
def _shots():
    if not S.LINES:
        return [wide(0.0, 0)]
    out = []
    sizes = [(110.0, (1.0, 1.04)), (118.0, (1.0, 1.05)), (104.0, (1.0, 1.035))]
    on = None
    since = changes = 0
    for i, ln in enumerate(S.LINES):
        lid, who, to, k = ln["id"], ln["who"], TO[ln["id"]], ln["scene"]
        first = i == 0 or S.LINES[i - 1]["scene"] != k
        last = i + 1 == len(S.LINES) or S.LINES[i + 1]["scene"] != k
        if first:                                         # the scene's set, then in to the first speaker
            t0 = 0.0 if i == 0 else m(f"scene_{k}")
            out.append(wide(t0, k, opening=True))
            t = max(t0 + 0.6, ls(lid) - 0.35)
            on, changes = None, 0
        else:
            t = m(f"pre_{lid}")
        if who == on and ls(lid) - since < 7.0:
            pass                                          # the same speaker carries on: no cut
        elif who == on and to in STAND[k]:
            out.append(two(t, k, who, to))                 # carried on too long: open out to the pair
            on, since = None, t
        else:
            changes += 1
            if changes > 2 and changes % 5 == 4 and to in STAND[k]:
                out.append(two(t, k, who, to))
                on = None
            elif changes > 2 and changes % 7 == 6 and len(STAND[k]) > 2:
                out.append(wide(t, k, push=1.06, z0=1.08, blur=0.8))
                on = None
            else:
                ed, push = sizes[changes % 3]
                out.append(close(t, k, who, to, ed, (1.0, 1.08) if last else push))
                on = who
            since = t
        # a reaction: a long line, answered by the one it is said to: cut to them on a word late in the line
        nxt = S.LINES[i + 1] if not last else None
        dur = le(lid) - ls(lid)
        if nxt and nxt["who"] == to and to in STAND[k] and dur > 4.0 and to != on:
            ws = [ls(lid) + w["s"] for w in L[lid]["words"] if 0.62 * dur < w["s"] < dur - 0.9]
            if ws:
                out.append(close(ws[0], k, to, who, 110.0, (1.0, 1.03)))
                on, since = to, ws[0]
    if "cut_title" in TL["marks"]:
        out.append(card(m("cut_title"), "title"))
    return out


SHOTS = finish(_shots(), TL["total"])


def _bebas(text, size, y):
    return (text.upper(), "BEBAS", size, None, 10, y, (255, 255, 255))


TITLE = tuple(x for x in ((_bebas(S.SPEC["show"], 120, 300) if S.SPEC.get("show") else None),
                          (_bebas(S.SPEC["title"], 150, 420) if S.SPEC.get("title") else None)) if x)
TAGLINE = ((S.SPEC["tagline"].upper(), "BEBAS", 60, None, 5, 760, (236, 236, 236)),) if S.SPEC.get("tagline") else ()


def _captions():
    caps = []
    for s in SHOTS:
        if s.get("opening"):
            sc = S.SCENES[s["scene"]]
            if sc.get("place"):
                caps.append((s["t"] + 0.35, max(s["t"] + 0.6, s["end"] - 0.45), "place", sc["place"].upper(),
                             sc.get("place_sub", "")))
    seen = set()
    for s in SHOTS:
        who = s.get("who")
        if s["kind"] == "single" and who and who not in seen and s["end"] - s["t"] > 1.2:
            seen.add(who)
            sub = S.CAST[who].get("caption") or str(S.info(who).get("role", "")).capitalize()
            caps.append((s["t"] + 0.25, s["end"] - 0.05, "name", S.name(who).upper(), sub))
    return caps


CAPTIONS = _captions()


def shot_at(t):
    s = _shot_at(SHOTS, t)
    if s.get("scene") is not None:
        EYES.scene = s["scene"]
    return s
