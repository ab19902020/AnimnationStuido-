"""Set dressing and graphics: the show's name on the studio's big screen, a broadcaster's caption low in its middle, between the two men's heads (OVERCRAP in
white, DAILY in red on a dark navy plate with the kit's ink outline), drawn at the plate's 4x resolution so it stays
crisp in the wides and goes soft with the wall in the singles; and in the portrait film, the divider of the split
screens with the same badge on it (the screen itself is left plain there: a tall frame only ever takes in an edge
of it, which would cut the name in half)."""
import functools

import numpy as np
from PIL import Image, ImageDraw

from studio.episode.upscale import upscaled
from studio.film.engine import OH, OW, VERTICAL
from studio.film.graphics import BEBAS, font
from studio.paths import BACKGROUNDS
from film.direction import PLATES

K = 4                                   # plate px are drawn at 4x


def logo(img):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 703 * K, 352 * K, 967 * K, 408 * K          # low in the middle of the screen, between the two
    d.rounded_rectangle((x0, y0, x1, y1), radius=7 * K, fill=(14, 22, 52), outline=(10, 10, 14), width=3 * K)
    d.rectangle((x0 + 5 * K, y1 - 9 * K, x1 - 5 * K, y1 - 5 * K), fill=(214, 30, 36))      # the red rule
    f = font(BEBAS, 44 * K)
    d.text((x0 + 12 * K, y0 + 3 * K), "OVERCRAP", font=f, fill=(255, 255, 255))
    w = d.textlength("OVERCRAP ", font=f)
    d.text((x0 + 12 * K + w, y0 + 3 * K), "DAILY", font=f, fill=(232, 40, 44))
    return img


def plate_image(k):
    big = upscaled(BACKGROUNDS / f"{PLATES[k]}.png", 4.0)[..., ::-1]
    if VERTICAL:                # the tall frames never take in the middle of the screen: the badge is on the divider
        return np.ascontiguousarray(big).copy()
    return np.asarray(logo(Image.fromarray(np.ascontiguousarray(big)))).copy()


@functools.lru_cache(maxsize=1)
def _badge_layer():
    """the split screen's divider: an ink rule with a red core across the middle, the show's badge on it (RGBA)"""
    u = OW / 1080
    im = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = OH // 2
    d.rectangle((0, y - int(7 * u), OW, y + int(7 * u)), fill=(10, 10, 14, 255))
    d.rectangle((0, y - int(2 * u), OW, y + int(2 * u)), fill=(214, 30, 36, 255))
    f = font(BEBAS, 58 * u)
    w = d.textlength("OVERCRAP DAILY", font=f)
    x0, x1 = OW / 2 - w / 2 - 26 * u, OW / 2 + w / 2 + 26 * u
    d.rounded_rectangle((x0, y - 40 * u, x1, y + 40 * u), radius=10 * u, fill=(14, 22, 52, 255),
                        outline=(10, 10, 14, 255), width=int(5 * u))
    d.text((x0 + 26 * u, y - 33 * u), "OVERCRAP", font=f, fill=(255, 255, 255, 255))
    d.text((x0 + 26 * u + d.textlength("OVERCRAP ", font=f), y - 33 * u), "DAILY", font=f, fill=(232, 40, 44, 255))
    a = np.asarray(im).astype(np.float32) / 255
    return a[..., :3] * a[..., 3:4], a[..., 3:4]


def badge(img, s, t):
    rgb, a = _badge_layer()
    return img * (1 - a) + rgb
