"""Joint positions on part drawings.

A limb segment is drawn as a straight tube with a rounded cap at each end; it turns about the centre of the cap.
The proximal end (the one nearer the body) is the upper end as drawn on the sheet. Everything is in part pixels."""
import cv2
import numpy as np


def mask_of(img):
    return img[..., 3] >= 128


def axis(m):
    """centroid and unit main axis (pointing down the drawing) of a mask"""
    ys, xs = np.nonzero(m)
    c = np.array([xs.mean(), ys.mean()])
    pts = np.stack([xs, ys], 1) - c
    w, v = np.linalg.eigh(pts.T @ pts / len(pts))
    a = v[:, np.argmax(w)]
    if a[1] < 0:
        a = -a
    return c, a, pts


def limb_joints(img):
    """(proximal pivot, distal socket, proximal width, distal width) for a limb segment drawing"""
    m = mask_of(img)
    c, a, pts = axis(m)
    n = np.array([-a[1], a[0]])
    t = pts @ a                     # position along the axis
    s = pts @ n                     # position across it
    t0, t1 = t.min(), t.max()
    L = t1 - t0

    def width_at(tt):
        band = np.abs(t - tt) < max(1.5, 0.03 * L)
        return (s[band].max() - s[band].min()) if band.any() else 0.0, (s[band].max() + s[band].min()) / 2 \
            if band.any() else 0.0

    wp, sp = width_at(t0 + 0.12 * L)
    wd, sd = width_at(t1 - 0.12 * L)
    # the cap centre sits half a width in from the very end (a semicircular cap), never past the middle
    tp = t0 + min(0.5 * wp, 0.35 * L)
    td = t1 - min(0.5 * wd, 0.35 * L)
    prox = c + a * tp + n * sp
    dist = c + a * td + n * sd
    return prox, dist, wp, wd


def top_centre(img, frac=0.15):
    """centre of the top band of a drawing (a hand's wrist, a shoe's opening)"""
    m = mask_of(img)
    ys, xs = np.nonzero(m)
    y0 = ys.min()
    h = ys.max() - y0
    sel = ys <= y0 + frac * h
    return np.array([xs[sel].mean(), ys[sel].mean()])


def bottom_centre(img, frac=0.12):
    m = mask_of(img)
    ys, xs = np.nonzero(m)
    y1 = ys.max()
    h = y1 - ys.min()
    sel = ys >= y1 - frac * h
    return np.array([xs[sel].mean(), ys[sel].mean()])


def stretch(img, prox, dist, k):
    """Resample a limb drawing along its own axis (prox -> dist) by factor k, keeping its width and the proximal
    joint fixed: generated limbs are often drawn too long for the figure. Returns (image, prox, dist)."""
    a = (dist - prox) / max(1e-6, np.linalg.norm(dist - prox))
    A = np.eye(2) + (k - 1) * np.outer(a, a)          # stretch along a only
    h, w = img.shape[:2]
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], float)
    moved = (corners - prox) @ A.T + prox
    lo = np.floor(moved.min(0)) - 2
    hi = np.ceil(moved.max(0)) + 2
    M = np.hstack([A, (prox - A @ prox - lo)[:, None]])
    size = (int(hi[0] - lo[0]), int(hi[1] - lo[1]))
    out = cv2.warpAffine(img, M, size, flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0, 0))
    f = lambda p: A @ (p - prox) + prox - lo
    return out, f(prox), f(dist)


