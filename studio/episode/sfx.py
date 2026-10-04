"""Plain synthesised sound effects for animatics: card tap, door squeak, printer, chime and so on. They are
stand-ins that land the cues in the right place; real sound design replaces them. Each takes nothing and returns a
mono float32 array at SR (48 kHz)."""
import numpy as np
from scipy.signal import butter, lfilter

SR = 48000


def _rng(seed):
    return np.random.default_rng(seed)


def _t(d):
    return np.arange(int(d * SR)) / SR


def _env(n, attack=0.004, decay=0.1):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / attack) * np.exp(-t / decay)


def _band(x, lo, hi):
    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, x)


def _low(x, f):
    b, a = butter(2, f / (SR / 2))
    return lfilter(b, a, x)


def card_tap():
    t = _t(0.2)
    tone = np.sin(2 * np.pi * 1760 * t) * (t < 0.07) + np.sin(2 * np.pi * 2349 * t) * ((t >= 0.09) & (t < 0.19))
    click = _band(_rng(1).standard_normal(len(t)), 2000, 6000) * _env(len(t), 0.0005, 0.01) * 0.6
    return (0.25 * tone * np.minimum(1, (0.2 - t) / 0.02) + click).astype(np.float32)


def door_squeak():
    t = _t(0.6)
    f = 520 + 380 * np.sin(np.pi * t / 0.6) ** 2 + 30 * np.sin(2 * np.pi * 14 * t)
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5 + np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.2
    return (_band(x, 400, 3500) * np.sin(np.pi * t / 0.6) ** 1.5 * 0.35).astype(np.float32)


def shoe_squeak():
    t = _t(0.13)
    f = 2600 - 900 * t / 0.13
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.13) * 0.3).astype(np.float32)


def printer_feed(seconds=2.8):
    t = _t(seconds)
    r = _rng(2)
    motor = np.sin(2 * np.pi * 95 * t) * 0.15 + _low(r.standard_normal(len(t)), 600) * 0.12
    steps = (np.sin(2 * np.pi * 21 * t) > 0.6).astype(float)
    chatter = _band(r.standard_normal(len(t)), 1200, 5000) * steps * 0.25
    env = np.minimum(1, t / 0.15) * np.minimum(1, (seconds - t) / 0.25)
    return ((motor + chatter) * env).astype(np.float32)


def wheel_roll():
    t = _t(1.5)
    r = _rng(3)
    rumble = _low(r.standard_normal(len(t)), 260) * (0.6 + 0.4 * np.sin(2 * np.pi * 6.5 * t)) * 0.5
    env = np.minimum(1, t / 0.2) * np.minimum(1, (1.5 - t) / 0.06)
    clunk = np.zeros(len(t))
    k = int(1.38 * SR)
    clunk[k:k + int(0.12 * SR)] = (np.sin(2 * np.pi * 90 * _t(0.12)) * _env(int(0.12 * SR), 0.001, 0.04))[: len(clunk) - k]
    return (rumble * env + clunk * 0.7).astype(np.float32)


def paper_spill():
    t = _t(1.0)
    r = _rng(4)
    bursts = np.zeros(len(t))
    for c in np.sort(r.uniform(0.0, 0.7, 9)):
        i = int(c * SR)
        n = min(int(0.18 * SR), len(t) - i)
        bursts[i:i + n] += _env(n, 0.003, 0.05) * r.uniform(0.4, 1.0)
    return (_band(r.standard_normal(len(t)), 900, 6500) * bursts * 0.28).astype(np.float32)


def curtain_rings():
    t = _t(0.8)
    r = _rng(5)
    out = np.zeros(len(t))
    for c in np.sort(r.uniform(0.0, 0.55, 9)):
        i = int(c * SR)
        n = min(int(0.12 * SR), len(t) - i)
        f = r.uniform(3000, 4200)
        out[i:i + n] += np.sin(2 * np.pi * f * _t(0.12)[:n]) * _env(n, 0.0008, 0.025) * r.uniform(0.4, 1.0)
    return (out * 0.18).astype(np.float32)


def clipboard_thump():
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 120 * t) * _env(n, 0.001, 0.05)
    snap = _band(_rng(6).standard_normal(n), 800, 5000) * _env(n, 0.0005, 0.012)
    return (0.55 * body + 0.35 * snap).astype(np.float32)


def thump():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return (0.7 * np.sin(2 * np.pi * 68 * t) * _env(n, 0.001, 0.08) + 0.25 * _low(_rng(7).standard_normal(n), 900) * _env(n, 0.0005, 0.02)).astype(np.float32)


def soft_thump():
    return (thump() * 0.45).astype(np.float32)


def chime():
    t = _t(1.1)
    note = lambda f, t0: np.where(t >= t0, np.sin(2 * np.pi * f * np.maximum(t - t0, 0)) * np.exp(-np.maximum(t - t0, 0) / 0.28), 0) * np.minimum(1, np.maximum(t - t0, 0) / 0.004)
    return (0.3 * (note(784, 0.0) + note(1175, 0.16) + 0.4 * note(1568, 0.16))).astype(np.float32)


def switch_click():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return (0.6 * _band(_rng(8).standard_normal(n), 1500, 7000) * _env(n, 0.0004, 0.006) + 0.3 * np.sin(2 * np.pi * 260 * t) * _env(n, 0.0004, 0.01)).astype(np.float32)


def chair_scrape():
    t = _t(0.7)
    f = 180 + 120 * t / 0.7
    x = _band(_rng(9).standard_normal(len(t)), 300, 2200) * (0.6 + 0.4 * np.sin(2 * np.pi * f * t / 8))
    return (x * np.sin(np.pi * t / 0.7) * 0.3).astype(np.float32)


SFX = dict(card_tap=card_tap, door_squeak=door_squeak, shoe_squeak=shoe_squeak, printer_feed=printer_feed,
           printer_feed_short=lambda: printer_feed(1.1), wheel_roll=wheel_roll, paper_spill=paper_spill,
           curtain_rings=curtain_rings, clipboard_thump=clipboard_thump, thump=thump, soft_thump=soft_thump,
           chime=chime, switch_click=switch_click, chair_scrape=chair_scrape)


def room_tone(seconds):
    """a quiet studio: low airy noise with a faint hum"""
    t = _t(seconds)
    x = _low(_rng(10).standard_normal(len(t)), 700) * 0.5 + 0.12 * np.sin(2 * np.pi * 60 * t)
    return (x / max(1e-6, float(np.abs(x).max()))).astype(np.float32)
