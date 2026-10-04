"""Rest placement of the anchor parts: where they sit in the sheet's assembled guide figure.

Registered directly: head, torso, pelvis, neck, eyes, mouth, hands, feet and the upper arms (for the shoulders).
The head, torso and pelvis are found anywhere in the guide; every other part only where the anatomy allows (hands
at the hip line, feet on the floor), which keeps look-alike parts out of each other's place. The arm and leg
segments in between are built by the rig (two-bone IK between shoulder and wrist, hip and ankle): in the guide they
are too covered up (shorts over thighs, one leg behind the other) to match reliably. Returns {part: Fit}."""
import numpy as np

from studio.ingest import register

LAMBDA = 0.004       # weight of one standard deviation of anatomical surprise, against the colour match error


def _box(cx, cy, w, h):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def turned(view):
    return view == "side"


def place(parts, guide, view):
    gh, gw = guide.shape[:2]
    fits = {}
    # the head (hair, skin, ears) is the most distinctive drawing: it fixes the assembly scale for the body, whose
    # plain clothes can match almost anywhere at almost any size
    HH, HW = parts["head"].shape[:2]

    def head_prior(cx, cy, s):
        # the head (hair included) is the top of the figure, drawn at about the sheet's one assembly scale; a
        # bald head or a plain face is otherwise free to match a smaller patch of skin
        hh = HH * s
        return LAMBDA * ((((cy - hh / 2) - 0) / (0.04 * hh)) ** 2 + (np.log(s) / 0.1) ** 2 +
                         ((cx - gw / 2) / (0.3 * HW * s)) ** 2)

    hd = fits["head"] = register.fit(parts["head"], guide, scales=(0.75, 0.82, 0.9, 1.0, 1.1, 1.2),
                                     angles=range(-14, 15, 7), prior=head_prior)
    body = dict(scales=tuple(hd.scale * k for k in (0.84, 0.9, 0.96, 1.02, 1.08)), angles=range(-12, 13, 4))
    hw, hh = parts["head"].shape[1] * hd.scale, parts["head"].shape[0] * hd.scale
    below = (0, hd.y, gw, gh)                        # the torso and pelvis are below the head's centre
    chin = hd.y + hh / 2
    TH, TW = parts["torso"].shape[:2]
    PH, PW = parts["pelvis"].shape[:2]

    def torso_prior(cx, cy, s):
        # the collar sits under the chin (the chin overlaps ~13% of the torso), at about the head's scale
        th, tw = TH * s, TW * s
        return LAMBDA * (((cx - hd.x) / (0.22 * tw)) ** 2 + ((cy - (chin + 0.37 * th)) / (0.09 * th)) ** 2 +
                         (np.log(s / (0.94 * hd.scale)) / 0.07) ** 2)

    fits["torso"] = register.fit(parts["torso"], guide, region=below, prior=torso_prior, **body)
    t = fits["torso"]
    hem = t.y + TH * t.scale / 2

    def pelvis_prior(cx, cy, s):
        # the waistband tucks ~12% of its height under the shirt's hem, centred under the torso
        ph, pw = PH * s, PW * s
        return LAMBDA * (((cx - t.x) / (0.2 * pw)) ** 2 + ((cy - (hem + 0.38 * ph)) / (0.1 * ph)) ** 2 +
                         (np.log(s / t.scale) / 0.08) ** 2)

    fits["pelvis"] = register.fit(parts["pelvis"], guide, region=below, prior=pelvis_prior, **body)
    p = fits["pelvis"]
    tw, th = parts["torso"].shape[1] * t.scale, parts["torso"].shape[0] * t.scale
    pw, ph = parts["pelvis"].shape[1] * p.scale, parts["pelvis"].shape[0] * p.scale

    face = dict(scales=(0.85, 0.92, 1.0, 1.08, 1.15), angles=range(-10, 11, 5))
    if "eyes" in parts:          # upper part of the head
        fits["eyes"] = register.fit(parts["eyes"], guide, region=(hd.x - hw / 2, hd.y - hh / 2, hd.x + hw / 2,
                                                                  hd.y + 0.15 * hh), **face)
    if "mouth" in parts:         # lower part of the head
        fits["mouth"] = register.fit(parts["mouth"], guide, region=(hd.x - hw / 2, hd.y - 0.05 * hh,
                                                                    hd.x + hw / 2, hd.y + hh / 2), **face)
    if "neck" in parts:
        ny = (hd.y + hh / 2 + t.y - th / 2) / 2
        fits["neck"] = register.fit(parts["neck"], guide, region=_box(hd.x, ny, hw * 0.6, hh * 0.5),
                                    scales=(0.8, 0.9, 1.0, 1.1, 1.2), angles=(0,))

    ends = dict(scales=tuple(hd.scale * k for k in (0.65, 0.75, 0.85, 0.95, 1.05, 1.15)), angles=range(-30, 31, 6))
    for side in "RL":
        sgn = -1 if side == "R" else 1           # front / three-quarter: the right side is on the viewer's left
        if f"upper_arm_{side}" in parts:
            x = t.x if turned(view) else t.x + sgn * tw * 0.45
            w = tw * (1.0 if turned(view) else 0.55)
            fits[f"upper_arm_{side}"] = register.fit(parts[f"upper_arm_{side}"], guide,
                                                     region=_box(x, t.y - th * 0.2, w, th * 0.6), **ends)
        if f"hand_{side}" in parts:
            x = t.x if turned(view) else t.x + sgn * tw * 0.6
            w = tw * (1.2 if turned(view) else 0.7)
            fits[f"hand_{side}"] = register.fit(parts[f"hand_{side}"], guide,
                                                region=_box(x, p.y + ph * 0.25, w, th * 0.8), **ends)
        if f"foot_{side}" in parts and not turned(view):
            x = gw / 2 + sgn * gw * 0.22
            fits[f"foot_{side}"] = register.fit(parts[f"foot_{side}"], guide,
                                                region=_box(x, gh * 0.93, gw * 0.6, gh * 0.14), **ends)
    if turned(view) and "foot_R" in parts and "foot_L" in parts:
        # profile: both shoes are the same drawing, so find one, hide it, find the other; the forward one is near
        a = register.fit(parts["foot_R"], guide, region=_box(gw / 2, gh * 0.93, gw, gh * 0.14), **ends)
        fh, fw = parts["foot_R"].shape[:2]
        masked = guide.copy()
        x0, x1 = int(a.x - 0.35 * fw * a.scale), int(a.x + 0.35 * fw * a.scale)
        masked[:, max(0, x0):max(0, x1), 3] = 0
        b = register.fit(parts["foot_L"], masked, region=_box(gw / 2, gh * 0.93, gw, gh * 0.14), **ends)
        if b.err > 2.5 * a.err:                       # only one shoe shows: put the far one a little behind
            b = register.Fit(a.x - 0.25 * fw * a.scale, a.y, a.scale, a.angle, a.err)
        fits["foot_R"], fits["foot_L"] = (a, b) if a.x >= b.x else (b, a)
    return fits


def settle_pelvis(rest, imgs, piv):
    """The pelvis is often half hidden in the guide (shirt hem, hands over it), so its match can drift. Its
    waistband must tuck just under the torso's hem: snap it there when the match disagrees."""
    t, p = rest["torso"], rest["pelvis"]
    ph = imgs["pelvis"].shape[0] * p["scale"]
    top = p["y"] - 0.15 * ph                        # the pelvis pivot sits 15% down its height
    tucked = t["y"] - top                           # how far the waistband runs up under the hem
    off = abs(p["x"] - t["x"]) > 0.25 * imgs["pelvis"].shape[1] * p["scale"]
    if tucked < 0.04 * ph or tucked > 0.45 * ph or off:
        p["y"] = t["y"] + (0.15 - 0.12) * ph        # 12% of the pelvis tucked under the hem
        p["x"] = t["x"]
        p["angle"] = t["angle"]
    return rest