def shorten(img, prox, dist, k):
    """Make a limb drawing shorter, k < 1 times the distance between its joints (the proximal joint stays put), by
    taking the length out of its middle instead of squashing it: both rounded ends and everything drawn on them
    (cuffs, hems, the open end showing skin) keep their size and shape. The stretch is carried by the stretch of
    the drawing where it varies least along its axis (a plain run of sleeve, trouser or skin), eased in and out
    so there is no seam. Returns (image, prox, dist) like `stretch`."""
    d = dist - prox
    Ld = float(np.linalg.norm(d))
    a = d / max(1e-6, Ld)
    n = np.array([-a[1], a[0]])
    cut = (1.0 - k) * Ld                                   # length to take out
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    u = (xs - prox[0]) * a[0] + (ys - prox[1]) * a[1]       # along the limb, 0 at the proximal joint
    s = (xs - prox[0]) * n[0] + (ys - prox[1]) * n[1]       # across it
    solid = img[..., 3] >= 128
    # how much the drawing changes along the limb: the silhouette's width and its colour, per step of 1 px
    steps = np.arange(int(np.floor(u[solid].min())), int(np.ceil(u[solid].max())) + 1)
    prof = np.zeros((len(steps), 4), np.float32)
    ui = np.round(u).astype(int) - steps[0]
    for i in range(len(steps)):
        m = solid & (ui == i)
        if m.sum() > 2:
            prof[i, 0] = m.sum() * 0.5
            prof[i, 1:] = img[..., :3][m].mean(0)
    vary = np.abs(np.gradient(cv2.GaussianBlur(prof, (1, 0), 2.0, borderType=cv2.BORDER_REPLICATE), axis=0)).sum(1)
    # the window the cut is spread over: long enough that the cut never squashes it past a sixth of its length
    m_len = int(min(max(1.6 * cut, 0.3 * Ld), 0.85 * Ld))
    lo, hi = int(0.12 * Ld) - steps[0], int(0.95 * Ld) - steps[0] - m_len
    cost = np.convolve(vary, np.ones(m_len), "valid")
    start = lo + int(np.argmin(cost[max(0, lo):max(1, hi)])) if hi > lo else max(0, lo)
    w0 = float(steps[0] + start)                             # window start in u (source)

    def squeeze(uu):                                        # source u -> output u'
        x = np.clip((uu - w0) / m_len, 0.0, 1.0)
        return uu - cut * x * x * (3.0 - 2.0 * x) if cut < m_len * 2 / 3 else uu - cut * x      # eased cut
    grid = np.linspace(u.min() - 4, u.max() + 4, 4000)
    out_u = squeeze(grid)
    out_u = np.maximum.accumulate(out_u)                    # monotonic, so it can be inverted

    # output canvas: the corners as moved by the squeeze (the far end moves up the limb by `cut`)
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], float)
    cu = (corners - prox) @ a
    moved = corners + np.outer(np.interp(cu, grid, out_u) - cu, a)
    lo_c, hi_c = np.floor(moved.min(0)) - 2, np.ceil(moved.max(0)) + 2
    W, H = int(hi_c[0] - lo_c[0]), int(hi_c[1] - lo_c[1])
    gy, gx = np.mgrid[0:H, 0:W]
    qx, qy = gx + lo_c[0], gy + lo_c[1]
    uo = (qx - prox[0]) * a[0] + (qy - prox[1]) * a[1]
    so = (qx - prox[0]) * n[0] + (qy - prox[1]) * n[1]
    us = np.interp(uo, out_u, grid)                          # where in the source each output pixel comes from
    sx = prox[0] + a[0] * us + n[0] * so
    sy = prox[1] + a[1] * us + n[1] * so
    out = cv2.remap(img, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    f = lambda p: p + a * (float(np.interp(float((p - prox) @ a), grid, out_u)) - float((p - prox) @ a)) - lo_c
    return out, f(prox), f(dist)


def fill_cap(img, prox, dist, skin, frac=0.42):
    """The open top of a sleeve or trouser leg is often drawn showing skin inside. On a clothed segment, paint the
    skin-coloured pixels in the proximal cap with the segment's own clothing colour, so the joint shows cloth."""
    a = (dist - prox) / max(1e-6, np.linalg.norm(dist - prox))
    L = np.linalg.norm(dist - prox)
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    t = (xs - prox[0]) * a[0] + (ys - prox[1]) * a[1]
    rgb = img[..., :3].astype(np.float32)
    solid = img[..., 3] >= 128
    is_skin = (np.linalg.norm(rgb - skin, axis=2) < 52) & solid
    cap = (t < frac * L) & solid
    lum = _lum(rgb)
    near = (t >= frac * L * 0.85) & (t < 1.25 * frac * L) & solid & ~is_skin   # the cloth just below the cap
    if near.sum() < 50 or (is_skin & cap).sum() < 20:
        return img
    body = near & (lum > _outline_cut(lum[near]))      # the cloth's fill, not its outline (works for black cloth)
    if body.sum() < 30:
        return img
    # the most common colour there (a median would blend in a cuff stripe)
    q = (rgb[body] // 16).astype(np.int32)
    keys, counts = np.unique(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2], return_counts=True)
    top = keys[np.argmax(counts)]
    pick = (q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]) == top
    cloth = np.median(rgb[body][pick], 0)
    if np.linalg.norm(cloth - skin) < 60:            # a bare arm or leg: nothing to fill
        return img
    out = img.copy()
    out[..., :3][is_skin & cap] = cloth.astype(np.uint8)
    return out


def _lum(rgb):
    return rgb @ np.array([0.299, 0.587, 0.114], np.float32)


def _outline_cut(lum):
    """luminance below which a pixel is outline rather than fill, relative to the fill (black clothes have a dark
    fill but an even darker line)"""
    fill = np.percentile(lum, 70) if len(lum) else 128.0
    return min(70.0, 0.55 * fill)


