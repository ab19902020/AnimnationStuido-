"""Walk, idle and gesture poses for a T-pose rig (studio.anim.figure).

    python3 -m studio.anim.gait CHARACTER [--outfit OUTFIT]
        build/anim/<id>/walk_right.jpg, walk_left.jpg, walk_toward.jpg   the cycles as strips of frames, with the checks
        build/anim/<id>/walk_test.mp4      (with --clip) idle, walk right, walk left, walk towards the camera, wave

    g = Gait(Figure("bruno-fernandes"))
    pose = g.walk(phase, dirn=1)       # phase 0..1 over one cycle; dirn +1 walks to screen right, -1 to the left
    pose = g.walk_toward(phase)        # the walk down the screen towards the camera
    pose = g.walk(phase, 1, amount)    # amount 0..1: 0 is standing, 1 the full walk; ramp it to start and stop
    pose = g.idle(t)                   # standing, breathing, shifting weight, the head moving; t in seconds
    pose = g.wave(t, arm="R")          # an arm up and waving, the rest as idle
    g.speed                            # T-pose px per second a walking figure must move across the screen so that a
                                       # planted foot stays put (times the draw scale for frame pixels, times amount)

A pose is the dict studio.anim.figure.Figure.draw takes: root, angles, offset, scale, front, toes.

The walk is a pelvis carried over two legs that take turns. Each foot is planted for 62% of the cycle (both are down
for 12% of it at each step), rolls heel, flat, toe, then swings through, lifted clear of the ground, and lands one
step ahead. The feet are placed first, in the world; the pelvis height follows from the legs (it drops only as far as
their length makes it), and two-bone IK bends each knee. Round that skeleton the pelvis rolls and sways over the
planted foot, the torso counters it and leans into the walk, the head stays level and lags the bounce, the arms
swing against the legs with forearms and hands trailing behind them (overlapping action).

The drawing is front on, so this is the sideways walk of a front-view cartoon: the boots both point the way he goes
(`toes`), the legs swing in the picture plane, the nearer leg is drawn in front when they cross.
Angles are degrees, clockwise on screen; positions are T-pose pixels (y down)."""
import argparse
import math
import subprocess
import sys
from dataclasses import dataclass, replace

import cv2
import numpy as np

from studio.anim.figure import Figure, bend_matrix, rot
from studio.paths import build_dir

smooth = lambda t: t * t * (3 - 2 * t)
clamp01 = lambda t: min(1.0, max(0.0, t))
TAU = 2 * math.pi
MAX_BEND = 66.0          # most a knee is bent, degrees


def lerp(a, b, t):
    return a + (b - a) * t


