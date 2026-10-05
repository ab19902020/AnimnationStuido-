"""Walk cycles for the puppet rigs, solved from each character's own proportions.

    python3 -m studio.anim.walk CHARACTER [CHARACTER ...] [--outfit OUTFIT] [--views side three_quarter front]
        build/anim/<id>/<outfit>_walk_<view>.jpg   the cycle as a strip of poses, with a report of the checks

    w = Walker(rig, rig_dir, "side")      # a rig from studio.rig.build (build/rig/<id>/<outfit>/<view>/)
    root, angles, info = w.pose(phase)    # phase 0..1 over one cycle; feed root and angles to build.draw
    w.travel                              # (x, y) the character moves per cycle, in guide pixels

The poses are in place (the pelvis stays put). The renderer moves the character by `travel` per cycle, which keeps
a planted foot still on the ground. Views: `side` (facing screen-right; a left-facing walk is the mirror image),
`three_quarter` (the same walk, shorter in depth, drifting towards the camera) and `front` (walking towards the
camera: weight shifting from foot to foot, the feet stepping up and down the picture).

A walk is a pelvis carried over two legs that take turns. Each foot is planted for 60% of the cycle and rolls heel,
flat, toe; then it swings through, lifted clear of the ground, to land one step ahead. The feet are placed first, so
a planted foot does not slide; the pelvis height follows from the legs (it drops only as far as the leg lengths force
it to), and two-bone IK bends each knee. Stride and lift are fractions of the character's own leg length, so a
stocky figure takes short steps and a tall one long. The arms swing against the legs, the torso leans a little and
counter-turns against the hips, the head stays level.
Angles follow skeleton.py: degrees, clockwise on screen; a hanging limb swung forward (to screen-right) is negative.

Status: prototype, not used by anything yet. For a character with a T-pose drawing, studio.anim.gait is the working
version (planted feet, smooth bends, a rig built for it). On the current kits the result is not good enough (limb ends show at
the knees and elbows, the head reads as stuck on): the kits' loose limbs are drawn at the wrong lengths and without
joint-centred ends. Kept as the starting point for walks once kits are drawn for animation.""" 
import argparse
import json
import math
import sys

import cv2
import numpy as np
import yaml

from studio.paths import CHARACTERS, build_dir
from studio.rig import build as rigbuild
from studio.rig import skeleton

STANCE = 0.6          # fraction of the cycle a foot is on the ground; each step starts with both feet down

# step: step length as a fraction of leg length. xs: how much of the stride shows across the picture. ys: how far a
# foot moves up and down the picture as it steps towards the camera (fraction of leg length). sway: pelvis shift
# over the planted foot (fraction of pelvis width). clear: swing-foot lift. bounce: extra hip bounce beyond what the
# legs force (fraction of leg length). arm: arm swing (degrees). elbow: elbow bend range at back and front of the
# swing. lean: forward lean of the torso. roll: how much the foot rolls heel to toe. knee: the way knees point
# (+1 forward, 0 outward as seen from the front)
PARAMS = {
    "side": dict(step=0.62, xs=1.0, ys=0.0, sway=0.0, clear=0.15, bounce=0.0, arm=27, elbow=(8, 26), lean=3.0,
                 roll=1.0, knee=+1),
    "three_quarter": dict(step=0.56, xs=0.85, ys=0.045, sway=0.03, clear=0.14, bounce=0.0, arm=21, elbow=(8, 20),
                          lean=2.0, roll=0.7, knee=+1),
    "front": dict(step=0.0, xs=0.0, ys=0.07, sway=0.07, clear=0.11, bounce=0.028, arm=9, elbow=(6, 14), lean=0.0,
                  roll=0.0, knee=0),
}


def ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def rot(v, deg):
    a = math.radians(deg)
    return np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def two_bone(H, A, L1, L2, prefer):
    """Knee of a leg from hip H to ankle A, on the side `prefer` points to. Returns (knee, overreach): overreach is
    how far the ankle was out of reach (0 when it can be reached)."""
    d = A - H
    D0 = float(np.linalg.norm(d))
    over = max(0.0, D0 - (L1 + L2))
    D = min(max(D0, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    u = d / max(1e-9, D0)
    a = math.degrees(math.acos(np.clip((L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), -1, 1)))
    k1, k2 = H + rot(u, a) * L1, H + rot(u, -a) * L1
    return (k1 if (k1 - H) @ prefer >= (k2 - H) @ prefer else k2), over


class Walker:
    def __init__(self, rig, rig_dir, view, **params):
        self.rig, self.view, self.rig_dir = rig, view, rig_dir
        self.P = P = rig["parts"]
        self.k = dict(PARAMS[view], **params)
        r = P["pelvis"]["rest"]
        self.M0 = M0 = skeleton.pose_matrices(P, root=(r["x"], r["y"], 0.0, 1.0))
        at = lambda n, which="pivot": skeleton.apply(M0[n], P[n][which])
        self.H0, self.K0, self.A0, self.S0, self.E0, self.W0 = {}, {}, {}, {}, {}, {}
        self.L1, self.L2 = {}, {}
        for s in "RL":
            self.H0[s], self.K0[s], self.A0[s] = at(f"thigh_{s}"), at(f"shin_{s}"), at(f"foot_{s}")
            self.S0[s], self.E0[s], self.W0[s] = at(f"upper_arm_{s}"), at(f"forearm_{s}"), at(f"hand_{s}")
            self.L1[s] = float(np.linalg.norm(self.K0[s] - self.H0[s]))
            self.L2[s] = float(np.linalg.norm(self.A0[s] - self.K0[s]))
        self.leg = float(np.mean([self.L1[s] + self.L2[s] for s in "RL"]))
        self.pelvis0 = np.array([r["x"], r["y"]])
        self.pelvis_w = P["pelvis"]["size"][0] * r["scale"]
        self.sole_px = {s: self._sole(s) for s in "RL"}               # heel and toe in foot pixels
        self.sole = {s: tuple(skeleton.apply(M0[f"foot_{s}"], p) - self.A0[s] for p in self.sole_px[s]) for s in "RL"}
        mid = 0.5 * (self.H0["R"][0] + self.H0["L"][0])
        self.base_x = {s: {"side": mid, "three_quarter": self.H0[s][0], "front": self.A0[s][0]}[view] for s in "RL"}
        self.S = self.k["step"] * self.leg                            # step length: one foot's strike to the next's
        self.travel = (2 * self.S * self.k["xs"], 2 * self.k["ys"] * self.leg / STANCE)
        self._drop = self._solve_drop()

    def _sole(self, s):
        """heel and toe contact points of a foot drawing (part pixels): the low points just inside its two ends"""
        img = cv2.imread(str(self.rig_dir / self.P[f"foot_{s}"]["file"]), cv2.IMREAD_UNCHANGED)
        ys, xs = np.nonzero(img[..., 3] >= 128)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        low = ys >= y1 - 0.12 * (y1 - y0)
        pick = lambda sel, q: np.array([np.percentile(xs[sel], q), ys[sel].max()], float)
        return pick(low & (xs <= x0 + 0.3 * (x1 - x0)), 10), pick(low & (xs >= x1 - 0.3 * (x1 - x0)), 90)

    # ------------------------------------------------------------------ feet
    def phase_of(self, s, phase):
        """(in stance?, progress 0..1 through the stance or the swing) of foot s"""
        f = (phase + (0.5 if s == "L" else 0.0)) % 1.0
        return (True, f / STANCE) if f < STANCE else (False, (f - STANCE) / (1.0 - STANCE))

    def ankle(self, s, phase):
        """(world ankle position, foot rotation) of foot s. A foot rolling on the floor pivots about its heel or toe,
        which stays where it was planted."""
        k, leg = self.k, self.leg
        stance, u = self.phase_of(s, phase)
        reach = STANCE * self.S * k["xs"]                              # half the foot's travel through a stance
        fx = (reach - 2 * reach * u) if stance else (-reach + 2 * reach * smooth(u))
        fy = k["ys"] * leg * ((1 - 2 * u) if stance else (-1 + 2 * smooth(u)))
        lift = 0.0 if stance else k["clear"] * leg * math.sin(math.pi * u ** 0.9)
        psi = 0.0
        if self.view != "front":
            if stance:      # heel strike (toes up), flat, then the heel lifts and the foot rolls on to the toe
                psi = (-14 * (1 - smooth(u / 0.14)) if u < 0.14 else 0.0) + (36 * smooth((u - 0.4) / 0.6) if u > 0.4 else 0.0)
            else:           # the toe drops as the foot leaves, comes level, and lifts again to meet the ground
                psi = 36 * (1 - smooth(u / 0.45)) - 14 * smooth((u - 0.55) / 0.45)
            psi *= k["roll"]
        flat = np.array([self.base_x[s] + fx, self.A0[s][1] + fy])
        a = flat.copy()
        if stance and psi != 0.0:
            o = self.sole[s][0] if psi < 0 else self.sole[s][1]
            a = flat + o - rot(o, psi)
        a[1] -= lift
        return a, psi

    # ----------------------------------------------------------------- pelvis
    def sway(self, phase):
        """pelvis shift over the planted leg: towards the right foot at the middle of its stance (screen-left)"""
        return -self.k["sway"] * self.pelvis_w * math.cos(2 * math.pi * (phase - 0.3))

    def roll(self, phase):
        """the pelvis tips: the swing side drops (front view: right foot planted, left hip down = clockwise)"""
        return (2.2 if self.view == "front" else 0.8 if self.view == "three_quarter" else 0.0) * math.cos(2 * math.pi * (phase - 0.3))

    def _solve_drop(self, n=96):
        """how far the pelvis sits below its rest height over the cycle (px, may be negative): as high as the legs
        allow (never quite straight), smoothed round the cycle, plus a little bounce where the view needs one"""
        need = np.zeros(n)
        for i in range(n):
            ph = i / n
            worst = -1e9
            for s in "RL":
                a, _ = self.ankle(s, ph)
                hx = self.H0[s][0] + self.sway(ph)
                reach = 0.985 * (self.L1[s] + self.L2[s])
                worst = max(worst, a[1] - math.sqrt(max(0.0, reach ** 2 - (a[0] - hx) ** 2)) - self.H0[s][1])
            need[i] = worst
        g = np.exp(-0.5 * (np.arange(-8, 9) / 3.0) ** 2)
        g /= g.sum()
        sm = np.convolve(np.concatenate([need[-8:], need, need[:8]]), g, "valid")
        sm += max(0.0, float((need - sm).max()))                    # never above what the legs need
        sm += self.k["bounce"] * self.leg * (1 + np.cos(4 * np.pi * (np.arange(n) / n - 0.05))) / 2
        return sm

    def drop(self, phase):
        n = len(self._drop)
        x = (phase % 1.0) * n
        i = int(x) % n
        return float(self._drop[i] + (self._drop[(i + 1) % n] - self._drop[i]) * (x - int(x)))

    # ------------------------------------------------------------------- pose
    def pose(self, phase):
        """(root, angles, info) of the rig at a cycle phase; phase 0 is the right heel striking. `info` has the
        joint positions and the IK overreach of each leg, for checking."""
        P, k, v = self.P, self.k, self.view
        phase %= 1.0
        side_view = v != "front"
        roll = self.roll(phase)
        root = (self.pelvis0[0] + self.sway(phase), self.pelvis0[1] + self.drop(phase), roll - P["pelvis"]["rest"]["angle"], 1.0)
        wr = {"pelvis": roll}                                      # world rotation of each part
        angles = {}

        def settle(n, world, parent):
            """give part n the world rotation `world`: the joint angle that does it"""
            wr[n] = world
            angles[n] = world - (wr[parent] + P[n]["rel_angle"])

        t = 2 * math.pi * phase
        settle("torso", k["lean"] + (0.8 * math.sin(4 * t - 1.0) if side_view else 0.0) - (0.9 * roll if v == "front" else 0.5 * roll), "pelvis")
        settle("neck", 0.45 * wr["torso"], "torso")
        settle("head", -0.3 * wr["torso"] + (0.6 * math.sin(4 * t - 0.4) if side_view else 0.0), "neck")
        for n in ("eyes", "mouth"):
            if n in P:
                settle(n, wr["head"] + P[n]["rel_angle"], "head")

        Mp = skeleton.pose_matrices(P, root=root)
        info = {}
        for s in "RL":
            a, psi = self.ankle(s, phase)
            H = skeleton.apply(Mp[f"thigh_{s}"], P[f"thigh_{s}"]["pivot"])
            prefer = np.array([float(k["knee"]), 0.0]) if k["knee"] else np.array([-1.0 if s == "R" else 1.0, 0.25])
            K, over = two_bone(H, a, self.L1[s], self.L2[s], prefer)
            settle(f"thigh_{s}", P[f"thigh_{s}"]["rest"]["angle"] + ang(K - H) - ang(self.K0[s] - self.H0[s]), "pelvis")
            settle(f"shin_{s}", P[f"shin_{s}"]["rest"]["angle"] + ang(a - K) - ang(self.A0[s] - self.K0[s]), f"thigh_{s}")
            settle(f"foot_{s}", P[f"foot_{s}"]["rest"]["angle"] + psi, f"shin_{s}")
            info[s] = dict(ankle=a, knee=K, hip=H, over=over, psi=psi)

        for s in "RL":          # an arm swings forward as the opposite leg does
            other = "L" if s == "R" else "R"
            fwd = math.cos(2 * math.pi * (((phase + (0.5 if other == "L" else 0.0)) % 1.0) - 0.02))   # +1: opposite foot forward
            lo, hi = k["elbow"]
            bend = lo + (hi - lo) * 0.5 * (1 + fwd)
            if side_view:
                upper = 90.0 - k["arm"] * fwd                       # 90 is straight down, smaller is forward
                lower = upper - bend                                # the elbow bends forward
            else:
                out = 1.0 if s == "R" else -1.0                     # the right arm is on the viewer's left
                upper = 90.0 + out * (5.0 + k["arm"] * 0.5 * fwd)
                lower = upper - out * bend * 0.4
            ua, fa, hd = f"upper_arm_{s}", f"forearm_{s}", f"hand_{s}"
            settle(ua, P[ua]["rest"]["angle"] + upper - ang(self.E0[s] - self.S0[s]), "torso")
            settle(fa, P[fa]["rest"]["angle"] + lower - ang(self.W0[s] - self.E0[s]), ua)
            settle(hd, P[hd]["rest"]["angle"] + lower - ang(self.W0[s] - self.E0[s]), fa)
        return root, angles, info

    def cycle(self, n=24):
        return [self.pose(i / n)[:2] for i in range(n)]

    # ----------------------------------------------------------------- checks
    def check(self, n=48):
        """measure the cycle through the real forward kinematics: how far a planted foot slides on the ground (its
        contact point in world terms, with the character moving `travel` per cycle), how far the legs are asked to
        reach beyond their length, and the range of the hip drop"""
        slide, over, drops = 0.0, 0.0, []
        plant = {(s, c): [] for s in "RL" for c in ("heel", "toe")}     # a contact point is still while it bears weight
        for i in range(n):
            ph = i / n
            root, angles, info = self.pose(ph)
            Ms = skeleton.pose_matrices(self.P, root=root, angles=angles)
            drops.append(root[1] - self.pelvis0[1])
            for s in "RL":
                over = max(over, info[s]["over"])
                if not self.phase_of(s, ph)[0]:
                    continue
                heel, toe = (skeleton.apply(Ms[f"foot_{s}"], p) for p in self.sole_px[s])
                psi = info[s]["psi"]
                t = ph + (1.0 if s == "L" and ph < 0.5 else 0.0)        # the left stance runs on past the cycle's end
                if psi <= 0.01:
                    plant[(s, "heel")].append(heel[0] + self.travel[0] * t)
                if psi >= -0.01:
                    plant[(s, "toe")].append(toe[0] + self.travel[0] * t)
        if self.view != "front":
            slide = max(float(np.ptp(v)) for v in plant.values() if v)
        return dict(slide_px=round(slide, 2), overreach_px=round(over, 2),
                    hip_drop_px=(round(min(drops), 1), round(max(drops), 1)), leg_px=round(self.leg),
                    step_px=round(self.S), travel_px=tuple(round(x) for x in self.travel))


# --------------------------------------------------------------------- review
def ensure_rig(cid, outfit, view):
    d = build_dir("rig", cid, outfit, view)
    if not (d / "rig.json").exists():
        rigbuild.build_view(cid, outfit, view, d)
    return json.loads((d / "rig.json").read_text()), d


def strip(w, n=8):
    """the cycle as a row of n poses on a grey ground, the planted contact points marked, cropped to the figure"""
    rig, gw, gh = w.rig, *w.rig["guide"]
    pad = int(0.4 * gw)
    size = (gw + 2 * pad, gh + 40)
    ground = max(w.A0[s][1] + max(w.sole[s][0][1], w.sole[s][1][1]) for s in "RL")
    frames, boxes = [], []
    for i in range(n):
        root, angles, info = w.pose(i / n)
        c = rigbuild.draw(rig, w.rig_dir, size, angles=angles, root=(root[0] + pad, root[1], root[2], root[3]))
        a = c[..., 3:4] / 255
        img = (c[..., :3] * a + 128 * (1 - a)).astype(np.uint8)
        cv2.line(img, (0, int(ground)), (size[0], int(ground)), (60, 60, 60), 1)
        for s in "RL":
            stance, u = w.phase_of(s, i / n)
            if stance:
                at = info[s]["ankle"]
                cv2.circle(img, (int(at[0] + pad), int(at[1])), 4, (255, 0, 0) if s == "R" else (0, 160, 255), -1)
        cv2.putText(img, f"{i}/{n}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        frames.append(img)
        ys, xs = np.nonzero(c[..., 3] > 20)
        boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    x0 = max(0, min(b[0] for b in boxes) - 10)
    x1 = min(size[0], max(b[2] for b in boxes) + 10)
    y0 = max(0, min(b[1] for b in boxes) - 10)
    y1 = min(size[1], max(b[3] for b in boxes) + 14)
    pan = [cv2.copyMakeBorder(f[y0:y1, x0:x1], 0, 0, 0, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for f in frames]
    return np.hstack(pan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chars", nargs="+")
    ap.add_argument("--outfit")
    ap.add_argument("--views", nargs="*", default=["side", "three_quarter", "front"])
    ap.add_argument("--frames", type=int, default=8)
    a = ap.parse_args()
    for cid in a.chars:
        c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text())
        for outfit in ([a.outfit] if a.outfit else list(c["outfits"])):
            rows = []
            for view in a.views:
                if not (CHARACTERS / cid / "kit" / outfit / f"{view}.png").exists():
                    continue
                rig, d = ensure_rig(cid, outfit, view)
                w = Walker(rig, d, view)
                rep = w.check()
                print(f"{cid} {outfit} {view}: {rep}", file=sys.stderr)
                rows.append(strip(w, a.frames))
            if rows:
                W = max(r.shape[1] for r in rows)
                rows = [cv2.copyMakeBorder(r, 0, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]
                out = build_dir("anim", cid) / f"{outfit}_walk.jpg"
                cv2.imwrite(str(out), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
                print(out, file=sys.stderr)


if __name__ == "__main__":
    main()