def end_colour(img, joint, inward, r):
    """median fill colour (outline excluded) of a drawing near one end: within r of `joint`, on the body side"""
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.stack([xs - joint[0], ys - joint[1]], -1)
    t = d @ inward
    rgb = img[..., :3].astype(np.float32)
    sel = (img[..., 3] >= 200) & (np.hypot(d[..., 0], d[..., 1]) < r) & (t > -0.2 * r)
    if sel.sum() < 30:
        return None
    px = rgb[sel]
    lum = _lum(px)
    keep = lum > _outline_cut(lum)
    return np.median(px[keep], 0) if keep.sum() > 20 else None


def open_end(img, joint, outward, r):
    """Remove the outline across one end of a limb drawing (the cap beyond `joint`, pointing along `outward`) by
    painting it in the end's fill colour, so that end blends into the segment drawn beneath it. Only the line that
    runs across the limb goes (its outward direction points along the limb); the side outlines stay intact."""
    from scipy import ndimage
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.stack([xs - joint[0], ys - joint[1]], -1)
    t = d @ outward
    rgb = img[..., :3].astype(np.float32)
    a = img[..., 3]
    m = a >= 128
    lum = _lum(rgb)
    # signed distance to the silhouette (+ inside) and its outward normal
    sd = ndimage.distance_transform_edt(m) - ndimage.distance_transform_edt(~m)
    sd = cv2.GaussianBlur(sd.astype(np.float32), (0, 0), 1.5)
    gy, gx = np.gradient(sd)
    norm = np.hypot(gx, gy) + 1e-6
    along = (-(gx * outward[0] + gy * outward[1]) / norm) > 0.5
    near = (np.hypot(d[..., 0], d[..., 1]) < 2.2 * r) & (t > 0.1 * r) & (a > 0)
    deep = near & m & (sd > 10)
    if deep.sum() < 20:
        return img
    deep_lum = lum[deep]
    fill_px = rgb[deep][deep_lum > _outline_cut(deep_lum)]
    if len(fill_px) < 10:
        return img
    colour = np.median(fill_px, 0)
    target = near & along & (sd > -3) & (sd < 11) & (lum < 0.93 * float(_lum(colour[None])[0]))
    out = img.copy()
    out[..., :3][target] = colour.astype(np.uint8)
    return out


def fill_end(img, joint, outward, r, cloth):
    """Paint over whatever else a sleeve or trouser end shows inside its opening (a white lining, a shirt cuff)
    with the cloth's own colour (measured at the joint), for joints where the same cloth carries on into the next
    segment."""
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.stack([xs - joint[0], ys - joint[1]], -1)
    t = d @ outward
    dist = np.hypot(d[..., 0], d[..., 1])
    rgb = img[..., :3].astype(np.float32)
    solid = img[..., 3] >= 128
    lum = _lum(rgb)
    end = solid & (t > -0.15 * r) & (dist < 1.8 * r)
    if end.sum() < 20:
        return img
    other = end & (lum > _outline_cut(lum[end])) & (np.linalg.norm(rgb - cloth, axis=2) > 60)
    out = img.copy()
    out[..., :3][other] = cloth.astype(np.uint8)
    return out


def trim_cuff(img, skin):
    """Some hand drawings come with their own shirt or jacket cuff at the wrist, which doubles up under the
    sleeve's cuff. Cut a hand back to where the skin starts (keeping a short overlap). Returns (image, top y)."""
    rgb = img[..., :3].astype(np.float32)
    solid = img[..., 3] >= 128
    is_skin = (np.linalg.norm(rgb - skin, axis=2) < 55) & solid
    rows = solid.sum(1)
    frac = is_skin.sum(1) / np.maximum(1, rows)
    ys = np.nonzero(rows > 0)[0]
    if not len(ys):
        return img, 0
    y0 = ys[0]
    top = frac[y0:y0 + max(3, int(0.15 * len(ys)))]
    if top.mean() > 0.5:                              # starts in skin: no cuff
        return img, y0
    first = next((y for y in ys if frac[y] > 0.6), y0)
    cut = max(y0, first - 3)
    out = img.copy()
    out[:cut, :, 3] = 0
    return out, cut


def ankle(img, view):
    """the ankle on a shoe drawing: the middle of the opening at the top (towards the heel in profile)"""
    m = mask_of(img)
    ys, xs = np.nonzero(m)
    y0, h = ys.min(), ys.max() - ys.min()
    sel = ys <= y0 + 0.25 * h
    return np.array([xs[sel].mean(), y0 + 0.2 * h])
