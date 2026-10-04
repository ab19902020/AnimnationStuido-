"""Mouth-shape timing for every spoken line, from the audio and the words (Rhubarb Lip Sync 1.14;
`tools/fetch_models.sh rhubarb`).

    python3 -m studio.episode.lipsync SLUG [--lines L001 ...] [--force]
        episodes/<slug>/build/lipsync/<line id>.json      the cues for one line
        episodes/<slug>/build/lipsync.json                {line id: [[start, end, shape], ...]} in the line's own seconds

Shapes are Rhubarb's: X rest, A closed (M B P), B teeth together (K S T and most consonants), C open (EH AE),
D wide open (AA), E rounded (AO ER), F pursed (UW OW W), G teeth on lip (F V), H tongue up (L)."""
import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import librosa
import soundfile as sf

from studio.episode import script
from studio.paths import MODELS

RHUBARB = MODELS / "rhubarb" / "rhubarb"


def cues_for(wav, text):
    """run Rhubarb on one take; returns [[start, end, shape], ...]"""
    x, sr = sf.read(wav, dtype="float32")
    with tempfile.TemporaryDirectory() as d:
        a, t, o = Path(d, "a.wav"), Path(d, "t.txt"), Path(d, "o.json")
        sf.write(a, librosa.resample(x, orig_sr=sr, target_sr=16000), 16000)
        t.write_text(text)
        subprocess.run([str(RHUBARB), "-q", "-f", "json", "-d", str(t), "-o", str(o), str(a)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return [[c["start"], c["end"], c["value"]] for c in json.loads(o.read_text())["mouthCues"]]


def run(slug, only=None, force=False, workers=4):
    ep = script.episode_dir(slug)
    out = ep / "build" / "lipsync"
    out.mkdir(parents=True, exist_ok=True)
    tts = json.loads((ep / "build" / "tts" / "tts.json").read_text())

    def one(i):
        f = out / f"{i}.json"
        if f.exists() and not force:
            return i, json.loads(f.read_text())
        c = cues_for(ep / "build" / "tts" / tts[i]["file"], tts[i]["text"])
        f.write_text(json.dumps(c))
        return i, c

    ids = [i for i in tts if not only or i in only]
    with ThreadPoolExecutor(workers) as ex:
        res = dict(ex.map(one, ids))
    allc = {i: res.get(i) or json.loads((out / f"{i}.json").read_text()) for i in tts}
    (ep / "build" / "lipsync.json").write_text(json.dumps(allc))
    return allc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--lines", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    c = run(a.slug, set(a.lines) if a.lines else None, a.force)
    shapes = {}
    for cues in c.values():
        for s, e, v in cues:
            shapes[v] = shapes.get(v, 0) + (e - s)
    print(f"{len(c)} lines;", "  ".join(f"{k} {v:.0f}s" for k, v in sorted(shapes.items())), file=sys.stderr)


if __name__ == "__main__":
    main()
