"""The soundtrack: the boy's real recording and the stand-in voices with a little of each room round them; the room
tone of every place; foley on every action; the smashes; and a scored comedy cue, a small band of plucked strings,
tuba, glockenspiel, brushes, a trombone and a music box, that follows the story and stops dead when the telly goes.
python3 -m studio.film broken-tele sound -> build/episode_audio.wav

The instruments are synthesised (plucked strings by Karplus-Strong, bells and brass additive); the foley builds on
the real recordings in library/audio/sfx (steps, cloth, creaks, the door, impacts), layered and pitched for the
things we don't have a recording of (the toy car's wheels, the reader's keys, the cardboard). Everything hangs off
the timeline marks, like the picture."""
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


def noise(sec, seed=None):
    r = RNG if seed is None else np.random.default_rng(seed)
    return r.standard_normal(int(sec * SR)).astype(np.float32)


def env(n, a=0.005, d=None, r=0.02):
    """attack, exponential decay (d s, None: hold), release"""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    if d:
        e = e * np.exp(-t / d)
    e = e * np.clip((n / SR - t) / max(r, 1e-4), 0, 1)
    return e.astype(np.float32)


def f_of(nm):
    return A.note(nm) if isinstance(nm, str) else float(nm)


# ---------------------------------------------------------------- instruments
def pluck(nm, dur, bright=0.55, decay=0.35, seed=0):
    """a plucked string (Karplus-Strong): pizzicato and guitar-ish"""
    f = f_of(nm)
    n = int(dur * SR)
    N = max(2, int(round(SR / f)))
    rng = np.random.default_rng(seed + int(f))
    buf = rng.uniform(-1, 1, N).astype(np.float32)
    buf = buf * bright + np.roll(buf, 1) * (1 - bright)          # a softer pluck: less high end
    out = np.empty(n + N, np.float32)
    out[:N] = buf
    g = np.exp(-N / (decay * SR))                                 # loss per period
    k = N
    while k < n + N:
        prev = out[k - N:k]
        blk = 0.5 * (prev + np.concatenate([[prev[-1]], prev[:-1]])) * g
        e = min(N, n + N - k)
        out[k:k + e] = blk[:e]
        k += N
    y = out[:n] * env(n, 0.001, None, 0.03)
    return A.hp(y, 60, 2).astype(np.float32)


def tuba(nm, dur, vel=1.0):
    """a tuba / bassoon: a soft brassy saw, low-passed, with a breathy attack"""
    f = f_of(nm)
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5 * t) * np.clip(t / 0.3, 0, 1)
    ph = np.cumsum(f * vib) / SR
    y = sum(np.sin(2 * np.pi * h * ph) / h ** 1.3 for h in range(1, 9))
    y = A.lp(y, 900, 2).astype(np.float32) * env(n, 0.03, None, 0.06)
    return y * vel * 0.5


def glock(nm, dur=1.2, vel=1.0):
    """a glockenspiel / music box bar: inharmonic partials, a quick ring"""
    f = f_of(nm)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.6) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.18)
         + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / 0.07))
    return (y * env(n, 0.001, None, 0.05) * vel * 0.35).astype(np.float32)


