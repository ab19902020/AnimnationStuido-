"""The mix (from All or Something): the dialogue edit, real recorded ambience and foley, a few synthesised sounds
that are electronic in life too (a card reader's beep), stings, and the master.

  - dialogue: every line at its timeline position, levelled, with a little of the room it was said in
  - ambience and foley: real recordings from library/audio/sfx (CC0, see its manifest.json; tools/get_sfx.py
    fetches more), named "<category>/<name>": "creaks/creak-short", "cloth/cloth-a"... Every cue is keyed to the
    picture by the same timeline marks the shots and the acting use. No whooshes on cuts: cuts are hard cuts
  - music: synthesised strings and piano for stings (the title), ducked under the dialogue
  - master: loudness to -16 LUFS integrated (EBU R128 / BS.1770 gating), a soft limit at -1 dBFS

An episode's film/sound.py builds its buses with these and ends with master(...):

    from studio.film import audio as A
    dlg, amb, fx, mus = A.Bus(), A.Bus(), A.Bus(), A.Bus()
    A.dialogue(dlg)
    A.bed(amb, "ambience/room-tone-hvac", 0.0, m("cut_title"), -52, lowpass=4500)
    A.ev(fx, "creaks/creak-short", m("squeak"), -38, pan=0.7)
    A.master(dlg, [amb, fx], [mus])

`check_words()` hears every line again in the finished mix (Whisper) and compares it with the script."""
import json
import math

import numpy as np
import soundfile as sf
from scipy import signal

from studio.film import ep
from studio.paths import SFX

SR = 48000
RNG = np.random.default_rng(2026)


def _tl():
    from film.timeline import TL
    return TL


def total():
    return _tl()["total"]


def db(x):
    return 10 ** (x / 20)


def at_level(x, target_db):
    """scale x so the RMS of its active part (above -50 dB of its peak) is target_db dBFS"""
    x = np.asarray(x, np.float32)
    mono = x.mean(1) if x.ndim == 2 else x
    a = np.abs(mono)
    if a.max() <= 0:
        return x
    act = mono[a > a.max() * db(-50)]
    r = np.sqrt(np.mean(act ** 2)) if len(act) else 1.0
    return x * (db(target_db) / max(r, 1e-9))


def bp(x, lo, hi, order=4):
    return signal.sosfilt(signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x, axis=0)


def lp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, btype="low", fs=SR, output="sos"), x, axis=0)


def hp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, btype="high", fs=SR, output="sos"), x, axis=0)


def fade(n, fin, fout):
    e = np.ones(n, np.float32)
    fi, fo = int(fin * SR), int(fout * SR)
    if fi:
        e[:fi] = np.linspace(0, 1, fi)
    if fo:
        e[-fo:] = np.minimum(e[-fo:], np.linspace(1, 0, fo))
    return e


class Bus:
    """a stereo track the length of the episode"""

    def __init__(self, seconds=None):
        self.n = int(round((seconds or total()) * SR))
        self.x = np.zeros((self.n, 2), np.float32)

    def add(self, y, t, gain=1.0, pan=0.0):
        """y (mono or stereo) at time t; pan -1 left .. 1 right (equal power)"""
        i = int(round(t * SR))
        y = np.asarray(y, np.float32)
        if y.ndim == 1:
            y = np.stack([y, y], 1)
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.4142, math.sin((pan + 1) * math.pi / 4) * 1.4142
        j0 = max(0, i)
        k0 = j0 - i
        n = min(len(y) - k0, self.n - j0)
        if n <= 0:
            return
        self.x[j0:j0 + n, 0] += y[k0:k0 + n, 0] * gain * gl
        self.x[j0:j0 + n, 1] += y[k0:k0 + n, 1] * gain * gr


def reverb_ir(seconds, damp=6000, predelay=0.01, seed=1):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)).astype(np.float32) * np.exp(-6.9 * t / seconds)[:, None]
    ir[:, 0] = lp(ir[:, 0], damp, 2)
    ir[:, 1] = lp(ir[:, 1], damp, 2)
    ir = np.concatenate([np.zeros((int(predelay * SR), 2), np.float32), ir])
    return ir / np.sqrt((ir ** 2).sum(0).mean())


