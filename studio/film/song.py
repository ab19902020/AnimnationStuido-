"""A song for a music video: everything the picture moves to, worked out once from the track.

    python3 -m studio.film SLUG song     -> build/song.json and build/stems/{vocals,accompaniment}.wav

  tempo, beats         the beat grid (librosa), seconds
  downbeats            the first beat of every bar (the beat phase where the kick lands hardest)
  hits                 kick / snare / crash onsets from the accompaniment: [[t, strength 0..1]]
  loud, vocal          loudness of the mix and of the voice, per frame (dB, 30 fps)
  sing                 the lead voice as mouth shapes, per frame: [viseme, amp]
  words, lines         the lyrics (lyrics.md) timed word by word: [[start, end, word, line]], [[start, end, text]]

The voice is separated with Spleeter (sherpa-onnx; tools/fetch_models.sh separate). With the lyrics, every phrase
of the voice is heard by Whisper, matched to the lyric words and force-aligned (pocketsphinx), so the mouths follow
the words; where singing defeats the aligner (held notes, choirs, the band over it) the words are spread over the
sung syllables, and the mouth is read off the voice itself: it opens with each syllable by its loudness, takes its
shape from the voice's spectrum (round for "home" and "oh", wide for "ee", open for "ah", teeth for "s") and closes
in the gaps, so every "home" ends on its M."""
import json

import numpy as np
import soundfile as sf

from studio.paths import MODELS

FPS = 30
SPLEETER = MODELS / "sherpa-onnx-spleeter-2stems-fp16"


def separate(song, out_dir):
    """the song split into vocals and accompaniment (44.1 kHz stereo wavs), cached"""
    out_dir.mkdir(parents=True, exist_ok=True)
    v, a = out_dir / "vocals.wav", out_dir / "accompaniment.wav"
    if v.exists() and a.exists():
        return v, a
    import librosa
    import sherpa_onnx as so
    cfg = so.OfflineSourceSeparationConfig(model=so.OfflineSourceSeparationModelConfig(
        spleeter=so.OfflineSourceSeparationSpleeterModelConfig(vocals=str(SPLEETER / "vocals.fp16.onnx"),
                                                               accompaniment=str(SPLEETER / "accompaniment.fp16.onnx")),
        num_threads=4, debug=False, provider="cpu"))
    y, sr = librosa.load(str(song), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    res = so.OfflineSourceSeparation(cfg).process(sample_rate=sr, samples=np.ascontiguousarray(y.astype(np.float32)))
    for path, st in zip((v, a), res.stems):
        sf.write(str(path), np.asarray(st.data).T, res.sample_rate)
    return v, a


def per_frame(x, sr, n):
    """RMS level (dB) of x in 1/30 s frames"""
    hop = sr / FPS
    out = np.full(n, -90.0, np.float32)
    for i in range(n):
        seg = x[int(i * hop):int((i + 1) * hop)]
        if len(seg):
            out[i] = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
    return out


def band_onsets(y, sr, lo, hi, delta, wait=0.09):
    """onsets of the energy in one frequency band -> [[t, strength 0..1]]"""
    import librosa
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=256))
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = S[(f >= lo) & (f < hi)].sum(0)
    env = np.maximum(0, np.diff(np.log1p(band), prepend=np.log1p(band[0])))
    env = env / (np.percentile(env, 99.5) + 1e-9)
    pk = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=8, post_avg=8, delta=delta,
                                wait=int(wait * sr / 256))
    t = librosa.frames_to_time(pk, sr=sr, hop_length=256)
    return [[round(float(a), 3), round(float(min(1.0, env[p])), 3)] for a, p in zip(t, pk)]