def brass(notes, dur, vel=1.0, bright=2400):
    """a brass section stab or chord: detuned saws through a closing filter"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    for nm in notes:
        for det in (-0.006, 0.0, 0.007):
            ph = np.cumsum(np.full(n, f_of(nm) * (1 + det))) / SR
            y += (2 * (ph % 1) - 1).astype(np.float32) * 0.2
    # the filter opens on the attack and closes: a brassy "blat"
    a = A.lp(y, bright, 2).astype(np.float32)
    b = A.lp(y, 700, 2).astype(np.float32)
    k = np.exp(-t / 0.18).astype(np.float32)
    return (a * k + b * (1 - k)) * env(n, 0.015, None, 0.12) * vel


def trombone(seq, vel=1.0):
    """the sad trombone: [(note, seconds)], each note a wah (a filter opening and closing), the last one wobbling"""
    out = []
    for i, (nm, d) in enumerate(seq):
        n = int(d * SR)
        t = np.arange(n) / SR
        last = i == len(seq) - 1
        f = f_of(nm) * (1 + (0.025 * np.sin(2 * np.pi * 6 * t) * np.clip(t / 0.25, 0, 1) if last else 0 * t))
        f = f * (1 - (0.06 * np.clip((t - d + 0.35) / 0.35, 0, 1) if last else 0))
        ph = np.cumsum(f) / SR
        y = (2 * (ph % 1) - 1).astype(np.float32)
        wah = 400 + 1600 * np.sin(np.pi * np.clip(t / min(d, 0.45), 0, 1)) ** 2
        # a time-varying low-pass, in short blocks with the filter's state carried across
        from scipy import signal
        o = np.zeros(n, np.float32)
        B = 256
        zi = None
        for k in range(0, n, B):
            sos = signal.butter(2, float(wah[k]), btype="low", fs=SR, output="sos")
            if zi is None:
                zi = np.zeros((sos.shape[0], 2))
            o[k:k + B], zi = signal.sosfilt(sos, y[k:k + B], zi=zi)
        out.append(o * env(n, 0.03, None, 0.08))
    return np.concatenate(out) * vel * 0.6


def tremolo(notes, dur, rise=True, vel=1.0):
    """strings, bowed fast (tremolo): the suspense under a wind-up, swelling"""
    y = A.strings([f_of(x) for x in notes], dur, 0.05, 0.05, 2400)
    t = np.arange(len(y)) / SR
    y = y * (0.6 + 0.4 * np.sin(2 * np.pi * 13 * t)) * ((0.15 + 0.85 * (t / dur) ** 1.6) if rise else 1.0)
    return (y * vel).astype(np.float32)


def kick():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    f = 45 + 80 * np.exp(-t / 0.03)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12)).astype(np.float32)


def brush(seed=0):
    """a brushed snare: a soft swish"""
    y = A.bp(noise(0.16, seed), 1800, 7000, 2) * env(int(0.16 * SR), 0.004, 0.05, 0.02)
    return y.astype(np.float32) * 0.8


def snare(seed=0):
    y = A.bp(noise(0.18, seed), 900, 6000, 2) * env(int(0.18 * SR), 0.001, 0.06, 0.02)
    t = np.arange(len(y)) / SR
    return (y + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.04)).astype(np.float32)


def timp(nm="D2", dur=1.6):
    f = f_of(nm)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5) + 0.4 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / 0.3)
    y += A.lp(noise(dur), 400, 2) * np.exp(-t / 0.05) * 0.6
    return (y * env(n, 0.002, None, 0.1)).astype(np.float32)


def cymbal(dur=2.0):
    y = A.hp(noise(dur), 5000, 2) * env(int(dur * SR), 0.002, 0.6, 0.2)
    return y.astype(np.float32) * 0.5


def epiano(nm, dur):
    """a cheap electric piano (the shop's muzak)"""
    f = f_of(nm)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t + 0.8 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t / 0.3)) * np.exp(-t / 0.7)
    return (y * env(n, 0.002, None, 0.05) * 0.4).astype(np.float32)


# ---------------------------------------------------------------- a small sequencer
class Score:
    """notes at beats of a tempo from a start time, onto a mono buffer"""

    def __init__(self, t0, t1, bpm):
        self.t0, self.t1, self.b = t0, t1, 60.0 / bpm
        self.y = np.zeros(int((t1 - t0 + 4) * SR), np.float32)

    def put(self, beat, x, gain=1.0):
        i = int(round(beat * self.b * SR))
        if i >= len(self.y) or beat * self.b > self.t1 - self.t0:
            return
        e = min(len(x), len(self.y) - i)
        self.y[i:i + e] += x[:e] * gain

    def out(self, level, room=0.18, fade_out=0.012):
        y = self.y[:int((self.t1 - self.t0) * SR)]
        k = int(fade_out * SR)
        if k:
            y[-k:] *= np.linspace(1, 0, k)
        y = A.room(y, 1.1, room)
        return A.at_level(y, level)


# the family theme (C major): a bouncy tune over an oom-pah; one phrase is 16 beats
THEME = [(0, "E5", .5), (.5, "G5", .5), (1, "C6", 1), (2, "B5", .5), (2.5, "G5", .5), (3, "E5", 1),
         (4, "F5", .5), (4.5, "A5", .5), (5, "D6", 1), (6, "C6", .5), (6.5, "A5", .5), (7, "F5", 1),
         (8, "E5", .5), (8.5, "G5", .5), (9, "C6", .5), (9.5, "E6", .5), (10, "D6", .5), (10.5, "B5", .5), (11, "G5", 1),
         (12, "A5", .5), (12.5, "B5", .5), (13, "C6", .5), (13.5, "G5", .5), (14, "E5", .5), (14.5, "D5", .5),
         (15, "C5", 1)]
