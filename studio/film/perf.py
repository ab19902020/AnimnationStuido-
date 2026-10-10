"""The acting (from All or Something): per character, per frame face and body state, from the dialogue and the
script's beats.

state(who, t, resolve) -> dict(vis, amp, blink, lookx, looky, brow, smile, tilt, nod, turn, lean, sink)
  * lip sync  - phones -> the mouth shapes (face.py), a frame early, closures held >= 2 frames; the jaw opens with
                the loudness of the line; nobody's mouth moves without their voice
  * blinks    - every 2.2-4.8 s, never in sync between characters, plus the blinks the script asks for
  * eyes      - on whoever is talking (a beat late), on the person being talked to while talking, or where a cue
                sends them (the lens, the floor, a prop); `resolve` turns a target into a screen direction for the
                shot being rendered
  * face      - brows / smile from each line's delivery tag, easing in and out
  * head      - small nods on the stressed words, slow idle drift, the nods and turns the script names
  * body      - leans and sinks the script names

An episode's perf.py builds one Performance with its data:
  META   {line id: (delivery tag, who it is said to, [stressed words])}
  BASE   {who: (brow, smile)} each character's resting face
  GAZE   {who: [(t0, t1, target)]}: targets are a character, "cam", "down", ("dir", lookx, looky, turn)
  EXPR   {who: [(t0, t1, brow, smile, ease-in)]}  reactions outside their own lines
  NODS   {who: [(t, count, amplitude %)]};  TURN {who: [(t0, t1, turn, tilt deg)]}
  FORCED {who: [t]} blinks on cue;  NOBLINK {who: [(t0, t1)]} no blinks in holds (looks into the lens)
  SHUT   {who: [(t0, t1)]} eyes closed (singing a long note with feeling)
  cuts   the shot list's cut times: automatic blinks keep clear of the first 0.4 s after a cut
  BODY   {who: [(t0, t1, lean, sink, ease-in)]}
  SQUINT {who: [(t0, t1, amount)]} lids partly down (smug, suspicious); SHAKE {who: [(t0, t1, hz, amount)]} the body
         bobbing (a laugh); darts: amplitude of the small eye darts (saccades) round wherever they look, 0 = none; SHOUT {line id: k} opens
         the mouth k times wider on a shouted line, its narrow shapes swapped for wider ones (SHOUTED)"""
import math

import numpy as np
import soundfile as sf

from studio.film import face

FPS = 30
# delivery tag -> (brow: + raised / - lowered, smile: + / - frown)
TAGS = dict(
    honest=(0.35, -0.05), calm=(0.05, 0.0), confident=(0.15, 0.35), relieved=(0.5, 0.55), casual=(0.1, 0.3),
    confused=(0.8, -0.15), obvious=(0.45, 0.12), explaining=(0.4, 0.2), stunned=(1.0, -0.25), diplomatic=(0.3, 0.1),
    deadpan=(-0.12, -0.05), matter=(0.25, 0.1), frustrated=(-0.55, -0.3), angry=(-0.95, -0.4),
    disbelieving=(0.85, -0.2), deadpan_happy=(0.2, 0.45), concerned=(0.5, -0.3), awkward=(0.4, 0.15),
    detached=(-0.05, 0.0), defensive=(0.4, -0.12), smug=(-0.25, 0.6), sigh=(-0.1, -0.2), firm=(-0.3, 0.0),
    proud=(0.25, 0.5), regretful=(0.35, -0.35), resigned=(0.2, -0.28), motivational=(0.3, 0.2), serious=(-0.3, -0.1),
    innocent=(0.55, 0.1), energised=(0.45, 0.35), positive=(0.35, 0.3), encouraging=(0.45, 0.45), flat=(-0.2, -0.15),
    restrained=(-0.05, -0.1), helpful=(0.45, 0.15), quiet=(-0.35, -0.2), irritated=(-0.6, -0.25),
    annoyed=(-0.4, -0.25), exhausted=(0.2, -0.3), salesman=(0.35, 0.45), sarcastic=(-0.3, 0.15), dry=(-0.2, 0.0),
    hopeful=(0.45, 0.3), precise=(0.1, -0.05), cold=(-0.35, -0.15), pleased=(0.2, 0.5), indignant=(0.6, -0.35))