def Rm(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


@dataclass
class Cfg:
    stride: float = 62.0         # how far a foot ends up ahead of / behind its rest place (px): half a step
    cycle: float = 0.72          # seconds for two steps
    stance: float = 0.62         # fraction of the cycle a foot is on the ground
    lift: float = 10.0           # how high the swinging foot clears the ground (px)
    bob_min: float = 0.982       # the leg is never straighter than this fraction of its length
    arm_in: float = 3.0          # the arms swing between this many degrees out from the body ...
    arm_out: float = 27.0        # ... and this many
    heel_strike: float = -6.0   # foot angle at landing (toe up), degrees; toe down is positive
    toe_off: float = 8.0        # foot angle as the heel lifts
    sway: float = 7.0            # the pelvis shifts sideways over the planted foot (px)
    roll: float = 2.4            # pelvis roll (degrees)
    lean: float = 2.5            # torso lean into the walk (degrees)
    depth: float = 7.0          # walking towards the camera: how far a foot goes up and down the picture (px)
    toward_out: float = 6.0      # ... how far the feet stand out from the hips
    toward_toe: float = 9.0
    toward_heel: float = -5.0
    toward_arm: float = 24.0     # ... how far the arms swing in depth (degrees), seen as foreshortening


class Gait:
    def __init__(self, fig, cfg=None):
        self.fig = fig
        self.cfg = cfg or Cfg()
        b = fig.bones
        self.hip = {s: np.array(b[f"thigh_{s}"]["pivot"], float) for s in "RL"}
        self.knee = {s: np.array(b[f"shin_{s}"]["pivot"], float) for s in "RL"}
        self.ankle = {s: np.array(b[f"foot_{s}"]["pivot"], float) for s in "RL"}
        self.l1 = float(np.linalg.norm(self.knee["R"] - self.hip["R"]))
        self.l2 = float(np.linalg.norm(self.ankle["R"] - self.knee["R"]))
        self.floor = float(fig.floor)
        self.heel_toe = self._contacts()
        self.root = np.array(b["pelvis"]["pivot"], float)
        self._bob = None
        self._bob_cache = {}

    @property
    def speed(self):
        c = self.cfg
        return 2 * c.stride / (c.stance * c.cycle)

    # ------------------------------------------------------------------ geometry
    def _contacts(self):
        """heel and toe contact points of each boot drawing, relative to its ankle: {art: (heel, toe)}. The art is
        the boot that points right ("L": toe at +x) or left ("R")"""
        out = {}
        for art in "RL":
            p = self.fig.parts[f"boot_{art}"]
            ys, xs = np.nonzero(p.src[..., 3] > 128)
            ymax = ys.max()
            band = ys >= ymax - 14
            x0, x1 = xs[band].min(), xs[band].max()
            toe_x, heel_x = (x1, x0) if art == "L" else (x0, x1)
            pt = lambda x, y: np.array([x / p.master + p.ox, y / p.master + p.oy])
            out[art] = (pt(heel_x, ymax) - self.ankle[art], pt(toe_x, ymax) - self.ankle[art])
        return out

    def solve_leg(self, Mp, side, target, foot_world, knee_dir):
        """(thigh angle, knee bend, foot angle) that put the ankle on `target` (world) with the boot turned
        `foot_world` degrees. knee_dir +1: the shin trails towards -x."""
        hip = (Mp @ [*self.hip[side], 1.0])[:2]
        pel = math.degrees(math.atan2(Mp[1, 0], Mp[0, 0]))
        d = target - hip
        dist = float(np.clip(np.linalg.norm(d), abs(self.l1 - self.l2) + 1e-3, (self.l1 + self.l2) * 0.9995))
        a1 = math.acos(np.clip((self.l1 ** 2 + dist ** 2 - self.l2 ** 2) / (2 * self.l1 * dist), -1, 1))
        rest_dir = math.atan2(*(self.knee[side] - self.hip[side])[::-1])
        th = math.degrees(math.atan2(d[1], d[0]) - knee_dir * a1 - rest_dir) - pel
        bend = knee_dir * math.degrees(math.pi - math.acos(np.clip((self.l1 ** 2 + self.l2 ** 2 - dist ** 2) / (2 * self.l1 * self.l2), -1, 1)))
        x = np.array([th, bend])
        zone = self.fig.bones[f"shin_{side}"]["bend"]["zone"]

        def ankle_at(v):
            M = Mp @ rot(v[0], *self.hip[side]) @ bend_matrix(self.knee[side], [0, 1], zone, v[1])
            return (M @ [*self.ankle[side], 1.0])[:2]

        for _ in range(6):                                                  # polish on the bend model itself
            e = target - ankle_at(x)
            if np.hypot(*e) < 0.05:
                break
            J = np.stack([(ankle_at(x + [0.05, 0]) - ankle_at(x)) / 0.05, (ankle_at(x + [0, 0.05]) - ankle_at(x)) / 0.05], 1)
            x = x + np.linalg.lstsq(J, e, rcond=None)[0]
        if abs(x[1]) > MAX_BEND:
            # a bend past MAX_BEND would crush the inside of the knee: hold it there and aim the leg at the target
            # (a lifted foot comes out a little lower than asked; planted feet are never bent that far)
            x[1] = math.copysign(MAX_BEND, x[1])
            for _ in range(3):
                v1, v2 = ankle_at(x) - hip, target - hip
                x[0] += math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1 @ v2))
        return float(x[0]), float(x[1]), float(foot_world - (pel + x[0] + x[1]))

    # ------------------------------------------------------------------ feet
    def planted(self, side, rel, ang, q, dirn):
        """ankle of a foot on the ground, its contact point q (offset from the ankle) staying where a flat foot would
        have it, turned `ang`. The flat foot's ankle is `rel` ahead of its rest place."""
        flat = np.array([self.ankle[side][0] + dirn * rel, self.floor - q[1]])
        return flat + q - Rm(ang) @ q

    def foot(self, side, phase, dirn):
        """(ankle in the world, foot angle, planted?) for one leg; phase 0 = heel strike"""
        c = self.cfg
        S, fs = c.stride, c.stance
        heel, toe = self.heel_toe["L" if dirn > 0 else "R"]
        hs, to = c.heel_strike * dirn, c.toe_off * dirn
        if phase < fs:
            rel = S - 2 * S * phase / fs
            f_h, f_t = 0.22 * fs, 0.50 * fs
            if phase < f_h:
                ang, q = hs * (1 - smooth(phase / f_h)), heel
            elif phase < f_t:
                ang, q = 0.0, heel
            else:
                ang, q = to * smooth((phase - f_t) / (fs - f_t)), toe
            return self.planted(side, rel, ang, q, dirn), ang, True
        u = (phase - fs) / (1 - fs)
        p0, p1 = self.planted(side, -S, to, toe, dirn), self.planted(side, S, hs, heel, dirn)
        m = np.array([dirn * (-2 * S * (1 - fs) / fs), 0.0])                # leave and arrive moving back at walking speed
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        pos = h00 * p0 + h10 * m + h01 * p1 + h11 * m
        pos[1] = lerp(p0[1], p1[1], smooth(u)) - c.lift * math.sin(math.pi * u) ** 0.9
        ang = lerp(to, hs, smooth(u)) - dirn * 5 * math.sin(math.pi * u)
        return pos, ang, False

    # ------------------------------------------------------------------ the pelvis
    def sway(self, p):
        return -self.cfg.sway * math.cos(TAU * (p - 0.31))

    def roll(self, p):
        return -self.cfg.roll * math.cos(TAU * (p - 0.31))

    def bob(self, p, dirn):
        """pelvis height offset (px, + down) at phase p: as low as the planted legs need, smoothed over the cycle.
        dirn is +1 / -1 for the walk across the screen, 0 for the walk towards the camera"""
        foot = self.foot if dirn else self.foot_toward
        if self._bob is None or self._bob[0] != dirn:
            n = 96
            reach = self.cfg.bob_min * (self.l1 + self.l2)
            raw = np.zeros(n)
            for k in range(n):
                ph = k / n
                need = []
                for side, off in (("R", 0.0), ("L", 0.5)):
                    pos = (foot(side, (ph + off) % 1.0, dirn) if dirn else foot(side, (ph + off) % 1.0))[0]   # a foot about to land counts too
                    dx = pos[0] - (self.hip[side][0] + self.sway(ph))
                    need.append(pos[1] - math.sqrt(max(reach ** 2 - dx ** 2, 1.0)))
                raw[k] = max(need)
            F = np.fft.rfft(raw)
            F[5:] = 0                                                       # four harmonics: no kinks at the transitions
            self._bob = (dirn, np.fft.irfft(F, n) - self.hip["R"][1])
        arr = self._bob[1]
        x = (p % 1.0) * len(arr)
        i = int(x) % len(arr)
        return lerp(arr[i], arr[(i + 1) % len(arr)], x - int(x))

    # ------------------------------------------------------------------ the walk
    def _walk(self, p, dirn):
        c = self.cfg
        p = p % 1.0
        dy = self.bob(p, dirn)
        dx = self.sway(p)
        pel = self.roll(p) * dirn
        pose = dict(root=(dx, dy), angles={"pelvis": pel}, offset={}, scale={}, toes=dirn)
        A = pose["angles"]
        Mp = self.fig.matrices(dict(root=(dx, dy), angles={"pelvis": pel}))["pelvis"]
        feet = {}
        for side, off in (("R", 0.0), ("L", 0.5)):
            pos, ang, down = self.foot(side, (p + off) % 1.0, dirn)
            th, kb, fa = self.solve_leg(Mp, side, pos, ang, dirn)
            A[f"thigh_{side}"], A[f"shin_{side}"], A[f"foot_{side}"] = th, kb, fa
            feet[side] = (pos, down)
        for side in "RL":                                                   # the lifted foot is the nearer one
            if not feet[side][1]:
                pose["front"] = side
        # torso, head
        A["torso"] = -0.7 * pel + dirn * c.lean + 0.8 * math.sin(TAU * (p - 0.05))
        A["head"] = -0.6 * (pel + A["torso"]) + dirn * 1.5 + 3.2 * math.sin(TAU * (p - 0.2))
        lag = 0.09
        pose["offset"]["head"] = (dirn * 6 + 4.5 * math.sin(TAU * (p - 0.12)),
                                  0.9 * (self.bob(p - lag, dirn) - dy) - 2.5 * math.cos(TAU * 2 * (p - 0.10)))
        # a little squash on the landings, stretch on the passing
        s = 0.012 * math.cos(TAU * 2 * (p - 0.31))
        pose["scale"]["torso"] = (1 - s * 0.5, 1 + s)
        # Arms. Seen from the front the swing of an arm is mostly out of the picture, so what shows is the arms riding
        # the body's sway like pendulums (both toward the same side, lagging it), with the elbows flexing in turn,
        # the forearms and hands trailing the shoulder.
        a_mid, a_amp = (c.arm_in + c.arm_out) / 2, (c.arm_out - c.arm_in) / 2
        g = math.cos(TAU * (p - 0.91))                                      # toward screen right, lagging the sway
        for side in "RL":
            al = a_mid + a_amp * g * (1 if side == "L" else -1)             # the left arm goes out as it swings right
            gs = 0.5 + 0.5 * math.cos(TAU * (p - (0.0 if side == "R" else 0.5) - 0.16))
            el = 6 + 17 * smooth(gs)
            wr = 5 + 11 * smooth(0.5 + 0.5 * math.cos(TAU * (p - (0.0 if side == "R" else 0.5) - 0.26)))
            sg = -1 if side == "R" else 1
            A[f"upper_arm_{side}"] = sg * (90 - al)
            A[f"forearm_{side}"], A[f"hand_{side}"] = sg * el, sg * wr
        return pose

    # ------------------------------------------------------------------ the walk towards the camera
    def foot_toward(self, side, phase):
        """(ankle in the world, foot angle, planted?, depth) walking down the screen: a foot ahead is nearer the
        camera, so lower in the picture and a little bigger; the planted foot goes back (up the picture) at walking
        speed; the swinging foot lifts and comes forward. The feet stay under the hips, a little further out."""
        c = self.cfg
        Z, fs = c.depth, c.stance
        flat = self.floor - (self.floor - self.ankle[side][1])
        if phase < fs:
            z = Z - 2 * Z * phase / fs
            lift, ang = 0.0, c.toward_toe * smooth(clamp01((phase - 0.55 * fs) / (0.45 * fs))) + c.toward_heel * (1 - smooth(clamp01(phase / (0.2 * fs))))
            planted = True
        else:
            u = (phase - fs) / (1 - fs)
            m = -2 * Z * (1 - fs) / fs
            z = (2 * u ** 3 - 3 * u ** 2 + 1) * -Z + (u ** 3 - 2 * u ** 2 + u) * m + (-2 * u ** 3 + 3 * u ** 2) * Z + (u ** 3 - u ** 2) * m
            lift = c.lift * math.sin(math.pi * u) ** 0.9
            ang = lerp(c.toward_toe, c.toward_heel, smooth(u))
            planted = False
        out = c.toward_out * (1 if side == "L" else -1)
        return np.array([self.ankle[side][0] + out, flat + z - lift]), ang, planted, z / Z

    def _walk_toward(self, p):
        c = self.cfg
        p = p % 1.0
        dy = self.bob(p, 0)
        dx = -c.sway * 1.5 * math.cos(TAU * (p - 0.31))
        pel = -c.roll * 1.3 * math.cos(TAU * (p - 0.31))
        A = {"pelvis": pel}
        pose = dict(root=(dx, dy), angles=A, offset={}, scale={}, toes=0)
        Mp = self.fig.matrices(dict(root=(dx, dy), angles={"pelvis": pel}))["pelvis"]
        near = None
        for side, off in (("R", 0.0), ("L", 0.5)):
            pos, ang, down, depth = self.foot_toward(side, (p + off) % 1.0)
            th, kb, fa = self.solve_leg(Mp, side, pos, ang, 1 if side == "L" else -1)
            A[f"thigh_{side}"], A[f"shin_{side}"], A[f"foot_{side}"] = th, kb, fa
            k = 1 + 0.07 * depth                                           # nearer is bigger
            pose["scale"][f"foot_{side}"] = (k, k)
            if near is None or depth > near[1]:
                near = (side, depth)
        pose["front"] = near[0]
        A["torso"] = -0.8 * pel + 0.7 * math.sin(TAU * (p - 0.05))
        A["head"] = -0.6 * (pel + A["torso"]) + 3.0 * math.sin(TAU * (p - 0.2))
        pose["offset"]["head"] = (4.0 * math.sin(TAU * (p - 0.12)), 0.9 * (self.bob(p - 0.09, 0) - dy) - 2.5 * math.cos(TAU * 2 * (p - 0.10)))
        s = 0.014 * math.cos(TAU * 2 * (p - 0.31))
        pose["scale"]["torso"] = (1 - s * 0.5, 1 + s)
        # arms swing in depth: the arm going forward (or back) is foreshortened, most so at the end of its swing,
        # and the forearm folds up as it comes forward
        for side in "RL":
            f = (-1 if side == "R" else 1) * math.cos(TAU * (p - 0.06))      # forward swing, opposite the same-side leg
            swing = math.radians(c.toward_arm) * f
            sg = -1 if side == "R" else 1
            al = 11 + 3.0 * math.cos(TAU * (p - 0.9)) * (1 if side == "L" else -1)
            A[f"upper_arm_{side}"] = sg * (90 - al)
            pose["scale"][f"upper_arm_{side}"] = (math.cos(swing), 1.0)
            fwd = 0.5 + 0.5 * math.cos(TAU * (p - 0.14 - (0.5 if side == "R" else 0.0)))
            A[f"forearm_{side}"] = sg * (5 + 9 * smooth(fwd))
            pose["scale"][f"forearm_{side}"] = (1 - 0.22 * smooth(fwd), 1.0)
            A[f"hand_{side}"] = sg * (4 + 6 * smooth(0.5 + 0.5 * math.cos(TAU * (p - 0.24 - (0.5 if side == "R" else 0.0)))))
        return pose

    # ------------------------------------------------------------------ amount: getting going and stopping
    def _scaled(self, a):
        c = self.cfg
        return replace(c, stride=c.stride * a, lift=c.lift * a, heel_strike=c.heel_strike * a, toe_off=c.toe_off * a,
                       sway=c.sway * a, roll=c.roll * a, lean=c.lean * a, depth=c.depth * a, toward_toe=c.toward_toe * a,
                       toward_heel=c.toward_heel * a, toward_arm=c.toward_arm * a)

    def _with_amount(self, fn, a, mode, *args):
        """run a walk with every size scaled by a; its pelvis-height curve is kept per (mode, a)"""
        base, saved, key = self.cfg, self._bob, (mode, round(a, 2))
        self.cfg, self._bob = self._scaled(a), self._bob_cache.get(key)
        try:
            return fn(*args)
        finally:
            self._bob_cache[key] = self._bob
            self.cfg, self._bob = base, saved

    def _amount(self, fn, mode, a, t, *args):
        a = clamp01(a)
        if a <= 0.001:
            return self.idle(t)
        if a >= 0.999:
            return fn(*args)
        return blend(self.idle(t), self._with_amount(fn, a, mode, *args), smooth(a))

    def walk(self, p, dirn=1, amount=1.0, t=0.0):
        """the sideways walk at phase p. amount 0..1 scales the stride and everything that goes with it: 0 is
        standing (the idle pose at time t), 1 the full walk; ramp it for getting going and stopping, with the
        body moving at speed * amount, and the planted feet stay put through it."""
        return self._amount(self._walk, dirn, amount, t, p, dirn)

    def walk_toward(self, p, amount=1.0, t=0.0):
        """the walk down the screen towards the camera (see walk)"""
        return self._amount(self._walk_toward, 0, amount, t, p)

    # ------------------------------------------------------------------ standing
    def _stand(self, root, roll, spread):
        """a standing pose: both feet flat where they are at rest, the pelvis a little lower than the legs' full reach"""
        A = {"pelvis": roll}
        Mp = self.fig.matrices(dict(root=root, angles={"pelvis": roll}))["pelvis"]
        for side in "RL":
            target = np.array([self.ankle[side][0], self.floor - (self.floor - self.ankle[side][1])])
            th, kb, fa = self.solve_leg(Mp, side, target, 0.0, 1 if side == "L" else -1)
            A[f"thigh_{side}"], A[f"shin_{side}"], A[f"foot_{side}"] = th, kb, fa
        A["upper_arm_R"], A["upper_arm_L"] = -(90 - spread), 90 - spread
        return A

    def idle(self, t):
        """standing: breathing, the weight shifting from foot to foot, the head moving, the arms hanging loose"""
        br = math.sin(TAU * t / 3.6)
        sh = math.sin(TAU * t / 5.2)
        look = math.sin(TAU * t / 6.5)
        root = (5.0 * sh, 5.0)
        A = self._stand(root, 1.2 * math.sin(TAU * t / 5.2 + 0.4), 10 + 2 * math.sin(TAU * t / 5.2 + 0.9))
        A["torso"] = -0.8 * A["pelvis"] + 0.6 * math.sin(TAU * t / 5.2 + 0.9)
        A["head"] = 3.5 * look + 1.2 * math.sin(TAU * t / 4.1)
        for side in "RL":
            sg = -1 if side == "R" else 1
            A[f"forearm_{side}"] = sg * (6 + 3 * math.sin(TAU * t / 5.2 + 1.3))
            A[f"hand_{side}"] = sg * (6 + 3 * math.sin(TAU * t / 5.2 + 1.8))
        return dict(root=root, angles=A, offset={"head": (4 * math.sin(TAU * t / 6.5 + 0.5), -2.2 * br + 1.5 * math.sin(TAU * t / 4.1))},
                    scale={"torso": (1 - 0.006 * br, 1 + 0.012 * br)}, toes=0)

    def wave(self, t, arm="R"):
        """idle, with one arm up and waving: the elbow out, the forearm up and swinging to and fro"""
        pose = self.idle(t)
        A = pose["angles"]
        up = smooth(clamp01(t / 0.5))                                       # raised, then waving
        s = -1 if arm == "R" else 1
        w = TAU * 2.0 * t
        A[f"upper_arm_{arm}"] = lerp(A[f"upper_arm_{arm}"], s * (90 - 126 - 3 * math.sin(w * 0.5)), up)
        A[f"forearm_{arm}"] = -s * (56 + 24 * math.sin(w)) * up
        A[f"hand_{arm}"] = -s * (6 + 20 * math.sin(w - 1.0)) * up
        A["head"] += (5 if arm == "L" else -5) * up
        A["torso"] += (-2 if arm == "L" else 2) * up
        return pose


