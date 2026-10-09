"""The soundtrack: the boy's real recording and the stand-in voices with a little of each room round them, the room
tone of each place (the living room, the office, the car, the shop), the foley the picture asks for (the toy car on
the floor, the throws, steps, the front door, the big box, the card reader, the sofa), the two smashes and the one we
only hear, and a small plucked comedy cue that runs while things are fine and stops dead when they are not.
python3 -m studio.film broken-tele sound -> build/episode_audio.wav"""
import json

import numpy as np

from studio.film import audio as A
from studio.film import ep
from studio.film.shots import Marks
from film.timeline import TL

L = json.loads(ep.path("lines.json").read_text())
T = Marks(TL, L)
m, ls, le = T.m, T.ls, T.le
SR = A.SR
RNG = np.random.default_rng(31)


def noise(sec):
    return RNG.standard_normal(int(sec * SR)).astype(np.float32)


def glass(size=1.0, seed=0):
    """a screen going: the crack (a sharp noise burst), the panel's thump, and glass tinkling down after"""
    rng = np.random.default_rng(seed)
    n = int((1.6 + 0.8 * size) * SR)
    t = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    burst = np.r_[0, np.diff(rng.standard_normal(n))].astype(np.float32) * np.exp(-t * (16 / size))
    y += A.hp(burst, 1800, 2).astype(np.float32) * 0.9
    for _ in range(int(40 * size)):                      # the pieces: short damped high partials, scattered
        t0 = rng.uniform(0.01, 0.25) + rng.exponential(0.25 * size)
        d = rng.uniform(0.05, 0.25)
        k0 = int(t0 * SR)
        tt = np.arange(int(d * SR)) / SR
        f = rng.uniform(2200, 8200)
        p = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.51 * tt)) * np.exp(-tt * rng.uniform(25, 60))
        e = min(len(p), n - k0)
        if e > 0:
            y[k0:k0 + e] += p[:e].astype(np.float32) * rng.uniform(0.05, 0.22)
    thump = A.varispeed(A.clip("impacts/tom-hit"), -3 - 3 * size)
    if thump.ndim == 2:
        thump = thump.mean(1)
    thump = A.at_level(thump[:n], -14) * 0.6
    y[:len(thump)] += thump
    return A.room(y, 0.8, 0.22)


def buzz(sec=0.9):
    """a phone vibrating on a desk: a 150 Hz motor in two pulses"""
    t = np.arange(int(sec * SR)) / SR
    y = np.sign(np.sin(2 * np.pi * 150 * t)) * 0.5 + np.sin(2 * np.pi * 300 * t) * 0.3
    gate = ((t % 0.45) < 0.32).astype(np.float32)
    return A.lp(y * gate, 1400, 2).astype(np.float32)


def rumble(sec):
    """the car on the road: low engine and tyre noise"""
    y = A.lp(noise(sec), 160, 2) * 3 + A.bp(noise(sec), 300, 900, 2) * 0.25
    t = np.arange(len(y)) / SR
    return (y * (1 + 0.15 * np.sin(2 * np.pi * 0.4 * t))).astype(np.float32)


def ambience(bus):
    hv = "ambience/room-tone-hvac"
    # the living room: quiet room tone, the street faint through the window
    for a, b in ((0.0, m("cut_office")), (m("cut_mumph1"), m("cut_dad2")), (m("cut_mumph2"), m("cut_dad3")),
                 (m("cut_install"), m("cut_black"))):
        A.bed(bus, hv, a, b, -56, lowpass=3200)
        A.bed(bus, "ambience/street-distant", a, b, -60, lowpass=2500)
    # Dad's office: air-conditioning and the city
    for a, b in ((m("cut_office"), m("cut_mumph1")), (m("cut_dad2"), m("cut_mumph2")), (m("cut_dad3"), m("cut_car"))):
        A.bed(bus, hv, a, b, -50, lowpass=4500)
        A.bed(bus, "ambience/city-through-window", a, b, -54)
    # the car, the shop, the hall
    bus.add(A.at_level(rumble(m("cut_shop") - m("cut_car")), -40), m("cut_car"))
    A.bed(bus, "ambience/street-distant", m("cut_car"), m("cut_shop"), -48, lowpass=1800)
    A.bed(bus, hv, m("cut_shop"), m("cut_hall"), -48)
    A.bed(bus, "crowd/crowd-large", m("cut_shop"), m("cut_hall"), -60, lowpass=1500)
    A.bed(bus, hv, m("cut_hall"), m("cut_install"), -54)


