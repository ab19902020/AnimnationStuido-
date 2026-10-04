"""The shared skeleton and forward kinematics.

Every view of every character uses the same hierarchy (the kit brief's bone tree):
    pelvis -> torso -> neck -> head -> eyes, mouth
    torso  -> upper_arm -> forearm -> hand          (R and L)
    pelvis -> thigh -> shin -> foot                  (R and L)
A part turns about its pivot (its joint with its parent, in part pixels). In the rest pose each part's pivot sits
on its parent's socket for it; a pose adds an angle to any joint. Angles are degrees, clockwise on screen (y down)."""
import math

import numpy as np

PARENT = {"pelvis": None, "torso": "pelvis", "neck": "torso", "head": "neck", "eyes": "head", "mouth": "head"}
for _s in "RL":
    PARENT.update({f"upper_arm_{_s}": "torso", f"forearm_{_s}": f"upper_arm_{_s}", f"hand_{_s}": f"forearm_{_s}",
                   f"thigh_{_s}": "pelvis", f"shin_{_s}": f"thigh_{_s}", f"foot_{_s}": f"shin_{_s}"})
ORDER = list(PARENT)          # parents always come before their children


def mat(x, y, angle, scale, px=0.0, py=0.0):
    """3x3: part pixels -> world, with the pivot (px, py) landing on (x, y)"""
    a = math.radians(angle)
    c, s = math.cos(a) * scale, math.sin(a) * scale
    return np.array([[c, -s, x - c * px + s * py],
                     [s, c, y - s * px - c * py],
                     [0, 0, 1.0]])


def apply(M, p):
    return (M @ np.array([p[0], p[1], 1.0]))[:2]


def decompose(M):
    """angle (deg) and uniform scale of a similarity matrix"""
    return math.degrees(math.atan2(M[1, 0], M[0, 0])), math.hypot(M[0, 0], M[1, 0])


def link(parts):
    """From each part's world rest placement (x, y, angle, scale of its pivot) derive the socket on its parent and
    the angle/scale relative to it. Mutates and returns `parts` (dicts with pivot, rest, parent)."""
    W = {n: mat(p["rest"]["x"], p["rest"]["y"], p["rest"]["angle"], p["rest"]["scale"], *p["pivot"])
         for n, p in parts.items()}
    for n, p in parts.items():
        q = p.get("parent")
        if q is None or q not in parts:
            p["parent"] = None
            continue
        inv = np.linalg.inv(W[q])
        p["socket"] = apply(inv, (p["rest"]["x"], p["rest"]["y"])).round(2).tolist()
        p["rel_angle"] = round(p["rest"]["angle"] - parts[q]["rest"]["angle"], 3)
        p["rel_scale"] = round(p["rest"]["scale"] / parts[q]["rest"]["scale"], 5)
    return parts


def pose_matrices(parts, root=(0.0, 0.0, 0.0, 1.0), angles=None, extra=None):
    """World matrix of every part. root = (x, y, angle, scale) placing the root (pelvis) pivot; angles = {part:
    degrees added at that joint}; extra = {part: 3x3 applied after, in parent space} for squash/stretch tricks."""
    angles = angles or {}
    out = {}
    for n in ORDER:
        if n not in parts:
            continue
        p = parts[n]
        px, py = p["pivot"]
        if p.get("parent") is None:
            x, y, a, s = root
            out[n] = mat(x, y, a + p["rest"]["angle"] + angles.get(n, 0.0), s * p["rest"]["scale"], px, py)
            continue
        Pm = out[p["parent"]]
        sx, sy = p["socket"]
        local = mat(sx, sy, p["rel_angle"] + angles.get(n, 0.0), p["rel_scale"], px, py)
        if extra and n in extra:
            local = extra[n] @ local
        out[n] = Pm @ local
    return out