ROOTS = [("C3", "G2", ["E4", "G4", "C5"]), ("F2", "C3", ["F4", "A4", "C5"]), ("C3", "G2", ["E4", "G4", "C5"]),
         ("G2", "D3", ["D4", "G4", "B4"])]


def theme(sc, beats, mel=True, drums=True, glk=True, mel_gain=1.0):
    for b0 in range(0, beats, 16):
        if mel:
            for b, nm, d in THEME:
                sc.put(b0 + b, pluck(nm, 0.5 + d * 0.3, 0.6, 0.3, seed=b0), 0.55 * mel_gain)
        for bar in range(4):
            r1, r2, ch = ROOTS[bar]
            for k, root in ((0, r1), (2, r2)):
                sc.put(b0 + bar * 4 + k, tuba(root, 0.42), 0.9)
            for k in (1, 3):
                for nm in ch:
                    sc.put(b0 + bar * 4 + k, pluck(nm, 0.3, 0.5, 0.12, seed=k), 0.22)
            if drums:
                sc.put(b0 + bar * 4, kick(), 0.35)
                for k in (1, 3):
                    sc.put(b0 + bar * 4 + k, brush(bar * 4 + k), 0.18)
            if glk and bar in (0, 2):
                sc.put(b0 + bar * 4, glock(THEME[0][1] if bar == 0 else "G6", 1.0), 0.4)


