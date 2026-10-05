"""Cut a T-pose drawing into the parts of a posable puppet.

    python3 -m studio.rig.tpose CHARACTER [--outfit OUTFIT]
        build/rig/<id>/<outfit>/tpose/<part>.png     the parts, cropped, with what is hidden behind their neighbours painted in
        build/rig/<id>/<outfit>/tpose/rig.json       joints, parts, z-order, where each part bends
        build/rig/<id>/<outfit>/tpose/parts.jpg      the parts laid out, to look at
        build/rig/<id>/<outfit>/tpose/rest.png       the parts put back together; the report says how far that is from the drawing

The source is library/characters/<id>/rig/<outfit>/tpose.png with a tpose.yaml beside it (how to cut it: polygons
for each part, the hidden overlaps, the joints). A single drawing of the character standing with arms out is the
ideal source for a cut-out rig: nothing overlaps, so every part can be lifted off whole. Where one part sits behind
another when assembled (a forearm under its sleeve, the neck under the beard, the thigh under the shorts) the
hidden end is painted in, so the parts can turn about their joints without leaving gaps.

The parts, back to front: leg (thigh skin and sock, bends at the knee), boot, pelvis (shorts), limb (bare arm,
bends at the elbow and wrist), sleeve (turns at the shoulder, with a rounded end), torso, head. The arms and legs
are strips that bend along an arc at their joints (see studio.anim.figure), the rest are rigid. Left parts are the right ones mirrored
about the body's centre line unless the yaml writes them out."""
import argparse
import json
import math
import sys

import cv2
import numpy as np
import yaml

from studio.paths import CHARACTERS, build_dir

ZORDER = ["leg_R", "leg_L", "boot_R", "boot_L", "pelvis", "limb_R", "limb_L", "sleeve_R", "sleeve_L", "torso", "head"]
SOCK = (28, 28, 30)                 # BGR of the sock's black, for the part of it inside the boot
OUTLINE = (20, 17, 24)


def source_dir(cid, outfit):
    return CHARACTERS / cid / "rig" / outfit


def load(cid, outfit):
    d = source_dir(cid, outfit)
    spec = yaml.safe_load((d / "tpose.yaml").read_text())
    img = cv2.imread(str(d / spec["image"]), cv2.IMREAD_UNCHANGED)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    img[..., 3] = np.where(img[..., 3] >= 248, 255, img[..., 3])        # generated mattes are 252/253 where solid
    return spec, drop_specks(img)


def drop_specks(img, min_area=2000):
    """clear the stray low-alpha dust a generated matte leaves round the figure"""
    near = cv2.dilate((img[..., 3] > 0).astype(np.uint8), np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(near, connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_area
    img = img.copy()
    img[~keep[lab]] = 0
    return img


def mirrored(pts, axis):
    return [[2 * axis - x, y] for x, y in pts]


def poly_mask(shape, pts):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(pts, float)).astype(np.int32)], 1)
    return m.astype(bool)


def cut(spec, img):
    """{part: full-canvas BGRA with only that part's pixels}, every opaque pixel in exactly one part"""
    axis = spec["axis"]
    polys = {}
    for name, p in spec["parts"].items():
        polys[name] = p["poly"]
        if p.get("mirror"):
            polys[name.replace("_R", "_L")] = mirrored(p["poly"], axis)
    taken = np.zeros(img.shape[:2], bool)
    parts = {}
    for name, pts in polys.items():
        m = poly_mask(img.shape, pts) & (img[..., 3] > 0) & ~taken
        taken |= m
        layer = np.zeros_like(img)
        layer[m] = img[m]
        parts[name] = layer
    return parts, int(((img[..., 3] > 0) & ~taken).sum())


def alpha(layer):
    return layer[..., 3] > 0


def solid(layer):
    return layer[..., 3] == 255                      # fully opaque: what really hides a part that sits behind it