def blend(a, b, w):
    """a pose part way from a to b"""
    out = dict(root=tuple(lerp(x, y, w) for x, y in zip(a["root"], b["root"])), angles={}, offset={}, scale={})
    for k in set(a["angles"]) | set(b["angles"]):
        out["angles"][k] = lerp(a["angles"].get(k, 0.0), b["angles"].get(k, 0.0), w)
    for k in set(a.get("offset", {})) | set(b.get("offset", {})):
        x, y = a.get("offset", {}).get(k, (0, 0)), b.get("offset", {}).get(k, (0, 0))
        out["offset"][k] = (lerp(x[0], y[0], w), lerp(x[1], y[1], w))
    for k in set(a.get("scale", {})) | set(b.get("scale", {})):
        x, y = a.get("scale", {}).get(k, (1, 1)), b.get("scale", {}).get(k, (1, 1))
        out["scale"][k] = (lerp(x[0], y[0], w), lerp(x[1], y[1], w))
    src = b if w >= 0.5 else a
    for k in ("front", "toes"):
        if k in src:
            out[k] = src[k]
    return out


# ------------------------------------------------------------------------------------------------------ review
def backdrop(w, h, floor_y, horizon=None):
    """a plain wall and floor to review against; the floor starts at `horizon` (default: the line the feet stand on)"""
    horizon = floor_y if horizon is None else horizon
    img = np.zeros((h, w, 3), np.uint8)
    top, bot = np.array([196, 188, 176]), np.array([226, 220, 208])
    for y in range(h):
        img[y] = (top + (bot - top) * y / h).astype(np.uint8)
    img[horizon:] = (150, 142, 132)
    cv2.line(img, (0, horizon), (w, horizon), (110, 104, 96), 2)
    return img