def music(bus):
    # 1. five minutes of peace: the family theme, until the boy starts looking at the telly
    s = Score(0.0, m("cut_look"), 112)
    theme(s, 48)
    bus.add(s.out(-29), 0.0)
    # 2. the look: a sneaky low pluck and strings that swell, a twinkle on his best smile; dead at the smash
    s = Score(m("cut_look"), m("smash1"), 96)
    nb = int((m("smash1") - m("cut_look")) / s.b) + 2
    for b in range(nb):
        s.put(b, pluck(["A2", "E3", "A2", "F3"][b % 4], 0.35, 0.4, 0.15), 0.9)
    s.y[:len(tremolo(["A3", "C4", "E4"], m("smash1") - m("cut_look")))] += \
        tremolo(["A3", "C4", "E4"], m("smash1") - m("cut_look")) * 0.5
    for k, nm in enumerate(("C6", "E6", "G6", "C7")):
        i = int((m("cut_look") + 2.38 - s.t0 + 0.07 * k) * SR)
        g = glock(nm, 0.9)
        s.y[i:i + len(g)] += g * 0.5
    bus.add(s.out(-30, 0.15, 0.004), m("cut_look"))
    # 3. the expensive way home: a march for the car and the shop, until the price comes up
    s = Score(m("cut_car"), m("beep") + 0.02, 124)
    nb = int((m("beep") - m("cut_car")) / s.b)
    for b0 in range(0, nb, 16):
        for b, nm, d in THEME:
            s.put(b0 + b, pluck(A.note(nm) * 2 ** (5 / 12), 0.4, 0.6, 0.25), 0.5)   # up a fourth: F major
    for b in range(nb):
        s.put(b, tuba(["F2", "C3"][b % 2], 0.3), 0.8)
        s.put(b, snare(b) if b % 2 else kick(), 0.22 if b % 2 else 0.3)
    bus.add(s.out(-31, 0.12, 0.006), m("cut_car"))
    # £799.00... APPROVED: the sad trombone
    bus.add(A.at_level(A.room(trombone([("F3", 0.42), ("E3", 0.42), ("D#3", 0.42), ("D3", 1.4)]), 0.9, 0.2), -24),
            m("beep") + 0.3)
    # home with the box: the tuba plods with his steps
    k, t = 0, m("cut_hall") + 0.25
    while t < m("cut_install") - 0.1:
        bus.add(A.at_level(tuba(["C2", "G1"][k % 2], 0.35), -30), t)
        k += 1
        t += 0.42
    # the new telly: a fanfare as it lights up
    for k, nm in enumerate(("C5", "E5", "G5", "C6", "E6")):
        bus.add(A.at_level(glock(nm, 1.2), -31), m("cut_install") + 0.45 + 0.08 * k)
    bus.add(A.at_level(brass(["C4", "E4", "G4"], 0.9), -32), m("cut_install") + 0.85)
    # the ban: Mum marches the toys out to a minor plod; the sulk gets a sad bassoon
    s = Score(m("cut_ban"), m("card_weeks"), 100)
    for b, nm in enumerate(["A2", "G2", "F2", "E2", "A2", "G2", "F2", "E2"]):
        s.put(b, tuba(nm, 0.5), 0.9)
        s.put(b + 0.5, pluck(["E4", "D4", "C4", "B3"][b % 4], 0.3, 0.5, 0.12), 0.35)
    i = int((m("cut_sulk") + 0.3 - s.t0) * SR)
    g = tuba("E2", 1.4) * np.linspace(1, 0.6, int(1.4 * SR))
    s.y[i:i + len(g)] += g * 0.8
    bus.add(s.out(-31), m("cut_ban"))
    # TWO WEEKS LATER: ta-da, and the theme again, brighter
    bus.add(A.at_level(A.room(brass(["C4", "E4", "G4", "C5"], 1.1), 1.2, 0.3), -24), m("card_weeks"))
    bus.add(A.at_level(cymbal(1.8), -34), m("card_weeks"))
    s = Score(m("card_weeks") + 0.9, m("card_minutes"), 116)
    theme(s, 32, mel_gain=0.8)
    bus.add(s.out(-30), m("card_weeks") + 0.9)
    # TWO MINUTES LATER: a minor stab and the timpani, then the creep (tiptoe plucks), the swell, dead at the smash
    bus.add(A.at_level(A.room(brass(["A3", "C4", "E4"], 0.9), 1.2, 0.3), -24), m("card_minutes"))
    bus.add(A.at_level(timp("A1", 1.5), -26), m("card_minutes"))
    s = Score(m("cut_sneak"), m("smash2"), 92)
    nb = int((m("smash2") - m("cut_sneak")) / s.b * 2) + 2
    creep = ["E2", "F2", "E2", "D#2", "E2", "G2", "F#2", "F2"]
    for b in range(nb):
        s.put(b / 2, pluck(creep[b % 8], 0.18, 0.35, 0.06), 1.0 if b % 2 == 0 else 0.6)
    d = m("smash2") - m("cut_wind2")
    i = int((m("cut_wind2") - s.t0) * SR)
    tr = tremolo(["E3", "G3", "A#3"], d)
    s.y[i:i + len(tr)] += tr * 0.55
    bus.add(s.out(-29, 0.12, 0.004), m("cut_sneak"))
    # Mum and Dad run in: DUN... DUN... DUNNN
    for k, (dt, ch) in enumerate(((0.0, ["D3", "F3", "A3"]), (0.28, ["D3", "F3", "A3"]), (0.56, ["C#3", "E3", "G3"]))):
        y = A.room(brass(ch, 0.24 if k < 2 else 0.6), 0.8, 0.25)
        y[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))[:, None]
        bus.add(A.at_level(y, -24), m("cut_run") + dt)
        bus.add(A.at_level(timp("D2", 0.5 if k < 2 else 0.6), -26), m("cut_run") + dt)
    # the sofa: a slow sad piano under the solution
    s = Score(m("cut_sofa"), m("cut_proj"), 66)
    prog = [["A2", "E3", "A3", "C4"], ["F2", "C3", "F3", "A3"], ["C3", "G3", "C4", "E4"], ["G2", "D3", "G3", "B3"]]
    for bar in range(int((m("cut_proj") - m("cut_sofa")) / (4 * s.b)) + 1):
        for k, nm in enumerate(prog[bar % 4]):
            s.put(bar * 4 + k, A.piano_note(A.note(nm), 2.0, 0.7), 0.9)
    bus.add(s.out(-31, 0.25), m("cut_sofa"))
    # the projector: a music box, hopeful; then he looks at the ball, and the low strings come up to the black
    s = Score(m("cut_proj"), m("cut_boy3") + 0.8, 100)
    box = ["C6", "E6", "G6", "E6", "F6", "A6", "G6", "E6", "D6", "F6", "E6", "C6"]
    for b, nm in enumerate(box):
        s.put(b / 2, glock(nm, 1.0, 0.8), 0.7)
    bus.add(s.out(-30, 0.3, 0.3), m("cut_proj"))
    d = m("cut_black") - (m("cut_boy3") + 0.8)
    y = tremolo(["A1", "A2", "D#3"], d) + tuba("A1", d) * 0.6
    y[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    bus.add(A.at_level(y, -29), m("cut_boy3") + 0.8)
    # the title chord, to the end; and a little pluck after the last "TV's broken?"
    n = TL["total"] - m("cut_title")
    y = A.title_sting(n + 0.2)[:int(n * SR)]
    y *= A.fade(len(y), 0.0, 0.8)[:, None]
    bus.add(A.at_level(y, -28), m("cut_title"))
    for k, nm in enumerate(("G4", "C4")):
        bus.add(A.at_level(pluck(nm, 0.6, 0.5, 0.2), -30), le("L025") + 0.3 + 0.22 * k)


# ---------------------------------------------------------------- effects
def glass(size=1.0, seed=0):
    """a screen going: the hit, the crack, the panel shattering, the pieces tinkling down, and the set's
    electronics dying with a fizz"""
    rng = np.random.default_rng(seed)
    dur = 1.8 + 0.9 * size
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    # the hit: one sharp broadband click and the panel's thump
    y[:int(0.004 * SR)] += rng.uniform(-1, 1, int(0.004 * SR)).astype(np.float32) * 1.2
    th = A.varispeed(A.clip("impacts/tom-hit"), -2 - 3 * size)
    th = th.mean(1) if th.ndim == 2 else th
    th = A.at_level(th[:n], -14) * (0.5 + 0.3 * size)
    y[:len(th)] += th
    # the crack: a bright burst, falling fast
    y += A.bp(rng.standard_normal(n), 2500, 9000, 2).astype(np.float32) * np.exp(-t / (0.035 * size)) * 0.9
    # the shatter: grains of glass noise, each its own band, thinning out over ~0.5 s
    for _ in range(int(140 * size)):
        t0 = rng.exponential(0.12 * size)
        d = rng.uniform(0.008, 0.05)
        k0, k1 = int(t0 * SR), int((t0 + d) * SR)
        if k1 >= n:
            continue
        lo = rng.uniform(2000, 7000)
        g = A.bp(rng.standard_normal(k1 - k0 + 400), lo, min(lo * 1.6, 15000), 2)[200:200 + k1 - k0]
        y[k0:k1] += g.astype(np.float32) * np.exp(-np.arange(k1 - k0) / SR / (d / 3)) * rng.uniform(0.2, 0.7)
    # the pieces landing: small glassy rings, scattered over the next second or two
    for _ in range(int(45 * size)):
        t0 = rng.uniform(0.15, 0.4) + rng.exponential(0.35 * size)
        d = rng.uniform(0.05, 0.22)
        k0 = int(t0 * SR)
        tt = np.arange(int(d * SR)) / SR
        f = rng.uniform(2600, 9000)
        p = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 2.32 * tt)
             + 0.3 * np.sin(2 * np.pi * f * 3.71 * tt)) * np.exp(-tt * rng.uniform(25, 70))
        e = min(len(p), n - k0)
        if e > 0:
            y[k0:k0 + e] += p[:e].astype(np.float32) * rng.uniform(0.04, 0.18)
    # the set dying: a 100 Hz fizz that sputters out
    fz = int(0.5 * SR)
    tf = np.arange(fz) / SR
    buzz = np.sign(np.sin(2 * np.pi * 100 * tf)) * (rng.uniform(0, 1, fz) > 0.35) * np.exp(-tf / 0.15)
    y[int(0.05 * SR):int(0.05 * SR) + fz] += A.bp(buzz, 150, 3000, 2).astype(np.float32) * 0.15
    return A.room(y, 0.7, 0.25)


