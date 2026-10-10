"""The soundtrack: the two actors' lines with a little of the studio round them, Jamie's laugh over the open (from
his own take), the studio's room tone, chair creaks and jacket rustles on the big gestures, a sly low piano bed
ducked well under the dialogue (it stops dead on "Brent!" and creeps back in with the rant), a punchy hit on FRAUD
and its twin on BLUE NOSE, and a comic sting on the freeze. Room tone and music stop dead on the cut to black.
python3 -m studio.film overcrap-the-fraud-off sound -> build/episode_audio.wav"""
import json

import librosa
import numpy as np

from studio.film import audio as A
from studio.film import ep
from studio.film.shots import Marks
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le, wt = T.m, T.ls, T.le, T.wt
END = m("black")


def jamie_laugh(bus):
    """the laugh Jamie gave before his first line (0.11-0.82 s of his take), under the opening two-shot"""
    y, _ = librosa.load(str(ep.DIR / "voiceovers" / "01-jamie-carragher.mp3"), sr=A.SR, mono=True)
    y = A.hp(y[int(0.08 * A.SR):int(0.86 * A.SR)], 75, 2).astype(np.float32)
    n = min(len(y), int((ls("L001") - 0.02) * A.SR))
    y = y[:n] * A.fade(n, 0.005, 0.06)
    bus.add(np.clip(A.at_level(y, -24), -0.95, 0.95), 0.0)


def ambience(bus):
    A.bed(bus, "ambience/room-tone-hvac", 0.0, END, -54, lowpass=3800)


def foley(bus):
    # the big gestures: Jamie's point at Mark, his hand to his chest, Mark's laugh, the lean in, the rant's raised
    # finger, the point, the final points
    A.ev(bus, "cloth/cloth-c", wt("L001", "you're") - 0.02, -44, pan=-0.3)
    A.ev(bus, "cloth/cloth-a", wt("L002", "who") - 0.02, -47, pan=-0.25)
    A.ev(bus, "creaks/creak-small", m("cut_laugh") + 0.06, -47, pan=0.3, semis=-2)
    A.ev(bus, "cloth/cloth-a", m("cut_laugh") + 0.08, -45, pan=0.3)
    A.ev(bus, "cloth/cloth-e", ls("L005") + 0.15, -48, pan=-0.2)               # Jamie leans in
    A.ev(bus, "creaks/creak-small", ls("L005") + 0.2, -50, pan=-0.2, semis=-3)
    A.ev(bus, "cloth/cloth-f", wt("L006", "played") - 0.05, -46, pan=0.25)
    A.ev(bus, "cloth/cloth-b", wt("L006", "you'll") - 0.05, -45, pan=0.2)
    A.ev(bus, "cloth/cloth-d", m("cut_jamie4"), -44, pan=-0.2)
    A.ev(bus, "creaks/creak-short", m("cut_mark4"), -48, pan=0.25, semis=2, highpass=400)


def hits(bus):
    # FRAUD: one punchy hit; BLUE NOSE: its twin a tone up; the freeze: the comic sting, cut dead at black
    A.ev(bus, "impacts/tom-hit", ls("L007") + 0.02, -30, semis=-2)
    A.ev(bus, "impacts/tom-hit", ls("L008") + 0.02, -30, semis=0)
    st = sting(END - m("freeze") + 0.4)
    n = int((END - m("freeze")) * A.SR)
    st = st[:n] * A.fade(n, 0.0, 0.008)[:, None]
    bus.add(A.at_level(st, -22), m("freeze"))


def sting(dur):
    """a stabbed comic chord: piano and strings hit together, bright, short"""
    ch = ("D3", "F#3", "A3", "C4", "D4")
    x = sum(A.piano_note(A.note(c), dur, 1.0) for c in ch)
    x = x + A.strings([A.note(c) for c in ch], dur, 0.01, 0.2, 3200)[:len(x)] * 0.6
    y = np.stack([x, x], 1).astype(np.float32)
    return y + A.convolve_st(x, A.reverb_ir(1.2, 5000, 0.01, 4))[:len(x)] * 0.2


def bed(bus):
    """a sly, sneaking piano figure (staccato bass and a cheeky off-beat answer), low and ducked under the voices"""
    bpm = 132.0
    beat = 60 / bpm
    bass = ["D2", "D2", "F2", "D2", "G2", "D2", "F2", "E2"]
    top = ["A3", None, "C4", None, "A3", None, "C#4", None]
    n = int(END * A.SR)
    y = np.zeros(n, np.float32)
    k, t = 0, 0.0
    while t < END:
        for nm, vel, dt in ((bass[k % 8], 0.9, 0.0), (top[k % 8], 0.45, beat / 2)):
            if nm is None:
                continue
            s = int((t + dt) * A.SR)
            x = A.piano_note(A.note(nm), 0.22, vel)
            x = x * A.fade(len(x), 0.002, 0.08)
            e = min(n, s + len(x))
            if s < n:
                y[s:e] += x[:e - s]
        k += 1
        t += beat
    y = A.lp(y, 2600, 2).astype(np.float32)
    y = A.at_level(y, -33)
    # the bed stops dead on "Brent!" (the biggest silence of the piece) and creeps back in with the rant
    tt = np.arange(n) / A.SR
    g = np.clip(1 - (tt - (le("L005") - 0.02)) / 0.03, 0, 1) + np.clip((tt - wt("L006", "you")) / 0.6, 0, 1)
    y *= np.clip(g, 0, 1).astype(np.float32)
    y[-int(0.006 * A.SR):] *= np.linspace(1, 0, int(0.006 * A.SR))
    bus.add(np.stack([y, y], 1), 0.0)


def main():
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    jamie_laugh(dlg)
    ambience(amb)
    foley(fx)
    hits(fx)
    bed(mus)
    A.master(dlg, [amb, fx], [mus])