def sing_track(v16, n):
    """the voice as mouth shapes per frame: [viseme, amp]"""
    import librosa
    sr = 16000
    hop = 128                                               # 125 analysis frames a second
    S = np.abs(librosa.stft(v16, n_fft=1024, hop_length=hop)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    # the analysis frames inside each video frame, found by time: a whole number of samples per video frame
    # (sr // 120 = 133 for 133.3) fell half a second behind the voice by the end of the song
    edges = np.round(np.arange(n + 1) * sr / FPS / hop).astype(int)

    def band(lo, hi):
        e = S[(f >= lo) & (f < hi)].sum(0)
        return np.array([e[edges[i]:max(edges[i] + 1, edges[i + 1])].mean() if edges[i] < len(e) else 0.0
                         for i in range(n)])
    low, mid, high, sib = band(200, 800), band(800, 1800), band(1800, 3800), band(4500, 8000)
    tot = low + mid + high + 1e-12
    db = 10 * np.log10(tot + 1e-12)
    # the gate follows the singing: 26 dB under the loudest second around it
    ref = np.array([db[max(0, i - 30):i + 30].max() for i in range(n)])
    voiced = (db > ref - 26) & (db > np.percentile(db, 20) + 6)
    o = np.clip((db - (ref - 26)) / 26, 0, 1)
    amp = 0.5 + 1.0 * o ** 0.8                               # belting opens wider than talking
    r_back = np.log((low + 1e-12) / (mid + high + 1e-12))    # energy low: back, rounded vowels (oh, oo)
    r_front = np.log((high + 1e-12) / (low + mid + 1e-12))   # energy high: front vowels (ee, eh)
    r_sib = np.log((sib + 1e-12) / tot)
    vv = voiced
    q_back = np.percentile(r_back[vv], 62) if vv.any() else 0
    q_front = np.percentile(r_front[vv], 75) if vv.any() else 0
    q_sib = np.percentile(r_sib[vv], 93) if vv.any() else 0
    vis = []
    for i in range(n):
        if not voiced[i]:
            vis.append("REST")
        elif r_sib[i] > q_sib:
            vis.append("CDG")
        elif r_back[i] > q_back:
            vis.append("O" if o[i] > 0.35 else "U")
        elif r_front[i] > q_front:
            vis.append("E" if o[i] > 0.45 else "I")
        else:
            vis.append("AI")
    # syllables: every onset in the voice starts with a consonant, a quick half-close before the vowel opens, so a
    # sung line reads as words rather than one long note
    from scipy.signal import find_peaks
    fine = 10 * np.log10(S[(f >= 200) & (f < 3800)].sum(0) + 1e-12)              # 125 per second
    fine = np.convolve(fine, np.ones(3) / 3, mode="same")
    dips, _ = find_peaks(-fine, prominence=2.0, distance=int(0.16 * sr / hop))
    keep = np.zeros(n, bool)
    for j in dips:
        i = int(round(j * hop * FPS / sr))
        if 1 <= i < n - 1 and voiced[i - 1] and voiced[i + 1]:
            vis[i] = "MBP" if vis[i - 1] in ("O", "U") and fine[j] < fine[max(0, j - 12):j].max() - 6 else "CDG"
            amp[i] = min(amp[i], 0.6)
            keep[i] = True
    # closures: a dip of 7 dB or more inside sung stretches is a consonant (an M, a B, a T): close for it
    for i in range(1, n - 1):
        if voiced[i - 1] and voiced[i + 1] and db[i] < min(db[max(0, i - 3):i].max(), db[i + 1:i + 4].max()) - 7:
            vis[i] = "MBP"
    # the end of a held note into silence ends on a closed mouth (home, home...)
    for i in range(1, n):
        if vis[i] == "REST" and vis[i - 1] in ("O", "U") and i + 1 < n:
            vis[i] = "MBP"
    # no single-frame flicker
    for i in range(1, n - 1):
        if vis[i] != "MBP" and not keep[i] and vis[i - 1] == vis[i + 1] != vis[i]:
            vis[i] = vis[i - 1]
    return [[v, round(float(a), 2)] for v, a in zip(vis, amp)]


def attacks(y, sr):
    """the drums' attacks, timed finely (3 ms hop, short window, backtracked to where the attack starts)"""
    import librosa
    perc = librosa.effects.percussive(y, margin=3.0)
    hop, n_fft = 128, 1024
    env = librosa.onset.onset_strength(y=perc, sr=sr, hop_length=hop, n_fft=n_fft, center=False)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, backtrack=True, units="time",
                                    delta=0.15)
    return on + n_fft / sr                               # uncentred frames: the attack enters at the frame's end


