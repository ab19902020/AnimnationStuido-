"""A talking puppet for the animatic: body, head and mouth as separate sprites built from a character's rig.

    p = Puppet("pep-guardiola", "casual")        # front view; builds the rig first if it is not built
    p.body, p.head[gaze][eyes], p.mouth["D"]     # Sprites, in the puppet's own space
    p.draw(frame, X, Y, k, state)                # onto a BGR frame; (X, Y) is where its feet are

A Sprite is a BGRA image plus the offset of its top-left corner from the puppet's anchor (the floor between the
feet), in "master" pixels (the rig's guide pixels times MASTER). The head and the mouth turn together about the
neck, so a nod or a tilt moves the mouth with the face. Blinks paint skin over the eyeballs and draw a lid line, so
brows stay put; gaze moves the eyes across the face a few pixels. The mouth shapes come from studio.episode.mouths.

Everything is BGR/BGRA, like OpenCV."""
from dataclasses import dataclass

import json

import cv2
import numpy as np
import yaml
from scipy import ndimage

from studio.episode.mouths import MouthSet
from studio.ingest import chart, kit
from studio.paths import CHARACTERS, build_dir
from studio.rig import build as rigbuild
from studio.rig import skeleton

MASTER = 1.4                                  # the default: sprites at 1.4x the kit's guide scale (closer shots)
HEAD_PARTS = ("head", "eyes", "mouth")
GAZE = {-1: -0.05, 0: 0.0, 1: 0.05}           # eye shift across the face, as a fraction of the head's width
OUTLINE = (16, 14, 22)


@dataclass
class Sprite:
    img: np.ndarray                           # BGRA uint8, premultiplied
    ox: float                                 # top-left corner relative to the anchor, master pixels
    oy: float


def corners(w, h):
    return np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float).T


def premultiply(img):
    """straight-alpha BGRA uint8 -> premultiplied float32 (warping straight-alpha images darkens their edges)"""
    f = img.astype(np.float32)
    f[..., :3] *= f[..., 3:4] / 255
    return f


def render(items, S, anchor):
    """composite [(image, world 3x3, z)] at scale S into a Sprite whose offsets are relative to `anchor` (guide px).
    The sprite is premultiplied."""
    pts = []
    for img, M, _ in items:
        pts.append((S * (M @ corners(img.shape[1], img.shape[0]))[:2]).T)
    pts = np.vstack(pts) - S * np.asarray(anchor)
    lo = np.floor(pts.min(0)) - 1
    hi = np.ceil(pts.max(0)) + 1
    W, H = int(hi[0] - lo[0]), int(hi[1] - lo[1])
    canvas = np.zeros((H, W, 4), np.float32)
    for img, M, _ in sorted(items, key=lambda t: t[2]):
        A = S * M[:2].copy()
        A[:, 2] -= S * np.asarray(anchor) + lo
        w = cv2.warpAffine(premultiply(img), A, (W, H), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0, 0))
        a = np.clip(w[..., 3:4], 0, 255) / 255
        canvas[..., :3] = w[..., :3] + canvas[..., :3] * (1 - a)
        canvas[..., 3:4] = w[..., 3:4] + canvas[..., 3:4] * (1 - a)
    return Sprite(np.clip(canvas, 0, 255).astype(np.uint8), float(lo[0]), float(lo[1]))


