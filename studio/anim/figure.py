"""A posable figure from a T-pose rig (studio.rig.tpose): forward kinematics, skinned limbs, compositing.

    f = Figure("bruno-fernandes")                       # builds the rig first if it is not built
    f.draw(frame, pose, x, y, scale)                    # onto a BGR frame; (x, y) is the floor under the feet
    pose = dict(root=(dx, dy), angles={bone: degrees}, offset={bone: (dx, dy)}, scale={bone: (sx, sy)}, front="R")

Bones are the skeleton of studio.rig.tpose.rig_json: pelvis > torso > head; torso > upper_arm > forearm > hand (R, L);
pelvis > thigh > shin > foot (R, L). A bone turns about its pivot, which is its joint with the parent, on the T-pose
drawing: so every angle is relative to the drawing, in degrees, clockwise on screen. Arms are drawn out sideways: an
arm hanging at the side is at -90 (right, image left) or +90 (left); `arms_down` below gives a starting pose.

Each part is a triangle mesh over its drawing. Rigid parts are one cell turned with their bone. The arms and legs
are strips with a bend zone at each joint: across the zone the strip curves along a circular arc, so the drawn
outline bends smoothly at the elbow, wrist and knee, keeps its thickness, and shows no join. A bending bone's matrix
is the rigid move that carries the straight part beyond the zone to where the arc ends, so everything attached
beyond it (hand, boot) sits exactly on the bent limb. Images are kept premultiplied, so edges do not darken, and
drawn at a master size near the size they are shown (no aliasing).

Offsets move a bone in its parent's frame (a head that lags a bob); scales squash a bone about its pivot (sx, sy);
`front` ("R"/"L") says which leg is drawn in front when the legs cross."""
import json

import cv2
import numpy as np

from studio.paths import build_dir
from studio.rig import tpose

def rot(deg, px, py):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, px - c * px + s * py], [s, c, py - s * px - c * py], [0, 0, 1.0]])


def trans(dx, dy):
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])


def scal(sx, sy, px, py):
    return np.array([[sx, 0, px - sx * px], [0, sy, py - sy * py], [0, 0, 1.0]])


def arc(d, k, w):
    """displacement along a strip that starts straight along unit vector d and turns at rate k (rad per pixel)
    for a length w (arrays ok): the integral of the turning direction"""
    d = np.asarray(d, float)
    w = np.asarray(w, float)
    if abs(k) < 1e-9:
        return w[..., None] * d
    kw = k * w
    x = (d[0] * np.sin(kw) - d[1] * (1 - np.cos(kw))) / k
    y = (d[0] * (1 - np.cos(kw)) + d[1] * np.sin(kw)) / k
    return np.stack([x, y], -1)


def bend_matrix(j, d, length, theta):
    """the move of everything beyond a bend zone (centred on joint j, `length` long, strip direction d) when the
    strip turns by theta degrees across it: the part past the zone's far end lands where the arc ends, turned"""
    d = np.asarray(d, float)
    P, D = np.asarray(j, float) - 0.5 * length * d, np.asarray(j, float) + 0.5 * length * d
    t = np.radians(theta)
    E = P + arc(d, t / length, length)
    return trans(*E) @ rot(theta, 0, 0) @ trans(-D[0], -D[1])


