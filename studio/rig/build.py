"""Build a character's puppet rigs from the labelled kit, one per view.

    python3 -m studio.rig.build CHARACTER [CHARACTER ...] [--outfit OUTFIT] [--views front side ...]

For each view: the anchor parts are placed where they sit in the kit's guide figure (place.py), the arm and leg
segments are built between them with two-bone IK, every part gets its joint pivot, and the skeleton links them
(skeleton.py). Output, rebuilt any time from the kit (git-ignored):
    build/rig/<id>/<outfit>/<view>/<part>.png   the cleaned drawings at kit resolution
    build/rig/<id>/<outfit>/<view>/rig.json     pivots, sockets, rest pose, layering
    build/rig/<id>/<outfit>/<view>_rest.jpg     the assembled rest puppet beside the guide figure"""
import argparse
import json
import math
import sys

import cv2
import numpy as np
import yaml

from studio.ingest import chart, kit
from studio.paths import CHARACTERS, build_dir
from studio.rig import geometry as geo
from studio.rig import place, skeleton

# drawing order, back to front. Inside a limb the upper segment covers the joint below it (upper arm over forearm
# over hand, thigh over shin, shoe over shin), and the pelvis covers the tops of the thighs, the collar the neck.
# Front view: both arms in front of the torso, so they can cross the body. Turned views (the character faces
# screen-right, so its right side is nearest): the far (left) limbs go behind everything, the near arm in front.
Z = {
    # front: the upper arms tuck behind the torso's shoulders (their rounded tops never show), the forearms and
    # hands come in front of it so the arms can still cross the body
    "front": ["shin_L", "foot_L", "thigh_L", "shin_R", "foot_R", "thigh_R", "pelvis", "neck",
              "upper_arm_L", "upper_arm_R", "torso", "hand_L", "forearm_L", "hand_R", "forearm_R",
              "head", "eyes", "mouth"],
    "turned": ["hand_L", "forearm_L", "upper_arm_L", "shin_L", "foot_L", "thigh_L",
               "shin_R", "foot_R", "thigh_R", "pelvis", "neck", "torso", "head", "eyes", "mouth",
               "hand_R", "forearm_R", "upper_arm_R"],
}
# joints whose seam is cleaned when both sides are the same colour (skin on skin, cloth on cloth): the segment
# drawn on top loses the outline across its end there, the other its rim. (parent segment, child segment)
SEAMS = [("upper_arm", "forearm"), ("forearm", "hand"), ("thigh", "shin")]
# which way elbows and knees bend, as a turn of the shoulder->wrist line (+1: towards screen-left when hanging)
BEND = {"front": dict(arm_R=+1, arm_L=-1, leg_R=+1, leg_L=-1),
        "three_quarter": dict(arm_R=+1, arm_L=+1, leg_R=-1, leg_L=-1),
        "side": dict(arm_R=+1, arm_L=+1, leg_R=-1, leg_L=-1)}
# hip joints in pelvis pixels (fractions of its box)
HIPS = {"front": dict(R=(0.28, 0.58), L=(0.72, 0.58)),
        "three_quarter": dict(R=(0.33, 0.6), L=(0.66, 0.6)),
        "side": dict(R=(0.52, 0.6), L=(0.46, 0.6))}


def rest_of(fit, img, pivot):
    """world rest placement of a registered part: its pivot's position, clockwise angle and scale"""
    h, w = img.shape[:2]
    x, y = fit.matrix(w, h) @ np.array([pivot[0], pivot[1], 1.0])
    return dict(x=float(x), y=float(y), angle=float(-fit.angle), scale=float(fit.scale))


def ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def rot(v, deg):
    a = math.radians(deg)
    return np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])


def ik2(S, T, L1, L2, bend):
    """Joint position of a two-segment chain from S to T, and the stretch needed (1 = none). `bend` picks the
    side the joint goes to."""
    d = T - S
    D = float(np.linalg.norm(d))
    if D >= L1 + L2 or D < 1e-6:
        k = max(1.0, D / (L1 + L2))
        return S + d / max(D, 1e-6) * L1 * k, k
    a = math.degrees(math.acos(np.clip((L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), -1, 1)))
    return S + rot(d / D, bend * a) * L1, 1.0


