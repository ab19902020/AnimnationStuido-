"""The dialogue edit's raw material: every scripted line as its own audio cut, with word and phone timings.

Each line comes either from its own take (a text-to-speech stand-in or a recorded line: the whole file is the
line) or from a longer recording (the line's words found inside it). Word + phone timings come from forced
alignment (pocketsphinx, en-us) against the line's words, so a wrong transcript fails loudly instead of
mis-syncing. Cuts snap to the quietest point next to the first / last word; pauses inside a line longer than
MAXGAP are shortened to it (no dead air); TEMPO speeds every line up without changing pitch.

Recordings that hold many lines (an actor reading their sheet: one file per character, or a few) are imported by
`from_recordings`: each file is split at its pauses, every stretch is heard by Whisper and placed in the script by
word alignment (so takes may run lines together, add an "ah", or split a line at a pause), then the lines are
force-aligned and cut word-exact.

Output: <episode>/build/lines/<id>.wav (48 kHz mono) and <episode>/build/lines.json
{id: {speaker, dur, text, words: [{w, s, e}], phones: [{p, s, e}]}} with times relative to the cut."""
import hashlib
import json
import re
import subprocess
import tempfile

import librosa
import numpy as np
import soundfile as sf

SR = 48000
# words the pocketsphinx dictionary lacks (ARPAbet); an episode adds its own
EXTRA = {"midfielders": "M IH D F IY L D ER Z", "saudi": "S AW D IY", "monaco": "M AA N AH K OW",
         "carrick": "K AE R IH K", "fourteens": "F AO R T IY N Z", "cristiano": "K R IH S T IY AA N OW",
         "pep": "P EH P", "micah": "M AY K AH", "keane": "K IY N", "neville": "N EH V IH L",
         "lineker": "L IH N AH K ER", "guardiola": "G W AA R D IY OW L AH", "ronaldo": "R AH N AA L D OW"}
NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
       "8": "eight", "9": "nine"}


def words_of(text):
    t = text.lower().replace("-", " ").replace("—", " ").replace("’", "'")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    return [w.strip("'") for w in t.split() if w.strip("'")]


def align_samples(y16, words, extra=None):
    """forced alignment of 16 kHz mono samples against a word list -> {dur, words, phones}"""
    from pocketsphinx import Decoder
    pcm = (np.clip(y16, -1, 1) * 32767).astype(np.int16).tobytes()
    d = Decoder(samprate=16000, bestpath=False, loglevel="FATAL")
    for w, ph in {**EXTRA, **(extra or {})}.items():
        if d.lookup_word(w) is None:
            d.add_word(w, ph, True)
    unknown = [w for w in words if d.lookup_word(w) is None]
    if unknown:
        raise KeyError(f"not in the pronouncing dictionary (add to EXTRA): {unknown}")
    d.set_align_text(" ".join(words))
    d.start_utt()
    d.process_raw(pcm, full_utt=True)
    d.end_utt()
    d.set_alignment()
    d.start_utt()
    d.process_raw(pcm, full_utt=True)
    d.end_utt()
    out_w, out_p = [], []
    for wseg in d.get_alignment():
        name = re.sub(r"\(\d+\)$", "", wseg.name)
        if name in ("<sil>", "<s>", "</s>", "[NOISE]"):
            continue
        i = len(out_w)
        ps = [(p.name, p.start / 100, (p.start + p.duration) / 100) for p in wseg]
        out_w.append({"w": name, "s": wseg.start / 100, "e": (wseg.start + wseg.duration) / 100, "ph": [p[0] for p in ps]})
        out_p += [{"p": n, "w": i, "s": s, "e": e} for n, s, e in ps]
    got = [w["w"] for w in out_w]
    if got != words:
        raise ValueError(f"alignment does not match the words: {got} != {words}")
    return {"dur": len(y16) / 16000, "words": out_w, "phones": out_p}


def quiet_point(y, sr, a, b):
    """time of the lowest-energy 20 ms window between a and b (seconds)"""
    if b - a < 0.03:
        return (a + b) / 2
    i0, i1 = int(a * sr), int(b * sr)
    seg = y[i0:i1] ** 2
    w = int(0.02 * sr)
    if len(seg) <= w:
        return (a + b) / 2
    e = np.convolve(seg, np.ones(w) / w, mode="valid")
    return (i0 + int(np.argmin(e)) + w // 2) / sr


def tempo(seg, k):
    """speed a cut up by k without changing its pitch (ffmpeg atempo)"""
    if abs(k - 1) < 1e-3:
        return seg
    with tempfile.TemporaryDirectory() as d:
        sf.write(f"{d}/a.wav", seg.astype(np.float32), SR)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{d}/a.wav", "-filter:a", f"atempo={k}", "-ar", str(SR),
                        f"{d}/b.wav"], check=True)
        return sf.read(f"{d}/b.wav", dtype="float32")[0]