class Part:
    """one drawing and its mesh. A rigid part follows one bone. A limb has a chain of bones and bend zones: its
    vertices sit on one bone, or in a zone between two, where they are placed along the zone's arc."""

    def __init__(self, name, spec, img, master, bones):
        self.name, self.spec, self.master = name, spec, master
        ox, oy = spec["origin"]
        pad = 3
        h, w = img.shape[:2]
        f = img.astype(np.float32)
        f[..., :3] *= f[..., 3:4] / 255
        f = np.pad(f, ((pad, pad), (pad, pad), (0, 0)))
        self.ox, self.oy = ox - pad, oy - pad
        self.w, self.h = w + 2 * pad, h + 2 * pad
        self.src = cv2.resize(f, None, fx=master, fy=master, interpolation=cv2.INTER_AREA)
        self.pyr = [self.src]                                  # successive halvings, for where a drawing is squeezed
        for _ in range(3):
            self.pyr.append(cv2.pyrDown(self.pyr[-1]))
        x0, x1, y0, y1 = self.ox, self.ox + self.w, self.oy, self.oy + self.h
        skin = spec.get("skin")
        self.skin = skin
        if skin is None:
            self.chain = [spec["bone"]]
            xs, ys = np.array([x0, x1], float), np.array([y0, y1], float)
        else:
            self.chain = skin["bones"]
            self.d = np.asarray(skin["axis"], float)
            self.n = np.array([-self.d[1], self.d[0]])
            self.zones = []                                   # (bone, start point P, zone length, joint)
            for b in self.chain[1:]:
                bb = bones[b]
                L = bb["bend"]["zone"]
                j = np.asarray(bb["pivot"], float)
                self.zones.append((b, j - 0.5 * L * self.d, L, j))
            idx = 0 if abs(self.d[0]) > 0 else 1
            lo, hi = (x0, x1) if idx == 0 else (y0, y1)
            cuts = [lo, hi]
            for _, P, L, j in self.zones:
                cuts += list(np.linspace(j[idx] - L / 2, j[idx] + L / 2, max(2, int(L / 4)) + 1))
            along = np.array(sorted(set(np.round(np.clip(cuts, lo, hi), 3))))
            xs, ys = (along, np.array([y0, y1], float)) if idx == 0 else (np.array([x0, x1], float), along)
        ny, nx = len(ys), len(xs)
        idx_ = np.arange(ny * nx).reshape(ny, nx)
        a, b, c, e = idx_[:-1, :-1].ravel(), idx_[:-1, 1:].ravel(), idx_[1:, :-1].ravel(), idx_[1:, 1:].ravel()
        self.tris = np.concatenate([np.stack([a, b, c], 1), np.stack([b, e, c], 1)])
        gx, gy = np.meshgrid(xs, ys)
        self.rest = np.stack([gx.ravel(), gy.ravel()], 1)
        self.uv = (self.rest - [self.ox, self.oy]) * master
        if skin is not None:
            # which bone each vertex rides, or which zone it is in, and where along it
            self.region = np.zeros(len(self.rest), int)       # 0: bone 0; 2i-1: zone i; 2i: bone i
            self.wz = np.zeros(len(self.rest))
            for i, (_, P, L, _) in enumerate(self.zones, 1):
                wv = (self.rest - P) @ self.d
                self.region[wv > L] = 2 * i
                inz = (wv >= 0) & (wv <= L)
                self.region[inz] = 2 * i - 1
                self.wz[inz] = wv[inz]
            self.vz = np.zeros(len(self.rest))
            for i, (_, P, L, j) in enumerate(self.zones, 1):
                m = self.region == 2 * i - 1
                self.vz[m] = (self.rest[m] - j) @ self.n

    def deform(self, M, ang, to_canvas, own=None):
        """vertices on the canvas; `own` replaces the matrix of a rigid part's bone (a boot drawn on the other foot)"""
        p = np.concatenate([self.rest, np.ones((len(self.rest), 1))], 1).T
        if self.skin is None:
            return ((to_canvas @ (M[self.chain[0]] if own is None else own) @ p)[:2]).T
        out = np.zeros((len(self.rest), 2))
        for r in np.unique(self.region):
            m = self.region == r
            if r % 2 == 0:                                     # rigid on bone r/2
                out[m] = (to_canvas @ M[self.chain[r // 2]] @ p[:, m])[:2].T
            else:                                              # in zone (r+1)/2: along the arc
                i = (r + 1) // 2
                _, P, L, _ = self.zones[i - 1]
                k = np.radians(ang.get(self.chain[i], 0.0)) / L
                w = self.wz[m]
                al = k * w
                n0 = self.n
                nv = np.stack([n0[0] * np.cos(al) - n0[1] * np.sin(al), n0[0] * np.sin(al) + n0[1] * np.cos(al)], 1)
                pts = P + arc(self.d, k, w) + self.vz[m][:, None] * nv
                q = np.concatenate([pts, np.ones((len(pts), 1))], 1).T
                out[m] = (to_canvas @ M[self.chain[i - 1]] @ q)[:2].T
        return out

    def sample(self, mx, my, lvl):
        """the drawing at the source positions (mx, my), taken from the halvings where the mesh squeezes it (the
        inside of a bend, a figure drawn small), blended between two of them: mip-mapping, so nothing aliases.
        lvl is the halving to use at each pixel (0 = the drawing as it is)"""
        if lvl.max() < 0.05:
            return cv2.remap(self.src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        lvl = np.clip(lvl, 0, len(self.pyr) - 1.001)
        out = np.zeros(mx.shape + (4,), np.float32)
        for k in range(int(np.ceil(lvl.max())) + 1):
            w = np.clip(1 - np.abs(lvl - k), 0, 1)
            if w.max() <= 0:
                continue
            f = 0.5 ** k
            out += w[..., None] * cv2.remap(self.pyr[k], mx * f, my * f, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return out

    def render(self, canvas, M, ang, to_canvas, own=None):
        """composite onto a float32 premultiplied BGRA canvas"""
        V = self.deform(M, ang, to_canvas, own)
        x0, y0 = np.floor(V.min(0)).astype(int) - 1
        x1, y1 = np.ceil(V.max(0)).astype(int) + 1
        H, W = canvas.shape[:2]
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        if x1 <= x0 or y1 <= y0:
            return
        ids = np.full((y1 - y0, x1 - x0), -1, np.int32)
        inv = np.zeros((len(self.tris), 2, 3), np.float32)
        for k, t in enumerate(self.tris):
            d = (V[t] - [x0, y0]).astype(np.float32)
            cv2.fillConvexPoly(ids, np.round(d).astype(np.int32), k)
            inv[k] = cv2.getAffineTransform(d, self.uv[t].astype(np.float32))
        gx, gy = np.meshgrid(np.arange(x1 - x0, dtype=np.float32), np.arange(y1 - y0, dtype=np.float32))
        A = inv[np.maximum(ids, 0)]
        mx = A[..., 0, 0] * gx + A[..., 0, 1] * gy + A[..., 0, 2]
        my = A[..., 1, 0] * gx + A[..., 1, 1] * gy + A[..., 1, 2]
        mx[ids < 0] = -1e4
        my[ids < 0] = -1e4
        det = np.abs(inv[:, 0, 0] * inv[:, 1, 1] - inv[:, 0, 1] * inv[:, 1, 0])          # source px squared per canvas px
        lvl = 0.5 * np.log2(np.maximum(det, 1.0))[np.maximum(ids, 0)]
        lvl[ids < 0] = 0
        lvl = cv2.GaussianBlur(lvl, (0, 0), 2.0) if lvl.max() > 0.05 else lvl
        spr = self.sample(mx, my, lvl)
        a = spr[..., 3:4] / 255
        roi = canvas[y0:y1, x0:x1]
        roi[:] = spr + roi * (1 - a)


class Figure:
    def __init__(self, cid, outfit="home", master=0.5):
        d = build_dir("rig", cid, outfit, "tpose")
        src = tpose.source_dir(cid, outfit)
        stale = [f for f in (src / "tpose.yaml", src / "tpose.png") if f.stat().st_mtime > (d / "rig.json").stat().st_mtime] \
            if (d / "rig.json").exists() else True
        if stale:
            tpose.build(cid, outfit, d)
        rig = json.loads((d / "rig.json").read_text())
        self.rig, self.master = rig, master
        self.bones = rig["bones"]
        self.floor = rig["floor"]
        self.axis = rig["axis"]
        self.order = list(self.bones)
        self.parts = {n: Part(n, p, cv2.imread(str(d / p["file"]), cv2.IMREAD_UNCHANGED), master, self.bones)
                      for n, p in rig["parts"].items()}

    # ------------------------------------------------------------------ kinematics
    def matrices(self, pose):
        """world 3x3 of every bone (T-pose pixels -> posed pixels)"""
        ang, off, sc = pose.get("angles", {}), pose.get("offset", {}), pose.get("scale", {})
        M = {}
        for n in self.order:
            b = self.bones[n]
            px, py = b["pivot"]
            if "bend" in b:
                bd = b["bend"]
                local = trans(*off.get(n, (0, 0))) @ bend_matrix(b["pivot"], bd["axis"], bd["zone"], ang.get(n, 0.0))
            else:
                local = trans(*off.get(n, (0, 0))) @ rot(ang.get(n, 0.0), px, py)
            if n in sc:
                local = local @ scal(*sc[n], px, py)
            if b["parent"] is None:
                rx, ry = pose.get("root", (0, 0))
                M[n] = trans(rx, ry) @ local
            else:
                M[n] = M[b["parent"]] @ local
        return M

    def point(self, M, bone, p):
        """where a point of the T-pose drawing (riding on `bone`) is in the pose"""
        return (M[bone] @ np.array([p[0], p[1], 1.0]))[:2]

    # ------------------------------------------------------------------ drawing
    def draw(self, frame, pose, x, y, scale, flip=False):
        """BGR uint8 frame; (x, y) the floor point under the feet; scale: frame px per T-pose px. flip mirrors it.
        pose["toes"] = +1 / -1 draws both boots as the one that points right / left (the drawing splays them out)."""
        M = self.matrices(pose)
        sx = -scale if flip else scale
        to_canvas = np.array([[sx, 0, x - sx * self.axis], [0, scale, y - scale * self.floor], [0, 0, 1.0]])
        canvas = np.zeros(frame.shape[:2] + (4,), np.float32)
        order = self.rig["parts"]
        names = sorted(order, key=lambda n: order[n]["z"])
        if pose.get("front") in ("R", "L"):                         # which leg is nearer when they cross
            back, near = ("L", "R") if pose["front"] == "R" else ("R", "L")
            legs = [f"leg_{back}", f"boot_{back}", f"leg_{near}", f"boot_{near}"]
            names = legs + [n for n in names if n not in legs]
        ang = pose.get("angles", {})
        toes = pose.get("toes", 0)
        for n in names:
            if toes and n.startswith("boot_"):
                side = n[-1]
                art = "L" if toes > 0 else "R"
                shift = trans(*(np.array(self.bones[f"foot_{side}"]["pivot"]) - self.bones[f"foot_{art}"]["pivot"]))
                self.parts[f"boot_{art}"].render(canvas, M, ang, to_canvas, M[f"foot_{side}"] @ shift)
            else:
                self.parts[n].render(canvas, M, ang, to_canvas)
        a = canvas[..., 3:4] / 255
        frame[:] = np.clip(canvas[..., :3] + frame * (1 - a), 0, 255).astype(np.uint8)
        return M


def arms_down(spread=8.0, elbow=6.0):
    """angles for arms hanging at the sides, a little out from the body, elbows a little bent"""
    return {"upper_arm_R": -(90 - spread), "upper_arm_L": 90 - spread, "forearm_R": -elbow, "forearm_L": elbow}