def over(top, bottom):
    """straight-alpha BGRA uint8, top over bottom"""
    t, b = top.astype(np.float32), bottom.astype(np.float32)
    ta, ba = t[..., 3:4] / 255, b[..., 3:4] / 255
    oa = ta + ba * (1 - ta)
    rgb = (t[..., :3] * ta + b[..., :3] * ba * (1 - ta)) / np.maximum(oa, 1e-6)
    return np.concatenate([rgb, oa * 255], -1).round().astype(np.uint8)


# ------------------------------------------------------------------------------------------------ hidden overlaps
def paint_neck(L, ov):
    """neck skin up under the beard: the torso's neck, carried up from where the head cuts it"""
    T = L["torso"]
    top = ov["top"]
    a = alpha(T)
    for x in range(ov["x"][0], ov["x"][1] + 1):
        ys = np.nonzero(a[top:, x])[0]
        if len(ys):
            y0 = top + ys[0]
            T[top:y0, x] = T[y0 + 2, x]
            T[top:y0, x, 3] = 255


def paint_waist(L, ov):
    """the shorts' waist carried up under the shirt hem (only where the shirt will cover it)"""
    P, T = L["pelvis"], L["torso"]
    ta = solid(T)
    for x in range(P.shape[1]):
        ys = np.nonzero(alpha(P)[:, x])[0]
        if not len(ys):
            continue
        y0 = ys[0]
        for y in range(y0 - ov["rows"], y0):
            if y >= 0 and ta[y, x] and not P[y, x, 3]:
                P[y, x] = P[y0 + 4, x]


def paint_thigh(L, ov):
    """the thigh skin carried up under the shorts: with its outline for the first rows (so a leg that swings out does
    not show a notch at the hem), then skin only and a little narrower than the visible leg"""
    P = L["pelvis"]
    pa = solid(P)
    ref = ov["ref"]
    for side in "RL":
        G = L[f"leg_{side}"]
        xs = np.nonzero(G[ref, :, 3])[0]
        for y in range(ref - ov["rows"], ref):
            full = y >= ref - 14
            lo, hi = (xs.min(), xs.max()) if full else (xs.min() + 9, xs.max() - 8)
            for x in range(lo, hi + 1):
                if pa[y, x] and not G[y, x, 3]:
                    G[y, x] = G[ref + (0 if full else 6), x]


def paint_sock(L, ov):
    """the sock run down inside the boot, ending in a round, so a boot that turns shows sock behind it, not a block"""
    ref = ov["ref"]
    for side in "RL":
        G, B = L[f"leg_{side}"], L[f"boot_{side}"]
        xs = np.nonzero(G[ref, :, 3])[0]
        cx, hw = (xs.min() + xs.max()) / 2, (xs.max() - xs.min()) / 2 - 5
        ba = solid(B)
        n = ov["down"] - 4
        for y in range(ref + 4, ref + ov["down"]):
            half = hw * math.sqrt(max(0.0, 1 - ((y - ref - 4) / n) ** 2))
            for x in range(int(cx - half), int(cx + half) + 1):
                if ba[y, x] and not G[y, x, 3]:
                    G[y, x] = (*SOCK, 255)


def paint_forearm(L, ov):
    """the bare arm run on in under its sleeve"""
    for side in "RL":
        o = ov["forearm"][side]
        G, S = L[f"limb_{side}"], L[f"sleeve_{side}"]
        sa = solid(S)
        step = 1 if o["to"] > o["cuff"] else -1
        src = o["cuff"] - 5 * step
        for x in range(o["cuff"], o["to"] + step, step):
            for y in np.nonzero(G[:, src, 3])[0]:
                if sa[y, x] and not G[y, x, 3]:
                    G[y, x] = G[y, src]