BLINK_SHAPE = [0.45, 0.95, 1.0, 0.7, 0.3]
# on a shouted line (SHOUT) the narrow mouth shapes open up: "oo" to "o", "o" to "ah", the tongue / teeth shapes to "e"
SHOUTED = {"U": "O", "O": "AI", "CDG": "E", "I": "E", "R": "O", "L": "AI"}


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ramp(t, a, b, fin=0.15, fout=0.3):
    """0 -> 1 over [a, a + fin], 1 until b, back to 0 over [b, b + fout]"""
    return float(sm((t - a) / max(fin, 1e-3)) * (1 - sm((t - b) / max(fout, 1e-3))))


def bump(u):
    """a nod: down then back (u in 0..1)"""
    return math.sin(math.pi * min(1.0, max(0.0, u))) if 0 <= u <= 1 else 0.0


class Performance:
    def __init__(self, TL, lines, who, spk, meta, line_wav, base=None, gaze=None, expr=None, nods=None, turn=None,
                 forced=None, noblink=None, body=None, smile_bias=None, tags=None, rest_target=None, seed=200,
                 cuts=(), shut=None, squint=None, shake=None, darts=0.0, shout=None):
        self.TL, self.L, self.WHO, self.SPK = TL, lines, list(who), spk
        self.META = meta
        self.line_wav = line_wav
        self.BASE = {w: (base or {}).get(w, (0.0, 0.0)) for w in self.WHO}
        self.GAZE = {w: list((gaze or {}).get(w, [])) for w in self.WHO}
        self.EXPR = {w: list((expr or {}).get(w, [])) for w in self.WHO}
        self.NODS = {w: list((nods or {}).get(w, [])) for w in self.WHO}
        self.TURN = {w: list((turn or {}).get(w, [])) for w in self.WHO}
        self.FORCED = {w: list((forced or {}).get(w, [])) for w in self.WHO}
        self.NOBLINK = {w: list((noblink or {}).get(w, [])) for w in self.WHO}
        self.SHUT = {w: list((shut or {}).get(w, [])) for w in self.WHO}
        self.BODY = {w: list((body or {}).get(w, [])) for w in self.WHO}
        self.SQUINT = {w: list((squint or {}).get(w, [])) for w in self.WHO}
        self.SHAKE = {w: list((shake or {}).get(w, [])) for w in self.WHO}
        self.DARTS = darts
        self.SHOUT = shout or {}
        self.SMILE_BIAS = smile_bias or {}
        self.TAGS = {**TAGS, **(tags or {})}
        self.rest_target = rest_target or {}
        self.N = int(math.ceil(TL["total"] * FPS)) + 2
        self.seed = seed
        self.CUTS = sorted(cuts)
        self.VIS, self.AMP, self.TALK = self._speech()
        self.BLINKS = self._blinks()
        self.EMPH = self._emph()
        self.DART = self._darts() if darts else {}

    # ------------------------------------------------------------ lip sync
    def _speech(self):
        N = self.N
        ev = {w: [] for w in self.WHO}
        amp = {w: np.zeros(N, np.float32) for w in self.WHO}
        talking = {w: np.zeros(N, bool) for w in self.WHO}
        for lid, v in self.TL["lines"].items():
            who = self.SPK.get(v["speaker"], v["speaker"])
            if who not in ev or self.L[lid].get("missing"):
                continue
            vs = face.viseme_events(self.L[lid]["phones"], v["start"])
            if lid in self.SHOUT:                # a yell is drawn wide open: each shape swapped for its wider cousin
                vs = [(a, b, SHOUTED.get(x, x)) for a, b, x in vs]
            ev[who] += vs
            y, sr = sf.read(self.line_wav(lid), dtype="float32")
            if y.ndim > 1:
                y = y.mean(1)
            hop = sr // FPS
            rms = np.array([np.sqrt(np.mean(y[i:i + hop] ** 2) + 1e-12) for i in range(0, len(y), hop)])
            ref = np.percentile(rms, 90) + 1e-6
            a = np.clip(0.55 + 0.55 * rms / ref, 0.5, 1.15) * self.SHOUT.get(lid, 1.0)
            f0 = int(round(v["start"] * FPS))
            for k, val in enumerate(a):
                if 0 <= f0 + k < N:
                    amp[who][f0 + k] = val
            talking[who][max(0, f0):min(N, int(round(v["end"] * FPS)))] = True
        vis = {w: face.track(ev[w], N, FPS) for w in self.WHO}
        for w in self.WHO:
            amp[w][amp[w] == 0] = 1.0
        return vis, amp, talking

    # ------------------------------------------------------------ blinks
    def _blinks(self):
        out = {}
        for k, w in enumerate(self.WHO):
            rng = np.random.default_rng(self.seed + k)
            t, ts = rng.uniform(0.4, 2.5), []
            while t < self.TL["total"]:
                # never in the first frames after a cut (it reads as a bad edit): wait until the shot settles
                c = next((c for c in self.CUTS if c - 0.08 <= t < c + 0.4), None)
                if c is not None:
                    t = c + 0.4 + rng.uniform(0.0, 0.3)
                if not any(a <= t <= b for a, b in self.NOBLINK[w]):
                    ts.append(t)
                t += rng.uniform(2.2, 4.8)
            ts += self.FORCED[w]
            ts.sort()
            clean = []
            for x in ts:                               # forced blinks win over nearby automatic ones
                if clean and x - clean[-1] < 0.5:
                    if x in self.FORCED[w]:
                        clean[-1] = x
                    continue
                clean.append(x)
            out[w] = clean
        return out

    def _darts(self):
        """per character: [(t, dx, dy)] small jumps of the eyes round their target, every 0.5-1.4 s, held until the
        next; none in the first 0.35 s after a cut (the eye settles on the new shot first)"""
        out = {}
        for k, w in enumerate(self.WHO):
            rng = np.random.default_rng(self.seed + 50 + k)
            t, ev = rng.uniform(0.2, 0.8), [(0.0, 0.0, 0.0)]
            while t < self.TL["total"]:
                if any(c <= t < c + 0.35 for c in self.CUTS):
                    t += 0.35
                    continue
                ev.append((t, rng.uniform(-1, 1) * self.DARTS, rng.uniform(-0.6, 0.6) * self.DARTS))
                t += rng.uniform(0.5, 1.4)
            out[w] = ev
        return out

    def dart(self, w, t):
        if not self.DARTS or any(a <= t <= b for a, b in self.NOBLINK[w]):     # a held stare stays put
            return 0.0, 0.0
        ev = self.DART[w]
        i = max(0, int(np.searchsorted([e[0] for e in ev], t, side="right")) - 1)
        t0, x, y = ev[i]
        px, py = ev[i - 1][1:] if i > 0 else (0.0, 0.0)
        u = sm((t - t0) / 0.05)                  # a saccade takes a frame or two
        return px + (x - px) * u, py + (y - py) * u

    def blink(self, w, t):
        shut = max([ramp(t, a, b, 0.1, 0.14) for a, b in self.SHUT[w]] or [0.0])
        shut = max([shut] + [amt * ramp(t, a, b, 0.12, 0.18) for a, b, amt in self.SQUINT[w]])
        f = t * FPS
        for b in self.BLINKS[w]:
            k = f - b * FPS
            if 0 <= k < len(BLINK_SHAPE):
                i = int(k)
                u = k - i
                nx = BLINK_SHAPE[i + 1] if i + 1 < len(BLINK_SHAPE) else 0.0
                return max(shut, BLINK_SHAPE[i] * (1 - u) + nx * u)
        return shut

    # ------------------------------------------------------------ where each one looks
    def speaker_at(self, t, lag=0.2):
        """the character whose line is current (or was the last one) at time t - lag"""
        best = None
        for lid, v in self.TL["lines"].items():
            who = self.SPK.get(v["speaker"], v["speaker"])
            if who not in self.WHO:
                continue
            if v["start"] + lag <= t:
                best = (who, lid)
        return best

    def target(self, w, t):
        for a, b, g in self.GAZE[w]:
            if a <= t < b:
                return g
        for lid, v in self.TL["lines"].items():          # talking: to the person the line is for
            if self.SPK.get(v["speaker"], v["speaker"]) == w and v["start"] - 0.1 <= t < v["end"] + 0.25:
                return self.META[lid][1]
        sp = self.speaker_at(t)
        if sp and sp[0] != w:
            return sp[0]
        return self.rest_target.get(w, "cam")

    # ------------------------------------------------------------ brows / smile
    def expression(self, w, t):
        b, s = self.BASE[w]
        for lid, v in self.TL["lines"].items():
            if self.SPK.get(v["speaker"], v["speaker"]) != w:
                continue
            k = ramp(t, v["start"] - 0.12, v["end"], 0.15, 0.45)
            if k > 0:
                tb, ts = self.TAGS[self.META[lid][0]]
                b, s = b + (tb - b) * k, s + (ts - s) * k
        for a, bb, cb, cs, fin in self.EXPR[w]:
            k = ramp(t, a, bb, fin, 0.3)
            if k > 0:
                b, s = b + (cb - b) * k, s + (cs - s) * k
        return b, s + self.SMILE_BIAS.get(w, 0.0)

    # ------------------------------------------------------------ head motion
    def _emph(self):
        """(t, strength) of every stressed word, per character"""
        out = {w: [] for w in self.WHO}
        for lid, v in self.TL["lines"].items():
            w = self.SPK.get(v["speaker"], v["speaker"])
            if w not in self.WHO:
                continue
            stress = self.META[lid][2]
            for wd in self.L[lid]["words"]:
                if wd["w"] in stress:
                    out[w].append((v["start"] + wd["s"] + 0.03, 1.0))
        return out

    def head(self, w, t):
        k = self.WHO.index(w)
        tilt = 1.1 * math.sin(t * 0.61 + k * 1.7) + 0.5 * math.sin(t * 1.37 + k)
        nod = 0.6 * math.sin(t * 0.83 + k * 2.3)
        turn = 0.02 * math.sin(t * 0.47 + k)
        for te, s in self.EMPH[w]:
            nod += 2.2 * s * bump((t - te) / 0.3)
        for tn, cnt, a in self.NODS[w]:
            for c in range(cnt):
                nod += a * bump((t - tn - c * 0.36) / 0.34)
        for a, b, tu, ti in self.TURN[w]:
            r = ramp(t, a, b, 0.25, 0.3)
            turn += tu * r
            tilt += ti * r
        if self.TALK[w][min(self.N - 1, int(t * FPS))]:
            tilt += 0.8 * math.sin(t * 2.3 + k)
        return tilt, nod, turn

    def body(self, w, t):
        lean = sink = 0.0
        for a, b, le, si, fin in self.BODY[w]:
            r = ramp(t, a, b, fin, 0.3)
            lean += le * r
            sink += si * r
        for a, b, hz, amt in self.SHAKE[w]:
            r = ramp(t, a, b, 0.06, 0.25)
            if r > 0:
                sink += amt * r * abs(math.sin(math.pi * hz * (t - a)))
        return lean, sink

    def state(self, w, t, resolve, t0=0.0):
        """face + body state; resolve(target) -> (lookx, looky, turn) for the current shot, which started at t0"""
        f = min(self.N - 1, max(0, int(round(t * FPS))))
        # eyes: stateless smoothing of the resolved targets over the last few frames (saccade ~ 60 ms, head
        # ~ 180 ms), never reaching back across the cut
        lx = ly = tu = 0.0
        we_s = wh_s = 0.0
        for j in range(8):
            tt = max(t0, t - j / FPS)
            gx, gy, gt = resolve(self.target(w, tt))
            we = math.exp(-j / 1.8)
            wh = math.exp(-j / 5.0)
            lx += gx * we
            ly += gy * we
            we_s += we
            tu += gt * wh
            wh_s += wh
        lx /= we_s
        ly /= we_s
        tu /= wh_s
        ddx, ddy = self.dart(w, t)
        lx += ddx
        ly += ddy
        brow, smile = self.expression(w, t)
        tilt, nod, turn = self.head(w, t)
        lean, sink = self.body(w, t)
        return dict(vis=self.VIS[w][f], amp=float(self.AMP[w][f]), blink=self.blink(w, t), lookx=lx, looky=ly,
                    brow=brow, smile=smile, tilt=tilt, nod=nod, turn=turn + tu, lean=lean, sink=sink)