def cut(y, W, P, i, j, maxgap, k):
    """words i..j of an aligned recording y (SR) -> (samples, words, phones) with times relative to the cut"""
    s, e = W[i]["s"], W[j]["e"]
    prev_e = W[i - 1]["e"] if i > 0 else 0.0
    next_s = W[j + 1]["s"] if j + 1 < len(W) else len(y) / SR
    cs = quiet_point(y, SR, max(prev_e, s - 0.10), s) if s - prev_e > 0.04 else max(0.0, s - 0.02)
    ce = quiet_point(y, SR, e, min(next_s, e + 0.14)) if next_s - e > 0.04 else e
    keep, a = [], cs
    for q in range(i, j):
        g0, g1 = W[q]["e"], W[q + 1]["s"]
        L = g1 - g0
        if L > maxgap + 0.05:
            qp = quiet_point(y, SR, g0 + 0.04, g1 - 0.04)
            c = L - maxgap
            r0 = min(max(g0 + 0.02, qp - c / 2), g1 - 0.02 - c)
            keep.append((a, r0))
            a = r0 + c
    keep.append((a, ce))
    f = int(0.008 * SR)
    parts, tmap, t = [], [], 0.0
    for k0, k1 in keep:
        p = y[int(k0 * SR):int(k1 * SR)].copy()
        if len(p) > 2 * f:
            p[:f] *= np.linspace(0, 1, f)
            p[-f:] *= np.linspace(1, 0, f)
        parts.append(p)
        tmap.append((k0, k1, t))
        t += len(p) / SR

    def T(x):
        for k0, k1, o in tmap:
            if x <= k1:
                return o + max(0.0, x - k0)
        return tmap[-1][2] + x - tmap[-1][0]

    seg = tempo(np.concatenate(parts), k)
    phones = [dict(p=p["p"], s=round(T(p["s"]) / k, 3), e=round(T(p["e"]) / k, 3)) for p in P if i <= p["w"] <= j]
    words = [dict(w=w["w"], s=round(T(w["s"]) / k, 3), e=round(T(w["e"]) / k, 3)) for w in W[i:j + 1]]
    return seg, words, phones


def find(W, seq, occ):
    n, c = len(seq), 0
    for i in range(len(W) - n + 1):
        if [w["w"] for w in W[i:i + n]] == seq:
            c += 1
            if c == occ:
                return i, i + n - 1
    raise KeyError(" ".join(seq))


def build(out_dir, lines, maxgap=0.2, gaps=None, k=1.0, extra=None):
    """lines: [(id, speaker, text, source, words, occurrence)]: source = an audio file; words = the words to take
    from it (None: the whole take is the line). -> lines.json dict"""
    (out_dir / "lines").mkdir(parents=True, exist_ok=True)
    out = {}
    cache = {}
    for lid, spk, text, src, words, occ in lines:
        if src not in cache:
            y, _ = librosa.load(src, sr=SR, mono=True)
            y16 = librosa.resample(y, orig_sr=SR, target_sr=16000)
            take_words = words_of(text) if words is None else None
            al = align_samples(y16, take_words or words_of(words), extra) if words is None else None
            cache[src] = (y, y16, al)
        y, y16, al = cache[src]
        if al is None:
            raise NotImplementedError("lines inside longer recordings: align the whole recording first")
        W, P = al["words"], al["phones"]
        i, j = 0, len(W) - 1
        seg, ws, ps = cut(y, W, P, i, j, (gaps or {}).get(lid, maxgap), k)
        sf.write(out_dir / "lines" / f"{lid}.wav", seg.astype(np.float32), SR)
        out[lid] = dict(speaker=spk, dur=round(len(seg) / SR, 3), text=text, words=ws, phones=ps)
        print(f"{lid:8s} {spk:8s} {len(seg) / SR:5.2f}s  {text}")
    (out_dir / "lines.json").write_text(json.dumps(out, indent=1))
    return out


# ---------------------------------------------------------------- recordings with many lines in them
def stretches(y16, min_pause=0.35, top_db=38):
    """the speech in a recording, split where it pauses for at least min_pause s -> [[start, end]] (s)"""
    out = []
    for a, b in librosa.effects.split(y16, top_db=top_db, frame_length=1024, hop_length=160):
        a, b = a / 16000, b / 16000
        if out and a - out[-1][1] < min_pause:
            out[-1][1] = b
        elif b - a >= 0.08:
            out.append([a, b])
    if top_db > 20:                      # a noisy take (a hiss under the voice) that never falls silent: split long
        long = []                        # stretches against a tighter threshold (Whisper hears 30 s at most)
        for a, b in out:
            if b - a > 20:
                long += [[a + s, a + e] for s, e in stretches(y16[int(a * 16000):int(b * 16000)], min_pause * 0.6,
                                                               top_db - 14)]
            else:
                long.append([a, b])
        out = long
    return out


def heard(path, y16, cache_dir):
    """Whisper's transcript of each speech stretch of a recording (cached by the file's hash) -> [[s, e, text]]"""
    from studio.episode.asr import recognizer
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    cf = cache_dir / f"{sha}.json"
    if cf.exists():
        return json.loads(cf.read_text())
    out = []
    for a, b in stretches(y16):
        x = np.concatenate([np.zeros(4000, np.float32), y16[int(a * 16000):int(b * 16000)], np.zeros(8000, np.float32)])
        st = recognizer().create_stream()
        st.accept_waveform(16000, x)
        recognizer().decode_stream(st)
        out.append([round(a, 3), round(b, 3), st.result.text.strip()])
    cache_dir.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(out, indent=1))
    return out