def foley(bus):
    # the toy car rolled across the floor: plastic wheels on wood
    y = A.bp(noise(1.2), 200, 1400, 2) * np.exp(-np.arange(int(1.2 * SR)) / SR * 1.8)
    bus.add(A.at_level(y.astype(np.float32), -40), m("cut_vroom") + 0.05, pan=0.2)
    A.ev(bus, "foley/pen-click-c", m("cut_vroom") + 1.1, -42, semis=-8, lowpass=3000)
    # Mum's phone on the arm of her chair: she goes back to it
    A.ev(bus, "cloth/cloth-b", m("cut_narrow") + 1.0, -46, pan=-0.3)
    # the throw: his T-shirt, then the screen
    A.ev(bus, "cloth/cloth-e", m("throw1") - 0.25, -40, pan=-0.4)
    bus.add(A.at_level(glass(1.0, 1), -16), m("smash1"))
    A.ev(bus, "foley/pen-click-a", m("smash1") + 0.5, -34, semis=-9, lowpass=3500, pan=0.2)       # the car lands
    A.ev(bus, "foley/pen-click-b", m("smash1") + 0.62, -38, semis=-10, lowpass=3000, pan=0.2)
    A.ev(bus, "foley/pen-click-c", m("cut_crack1") + 0.62, -36, semis=7, highpass=2500, pan=0.25)  # the one shard
    # the call: the phone buzzes on the desk; Dad picks up
    bus.add(A.at_level(buzz(0.9), -36), m("cut_office") + 0.05, pan=0.1)
    A.ev(bus, "cloth/cloth-d", m("answer") - 0.15, -46)
    # the shop: Dad's trudge; the reader: the card's tap and the beep
    A.steps(bus, m("cut_shop") + 0.05, ls("L012") + 0.1, -44, pace=0.24, pan=-0.4, pan_to=0.2)
    A.ev(bus, "foley/pen-click-a", m("beep") - 0.04, -38, semis=-5, lowpass=3500)
    bus.add(A.at_level(A.room(A.beep(2700, 0.17), 0.3, 0.12), -30), m("beep"))
    # home with the box: the front door, his steps, the cardboard
    A.ev(bus, "doors/door-shut", m("cut_hall") + 0.05, -36, pan=-0.2)
    A.steps(bus, m("cut_hall") + 0.25, m("cut_install") - 0.1, -42, pace=0.42, pan=-0.6, pan_to=0.6)
    A.ev(bus, "paper/paper-handle", m("cut_hall") + 0.9, -44)
    A.ev(bus, "paper/paper-handle", m("cut_install") + 0.1, -42, semis=-3)
    A.ev(bus, "foley/cup-down", m("cut_install") + 0.35, -40, semis=-6, lowpass=2500)
    # the ban: Mum's steps and the toys rattling in their box
    A.steps(bus, m("cut_ban"), le("L015") + 0.3, -44, pace=0.38, pan=-0.5, pan_to=0.5)
    for k in range(5):
        A.ev(bus, ("foley/pen-click-a", "foley/pen-click-b", "foley/pen-click-c")[k % 3], m("cut_ban") + 0.25 + k * 0.38,
             -44, semis=-4 + k, lowpass=4000)
    # the sneak: little careful steps
    A.steps(bus, m("cut_sneak") + 0.05, m("cut_sneak") + 1.25, -48, pace=0.17, pan=-0.6, pan_to=-0.3, lowpass=3000)
    A.ev(bus, "cloth/cloth-a", m("cut_wind2") + 0.2, -46, pan=-0.4)
    A.ev(bus, "cloth/cloth-e", m("throw2") - 0.25, -38, pan=-0.4)
    bus.add(A.at_level(glass(1.6, 2), -13), m("smash2"))
    bus.add(A.at_level(A.big_boom(0.4, tail=0.5), -24), m("smash2"))
    # Mum and Dad come running
    A.steps(bus, m("cut_run") - 0.6, m("cut_run") + 0.4, -36, pace=0.13, pan=-0.6, pan_to=-0.2)
    A.ev(bus, "cloth/cloth-c", m("cut_run") + 0.3, -42, pan=-0.3)
    # the sofa takes them
    A.ev(bus, "creaks/creak-long", m("cut_sofa") + 0.1, -42, semis=-3)
    A.ev(bus, "cloth/cloth-f", m("cut_sofa") + 0.25, -44)
    # the projector's fan
    t = np.arange(int((m("cut_black") - m("cut_proj")) * SR)) / SR
    fan = A.bp(noise(len(t) / SR), 500, 3000, 2) * 0.6 + np.sin(2 * np.pi * 110 * t) * 0.15
    bus.add(A.at_level(fan.astype(np.float32), -54), m("cut_proj"), pan=-0.3)
    # black: the third one, heard and not seen
    bus.add(A.at_level(glass(2.0, 3), -12), m("cut_black") + 0.12)
    bus.add(A.at_level(A.big_boom(0.6, tail=0.6), -22), m("cut_black") + 0.12)
    # the title boom
    bus.add(A.at_level(A.big_boom(1.0), -16), m("cut_title"))


