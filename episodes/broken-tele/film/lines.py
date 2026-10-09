"""Which take each scripted line comes from. The boy is the real recording (voiceovers/01-family-boy.m4a: three
takes of "TV's broken"; the first, flat, for the first telly, the third, long and drawn out, for the second, and
the second, rising like a question, for the projector after the title). Mum, Dad and the shop assistant each
read all their lines into one file (voiceovers/02-04), found and cut word-exact by studio.film.voices.
-> build/lines/<id>.wav and build/lines.json"""
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
# the actors' recordings: each reads all their lines in script order
VO = ep.DIR / "voiceovers"
RECORDINGS = [(VO / "02-family-mum.mp3", "mum"), (VO / "03-family-dad.mp3", "dad"),
              (VO / "04-shop-assistant.mp3", "shop")]
# the adults' lines (the boy's are added by after())
IDS = [f"L{n:03d}" for n in range(1, 26) if f"L{n:03d}" not in KID_TAKES]
MAXGAP = 0.18          # pauses inside a line are trimmed to this: snappy
GAPS = {"L011": 0.26, "L024": 0.38, "L005": 0.24, "L009": 0.22}
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


def after(build):
    """the boy's lines: his whole takes, with the hand-timed words and their phones spread evenly over each word"""
    import json
    import shutil
    lj = build / "lines.json"
    L = json.loads(lj.read_text())
    for lid, words in KID_WORDS.items():
        f = build / "takes" / f"{lid}.wav"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            kid_take(lid, f)
        shutil.copyfile(f, build / "lines" / f"{lid}.wav")
        y, sr = sf.read(f)
        ws, ps = [], []
        for i, (w, a, b, arpa) in enumerate(words):
            ph = arpa.split()
            ws.append({"w": w, "s": a, "e": b, "ph": ph})
            d = (b - a) / len(ph)
            ps += [{"p": p, "w": i, "s": round(a + k * d, 3), "e": round(a + (k + 1) * d, 3)} for k, p in enumerate(ph)]
        L[lid] = dict(speaker="boy", text=dict((i, t) for i, _, t in script())[lid], dur=round(len(y) / sr, 3),
                      words=ws, phones=ps)
        print(f"{lid:8s} boy      {len(y) / sr:5.2f}s  (whole take, words timed by hand)")
    order = [i for i, _, _ in script()]
    lj.write_text(json.dumps(dict(sorted(L.items(), key=lambda kv: order.index(kv[0]))), indent=1))