def shadow(frame, x, y, scale, fig):
    ov = frame.copy()
    cv2.ellipse(ov, (int(x), int(y)), (int(150 * scale), int(22 * scale)), 0, 0, 360, (60, 56, 52), -1, cv2.LINE_AA)
    frame[:] = cv2.addWeighted(ov, 0.28, frame, 0.72, 0)


def strip(g, phases, dirn, path, scale=0.30, labels=True):
    n = len(phases)
    W, H = int(1402 * scale * 0.62), int(1122 * scale)
    floor_y = H - 18
    tiles = []
    for ph in phases:
        fr = backdrop(W, H, floor_y)
        pose = g.walk(ph, dirn) if dirn else g.walk_toward(ph)
        shadow(fr, W / 2, floor_y, scale, g.fig)
        g.fig.draw(fr, pose, W / 2, floor_y, scale)
        if labels:
            cv2.putText(fr, f"{ph:.2f}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
        tiles.append(fr)
    rows = [np.hstack(tiles[i:i + 8]) for i in range(0, n, 8)]
    width = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0)), constant_values=200) for r in rows]
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])


def check(g, dirn=1, fps=24, cycles=3):
    """numbers a walk must satisfy, measured on the poses at film rate: the ankles land where the feet are placed
    (reach, px), no foot goes below the floor (sink), the heel or toe a planted foot rolls on stays put in the world,
    the figure moving at g.speed (slide, px per frame, in T-pose px), and the knee and pelvis ranges"""
    out = dict(reach=0.0, sink=0.0, slide=0.0, knee=0.0, bob=[1e9, -1e9])
    c = g.cfg
    prev = {}
    for k in range(int(cycles * c.cycle * fps)):
        t = k / fps
        p = (t / c.cycle) % 1.0
        pose = g.walk(p, dirn) if dirn else g.walk_toward(p)
        M = g.fig.matrices(pose)
        cur = {}
        for side, off in (("R", 0.0), ("L", 0.5)):
            ph = (p + off) % 1.0
            tgt = g.foot(side, ph, dirn)[0] if dirn else g.foot_toward(side, ph)[0]
            out["reach"] = max(out["reach"], float(np.hypot(*(g.fig.point(M, f"foot_{side}", g.ankle[side]) - tgt))))
            heel, toe = g.heel_toe["L" if dirn >= 0 else "R"]
            pts = [g.fig.point(M, f"foot_{side}", g.ankle[side] + q) for q in (heel, toe)]
            out["sink"] = max(out["sink"], max(pt[1] for pt in pts) - g.floor)
            if dirn and ph < c.stance:
                kind = "heel" if ph < 0.5 * c.stance else "toe"
                cur[side] = (kind, dirn * g.speed * t + pts[0 if kind == "heel" else 1][0])
            out["knee"] = max(out["knee"], abs(pose["angles"][f"shin_{side}"]))
        for side in cur:
            if side in prev and prev[side][0] == cur[side][0]:            # the same contact point on both frames
                out["slide"] = max(out["slide"], abs(cur[side][1] - prev[side][1]))
        prev = cur
        out["bob"] = [min(out["bob"][0], pose["root"][1]), max(out["bob"][1], pose["root"][1])]
    return {k: ([round(float(x), 1) for x in v] if isinstance(v, list) else round(float(v), 2)) for k, v in out.items()}


