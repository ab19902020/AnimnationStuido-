"""Set dressing: the show's name on the studio's big screen, a broadcaster's caption low in its middle, between the two men's heads (OVERCRAP in
white, DAILY in red on a dark navy plate with the kit's ink outline), drawn at the plate's 4x resolution so it stays
crisp in the wides and goes soft with the wall in the singles."""
import numpy as np
from PIL import Image, ImageDraw

from studio.episode.upscale import upscaled
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
    return np.asarray(logo(Image.fromarray(np.ascontiguousarray(big)))).copy()