def snap(times, on, window):
    """times shifted by their median offset to the nearest true attacks (beat trackers and band onsets report
    their windows' centres: tens of ms off the real hit) -> (shifted times, offset s)"""
    times = np.asarray(times, np.float64)
    if not len(times) or not len(on):
        return times, 0.0
    j = np.clip(np.searchsorted(on, times), 1, len(on) - 1)
    near = np.where(np.abs(on[j] - times) < np.abs(on[j - 1] - times), on[j], on[j - 1])
    d = near - times
    d = d[np.abs(d) < window]
    off = float(np.median(d)) if len(d) else 0.0
    return times + off, off


def analyse(song, build):
    import librosa
    vpath, apath = separate(song, build / "stems")
    y, sr = librosa.load(str(song), sr=22050, mono=True)
    dur = len(y) / sr
    n = int(np.ceil(dur * FPS)) + 1
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", tightness=120)
    acc, _ = librosa.load(str(apath), sr=22050, mono=True)
    perc = librosa.effects.percussive(acc, margin=2.0)
    kick = band_onsets(perc, sr, 30, 140, 0.18)
    snare = band_onsets(perc, sr, 1500, 5000, 0.2)
    crash = band_onsets(perc, sr, 7000, 11000, 0.35, wait=0.4)
    # everything onto the true attacks: the beat grid and the band onsets are each some tens of ms off them
    acc44, sr44 = librosa.load(str(apath), sr=44100, mono=True)
    on = attacks(acc44, sr44)
    beats, boff = snap(beats, on, 0.1)
    shifts = {"beats": boff}
    for name, hits in (("kick", kick), ("snare", snare), ("crash", crash)):
        t2, off = snap([h[0] for h in hits], on, 0.06)
        for h, tt in zip(hits, t2):
            h[0] = round(float(tt), 3)
        shifts[name] = off
    print("onto the attacks: " + ", ".join(f"{k} {v * 1000:+.0f} ms" for k, v in shifts.items()))
    # downbeats: the beat phase (of four) where the chords change. That is the bar line; a rock kick lands on 1 and 3
    # alike, so it only breaks a tie (kick on 1 and 3, snare on 2 and 4)
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(acc), sr=sr, hop_length=hop)
    seg = librosa.util.sync(chroma, librosa.time_to_frames(beats, sr=sr, hop_length=hop), aggregate=np.median)
    seg = seg / (np.linalg.norm(seg, axis=0, keepdims=True) + 1e-9)       # seg[:, j + 1]: beat j to beat j + 1
    change = np.zeros(4)
    for j in range(1, min(len(beats), seg.shape[1] - 1)):
        change[j % 4] += 1 - float(seg[:, j + 1] @ seg[:, j])
    change /= max(1e-9, change.max())

    def drums(kind, p):
        t = np.array([h[0] for h in kind]) if kind else np.zeros(0)
        st = np.array([h[1] for h in kind]) if kind else np.zeros(0)
        tot = 0.0
        for b in beats[p::2]:
            m = np.abs(t - b) < 0.05
            tot += st[m].max() if m.any() else 0.0
        return tot
    beat = np.array([drums(kick, p % 2) - drums(snare, p % 2) for p in range(4)])
    beat = beat / max(1e-9, np.abs(beat).max())
    score = change + 0.25 * beat
    p = int(np.argmax(score))
    print("bar line: chord change per beat " + " ".join(f"{c:.2f}" for c in change)
          + ", kick-snare " + " ".join(f"{c:+.2f}" for c in beat) + f" -> beat {p}")
    v16, _ = librosa.load(str(vpath), sr=16000, mono=True)
    lyr = song.parent / "lyrics.md"
    words, lines, phones = align_lyrics(v16, lyric_lines(lyr), build) if lyr.exists() else ([], [], [])
    out = dict(duration=round(dur, 3), tempo=round(float(np.atleast_1d(tempo)[0]), 2), shifts=shifts,
               beats=[round(float(b), 3) for b in beats], downbeats=[round(float(b), 3) for b in beats[p::4]],
               hits=dict(kick=kick, snare=snare, crash=crash),
               loud=[round(float(v), 1) for v in per_frame(y, sr, n)],
               vocal=[round(float(v), 1) for v in per_frame(librosa.resample(v16, orig_sr=16000, target_sr=22050), 22050, n)],
               sing=sing_track(v16, n), words=words, lines=lines, phones=phones)
    out["lead"] = lead_track(out, n)
    (build / "song.json").write_text(json.dumps(out))
    print(f"{build / 'song.json'}: {dur:.1f} s, {out['tempo']} bpm, {len(beats)} beats, bar phase {p}, "
          f"{len(kick)} kicks, {len(snare)} snares, {len(crash)} crashes")
    return out