def fit_chain(imgs, piv, a, b, S, T, base, slack):
    """Make a two-segment chain (a, then b) reach from S to T with a natural slight bend: both drawings are
    resampled along their own axis by the same factor (their width is kept), so the chain is `slack` times the
    straight distance. Updates imgs/piv in place; returns the two segment lengths in guide pixels."""
    L1 = np.linalg.norm(piv[a][1] - piv[a][0]) * base
    L2 = np.linalg.norm(piv[b][1] - piv[b][0]) * base
    k = float(np.clip(slack * np.linalg.norm(T - S) / (L1 + L2), 0.6, 1.5))
    if abs(k - 1) > 0.02:
        for n in (a, b):
            imgs[n], p0, p1 = geo.stretch(imgs[n], piv[n][0], piv[n][1], k)
            piv[n] = (p0, p1)
    return L1 * k, L2 * k


def check_arm(S, T, L, torso, torso_img, view, side):
    """Sanity of the registered shoulder S and wrist T, with anatomical fallbacks: the shoulder sits at the top
    corner of the torso (or over it, in profile) and the hand hangs below it, about an arm's length down."""
    th, tw = torso_img.shape[0] * torso["scale"], torso_img.shape[1] * torso["scale"]
    top = torso["y"] - th                             # the torso's pivot is the middle of its hem
    sgn = -1 if side == "R" else 1
    far = view != "front" and side == "L"             # turned views: the far arm is mostly hidden in the guide
    if view == "front":
        sx, ok_x = torso["x"] + sgn * 0.4 * tw, 0.2 * tw < abs(S[0] - torso["x"]) < 0.75 * tw
    elif view == "three_quarter":
        sx = torso["x"] + (-0.28 if side == "R" else 0.34) * tw
        ok_x = abs(S[0] - sx) < 0.3 * tw
    else:
        sx, ok_x = torso["x"] - (0.04 if side == "R" else 0.07) * tw, abs(S[0] - torso["x"]) < 0.4 * tw
    if far or not (ok_x and top - 0.1 * th < S[1] < top + 0.4 * th):
        # in profile the far shoulder sits right behind the near one, low enough that its cap stays hidden
        S = np.array([sx, top + ((0.3 if view == "side" else 0.22) if far else 0.16) * th])
    d = T - S
    if far or not (d[1] > 0.55 * L and abs(d[0]) < 0.5 * L):
        lean = 0.0 if view == "side" else (0.06 if far else sgn * 0.12)
        T = S + 0.96 * L * np.array([lean, 1.0]) / math.hypot(lean, 1.0)
    return S, T


def width_at(img, joint, axis_dir):
    """the drawing's width across its axis at a joint"""
    m = geo.mask_of(img)
    ys, xs = np.nonzero(m)
    n = np.array([-axis_dir[1], axis_dir[0]])
    d = np.stack([xs - joint[0], ys - joint[1]], 1)
    band = np.abs(d @ axis_dir) < 3
    s = d[band] @ n
    return float(s.max() - s.min()) if len(s) else 20.0


def open_seams(imgs, piv, z):
    """Where two limb segments meet in the same colour, the joint should read as one limb: the segment drawn on
    top loses the outline across its end (and any lining in its opening), the one beneath loses its end rim so a
    wider cap can't show around it. A cuff over a hand keeps its line: different colours."""
    for s in "RL":
        for up, lo in SEAMS:
            u, l = f"{up}_{s}", f"{lo}_{s}"
            if u not in imgs or l not in imgs or piv[u][1] is None:
                continue
            # the joint as seen from each side: (part, joint point, direction out of the part across the joint)
            p0, p1 = piv[u]
            ax = (p1 - p0) / max(1e-6, np.linalg.norm(p1 - p0))
            ends = {u: (p1, ax)}
            if lo == "hand":                           # the hand's wrist is at the top of its drawing
                ends[l] = (piv[l][0], np.array([0.0, -1.0]))
            else:
                q0, q1 = piv[l]
                ends[l] = (q0, -(q1 - q0) / max(1e-6, np.linalg.norm(q1 - q0)))
            rad = {k: 0.5 * width_at(imgs[k], j, d) if k != l or lo != "hand" else 0.25 * imgs[k].shape[1]
                   for k, (j, d) in ends.items()}
            col = {k: geo.end_colour(imgs[k], j, -d, rad[k]) for k, (j, d) in ends.items()}
            if col[u] is None or col[l] is None or np.linalg.norm(col[u] - col[l]) > 48:
                continue
            top, under = (u, l) if z.index(u) > z.index(l) else (l, u)
            j, d = ends[top]
            imgs[top] = geo.fill_end(imgs[top], j, d, rad[top], col[top])   # the cloth carries on: no lining
            imgs[top] = geo.open_end(imgs[top], j, d, rad[top])
            if under != l or lo != "hand":
                j, d = ends[under]
                imgs[under] = geo.open_end(imgs[under], j, d, rad[under])