def skin_of(img):
    """the most common mid-tone colour of a part (BGR): the skin"""
    a = img[..., 3] >= 200
    px = img[..., :3][a].astype(np.int32)
    lum = px @ np.array([0.114, 0.587, 0.299])
    px = px[(lum > 110) & (lum < 235)]
    keys, counts = np.unique(px // 12, axis=0, return_counts=True)
    return tuple(int(min(v, 255)) for v in keys[np.argmax(counts)] * 12 + 6)


def lidded(eyes, skin, amount):
    """the eyes tile with each eyeball (and its outline ring) covered by skin from the top down, and a lid line
    along the edge of the cover: amount 1 shuts the eye, 0.5 is half-lidded"""
    out = eyes.copy()
    white = (eyes[..., :3].min(2) > 200) & (eyes[..., 3] >= 200)
    ball = ndimage.binary_fill_holes(white)
    lab, n = ndimage.label(ball)
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < 30:
            continue
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        ring = 5                                                      # the eyeball's dark outline
        edge = y0 + amount * (y1 - y0 + 1)
        region = ndimage.binary_dilation(m, iterations=ring) & (np.arange(eyes.shape[0])[:, None] <= edge + (ring if amount >= 1 else 0))
        region &= eyes[..., 3] > 0
        out[..., :3][region] = skin
        ly = int(round(edge + (ring - 2 if amount >= 1 else -1)))
        sag = 0.12 * (x1 - x0)
        pts = np.array([[x0 - ring, ly - sag], [(x0 + x1) / 2, ly + sag], [x1 + ring, ly - sag]])
        xs_ = np.linspace(pts[0, 0], pts[2, 0], 20)
        ys_ = np.interp(xs_, pts[:, 0], pts[:, 1]) if False else ly - sag + 2 * sag * (1 - ((xs_ - (x0 + x1) / 2) / ((x1 - x0) / 2 + ring)) ** 2) * -1
        cv2.polylines(out, [np.round(np.stack([xs_, ys_], 1)).astype(np.int32)], False, (*OUTLINE, 255), 3, cv2.LINE_AA)
    return out


class Puppet:
    def __init__(self, cid, outfit, view="front", master=MASTER):
        self.cid, self.outfit, self.view, self.master = cid, outfit, view, master
        d = build_dir("rig", cid, outfit, view)
        if not (d / "rig.json").exists():
            rigbuild.build_view(cid, outfit, view, d)
        self.rig = json.loads((d / "rig.json").read_text())
        P = self.rig["parts"]
        self.P = P
        self.imgs = {n: cv2.imread(str(d / p["file"]), cv2.IMREAD_UNCHANGED) for n, p in P.items()}
        r = P["pelvis"]["rest"]
        self.M0 = skeleton.pose_matrices(P, root=(r["x"], r["y"], 0.0, 1.0))
        feet = [skeleton.apply(self.M0[f"foot_{s}"], self.P[f"foot_{s}"]["pivot"]) for s in "RL"]
        self.floor = float(self.rig["floor"])
        self.anchor = np.array([np.mean([f[0] for f in feet]), self.floor])
        self.guide_h = self.floor
        # the head pivot, in anchor-relative master pixels: the head and mouth turn about it
        hp = skeleton.apply(self.M0["head"], P["head"]["pivot"])
        self.pivot = (hp - self.anchor) * self.master
        self.skin = skin_of(self.imgs["head"])
        self.mouths = MouthSet(self.imgs["mouth"])
        self.body = self._body()
        self.head = {g: {e: self._head(g, e) for e in (0, 1, 2)} for g in (-1, 0, 1)}     # gaze, eyes (0 open, 1 half, 2 shut)
        self.mouth = {s: self._mouth(s) for s in "XABCDEFGH"}

    def _guide(self):
        """the kit sheet's assembled figure (BGRA), in the coordinates the rig was placed in"""
        png = CHARACTERS / self.cid / "kit" / self.outfit / f"{self.view}.png"
        spec = yaml.safe_load(png.with_suffix(".yaml").read_text())
        rgba, named, guide, _ = kit.resolve(png, spec)
        G = chart.cutout(rgba, [guide])
        return cv2.cvtColor(G, cv2.COLOR_RGBA2BGRA)

    def _body(self):
        """the whole figure minus the head: the guide drawing is clean and correct, where the rig's loose arms and
        legs show their joints. The head, eyes and mouth are drawn over the gap, so they can move."""
        G = self._guide()
        gh, gw = G.shape[:2]
        head = cv2.warpAffine(self.imgs["head"][..., 3], self.M0["head"][:2], (gw, gh), flags=cv2.INTER_LINEAR)
        hole = cv2.dilate((head > 30).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        G[hole] = 0
        return render([(G, np.eye(3), 0)], self.master, self.anchor)

    def _head(self, gaze, eyes):
        eyes_img = self.imgs["eyes"] if eyes == 0 else lidded(self.imgs["eyes"], self.skin, 0.5 if eyes == 1 else 1.0)
        shift = GAZE[gaze] * self.imgs["head"].shape[1]
        Me = self.M0["eyes"].copy()
        Me[0, 2] += shift * self.P["head"]["rest"]["scale"]
        items = [(self.imgs["head"], self.M0["head"], 0), (eyes_img, Me, 1)]
        return render(items, self.master, self.anchor)

    def _mouth(self, shape):
        spr, (px, py) = self.mouths.shape(shape)
        M = self.M0["mouth"] @ np.array([[1, 0, -px], [0, 1, -py], [0, 0, 1.0]])
        return render([(spr, M, 0)], self.master, self.anchor)

    # ------------------------------------------------------------------ drawing
    def draw(self, frame, X, Y, k, s):
        """draw onto frame (BGR uint8). (X, Y): the anchor on the frame; k: frame pixels per master pixel;
        s: dict(mouth='D', eyes=0, gaze=0, nod=degrees, roll=degrees about the feet, bob=(dx, dy) in master px,
        squash=(sx, sy))"""
        sx, sy = s.get("squash", (1.0, 1.0))
        bx, by = s.get("bob", (0.0, 0.0))
        T = lambda x, y: np.array([[1, 0, x], [0, 1, y], [0, 0, 1.0]])
        r = np.radians(s.get("roll", 0.0))
        Ro = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1.0]])
        Sc = np.array([[k * sx, 0, 0], [0, k * sy, 0], [0, 0, 1.0]])
        base = T(X, Y) @ Ro @ Sc
        blit(frame, self.body, base @ T(0, by) @ T(self.body.ox, self.body.oy))
        a = np.radians(s.get("nod", 0.0))
        c, sn = np.cos(a), np.sin(a)
        piv = self.pivot
        R = T(piv[0], piv[1]) @ np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1.0]]) @ T(-piv[0], -piv[1])
        head = base @ T(bx, by) @ R
        h = self.head[s.get("gaze", 0)][s.get("eyes", 0)]
        blit(frame, h, head @ T(h.ox, h.oy))
        m = self.mouth[s.get("mouth", "X")]
        blit(frame, m, head @ T(m.ox, m.oy))


def blit(frame, spr, M):
    """alpha-blend a sprite onto a BGR frame; M (3x3) maps sprite pixels to frame pixels. Only the sprite's own
    bounding box is touched."""
    h, w = spr.img.shape[:2]
    pts = (M @ corners(w, h))[:2].T
    x0, y0 = int(np.floor(pts[:, 0].min())), int(np.floor(pts[:, 1].min()))
    x1, y1 = int(np.ceil(pts[:, 0].max())), int(np.ceil(pts[:, 1].max()))
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x1, frame.shape[1]), min(y1, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return
    A = M[:2].copy()
    A[:, 2] -= (fx0, fy0)
    w_ = cv2.warpAffine(spr.img, A, (fx1 - fx0, fy1 - fy0), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = w_[..., 3:4].astype(np.float32) / 255
    roi = frame[fy0:fy1, fx0:fx1]
    roi[:] = np.clip(w_[..., :3] + roi * (1 - a), 0, 255).astype(np.uint8)