# ---------------------------------------------------------------- moving to it
class Song:
    """song.json with the timing helpers the picture uses"""

    def __init__(self, path):
        d = json.loads(path.read_text())
        self.__dict__.update(d)
        self.B = np.array(self.beats)
        self.D = np.array(self.downbeats)
        self.H = {k: np.array([x[0] for x in v]) if v else np.zeros(0) for k, v in self.hits.items()}
        self.HS = {k: np.array([x[1] for x in v]) if v else np.zeros(0) for k, v in self.hits.items()}
        self.period = float(np.median(np.diff(self.B)))
        self.energy_range = np.percentile(self.loud, [10, 99])

    def phase(self, t):
        """position inside the current beat, 0 on the beat .. 1 just before the next"""
        i = int(np.searchsorted(self.B, t, side="right")) - 1
        if i < 0:
            return ((t - self.B[0]) / self.period) % 1.0
        nxt = self.B[i + 1] if i + 1 < len(self.B) else self.B[i] + self.period
        return float((t - self.B[i]) / max(1e-3, nxt - self.B[i]))

    def beat_index(self, t):
        return int(np.searchsorted(self.B, t, side="right")) - 1

    def bar_phase(self, t):
        """position inside the bar, 0 .. 4 beats"""
        i = int(np.searchsorted(self.D, t, side="right")) - 1
        if i < 0:
            return 0.0
        nxt = self.D[i + 1] if i + 1 < len(self.D) else self.D[i] + 4 * self.period
        return float(4 * (t - self.D[i]) / max(1e-3, nxt - self.D[i]))

    def hit(self, kind, t, decay=0.12, lead=0.5 / FPS):
        """the envelope of the latest hit of a kind (1 on the hit, decaying), with its strength. A frame shows the
        instant it starts at; half a frame of lead puts a hit on the frame nearest it, not the one after"""
        h = self.H[kind]
        i = int(np.searchsorted(h, t + lead, side="right")) - 1
        if i < 0:
            return 0.0
        dt = t + lead - h[i]
        return float(self.HS[kind][i] * np.exp(-dt / decay)) if dt < 6 * decay else 0.0

    def frame(self, t):
        return min(len(self.loud) - 1, max(0, int(round(t * FPS))))

    def energy(self, t, width=1.0):
        """the mix's loudness around t, 0 (quiet) .. 1 (the loudest part of the song)"""
        lo, hi = self.energy_range
        f0, f1 = self.frame(t - width / 2), self.frame(t + width / 2)
        v = float(np.mean(self.loud[f0:f1 + 1]))
        return float(np.clip((v - lo) / max(1e-3, hi - lo), 0, 1))


# ---------------------------------------------------------------- the lyrics, timed
def lyric_lines(path):
    """lyrics.md -> the sung lines in order (section headings, notes and blank lines dropped)"""
    out = []
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith("[") or ln.startswith("As supplied") or ln.startswith("by word"):
            continue
        out.append(ln.strip("()"))
    return out