def segment(img_joints, S, E, base_scale):
    """rest placement of a limb segment whose pivot sits on S and whose far joint must reach E"""
    prox, dist = img_joints
    u = dist - prox
    w = E - S
    return dict(x=float(S[0]), y=float(S[1]), angle=ang(w) - ang(u),
                scale=float(np.linalg.norm(w) / max(1e-6, np.linalg.norm(u))))


def build_view(cid, outfit, view, out_dir):
    png = CHARACTERS / cid / "kit" / outfit / f"{view}.png"
    spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
    rgba, named, guide, _ = kit.resolve(png, spec)
    G = chart.cutout(rgba, [guide])
    imgs = {k: chart.cutout(rgba, v) for k, v in named.items() if k in skeleton.PARENT}
    fits = place.place(imgs, G, view)
    piv, parts = {}, {}

    # pivots, in part pixels
    for n, img in imgs.items():
        h, w = img.shape[:2]
        if n.startswith(("upper_arm", "forearm", "thigh", "shin")):
            prox, dist, wp, wd = geo.limb_joints(img)
            piv[n] = (prox, dist)
        elif n.startswith("hand"):
            imgs[n], _ = geo.trim_cuff(img, kit.skin_of(cid, outfit))
            piv[n] = (geo.top_centre(imgs[n]), None)
        elif n.startswith("foot"):
            piv[n] = (geo.ankle(img, view), None)
        elif n == "pelvis":
            piv[n] = (np.array([w / 2, 0.15 * h]), None)
        elif n == "torso":
            piv[n] = (geo.bottom_centre(img), None)
        elif n == "neck":
            piv[n] = (geo.bottom_centre(img), None)
        elif n == "head":
            b = geo.bottom_centre(img)
            piv[n] = (np.array([b[0], b[1] - 0.06 * h]), None)
        else:                                   # eyes, mouth: fixed on the head
            piv[n] = (np.array([w / 2, h / 2]), None)

    rest = {}
    for n in ("pelvis", "torso", "head", "neck", "eyes", "mouth"):
        if n in imgs:
            rest[n] = rest_of(fits[n], imgs[n], piv[n][0])
    place.settle_pelvis(rest, imgs, piv)
    base = fits["torso"].scale
    bend = BEND[view]
    skin = kit.skin_of(cid, outfit)

    # arms: shoulder (from the registered upper arm) to wrist (from the registered hand)
    for s in "RL":
        ua, fa, hd = f"upper_arm_{s}", f"forearm_{s}", f"hand_{s}"
        if not all(k in imgs for k in (ua, fa, hd)):
            continue
        S = np.array([*rest_of(fits[ua], imgs[ua], piv[ua][0]).values()][:2])
        hr = rest_of(fits[hd], imgs[hd], piv[hd][0])
        T = np.array([hr["x"], hr["y"]])
        L = (np.linalg.norm(piv[ua][1] - piv[ua][0]) + np.linalg.norm(piv[fa][1] - piv[fa][0])) * base
        S, T = check_arm(S, T, L, rest["torso"], imgs["torso"], view, s)
        imgs[ua] = geo.fill_cap(imgs[ua], piv[ua][0], piv[ua][1], skin)
        L1, L2 = fit_chain(imgs, piv, ua, fa, S, T, base, 1.04)
        E, k = ik2(S, T, L1, L2, bend[f"arm_{s}"])
        rest[ua] = segment(piv[ua], S, E, base)
        Wr = E + (T - E) / max(1e-6, np.linalg.norm(T - E)) * L2 * k
        rest[fa] = segment(piv[fa], E, Wr, base)
        rest[hd] = dict(hr, x=float(Wr[0]), y=float(Wr[1]))

    # legs: hip (on the pelvis) to ankle (from the registered foot)
    Pm = skeleton.mat(rest["pelvis"]["x"], rest["pelvis"]["y"], rest["pelvis"]["angle"], rest["pelvis"]["scale"],
                      *piv["pelvis"][0])
    ph, pw = imgs["pelvis"].shape[:2]
    for s in "RL":
        th, sh, ft = f"thigh_{s}", f"shin_{s}", f"foot_{s}"
        if not all(k in imgs for k in (th, sh, ft)):
            continue
        fx, fy = HIPS[view][s]
        Hp = skeleton.apply(Pm, (fx * pw, fy * ph))
        fr = rest_of(fits[ft], imgs[ft], piv[ft][0])
        A = np.array([fr["x"], fr["y"]])
        L1, L2 = fit_chain(imgs, piv, th, sh, Hp, A, base, 1.01)
        K, k = ik2(Hp, A, L1, L2, bend[f"leg_{s}"])
        rest[th] = segment(piv[th], Hp, K, base)
        Ar = K + (A - K) / max(1e-6, np.linalg.norm(A - K)) * L2 * k
        rest[sh] = segment(piv[sh], K, Ar, base)
        rest[ft] = dict(fr, x=float(Ar[0]), y=float(Ar[1]))

    z = Z["front"] if view == "front" else Z["turned"]
    open_seams(imgs, piv, z)
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, img in imgs.items():
        if n not in rest:
            continue
        cv2.imwrite(str(out_dir / f"{n}.png"), cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA))
        parts[n] = dict(file=f"{n}.png", size=[img.shape[1], img.shape[0]],
                        pivot=[round(float(v), 2) for v in piv[n][0]],
                        joint=[round(float(v), 2) for v in piv[n][1]] if piv[n][1] is not None else None,
                        parent=skeleton.PARENT[n], rest={k: round(v, 3) for k, v in rest[n].items()},
                        z=z.index(n), err=round(fits[n].err, 4) if n in fits else None)
    skeleton.link(parts)
    feet = [n for n in ("foot_R", "foot_L") if n in parts]
    rig = dict(character=cid, outfit=outfit, view=view, guide=[G.shape[1], G.shape[0]],
               floor=float(G.shape[0]), parts=parts)
    (out_dir / "rig.json").write_text(json.dumps(rig, indent=1))
    return rig, G