def clip(g, path, fps=24, W=1920, H=1080):
    """test film: idle, walk right across the floor, walk back left, walk towards the camera, idle, wave"""
    fig = g.fig
    scale = 0.50
    floor_y = H - 170
    vel = g.speed * scale                                                   # frame px per second at full stride
    ramp = 0.5                                                              # seconds to get going / to stop
    margin = 330
    walk_t = (W - 2 * margin) / vel - ramp + 2 * ramp                       # the distance covered is vel * (time - ramp)
    near_t = 4.2
    segs = [("idle", 1.8), ("right", walk_t), ("idle", 1.0), ("left", walk_t), ("idle", 1.0), ("toward", near_t),
            ("idle", 1.0), ("wave", 3.4), ("idle", 1.0)]
    total = sum(s[1] for s in segs)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
                           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    bg = backdrop(W, H, floor_y, floor_y - 260)
    x = margin
    t0 = 0.0
    for name, dur in segs:
        for k in range(int(dur * fps)):
            t = k / fps
            now = t0 + t
            run = smooth(clamp01(t / ramp)) * smooth(clamp01((dur - t) / ramp))        # 0 standing .. 1 full stride
            sc, fy, xx = scale, floor_y, x
            if name == "idle":
                pose = g.idle(now)
            elif name == "wave":
                pose = g.wave(t, "R")
            elif name == "toward":
                e = smooth(clamp01(t / dur))
                sc, fy, xx = lerp(0.34, 0.58, e), lerp(floor_y - 120, floor_y + 60, e), W / 2
                pose = g.walk_toward((t / g.cfg.cycle) % 1.0, run, now)
            else:
                d = 1 if name == "right" else -1
                x += d * vel * run / fps
                xx = x
                pose = g.walk((t / g.cfg.cycle) % 1.0, d, run, now)
            fr = bg.copy()
            shadow(fr, xx, fy, sc, fig)
            fig.draw(fr, pose, xx, fy, sc)
            ff.stdin.write(fr.tobytes())
        t0 += dur
    ff.stdin.close()
    ff.wait()
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("character")
    ap.add_argument("--outfit", default="home")
    ap.add_argument("--clip", action="store_true", help="also render the test film")
    a = ap.parse_args()
    fig = Figure(a.character, a.outfit, master=0.45)
    g = Gait(fig)
    out = build_dir("anim", a.character)
    for d, name in ((1, "walk_right"), (-1, "walk_left")):
        strip(g, [k / 16 for k in range(16)], d, out / f"{name}.jpg")
        print(name, check(g, d), file=sys.stderr)
    strip(g, [k / 16 for k in range(16)], 0, out / "walk_toward.jpg")
    print("walk_toward", check(g, 0), file=sys.stderr)
    if a.clip:
        secs = clip(g, out / "walk_test.mp4")
        print(f"{out / 'walk_test.mp4'}  {secs:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