def _norm(w):
    w = w.lower().replace("’", "'")
    return {"giveee": "give", "'em": "em", "'cause": "cause", "reds": "reds"}.get(w, w)


def align_lyrics(v16, lines, cache):
    """time every lyric word in the separated voice (16 kHz) -> words [[s, e, word, line]], lines [[s, e, text]]"""
    from studio.film.voices import _pair, align_samples, stretches, words_of
    from studio.episode.asr import recognizer, words as asr_words
    cf = cache / "lyrics_asr.json"
    if cf.exists():
        chunks = json.loads(cf.read_text())
    else:
        chunks = []
        for a, b in stretches(v16, min_pause=0.18, top_db=28):
            if b - a < 0.2:
                continue
            t = a
            while t < b - 0.15:                                  # Whisper hears at most 30 s
                e = min(b, t + 20.0)
                x = np.concatenate([np.zeros(4000, np.float32), v16[int(t * 16000):int(e * 16000)], np.zeros(8000, np.float32)])
                st = recognizer().create_stream()
                st.accept_waveform(16000, x)
                recognizer().decode_stream(st)
                chunks.append([round(t, 3), round(e, 3), st.result.text.strip()])
                t = e
        cf.write_text(json.dumps(chunks, indent=1))
    # the lyric words against the heard words, in order
    lw, lline = [], []
    for k, ln in enumerate(lines):
        for w in words_of(ln):
            lw.append(_norm(w))
            lline.append(k)
    hw, hchunk = [], []
    for c, (_, _, text) in enumerate(chunks):
        for w in asr_words(text):
            hw.append(w)
            hchunk.append(c)
    pairs = _pair(hw, lw)
    owner = [hchunk[p] if p is not None else None for p in pairs]
    # unpaired lyric words go with their neighbours' stretch
    for i in range(len(owner)):
        if owner[i] is None:
            prev = next((owner[j] for j in range(i - 1, -1, -1) if owner[j] is not None), None)
            nxt = next((owner[j] for j in range(i + 1, len(owner)) if owner[j] is not None), None)
            owner[i] = prev if prev is not None else nxt
    words, phones = [], []
    extra = {"em": "EH M", "cantona": "K AE N T OW N AH", "trafford": "T R AE F ER D", "treble": "T R EH B AH L",
             "trophies": "T R OW F IY Z", "giveee": "G IH V"}
    i = 0
    while i < len(lw):
        c = owner[i]
        j = i
        while j + 1 < len(lw) and owner[j + 1] == c:
            j += 1
        a, b = chunks[c][0], chunks[c][1]
        seg = lw[i:j + 1]
        try:
            al = align_samples(v16[int(a * 16000):int(b * 16000)], seg, extra)
            for k, w in enumerate(al["words"]):
                words.append([round(a + w["s"], 3), round(a + w["e"], 3), seg[k], lline[i + k]])
            phones.extend([p["p"], round(a + p["s"], 3), round(a + p["e"], 3)] for p in al["phones"])
        except Exception:                                        # spread over the stretch by syllable count
            syl = [max(1, sum(1 for ch in w if ch in "aeiouy")) for w in seg]
            tot, t = sum(syl), a
            for k, w in enumerate(seg):
                d = (b - a) * syl[k] / tot
                words.append([round(t, 3), round(t + d, 3), w, lline[i + k]])
                t += d
        i = j + 1
    out_lines = []
    for k, ln in enumerate(lines):
        ws = [w for w in words if w[3] == k]
        if ws:
            out_lines.append([ws[0][0], ws[-1][1], ln])
    return words, out_lines, phones


SING_LEAD = 2          # frames: the mouth leads the soundtrack very slightly, as an animator would


VOWEL_VIS = {"AI", "E", "I", "O", "U"}