def build_hands(cid, outfit, out_dir, body_hand_width):
    """The gesture library: every hand pose from the hands sheet, cuffs trimmed, with its wrist point, the
    direction from wrist to fingers, and the scale that matches the body sheet's hands. The relaxed hand is drawn
    fingers-down (wrist at the top); every other gesture wrist-down."""
    png = CHARACTERS / cid / "kit" / outfit / "hands.png"
    if not png.exists():
        return None
    spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
    rgba, named, guide, _ = kit.resolve(png, spec)
    skin = kit.skin_of(cid, outfit)
    out_dir.mkdir(parents=True, exist_ok=True)
    lib = {}
    for name, pieces in named.items():
        img = chart.cutout(rgba, pieces)
        up = name.startswith("relaxed")              # wrist at the top
        if not up:
            img = img[::-1].copy()
        img, _ = geo.trim_cuff(img, skin)
        wrist = geo.top_centre(img, 0.08)
        if not up:
            img = img[::-1].copy()
            wrist = np.array([wrist[0], img.shape[0] - 1 - wrist[1]])
        m = geo.mask_of(img)
        ys, xs = np.nonzero(m)
        c = np.array([xs.mean(), ys.mean()])
        cv2.imwrite(str(out_dir / f"{name}.png"), cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA))
        lib[name] = dict(file=f"{name}.png", size=[img.shape[1], img.shape[0]],
                         wrist=[round(float(v), 2) for v in wrist], axis=round(ang(c - wrist), 2))
    # scale: the library's relaxed hand against the body sheet's (the sheets are drawn at different sizes); a
    # library hand drawn in place of the rig's hand gets the rig hand's own scale times this
    ref = [lib[k] for k in ("relaxed_R", "relaxed_L") if k in lib]
    k = body_hand_width / np.mean([r["size"][0] for r in ref]) if ref and body_hand_width else 1.0
    for v in lib.values():
        v["scale"] = round(float(k), 4)
    (out_dir / "hands.json").write_text(json.dumps(lib, indent=1))
    return lib


