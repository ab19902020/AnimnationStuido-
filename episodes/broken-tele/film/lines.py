"""Which take each scripted line comes from. The boy is the real recording (voiceovers/01-family-boy.m4a: three
takes of "TV's broken"; the first, flat, for the first telly, the third, long and drawn out, for the second, and
the second, rising like a question, for the projector after the title). Mum, Dad and the shop assistant are
Kokoro text-to-speech stand-ins (studio.episode.tts) until their voices are recorded.
-> build/takes/<id>.wav, then build/lines/<id>.wav and build/lines.json"""
import re
import subprocess

import numpy as np
import soundfile as sf

from studio.film import ep

SCRIPT = ep.DIR / "script.md"
KID = ep.DIR / "voiceovers" / "01-family-boy.m4a"
SPEAKER = {"BOY": "boy", "MUM": "mum", "DAD": "dad", "SHOP": "shop"}
# the boy's takes in his recording (s): each one whole, from just before its first word to just after its last
KID_TAKES = {"L004": (0.47, 2.42), "L019": (6.78, 9.45), "L025": (3.50, 5.52)}
# his words, timed by hand from the spectrogram (s in the take): the aligner can't follow a three-year-old, and
# cuts off his long "ken". T / V's / bro / ken are separate puffs of voice in every take
KID_WORDS = {"L004": [("tv's", 0.08, 0.78, "T IY V IY Z"), ("broken", 0.86, 1.83, "B R OW K AH N")],
             "L019": [("tv's", 0.13, 0.75, "T IY V IY Z"), ("broken", 1.07, 2.46, "B R OW OW K AH N")],
             "L025": [("tv's", 0.10, 0.85, "T IY V IY Z"), ("broken", 0.95, 1.90, "B R OW K AH N")]}
# stand-in voices (Kokoro): British, a spread of pitch; speed per line where the delivery wants it
VOICE = {"mum": ("bf_emma", 1.0), "dad": ("bm_george", 1.0), "shop": ("bm_lewis", 1.08)}
SPEED = {"L003": 0.86, "L005": 0.92, "L010": 1.05, "L011": 1.08, "L013": 0.82, "L017": 0.9, "L020": 0.85,
         "L022": 0.98, "L023": 0.88, "L024": 0.62}
# what the voice is asked to say, where the script's spelling is not how it should sound
SAY = {"L018": "What the fuck", "L024": "Don't. You. Dare."}
CUT_AT = {"L018": ("fuck", 0.09)}       # cut off inside this word, this far in (s): "What the f..."
IDS = [f"L{n:03d}" for n in range(1, 26)]
MAXGAP = 0.30          # pauses inside a line are trimmed to this
GAPS = {"L011": 0.42, "L022": 0.38, "L024": 0.55, "L009": 0.36}
TEMPO = 1.0
EXTRA = {"tv's": "T IY V IY Z", "hiya": "HH AY Y AH", "mummy": "M AH M IY", "telly": "T EH L IY",
         "fuck's": "F AH K S", "could've": "K UH D AH V", "f": "F AH"}


def script():
    """every scripted line in order: [(id, speaker, text)]"""
    return [(lid, SPEAKER[spk], text) for lid, spk, text in
            re.findall(r"^\[(L\d+)\]\s+([A-Z]+):\s*(.+)$", SCRIPT.read_text(), re.M)]


def kid_take(lid, out):
    a, b = KID_TAKES[lid]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(KID), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32)[int(a * 48000):int(b * 48000)].copy()
    y -= y.mean()
    n = int(0.01 * 48000)
    y[:n] *= np.linspace(0, 1, n)
    y[-n:] *= np.linspace(1, 0, n)
    sf.write(out, y, 48000)


def tts_take(lid, spk, text, out):
    from studio.episode import tts
    voice, speed = VOICE[spk]
    x = tts.speak(SAY.get(lid, text), voice, SPEED.get(lid, speed), tts.speaker_ids())
    if lid in CUT_AT:                      # broken off mid-word
        from studio.film.voices import align_samples, words_of
        import librosa
        al = align_samples(librosa.resample(x, orig_sr=tts.SR, target_sr=16000), words_of(SAY.get(lid, text)), EXTRA)
        w, dt = CUT_AT[lid]
        s = next(v["s"] for v in al["words"] if v["w"] == w) + dt
        x = x[:int(s * tts.SR)]
        n = int(0.012 * tts.SR)
        x[-n:] *= np.linspace(1, 0, n)
    sf.write(out, x, tts.SR)


def lines():
    """[(id, speaker, text, take, None, 1)]: every line is its own take, made here once"""
    d = ep.path("takes")
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for lid, spk, text in script():
        if lid not in IDS:
            continue
        f = d / f"{lid}.wav"
        if not f.exists():
            kid_take(lid, f) if spk == "boy" else tts_take(lid, spk, text, f)
        words = None
        out.append((lid, spk, SAY.get(lid, text) if lid not in CUT_AT else "What the f", f, words, 1))
    return out


def after(build):
    """the boy's lines: his whole takes, with the hand-timed words and their phones spread evenly over each word"""
    import json
    import shutil
    lj = build / "lines.json"
    L = json.loads(lj.read_text())
    for lid, words in KID_WORDS.items():
        f = build / "takes" / f"{lid}.wav"
        shutil.copyfile(f, build / "lines" / f"{lid}.wav")
        y, sr = sf.read(f)
        ws, ps = [], []
        for i, (w, a, b, arpa) in enumerate(words):
            ph = arpa.split()
            ws.append({"w": w, "s": a, "e": b, "ph": ph})
            d = (b - a) / len(ph)
            ps += [{"p": p, "w": i, "s": round(a + k * d, 3), "e": round(a + (k + 1) * d, 3)} for k, p in enumerate(ph)]
        L[lid].update(dur=round(len(y) / sr, 3), words=ws, phones=ps)
        print(f"{lid:8s} boy      {len(y) / sr:5.2f}s  (whole take, words timed by hand)")
    lj.write_text(json.dumps(L, indent=1))