def wheels(sec):
    """plastic wheels on a wooden floor: a rattle that slows as the car rolls to a stop"""
    n = int(sec * SR)
    t = np.arange(n) / SR
    rate = 38 * np.clip(1 - t / sec, 0.15, 1)
    tick = (np.sin(2 * np.pi * np.cumsum(rate) / SR) > 0.95).astype(np.float32)
    y = A.bp(noise(sec) * (0.3 + tick), 500, 3500, 2) + A.lp(noise(sec), 180, 2) * 1.5
    return (y * env(n, 0.05, None, 0.2) * np.clip(1.2 - t / sec, 0, 1)).astype(np.float32)


def swish(sec=0.35):
    """something small flying past: band-passed air rising and falling"""
    n = int(sec * SR)
    t = np.arange(n) / SR
    y = A.bp(noise(sec), 700, 4000, 2) * np.sin(np.pi * t / sec) ** 2
    return y.astype(np.float32)


def buzz(sec=0.9):
    """a phone vibrating on a desk: two pulses of a 150 Hz motor rattling the wood"""
    t = np.arange(int(sec * SR)) / SR
    y = np.sign(np.sin(2 * np.pi * 150 * t)) * 0.5 + np.sin(2 * np.pi * 300 * t) * 0.3
    gate = ((t % 0.45) < 0.32).astype(np.float32)
    return A.lp(y * gate, 1400, 2).astype(np.float32)