def _pair(a, b):
    """align recognised words a against script words b, the script free to start and end anywhere (a file holds a
    run of the script) -> for each script word, the index of the recognised word it pairs with, or None"""
    n, m = len(a), len(b)
    D = np.zeros((n + 1, m + 1), np.int32)
    D[1:, 0] = np.arange(1, n + 1)
    for i in range(1, n + 1):
        ai, Di, Dp = a[i - 1], D[i], D[i - 1]
        for j in range(1, m + 1):
            Di[j] = min(Dp[j - 1] + (ai != b[j - 1]), Dp[j] + 1, Di[j - 1] + 1)
    j = int(np.argmin(D[n]))
    i, out = n, [None] * m
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (a[i - 1] != b[j - 1]):
            out[j - 1] = i - 1
            i, j = i - 1, j - 1
        elif D[i, j] == D[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return out


def locate(chunks, lines):
    """which stretches of a recording each scripted line is in. chunks: [[s, e, text]]; lines: [(id, text)] in the
    order the actor read them -> {id: (first stretch, last stretch, share of its words heard)}"""
    from studio.episode.asr import words as norm
    a, a_chunk = [], []
    for c, (_, _, text) in enumerate(chunks):
        ws = norm(text)
        a += ws
        a_chunk += [c] * len(ws)
    b, b_line = [], []
    for k, (_, text) in enumerate(lines):
        ws = norm(text)
        b += ws
        b_line += [k] * len(ws)
    pairs = _pair(a, b)
    out = {}
    for k, (lid, _) in enumerate(lines):
        js = [j for j in range(len(b)) if b_line[j] == k]
        got = [pairs[j] for j in js if pairs[j] is not None]
        hits = sum(1 for j in js if pairs[j] is not None and a[pairs[j]] == b[j])
        if got and hits / max(1, len(js)) >= 0.5:
            out[lid] = (a_chunk[min(got)], a_chunk[max(got)], hits / len(js))
    return out


def from_recordings(out_dir, recordings, script, want, maxgap=0.2, gaps=None, k=1.0, extra=None):
    """cut the lines `want` out of recordings that each hold many lines.
    recordings: [(path, speaker)], the speaker's lines read in script order (one file or several);
    script: [(id, speaker, text)] every scripted line in order. -> lines.json dict"""
    (out_dir / "lines").mkdir(parents=True, exist_ok=True)
    out, found = {}, {}
    for path, spk in recordings:
        y, _ = librosa.load(str(path), sr=SR, mono=True)
        y16 = librosa.resample(y, orig_sr=SR, target_sr=16000)
        chunks = heard(path, y16, out_dir / "asr")
        mine = [(lid, text) for lid, sp, text in script if sp == spk]
        where = {lid: v for lid, v in locate(chunks, mine).items() if lid in want and lid not in found}
        order = [lid for lid, _ in mine if lid in where]
        # lines that share a stretch are aligned together (an actor running two lines into one breath)
        groups = []
        for lid in order:
            if groups and where[lid][0] <= where[groups[-1][-1]][1]:
                groups[-1].append(lid)
            else:
                groups.append([lid])
        text = dict(mine)
        for g in groups:
            c0, c1 = where[g[0]][0], max(where[lid][1] for lid in g)
            a = max(chunks[c0 - 1][1] + 0.02 if c0 > 0 else 0.0, chunks[c0][0] - 0.15)
            b = min(chunks[c1 + 1][0] - 0.02 if c1 + 1 < len(chunks) else len(y) / SR, chunks[c1][1] + 0.15)
            yg = y[int(a * SR):int(b * SR)]
            ws = [words_of(text[lid]) for lid in g]
            al = align_samples(y16[int(a * 16000):int(b * 16000)], sum(ws, []), extra)
            W, P = al["words"], al["phones"]
            i = 0
            for lid, w in zip(g, ws):
                seg, wl, pl = cut(yg, W, P, i, i + len(w) - 1, (gaps or {}).get(lid, maxgap), k)
                i += len(w)
                sf.write(out_dir / "lines" / f"{lid}.wav", seg.astype(np.float32), SR)
                found[lid] = dict(speaker=spk, dur=round(len(seg) / SR, 3), text=text[lid], words=wl, phones=pl,
                                  source=f"{path.name} {a + wl[0]['s']:.2f}s")
                print(f"{lid:8s} {spk:8s} {len(seg) / SR:5.2f}s  {path.name} @{a:6.2f}s  {text[lid]}")
    missing = [lid for lid in want if lid not in found]
    if missing:
        raise KeyError(f"not found in any recording: {missing}")
    for lid, *_ in script:
        if lid in found:
            out[lid] = found[lid]
    (out_dir / "lines.json").write_text(json.dumps(out, indent=1))
    return out