def _word_units(word):
    """a lyric word as mouth units read off its spelling: [(viseme, is_vowel)] (the fallback where the phone aligner
    lost a sung word)"""
    w = "".join(ch for ch in word.lower() if ch.isalpha())
    if len(w) > 2 and w.endswith("e") and not w.endswith(("ee", "oe", "ie", "ye")) and any(c in "aeiouy" for c in w[:-1]):
        w = w[:-1]                                             # a silent final e (home, take, believe)
    vpairs = {"oo": "U", "ee": "I", "ea": "E", "ou": "O", "ow": "O", "ai": "AI", "ay": "AI", "oi": "O", "oy": "O",
              "oa": "O", "ie": "I", "ue": "U", "au": "O", "aw": "O", "ei": "E", "ey": "E", "io": "O", "eo": "O"}
    cpairs = {"th": "L", "sh": "U", "ch": "U", "ph": "FV", "ng": "CDG", "ck": "CDG", "wh": "U", "qu": "U", "gh": None}
    cons = {"m": "MBP", "b": "MBP", "p": "MBP", "f": "FV", "v": "FV", "l": "L", "r": "R", "s": "CDG", "z": "CDG",
            "c": "CDG", "d": "CDG", "t": "CDG", "k": "CDG", "g": "CDG", "n": "CDG", "x": "CDG", "j": "U", "w": "U",
            "h": None}
    vows = {"a": "AI", "e": "E", "i": "I", "o": "O", "u": "U"}
    out, i = [], 0
    while i < len(w):
        q = w[i:i + 2]
        if q in vpairs:
            out.append((vpairs[q], True))
            i += 2
            continue
        if q in cpairs:
            if cpairs[q]:
                out.append((cpairs[q], False))
            i += 2
            continue
        ch = w[i]
        if ch == "y":                                          # a glide before a vowel; a vowel after a consonant
            if i + 1 < len(w) and w[i + 1] in "aeiou":
                out.append(("I", False))
            else:
                out.append(("AI" if len(w) <= 4 and i == len(w) - 1 else "I", True))   # my, sky; glory
        elif ch in vows:
            out.append((vows[ch], True))
        elif cons.get(ch):
            out.append((cons[ch], False))
        i += 1
    merged = []
    for v, isv in out:                                         # doubled letters (ff, ll) are one sound
        if merged and merged[-1][0] == v and merged[-1][1] == isv:
            continue
        merged.append((v, isv))
    return merged or [("E", True)]


def _sung_events(units, a, b):
    """a sung word's units spread over [a, b] (s): the consonants brief (a closure on M, B, P or F/V long enough
    to read), the vowels holding the note -> [(start, end, viseme)]"""
    dur = b - a
    nv = sum(1 for _, isv in units if isv)
    if nv == 0:
        return [(a, b, units[0][0])]
    c_len = min(0.075, 0.18 * dur)                              # about two frames
    cons = [(k, v) for k, (v, isv) in enumerate(units) if not isv]
    budget = 0.45 * dur                                         # the consonants never take more than this
    if len(cons) * c_len > budget:                              # a short word: keep the closures and the onset
        keep = {k for k, v in cons if v in ("MBP", "FV")} | ({cons[0][0]} if cons else set())
        units = [u for k, u in enumerate(units) if u[1] or k in keep]
        cons = [(k, v) for k, (v, isv) in enumerate(units) if not isv]
        c_len = min(c_len, budget / max(1, len(cons)))
    v_len = (dur - len(cons) * c_len) / nv
    ev, t = [], a
    for v, isv in units:
        d = v_len if isv else c_len
        ev.append((t, t + d, v))
        t += d
    return ev


def _capped(evs, cap=0.09):
    """aligned phones of a sung word, each consonant cut to at most `cap` s and the time given to the vowel next to it
    (the following vowel for an onset, the one before for a coda or a closing M, B, P, F, V): the voice holds the
    vowel where a speech aligner stretches the consonants over the note"""
    vi = [k for k, e in enumerate(evs) if e[2] in VOWEL_VIS]
    if not vi:
        return list(evs)
    dur = [e[1] - e[0] for e in evs]
    for k, (_, _, v) in enumerate(evs):
        if v in VOWEL_VIS or dur[k] <= cap:
            continue
        nxt = next((j for j in vi if j > k), None)
        prv = next((j for j in reversed(vi) if j < k), None)
        to = nxt if nxt is not None and (prv is None or v not in ("MBP", "FV")) else prv
        dur[to] += dur[k] - cap
        dur[k] = cap
    out, t = [], evs[0][0]
    for k, (_, _, v) in enumerate(evs):
        out.append((t, t + dur[k], v))
        t += dur[k]
    return out