def engine(sec):
    """inside the car: the engine's low hum and the road under the tyres"""
    n = int(sec * SR)
    t = np.arange(n) / SR
    rpm = 30 * (1 + 0.04 * np.sin(2 * np.pi * 0.21 * t))
    ph = np.cumsum(rpm) / SR
    hum = sum(np.sin(2 * np.pi * h * ph) / h for h in (1, 2, 3, 4))
    road = A.lp(noise(sec), 350, 2) * 2.5 + A.bp(noise(sec), 600, 2000, 2) * 0.2
    return (hum * 0.5 + road).astype(np.float32)


def indicator(sec):
    """the indicator: tick... tock"""
    y = np.zeros(int(sec * SR), np.float32)
    k = 0
    while k * 0.38 < sec - 0.05:
        c = A.hp(noise(0.012, k), 2000, 2) * (1.0 if k % 2 == 0 else 0.7)
        i = int(k * 0.38 * SR)
        y[i:i + len(c)] += c
        k += 1
    return y


def wood(seed, f=None):
    """a wooden block knocking: a resonant tap"""
    rng = np.random.default_rng(seed)
    f = f or rng.uniform(600, 1400)
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.025) + 0.5 * np.sin(2 * np.pi * f * 2.7 * t) * np.exp(-t / 0.012)
    return (y + rng.standard_normal(n) * np.exp(-t / 0.003) * 0.4).astype(np.float32)


def keypress(seed):
    return (A.bp(noise(0.03, seed), 1500, 5000, 2) * env(int(0.03 * SR), 0.001, 0.008, 0.005)).astype(np.float32)


def printer(sec=0.8):
    """a receipt printing: a fast buzzing rattle"""
    t = np.arange(int(sec * SR)) / SR
    y = A.bp(noise(sec), 800, 4000, 2) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 45 * t)))
    return (y * env(len(t), 0.02, None, 0.05)).astype(np.float32)


def jingle(sec=0.6, seed=4):
    """keys on a ring: small metal rings at random"""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(sec * SR), np.float32)
    for _ in range(14):
        i = int(rng.uniform(0, sec - 0.1) * SR)
        tt = np.arange(int(0.08 * SR)) / SR
        f = rng.uniform(3000, 7000)
        p = (np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(2 * np.pi * f * 1.73 * tt)) * np.exp(-tt * 60)
        y[i:i + len(p)] += p.astype(np.float32) * rng.uniform(0.1, 0.3)
    return y


def rip(sec=0.5):
    """packing tape coming off the box"""
    t = np.arange(int(sec * SR)) / SR
    crackle = (np.random.default_rng(9).uniform(0, 1, len(t)) > 0.92).astype(np.float32)
    y = A.bp(noise(sec) * (0.4 + crackle * 2), 1200, 6000, 2)
    return (y * env(len(t), 0.01, None, 0.08)).astype(np.float32)


def bloop():
    """the new telly switching on: a soft rising electronic chime"""
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    f = 440 * 2 ** (t / 0.55 * 1.0)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.01, 0.25, 0.1)
    return y.astype(np.float32)


def chime():
    """the shop's PA: ding-dong"""
    return np.concatenate([glock("E5", 0.5, 1.0), glock("C5", 1.0, 1.0)])


def puff(sec=0.5):
    """a big cushion taking someone's weight"""
    t = np.arange(int(sec * SR)) / SR
    return (A.lp(noise(sec), 500, 2) * np.exp(-t / 0.12) * np.clip(t / 0.02, 0, 1)).astype(np.float32)


def muzak(a, b):
    """the shop's in-store music: the family theme on a cheap electric piano through a small ceiling speaker"""
    s = Score(a, b, 100)
    for b0 in range(0, int((b - a) / s.b) + 16, 16):
        for bb, nm, d in THEME:
            s.put(b0 + bb, epiano(A.note(nm) / 2, 0.4 + d * 0.3), 0.6)
        for bar in range(4):
            for nm in ROOTS[bar][2]:
                s.put(b0 + bar * 4, epiano(A.note(nm) / 2, 1.8), 0.15)
    y = s.y[:int((b - a) * SR)]
    y = A.bp(y, 450, 3200, 2).astype(np.float32)
    return A.room(y, 1.4, 0.45)


