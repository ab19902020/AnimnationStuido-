"""Playing motion on approved whole-character poses, with continuous wrists.

The instruments are already held in the drawings. Only a small local remap
of the hand and forearm is needed; no detached replacement hands are used.
"""
import math

import cv2
import numpy as np

from studio.film.cast import hands as hands_of


def wrist(layer, at, radius, delta):
    """Translate a grip with a smooth falloff into its connected forearm."""
    cx, cy = at
    dx, dy = delta
    r = max(2.0, radius)
    h, w = layer.shape[:2]
    x0, x1 = max(0, int(cx - 3.2*r)), min(w, int(cx + 3.2*r + 1))
    y0, y1 = max(0, int(cy - 5.0*r)), min(h, int(cy + 3.0*r + abs(dy) + 1))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = ((xx-cx)/(2.8*r))**2 + ((yy-cy)/(3.5*r))**2
    weight = np.clip(1-d, 0, 1)
    weight = weight*weight*(3-2*weight)
    # Full translation inside the fingers; blend through wrist to elbow.
    grip = np.clip(1-((xx-cx)/(1.25*r))**2-((yy-cy)/(1.25*r))**2, 0, 1)
    weight = np.maximum(weight, np.minimum(1, grip*4))
    layer[y0:y1, x0:x1] = cv2.remap(
        layer, (xx-dx*weight).astype(np.float32), (yy-dy*weight).astype(np.float32), cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT)


def play_native(lay, instrument, actor_matrix, key, t, height, playing, stage_matrix, direction):
    from studio.film.stage import SONG, apply, drumsticks, hand_cover, stick
    hs = hands_of(key)
    scale = math.sqrt(abs(np.linalg.det(actor_matrix[:, :2])))
    grips = {side: apply(actor_matrix, *p[:2]) for side, p in hs.items()}
    radii = {side: p[2]*scale for side, p in hs.items()}
    if instrument == "drumming":
        spec = dict(direction.DRUMS, connected=True, fist=None,
                    grips=grips, drums={k: apply(stage_matrix, *p) for k, p in direction.DRUMS['drums'].items()})
        motion = drumsticks(None, t, np.float32([[1, 0, 0], [0, 1, 0]]), spec, height)
        for side, m in motion.items():
            p = grips[side]
            wrist(lay, p, radii[side], (m['hand'][0]-p[0], m['hand'][1]-p[1]))
        hands = lay.copy()
        for side, m in motion.items():
            stick(lay, m['butt'], m['tip'], max(2.0, .012*height))
            hand_cover(hands, lay, *m['hand'], radii[side]*1.18)
    else:
        song = SONG()
        beat = song.beat_index(t)+song.phase(t)
        if 'R' in grips:
            wrist(lay, grips['R'], radii['R'], (0, .16*radii['R']*math.sin(4*math.pi*beat)*playing))
        if 'L' in grips:
            d = .11*radii['L']*math.sin(math.pi*beat/2)*playing
            wrist(lay, grips['L'], radii['L'], (d, -.4*d))
    return lay