def lead_track(d, n):
    """the lead singer's mouth per frame -> [[viseme, amp]]: every lyric word sung with its vowel held and its
    consonants brief (the aligned phones where the aligner followed the voice, the word's spelling spread over its
    timing where it did not), the shapes read off the voice in the gaps between words (ad libs, oh-ohs), and the
    jaw from the voice's loudness"""
    from studio.film import face
    sing = d["sing"]
    phones = [dict(p=p, s=a, e=b) for p, a, b in d.get("phones", [])]
    ps = np.array([x["s"] for x in phones]) if phones else np.zeros(0)
    ev = []
    inword = np.zeros(n, bool)
    for a, b, word, _line in d.get("words", []):
        if b - a < 1.0 / FPS:
            continue
        inword[max(0, int(a * FPS)):min(n, int(np.ceil(b * FPS)))] = True
        j0, j1 = int(np.searchsorted(ps, a - 0.02)), int(np.searchsorted(ps, b - 0.01))
        own = [x for x in phones[j0:j1] if x["e"] <= b + 0.03 and x["p"] != "SIL"]
        wev = face.viseme_events(own) if own else []
        if wev and any(v in VOWEL_VIS for _, _, v in wev) and own[0]["s"] - a < 0.25 and b - own[-1]["e"] < 0.25:
            wev = _capped(wev)
            wev[0] = (a, wev[0][1], wev[0][2])                   # the word's own edges
            wev[-1] = (wev[-1][0], b, wev[-1][2])
        else:
            wev = _sung_events(_word_units(word), a, b)
        ev.extend(wev)
    tr = face.track(ev, n)
    # between the words the mouth follows the voice only where someone is really singing (an oh, an ad lib): loud,
    # held for a few frames, inside the sung part of the song. The separated voice carries quiet bleed from the band
    # (the intro's guitars), and a singer mouthing to that before his first line looks out of sync
    voc = np.array(d.get("vocal") or [-90.0] * n, np.float32)
    ref = np.median(voc[inword]) if inword.any() else -24.0
    loud = voc[:n] > ref - 9.0 if len(voc) >= n else np.zeros(n, bool)
    held = np.convolve(loud.astype(np.float32), np.ones(5), mode="same") >= 4
    first = min((a for a, *_ in d.get("words", [])), default=0.0)
    last = max((b for _, b, *_ in d.get("words", [])), default=n / FPS)
    out = []
    for f in range(n):
        spec_v, amp = sing[min(f + SING_LEAD, len(sing) - 1)]
        v = tr[f]
        if v == "REST" and not inword[f]:
            sung = held[f] and first - 0.5 <= f / FPS <= last + 1.0
            v = spec_v if sung else "REST"                      # between the words: what the voice is doing
        out.append([v, amp])
    # one-frame changes are chatter, not a sung consonant
    for i in range(1, n - 1):
        if out[i][0] not in ("MBP", "FV") and out[i - 1][0] == out[i + 1][0] != out[i][0]:
            out[i][0] = out[i - 1][0]
    # singing opens wider than talking: a held ee or oo is sung on a fuller mouth (I as E, U as O) after its first
    # two frames, so a chorus reads as sung from the back of the room
    k = 0
    while k < n:
        v, j = out[k][0], k
        while j + 1 < n and out[j + 1][0] == v:
            j += 1
        if v in ("I", "U") and j - k + 1 >= 6:
            for q in range(k + 2, j + 1):
                out[q][0] = "E" if v == "I" else "O"
        k = j + 1
    return out