def hand_matrix(rig, Ms, side, lib, pose):
    """world matrix for a gesture-library hand on this rig's wrist, pointing along the forearm"""
    parts = rig["parts"]
    fa, hd = parts[f"forearm_{side}"], parts[f"hand_{side}"]
    Wf = Ms[f"forearm_{side}"]
    wrist = skeleton.apply(Wf, hd["socket"])
    elbow = skeleton.apply(Wf, fa["pivot"])
    phi = ang(wrist - elbow)
    g = lib[f"{pose}_{side}"]
    _, s_hand = skeleton.decompose(Ms[f"hand_{side}"])
    return skeleton.mat(wrist[0], wrist[1], phi - g["axis"], s_hand * g["scale"], *g["wrist"])


def draw(rig, base_dir, size, angles=None, root=None, bg=None, hands=None):
    """Quick numpy drawing of a rig at kit resolution (review only; the renderer uses Skia). hands = {"R": pose}
    swaps in gesture-library hands."""
    parts = rig["parts"]
    r = root or (parts["pelvis"]["rest"]["x"], parts["pelvis"]["rest"]["y"], 0.0, 1.0)
    Ms = skeleton.pose_matrices(parts, root=(r[0], r[1], r[2], r[3]), angles=angles)
    lib, hdir = None, base_dir.parent / "hands"
    if hands and (hdir / "hands.json").exists():
        lib = json.loads((hdir / "hands.json").read_text())
    W, H = size
    canvas = np.zeros((H, W, 4), np.float32)
    for n in sorted(parts, key=lambda n: parts[n]["z"]):
        src, M = base_dir / parts[n]["file"], Ms[n]
        side = n[-1]
        if lib and n.startswith("hand_") and side in hands:
            src, M = hdir / lib[f"{hands[side]}_{side}"]["file"], hand_matrix(rig, Ms, side, lib, hands[side])
        img = cv2.cvtColor(cv2.imread(str(src), cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
        w = cv2.warpAffine(img.astype(np.float32), M[:2], (W, H), flags=cv2.INTER_LINEAR,
                           borderValue=(0, 0, 0, 0))
        a = w[..., 3:4] / 255
        canvas[..., :3] = w[..., :3] * a + canvas[..., :3] * (1 - a)
        canvas[..., 3:4] = np.maximum(canvas[..., 3:4], w[..., 3:4])
    return canvas


def flat(x, grey=128):
    a = x[..., 3:4].astype(np.float32) / 255
    return (x[..., :3] * a + grey * (1 - a)).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chars", nargs="+")
    ap.add_argument("--outfit")
    ap.add_argument("--views", nargs="*", default=["front", "three_quarter", "side"])
    a = ap.parse_args()
    for cid in a.chars:
        c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text())
        for outfit in ([a.outfit] if a.outfit else list(c["outfits"])):
            panels = []
            body_hand = None
            for view in a.views:
                if not (CHARACTERS / cid / "kit" / outfit / f"{view}.png").exists():
                    continue
                d = build_dir("rig", cid, outfit, view)
                rig, G = build_view(cid, outfit, view, d)
                if view == "front" and "hand_R" in rig["parts"]:
                    body_hand = rig["parts"]["hand_R"]["size"][0]     # library hands are drawn to match it
                gh, gw = G.shape[:2]
                pad = int(0.15 * gw)
                canvas = draw(rig, d, (gw + 2 * pad, gh + pad // 2),
                              root=(rig["parts"]["pelvis"]["rest"]["x"] + pad,
                                    rig["parts"]["pelvis"]["rest"]["y"], 0.0, 1.0))
                Gp = np.zeros_like(canvas)
                Gp[:gh, pad:pad + gw] = G
                panels.append(np.hstack([flat(Gp), flat(canvas)]))
                bad = {n: p["err"] for n, p in rig["parts"].items() if p["err"] and p["err"] > 0.08}
                print(f"{cid} {outfit} {view}: {len(rig['parts'])} parts" + (f", weak matches {bad}" if bad else ""),
                      file=sys.stderr)
            lib = build_hands(cid, outfit, build_dir("rig", cid, outfit, "hands"), body_hand)
            if lib:
                print(f"{cid} {outfit} hands: {len(lib)} gestures", file=sys.stderr)
            if panels:
                h = max(p.shape[0] for p in panels)
                panels = [cv2.copyMakeBorder(p, 0, h - p.shape[0], 0, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                          for p in panels]
                cv2.imwrite(str(build_dir("rig", cid) / f"{outfit}_rest.jpg"),
                            cv2.cvtColor(np.hstack(panels), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])


if __name__ == "__main__":
    main()