# ---------------------------------------------------------------- the layers
def ambience(bus):
    hv = "ambience/room-tone-hvac"
    living = ((0.0, m("cut_office")), (m("cut_mumph1"), m("cut_dad2")), (m("cut_mumph2"), m("cut_dad3")),
              (m("cut_install"), m("cut_black")))
    for a, b in living:                                   # the living room: still, the street faint outside
        A.bed(bus, hv, a, b, -57, lowpass=3000)
        A.bed(bus, "ambience/street-distant", a, b, -58, lowpass=2200)
    for a, b in ((m("cut_office"), m("cut_mumph1")), (m("cut_dad2"), m("cut_mumph2")), (m("cut_dad3"), m("cut_car"))):
        A.bed(bus, hv, a, b, -50, lowpass=4500)           # Dad's office: air-conditioning and the city
        A.bed(bus, "ambience/city-through-window", a, b, -53)
    bus.add(A.at_level(engine(m("cut_shop") - m("cut_car")), -36), m("cut_car"))
    A.bed(bus, "ambience/street-distant", m("cut_car"), m("cut_shop"), -47, lowpass=1600)
    bus.add(A.at_level(indicator(1.6), -40), m("cut_shop") - 1.7, pan=0.4)     # turning into the car park
    A.bed(bus, hv, m("cut_shop"), m("cut_hall"), -47)     # the shop: aircon, shoppers, the muzak in the ceiling
    A.bed(bus, "crowd/crowd-large", m("cut_shop"), m("cut_reader"), -57, lowpass=1400)
    bus.add(A.at_level(muzak(m("cut_shop"), m("cut_hall")), -42), m("cut_shop"))
    A.bed(bus, hv, m("cut_hall"), m("cut_install"), -55)
    A.bed(bus, "ambience/street-distant", m("cut_hall"), m("cut_hall") + 0.7, -46, fout=0.3)    # the door open


