"""The soundtrack, as the director asks: dialogue foremost, no music and no whooshes. The two actors' lines with a
little of the studio round them, the studio's room tone under everything, a little foley on what the picture does (the
slump into the chair, the wheeze's shoulders, the hand to the forehead, the lean in to point) and one synthesised
console chime for the achievement. Everything stops dead on the cut to black.
EP_RES=1080x1920 python3 -m studio.film overcrap-consistently-shit sound -> build/episode_audio.wav"""
import json

import numpy as np

from studio.film import audio as A
from studio.film import ep
from studio.film.shots import Marks
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt = T.m, T.ls, T.le, T.wt
END = m("black")


def ambience(bus):
    A.bed(bus, "ambience/room-tone-hvac", 0.0, END, -52, lowpass=3800)


def foley(bus):
    A.ev(bus, "creaks/creak-small", m("slump") + 0.05, -44, pan=-0.2, semis=-3)        # Mark sinks into his chair
    A.ev(bus, "cloth/cloth-b", m("slump") + 0.02, -46, pan=-0.2)
    A.ev(bus, "cloth/cloth-c", m("cut_laugh") + 0.05, -47, pan=-0.2)                    # the wheeze
    A.ev(bus, "cloth/cloth-e", m("cut_mark2") + 0.04, -45, pan=-0.2)                     # the point
    A.ev(bus, "foley/clap-single", m("cut_palm") + 0.06, -40, semis=-5, lowpass=2500)   # hand to the forehead
    A.ev(bus, "creaks/creak-small", m("cut_palm") + 0.2, -48, pan=0.2, semis=-2)
    A.ev(bus, "cloth/cloth-a", m("cut_nod") + 0.1, -48, pan=-0.2)


def chime(bus):
    """the console's achievement chime: two bright bell tones, a fifth apart, as the pop-up lands"""
    t0 = m("toast") + 0.25
    dur = END - t0
    x = A.piano_note(A.note("B5"), dur, 1.0)
    y = A.piano_note(A.note("F#6"), dur, 0.9)
    n = len(x)
    off = int(0.11 * A.SR)
    z = x.copy()
    z[off:] += y[:n - off]
    z *= A.fade(n, 0.0, 0.01)
    st = np.stack([z, z], 1).astype(np.float32)
    st = st + A.convolve_st(z, A.reverb_ir(1.0, 6000, 0.01, 5))[:n] * 0.25
    bus.add(A.at_level(st, -26), t0)


def main():
    dlg, amb, fx = A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    ambience(amb)
    foley(fx)
    chime(fx)
    A.master(dlg, [amb, fx], [])