def convolve_st(x, ir):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    return np.stack([signal.fftconvolve(x[:, 0], ir[:, 0]), signal.fftconvolve(x[:, 1], ir[:, 1])], 1).astype(np.float32)


def room(x, seconds=2.4, mix=0.25, seed=7):
    ir = reverb_ir(seconds, 5000, 0.02, seed)
    n = len(x)
    return (x if x.ndim == 2 else np.stack([x, x], 1)) * 0.85 + convolve_st(x, ir)[:n] * mix


# ---------------------------------------------------------------- recorded clips
_CLIPS = {}


def clip(name):
    """a clip from library/audio/sfx ("category/name") as float32 (n,) or (n, 2) at 48 kHz"""
    if name not in _CLIPS:
        y, sr = sf.read(str(SFX / f"{name}.ogg"), dtype="float32", always_2d=False)
        if sr != SR:
            import librosa
            y = librosa.resample(y.T, orig_sr=sr, target_sr=SR).T.astype(np.float32)
        _CLIPS[name] = y
    return _CLIPS[name].copy()


def varispeed(y, semis):
    """pitch (and length) by resampling, as with tape: + semitones = higher and shorter"""
    if abs(semis) < 1e-3:
        return y
    f = 2 ** (semis / 12)
    n = int(len(y) / f)
    x = np.arange(n) * f
    if y.ndim == 1:
        return np.interp(x, np.arange(len(y)), y).astype(np.float32)
    return np.stack([np.interp(x, np.arange(len(y)), y[:, c]) for c in range(y.shape[1])], 1).astype(np.float32)


def looped(name, dur, xf=1.5):
    """an ambience clip looped with crossfades to dur seconds"""
    y = clip(name)
    n, k = int(dur * SR), int(xf * SR)
    out = y[:0]
    while len(out) < n:
        if len(out) == 0:
            out = y.copy()
            continue
        r = np.linspace(0, 1, k)[:, None] if y.ndim == 2 else np.linspace(0, 1, k)
        out = np.concatenate([out[:-k], out[-k:] * (1 - r) + y[:k] * r, y[k:]])
    return out[:n]


def big_boom(size=1.0, tail=None):
    """a cinematic impact: bass tom (pitched down) for the punch, gong down an octave and thunder for the body
    and tail, a touch of hall"""
    tom = varispeed(clip("impacts/tom-hit"), -5 - 2 * size)
    gong = lp(varispeed(clip("impacts/gong-big"), -12), 700, 2).astype(np.float32)
    thun = lp(clip("impacts/thunder-roll"), 380, 2).astype(np.float32)
    n = int((2.2 + 2.5 * size) * SR)

    def fit(y):
        if y.ndim == 2:
            y = y.mean(1)
        a = np.abs(y)
        i0 = int(np.argmax(a > 0.25 * a.max()))          # start on the attack, not the lead-in
        y = y[max(0, i0 - int(0.004 * SR)):][:n]
        return np.pad(y, (0, n - len(y)))

    t = np.arange(n) / SR
    body = at_level(fit(tom), -12) + at_level(fit(gong), -20) * 0.9 * size + at_level(fit(thun), -22) * size
    body *= np.exp(-t / (0.9 + 1.2 * size))
    wet = convolve_st(body, reverb_ir(2.2 + size, 3500, 0.02, 21))[:n]
    out = np.stack([body, body], 1) * 0.85 + wet * 0.28
    if tail is not None:                                   # a short tail, out of the way of the next line
        out *= np.exp(-np.maximum(0, t - 0.1) / tail)[:, None]
    return out