def paint_shoulder(L, ov):
    """the sleeve's end rounded off: a dome (shirt colour mirrored from the sleeve, with an outline) behind the
    sleeve and under the torso, so that a sleeve that turns down carries a rounded shoulder. Only the dome's outer
    half ever shows."""
    ss, t = 4, 7.0                                       # outline supersampling and thickness
    for side in "RL":
        o = ov["shoulder"][side]
        S = L[f"sleeve_{side}"]
        cx, cy, r = o["x"], o["y"], o["r"]
        sgn = 1 if side == "R" else -1                   # the dome lies on the body side of the pivot
        x0, y0 = (cx - 4, cy - r - 4) if sgn > 0 else (cx - r - 4, cy - r - 4)
        w, h = r + 8, 2 * r + 8
        ys, xs = np.mgrid[y0:y0 + h, x0:x0 + w]
        src = S[ys, np.clip(2 * cx - xs, 0, S.shape[1] - 1)]          # the sleeve, mirrored about the pivot
        inside = ((xs - cx) ** 2 + (ys - cy) ** 2 <= r * r) & (sgn * (xs - cx) >= 0) & (src[..., 3] > 0)
        dome = np.zeros((h, w, 4), np.uint8)
        dome[inside] = src[inside]
        big = np.zeros((h * ss, w * ss), np.uint8)
        for ang in np.linspace(-90, 90, 181):
            a = np.radians(ang)
            px, py = cx + sgn * (r - t / 2) * np.cos(a), cy + (r - t / 2) * np.sin(a)
            cv2.circle(big, (int(round((px - x0) * ss)), int(round((py - y0) * ss))), int(t / 2 * ss), 255, -1, cv2.LINE_AA)
        arc = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        arc *= (sgn * (xs - cx) >= -1)
        d = dome.astype(np.float32)
        for c, v in enumerate(OUTLINE):
            d[..., c] = d[..., c] * (1 - arc) + v * arc
        d[..., 3] = np.maximum(d[..., 3], arc * 255)
        layer = np.zeros_like(S)
        layer[y0:y0 + h, x0:x0 + w] = d.round().astype(np.uint8)
        yy, xx = np.mgrid[0:S.shape[0], 0:S.shape[1]]
        S[(sgn * (xx - cx) > 0) & ((xx - cx) ** 2 + (yy - cy) ** 2 > r * r)] = 0         # the seam's corner tucked away
        out = over(S, layer)
        # the crease and seam lines drawn on the shoulder would show as a black thorn once the sleeve hangs: even them out
        inner = (sgn * (xx - (cx - 4 * sgn)) > 0) & ((xx - cx) ** 2 + (yy - cy) ** 2 < (r - 10) ** 2)
        dark = inner & (out[..., 3] == 255) & (out[..., :3].max(-1) < 95)
        shirt = np.median(out[cy - 10:cy + 10, cx - 30 * sgn - 6:cx - 30 * sgn + 6].reshape(-1, 4), 0)[:3]
        out[dark, :3] = shirt.astype(np.uint8)
        L[f"sleeve_{side}"] = out


OVERLAPS = [("neck", paint_neck), ("waist", paint_waist), ("thigh", paint_thigh), ("sock", paint_sock)]


def overlap(L, spec):
    ov = spec["overlaps"]
    for key, fn in OVERLAPS:
        fn(L, ov[key])
    paint_forearm(L, ov)          # needs the sleeves as cut, before the dome is added
    paint_shoulder(L, ov)


# -------------------------------------------------------------------------------------------------- assembly
def assemble(L, order=ZORDER):
    out = np.zeros_like(next(iter(L.values())))
    for n in order:
        out = over(L[n], out)
    return out


def crop(layer):
    ys, xs = np.nonzero(layer[..., 3])
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return layer[y0:y1, x0:x1], (int(x0), int(y0))