def foley(bus):
    # the toy car rolling across the floor to the telly unit, and stopping against it
    bus.add(A.at_level(wheels(1.3), -38), m("cut_vroom") + 0.02, pan=0.15)
    A.ev(bus, "foley/pen-click-c", m("cut_vroom") + 1.3, -40, semis=-8, lowpass=3000, pan=0.3)
    # Mum shifting in her chair and picking up her phone; the boy getting up off the rug
    A.ev(bus, "creaks/creak-small", 0.6, -48, pan=-0.5, semis=-2)
    A.ev(bus, "cloth/cloth-b", m("cut_narrow") + 1.0, -45, pan=-0.3)
    A.ev(bus, "cloth/cloth-d", m("cut_wind1") + 0.1, -44, pan=-0.4)
    # the throw: his T-shirt, the car through the air, the screen
    A.ev(bus, "cloth/cloth-e", m("throw1") - 0.2, -40, pan=-0.4)
    bus.add(A.at_level(swish(0.36), -40), m("throw1"), pan=0.2)
    bus.add(A.at_level(glass(1.0, 1), -15), m("smash1"))
    A.ev(bus, "foley/pen-click-a", m("smash1") + 0.52, -32, semis=-10, lowpass=3200, pan=0.25)     # the car lands
    A.ev(bus, "foley/pen-click-b", m("smash1") + 0.66, -36, semis=-11, lowpass=2800, pan=0.25)     # and bounces
    A.ev(bus, "foley/pen-click-c", m("smash1") + 0.74, -40, semis=-12, lowpass=2400, pan=0.25)
    A.ev(bus, "foley/pen-click-c", m("cut_crack1") + 0.62, -34, semis=8, highpass=2500, pan=0.2)    # the one shard
    A.ev(bus, "foley/pen-click-a", m("cut_crack1") + 0.75, -40, semis=10, highpass=3000, pan=0.2)
    # the call: the phone buzzing on the desk; Dad picks up
    bus.add(A.at_level(buzz(0.9), -35), m("cut_office") + 0.05, pan=0.15)
    A.ev(bus, "cloth/cloth-d", m("answer") - 0.15, -45)
    # the shop: the PA's ding-dong, Dad's trudge
    bus.add(A.at_level(A.room(chime(), 1.5, 0.4), -40), m("cut_shop") + 0.2, pan=-0.2)
    A.steps(bus, m("cut_shop") + 0.05, ls("L012") + 0.1, -43, pace=0.24, pan=-0.4, pan_to=0.2)
    # the reader: the assistant keys it in, the card taps, the beep, the receipt
    for k in range(4):
        bus.add(A.at_level(keypress(k), -42), m("cut_reader") + 0.1 + 0.13 * k)
    A.ev(bus, "foley/pen-click-a", m("beep") - 0.04, -36, semis=-5, lowpass=3500)
    bus.add(A.at_level(A.room(A.beep(2700, 0.12), 0.3, 0.12), -30), m("beep"))
    bus.add(A.at_level(A.room(A.beep(3200, 0.18), 0.3, 0.12), -30), m("beep") + 0.17)
    bus.add(A.at_level(printer(0.8), -42), m("beep") + 0.5)
    # home with the box: keys, the front door, his steps, the cardboard
    bus.add(A.at_level(jingle(0.5), -42), m("cut_hall") - 0.25, pan=-0.3)
    A.ev(bus, "creaks/creak-short", m("cut_hall") - 0.05, -44, pan=-0.3, semis=2)
    A.ev(bus, "doors/door-shut", m("cut_hall") + 0.55, -36, pan=-0.2)
    A.steps(bus, m("cut_hall") + 0.25, m("cut_install") - 0.1, -41, pace=0.42, pan=-0.6, pan_to=0.6)
    A.ev(bus, "paper/paper-handle", m("cut_hall") + 0.9, -43)
    # setting up: the box down, the tape, the telly on
    A.ev(bus, "impacts/tom-hit", m("cut_install") + 0.05, -40, semis=-9, lowpass=900)
    A.ev(bus, "paper/paper-handle", m("cut_install") + 0.1, -42, semis=-3)
    bus.add(A.at_level(rip(0.45), -42), m("cut_install") + 0.2, pan=-0.2)
    bus.add(A.at_level(A.room(bloop(), 0.6, 0.2), -36), m("cut_install") + 0.4, pan=0.3)
    # the ban: Mum's steps, the toys knocking about in their box
    A.steps(bus, m("cut_ban"), le("L015") + 0.3, -43, pace=0.38, pan=-0.5, pan_to=0.5)
    for k in range(9):
        bus.add(A.at_level(wood(k), -42), m("cut_ban") + 0.2 + 0.25 * k + 0.08 * (k % 3), pan=-0.5 + k * 0.11)
    A.ev(bus, "cloth/cloth-c", m("cut_sulk") + 0.2, -46)                   # his arms fold
    # two weeks later: the toy box set down by the telly
    for k in range(3):
        bus.add(A.at_level(wood(20 + k), -44), m("cut_dad5") + 0.15 + 0.07 * k, pan=0.3)
    # the sneak: little careful steps, the T-shirt, the throw, the soft ball, the screen
    A.steps(bus, m("cut_sneak") + 0.05, m("cut_sneak") + 1.25, -49, pace=0.17, pan=-0.6, pan_to=-0.3, lowpass=3000)
    A.ev(bus, "cloth/cloth-a", m("cut_wind2") + 0.2, -45, pan=-0.4)
    A.ev(bus, "cloth/cloth-e", m("throw2") - 0.2, -38, pan=-0.4)
    bus.add(A.at_level(swish(0.45), -38), m("throw2"), pan=0.2)
    bus.add(A.at_level(glass(1.7, 2), -12), m("smash2"))
    bus.add(A.at_level(A.big_boom(0.4, tail=0.5), -24), m("smash2"))
    # Mum and Dad come running
    A.steps(bus, m("cut_run") - 0.7, m("cut_run") + 0.4, -35, pace=0.12, pan=-0.6, pan_to=-0.2)
    A.ev(bus, "cloth/cloth-c", m("cut_run") + 0.3, -42, pan=-0.3)
    # the sofa takes them
    bus.add(A.at_level(puff(0.6), -36), m("cut_sofa") + 0.05)
    A.ev(bus, "creaks/creak-long", m("cut_sofa") + 0.1, -42, semis=-3)
    A.ev(bus, "cloth/cloth-f", m("cut_sofa") + 0.25, -44)
    # the projector: its fan
    t = np.arange(int((m("cut_black") - m("cut_proj")) * SR)) / SR
    fan = A.bp(noise(len(t) / SR), 500, 3000, 2) * 0.6 + np.sin(2 * np.pi * 110 * t) * 0.12
    bus.add(A.at_level(fan.astype(np.float32), -55), m("cut_proj"), pan=-0.3)
    # black: the third one, heard and not seen
    bus.add(A.at_level(glass(2.2, 3), -11), m("cut_black") + 0.12)
    bus.add(A.at_level(A.big_boom(0.6, tail=0.6), -21), m("cut_black") + 0.12)
    # the title boom
    bus.add(A.at_level(A.big_boom(1.0), -16), m("cut_title"))


def main():
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg, room_s=0.3, room_db=-24)
    ambience(amb)
    foley(fx)
    music(mus)
    A.master(dlg, [amb, fx], [mus])