def beep(freq=2700.0, dur=0.16, harm=0.18):
    """an electronic beep (a card reader, a till): a sine with a soft edge and a little second harmonic"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * freq * t) + harm * np.sin(4 * np.pi * freq * t)
    e = np.minimum(1, t / 0.004) * np.minimum(1, (dur - t) / 0.02)
    return (y * np.clip(e, 0, 1)).astype(np.float32)


# ---------------------------------------------------------------- instruments (stings)
def note(nm):
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0,
             "Bb": 1, "A#": 1, "B": 2}
    p, o = nm[:-1], int(nm[-1])
    return 440.0 * 2 ** ((names[p] + 12 * (o - 4)) / 12)


def piano_note(f, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, np.float32)
    for h, (g, d) in enumerate([(1.0, 1.6), (0.45, 1.1), (0.22, 0.8), (0.12, 0.6), (0.06, 0.4)], 1):
        x += g * np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h * h)) * np.exp(-t * (1.0 + 0.9 * h) / d)
    return x * np.minimum(1, t / 0.004) * vel * 0.25


def strings(freqs, dur, attack=0.8, release=1.2, bright=1600):
    """a bowed string section: detuned saws, gentle vibrato, low-passed"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, np.float32)
    for f in freqs:
        for det in (-0.09, 0.0, 0.11):
            vib = 1 + 0.003 * np.sin(2 * np.pi * (5.1 + det) * t + RNG.uniform(0, 6))
            ph = 2 * np.pi * np.cumsum(f * (2 ** (det / 12)) * vib) / SR
            x += signal.sawtooth(ph + RNG.uniform(0, 6)).astype(np.float32) * 0.16
    x = lp(x, bright, 2)
    e = np.minimum(1, t / max(attack, 1e-3)) * np.minimum(1, (dur - t) / max(release, 1e-3))
    return (x * np.clip(e, 0, 1)).astype(np.float32)


def title_sting(dur, chord=("D2", "A2", "D3", "F3", "A3")):
    """the chord under the title boom"""
    n = int(dur * SR)
    ch = strings([note(c) for c in chord], dur + 1.0, 0.03, 0.5, 2200)[:n]
    y = np.stack([ch, ch], 1)
    return y + convolve_st(ch, reverb_ir(3.0, 4000, 0.03, 3))[:n] * 0.3


# ---------------------------------------------------------------- layers
def dialogue(bus, level=-20.0, room_s=0.35, room_db=-22.0, damp=5600, lines=None):
    """every line of the edit at its place, high-passed and levelled, with a little of the room it is said in"""
    TL = _tl()
    L = lines or json.loads(ep.path("lines.json").read_text())
    ir = reverb_ir(room_s, damp, 0.006, 11) if room_s else None
    for lid, v in TL["lines"].items():
        y, sr = sf.read(str(ep.path("lines", f"{lid}.wav")), dtype="float32")
        if y.ndim > 1:
            y = y.mean(1)
        y = hp(y, 75, 2).astype(np.float32)
        y = np.clip(at_level(y, level + L[lid].get("gain", 0.0)), -0.95, 0.95)
        bus.add(y, v["start"])
        if ir is not None:
            bus.add(convolve_st(y, ir), v["start"], db(room_db))


def bed(bus, name, a, b, level, lowpass=None, highpass=None, fin=0.004, fout=0.004, gain_fn=None):
    """an ambience clip looped from a to b at an RMS level (dB), hard cuts by default"""
    y = looped(name, b - a)
    if lowpass:
        y = lp(y, lowpass, 2).astype(np.float32)
    if highpass:
        y = hp(y, highpass, 2).astype(np.float32)
    y = at_level(y, level)
    e = fade(len(y), fin, fout)
    if gain_fn is not None:
        e = e * gain_fn(a + np.arange(len(y)) / SR)
    bus.add(y * (e[:, None] if y.ndim == 2 else e), a)


def ev(bus, name, t, level, pan=0.0, semis=0.0, lowpass=None, highpass=None, dur=None):
    """one recorded sound at time t, at an RMS level (dB)"""
    y = varispeed(clip(name), semis)
    if y.ndim == 2:
        y = y.mean(1)
    if dur:
        y = y[:int(dur * SR)] * fade(min(len(y), int(dur * SR)), 0.0, 0.04)
    if lowpass:
        y = lp(y, lowpass, 2).astype(np.float32)
    if highpass:
        y = hp(y, highpass, 2).astype(np.float32)
    bus.add(at_level(y, level), t, 1.0, pan)