# the comedy cue: a plucked bass and a little tune, 112 bpm, while everything is fine
BEAT = 60 / 112
TUNE = ["C5", "E5", "G5", "E5", "D5", "F5", "A5", "F5", "B4", "D5", "G5", "D5", "C5", "E5", "G5", "C6"]
BASS = ["C3", "F3", "G3", "C3"]


def cue(a, b, level, seed=0):
    """the cue from a to b (s), stopping dead at b"""
    n = int((b - a) * SR)
    y = np.zeros(n + SR, np.float32)
    k = 0
    tt = 0.0
    while tt < b - a:
        i = int(tt * SR)
        p = A.piano_note(A.note(TUNE[k % 16]), 0.5, 0.55)
        y[i:i + len(p)] += p[:len(y) - i]
        if k % 2 == 0:
            q = A.piano_note(A.note(BASS[(k // 8) % 4]), 0.7, 1.0)
            y[i:i + len(q)] += A.lp(q, 600, 2)[:len(y) - i].astype(np.float32)
        k += 1
        tt += BEAT / 2
    y = y[:n]
    y[-int(0.012 * SR):] *= np.linspace(1, 0, int(0.012 * SR))
    return A.at_level(A.room(y, 1.2, 0.2), level)


def music(bus):
    bus.add(cue(0.0, m("throw1") - 0.05, -30), 0.0)                        # until he lets go
    bus.add(cue(m("cut_car"), m("cut_ban"), -31), m("cut_car"))            # the expensive way home
    bus.add(cue(m("card_weeks"), m("card_minutes") + 1.4, -30), m("card_weeks"))
    # two minutes later: the bass only, creeping, until he winds up
    k, t = 0, m("cut_sneak")
    while t < m("cut_wind2") + 0.6:
        q = A.lp(A.piano_note(A.note(["C3", "D#3", "F3", "F#3"][k % 4]), 0.4, 1.0), 500, 2).astype(np.float32)
        bus.add(A.at_level(q, -30), t)
        k += 1
        t += BEAT / 2
    # the sparkle on the new telly: two bell notes
    for i, nm in enumerate(("E6", "B6")):
        bus.add(A.at_level(A.room(A.piano_note(A.note(nm), 0.8, 0.6), 1.0, 0.3), -34), m("cut_install") + 0.5 + 0.4 * i)
    # the title chord, to the end
    n = TL["total"] - m("cut_title")
    y = A.title_sting(n + 0.2)[:int(n * SR)]
    y *= A.fade(len(y), 0.0, 0.8)[:, None]
    bus.add(A.at_level(y, -27), m("cut_title"))


def main():
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    ambience(amb)
    foley(fx)
    music(mus)
    A.master(dlg, [amb, fx], [mus])