def rig_json(spec, boxes):
    """bones (parent, pivot, and for a bending joint the axis and length of its bend zone) and parts (file, origin,
    z, and which bone drives it: one for a rigid part, a chain for a limb that bends)"""
    J = {k: list(v) for k, v in spec["joints"].items()}
    zone = spec["bends"]
    bones = {
        "pelvis": dict(parent=None, pivot=J["root"]),
        "torso": dict(parent="pelvis", pivot=J["waist"]),
        "head": dict(parent="torso", pivot=J["neck"]),
    }
    for s in "RL":
        d = [-1, 0] if s == "R" else [1, 0]                         # along the arm, shoulder to hand
        bones[f"upper_arm_{s}"] = dict(parent="torso", pivot=J[f"shoulder_{s}"])
        bones[f"forearm_{s}"] = dict(parent=f"upper_arm_{s}", pivot=J[f"elbow_{s}"], bend=dict(axis=d, zone=zone["elbow"]))
        bones[f"hand_{s}"] = dict(parent=f"forearm_{s}", pivot=J[f"wrist_{s}"], bend=dict(axis=d, zone=zone["wrist"]))
        bones[f"thigh_{s}"] = dict(parent="pelvis", pivot=J[f"hip_{s}"])
        bones[f"shin_{s}"] = dict(parent=f"thigh_{s}", pivot=J[f"knee_{s}"], bend=dict(axis=[0, 1], zone=zone["knee"]))
        bones[f"foot_{s}"] = dict(parent=f"shin_{s}", pivot=J[f"ankle_{s}"])
    parts = {}
    for n in ZORDER:
        p = dict(file=f"{n}.png", origin=boxes[n], z=ZORDER.index(n))
        if n.startswith("limb_"):
            s = n[-1]
            p["skin"] = dict(bones=[f"upper_arm_{s}", f"forearm_{s}", f"hand_{s}"], axis=bones[f"forearm_{s}"]["bend"]["axis"])
        elif n.startswith("leg_"):
            s = n[-1]
            p["skin"] = dict(bones=[f"thigh_{s}", f"shin_{s}"], axis=[0, 1])
        else:
            p["bone"] = {"pelvis": "pelvis", "torso": "torso", "head": "head", "sleeve_R": "upper_arm_R",
                         "sleeve_L": "upper_arm_L", "boot_R": "foot_R", "boot_L": "foot_L"}[n]
        parts[n] = p
    return dict(canvas=[1402, 1122], axis=spec["axis"], floor=spec["floor"], bones=bones, parts=parts)


def sheet(L, path):
    """the parts laid out on a grey ground, for review"""
    names = list(L)
    tiles = []
    for n in names:
        c, _ = crop(L[n])
        tiles.append((n, c))
    W = 1800
    x = y = row_h = 0
    pos = []
    for n, c in tiles:
        h, w = c.shape[:2]
        if x + w + 12 > W:
            x, y, row_h = 0, y + row_h + 26, 0
        pos.append((n, c, x, y + 18))
        x += w + 12
        row_h = max(row_h, h + 4)
    canvas = np.full((y + row_h + 30, W, 3), (92, 112, 92), np.uint8)
    for n, c, x, y in pos:
        a = c[..., 3:4].astype(np.float32) / 255
        roi = canvas[y:y + c.shape[0], x:x + c.shape[1]]
        roi[:] = (c[..., :3] * a + roi * (1 - a)).astype(np.uint8)
        cv2.putText(canvas, n, (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas)


def build(cid, outfit="home", out=None):
    spec, img = load(cid, outfit)
    out = out or build_dir("rig", cid, outfit, "tpose")
    L, stray = cut(spec, img)
    rest0 = assemble(L)
    overlap(L, spec)
    rest = assemble(L)
    diff = np.abs(rest.astype(int) - img.astype(int)).max(-1)
    boxes = {}
    for n, layer in L.items():
        c, o = crop(layer)
        cv2.imwrite(str(out / f"{n}.png"), c)
        boxes[n] = list(o)
    (out / "rig.json").write_text(json.dumps(rig_json(spec, boxes), indent=1))
    cv2.imwrite(str(out / "rest.png"), rest)
    sheet(L, out / "parts.jpg")
    print(f"{cid}/{outfit}: {len(L)} parts, {stray} opaque pixels in no part; put back together the parts differ from the "
          f"drawing in {int((diff > 8).sum())} pixels (the shoulder domes and the tucked seam corners; the cut alone: "
          f"{int((np.abs(rest0.astype(int) - img.astype(int)).max(-1) > 8).sum())})", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("character")
    ap.add_argument("--outfit", default="home")
    a = ap.parse_args()
    print(build(a.character, a.outfit))


if __name__ == "__main__":
    main()