def steps(bus, t0, t1, level, pace=0.28, pan=0.0, pan_to=None, lowpass=None,
          names=("footsteps/step-a", "footsteps/step-b")):
    """footsteps from t0 to t1, one every `pace` s, alternating recorded steps"""
    k, t = 0, t0
    while t < t1:
        p = pan if pan_to is None else pan + (pan_to - pan) * (t - t0) / max(1e-3, t1 - t0)
        ev(bus, names[k % 2], t, level + (0 if k % 2 else -1.5), pan=p, lowpass=lowpass, semis=-0.5 + 0.4 * (k % 3))
        k += 1
        t += pace


# ---------------------------------------------------------------- master
def _k_weight(x):
    """the BS.1770 K-weighting (48 kHz): a high shelf, then the RLB high-pass"""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def lufs(x):
    """integrated loudness (LUFS) of a 48 kHz stereo signal, with the absolute and relative gates"""
    y = _k_weight(np.asarray(x, np.float64))
    if y.ndim == 1:
        y = y[:, None]
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    ms = np.array([np.mean(y[i:i + blk] ** 2, 0).sum() for i in range(0, max(1, len(y) - blk + 1), hop)])
    ld = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[ld > -70]
    if not len(g):
        return -70.0
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g = ms[(ld > -70) & (ld > rel)]
    return float(-0.691 + 10 * np.log10(g.mean()))


def duck(dlg, depth_db=-7.0):
    """a gain curve that dips music under the dialogue"""
    env = lp(np.abs(dlg.x.mean(1)), 6, 1)
    g = 1.0 / (1.0 + 7.0 * np.clip(env / db(-26), 0, 1))
    return np.clip(g, db(depth_db), 1.0).astype(np.float32)


def master(dlg, buses=(), music=(), target=-16.0, out=None):
    """dialogue + other buses + music (ducked under the dialogue) -> loudness-normalised mix, soft-limited at
    -1 dBFS, the very end cut hard (10 ms) -> build/episode_audio.wav"""
    mix = dlg.x.copy()
    for b in buses:
        mix += b.x
    if music:
        d = duck(dlg)[:, None]
        for b in music:
            mix += b.x * d
    mix *= db(target - lufs(mix))
    peak = db(-1)
    mix = np.tanh(mix / peak) * peak
    mix *= db(target - lufs(mix))                          # the limiter takes a little off: put it back
    mix = np.clip(mix, -peak, peak)
    mix[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))[:, None]
    out = out or ep.path("episode_audio.wav")
    sf.write(str(out), mix.astype(np.float32), SR, subtype="PCM_24")
    print(f"{out}  {len(mix) / SR:.2f}s  {lufs(mix):.1f} LUFS  peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS")
    return mix


# ---------------------------------------------------------------- QC
def check_words(path=None, limit=0.25):
    """hear every line again in the finished mix (or the video's soundtrack) and score it against the script:
    word error rate per line; anything over `limit` is flagged"""
    import librosa
    from studio.episode.asr import transcribe, wer
    TL = _tl()
    L = json.loads(ep.path("lines.json").read_text())
    src = path or ep.path("episode_audio.wav")
    y, _ = librosa.load(str(src), sr=16000, mono=True)
    tmp = ep.path("check_line.wav")
    bad = []
    for lid, v in TL["lines"].items():
        a, b = max(0, int((v["start"] - 0.05) * 16000)), int((v["end"] + 0.08) * 16000)
        sf.write(str(tmp), y[a:b], 16000)
        h = transcribe(str(tmp))
        e = wer(L[lid]["text"], h)
        flag = "  <--" if e > limit else ""
        if flag:
            bad.append(lid)
        print(f"{lid} {v['speaker']:8s} wer {e:4.2f}  {h}{flag}")
    tmp.unlink(missing_ok=True)
    print("all lines heard as scripted" if not bad else f"check these: {' '.join(bad)}")
    return bad
