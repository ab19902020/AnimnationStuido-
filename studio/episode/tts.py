"""Text to speech for test runs, before the real voices are recorded.

    python3 -m studio.episode.tts SLUG [--lines L001 L002 ...] [--force]
        episodes/<slug>/build/tts/<line id>.wav     one file per spoken line, 24 kHz mono
        episodes/<slug>/build/tts/tts.json          what was said, by whom, with which voice, and how long it is

Kokoro (82M, via sherpa-onnx; fetch it with `tools/fetch_models.sh tts`) speaks each line with the voice and speed
the episode's cast.yaml gives that speaker. Each take is trimmed to its speech, with a few frames of room either
side, and levelled so no character is louder than another. These are stand-ins that set the timing: the voices
cannot do the accents or the acting."""
import argparse
import json
import re
import sys
import time

import numpy as np
import soundfile as sf

from studio.episode import script
from studio.paths import MODELS

SR = 24000
KOKORO = MODELS / "kokoro-multi-lang-v1_0"
TARGET_RMS = 0.075            # about -22.5 dBFS while speaking
PAD = 0.04                    # seconds of room kept either side of the speech

# spelled as it should sound; the script's own wording on screen and in captions is untouched
SAY = [(r"\bTED Talk\b", "Ted Talk"), (r"\bCris\b", "Chris"), (r"\bCristiano\b", "Cris-tee-ah-no")]


def say(text):
    for a, b in SAY:
        text = re.sub(a, b, text)
    return text


class Voice:
    """a Kokoro engine for one accent (the British voices use the British lexicon)"""
    _engines = {}

    @classmethod
    def engine(cls, british):
        import sherpa_onnx as so
        if british not in cls._engines:
            lex = KOKORO / ("lexicon-gb-en.txt" if british else "lexicon-us-en.txt")
            kokoro = so.OfflineTtsKokoroModelConfig(
                model=str(KOKORO / "model.onnx"), voices=str(KOKORO / "voices.bin"), tokens=str(KOKORO / "tokens.txt"),
                lexicon=str(lex), data_dir=str(KOKORO / "espeak-ng-data"), dict_dir=str(KOKORO / "dict"))
            model = so.OfflineTtsModelConfig(kokoro=kokoro, num_threads=4, provider="cpu")
            cls._engines[british] = so.OfflineTts(so.OfflineTtsConfig(model=model, max_num_sentences=1))
        return cls._engines[british]


def speaker_ids():
    import onnxruntime as ort
    s = ort.InferenceSession(str(KOKORO / "model.onnx"), providers=["CPUExecutionProvider"])
    names = s.get_modelmeta().custom_metadata_map["speaker_names"].split(",")
    return {n: i for i, n in enumerate(names)}


def speak(text, voice, speed, ids):
    """one take: float32 samples at SR, trimmed and levelled"""
    eng = Voice.engine(voice.startswith("b"))
    g = eng.generate(say(text), sid=ids[voice], speed=speed)
    x = np.asarray(g.samples, np.float32)
    assert g.sample_rate == SR, g.sample_rate
    return level(trim(x))


def trim(x, floor=0.012):
    loud = np.nonzero(np.abs(x) > floor)[0]
    if not len(loud):
        return x
    pad = int(PAD * SR)
    return x[max(0, loud[0] - pad):loud[-1] + pad]


def level(x):
    """scale to a common loudness while speaking (the RMS of the frames above the noise floor), never clipping"""
    frames = x[: len(x) // 480 * 480].reshape(-1, 480)
    rms = np.sqrt((frames ** 2).mean(1))
    speech = rms[rms > 0.02]
    if not len(speech):
        return x
    g = TARGET_RMS / float(np.sqrt((speech ** 2).mean()))
    return np.clip(x * min(g, 0.95 / max(1e-6, float(np.abs(x).max()))), -1, 1)


def build_dir(slug):
    d = script.episode_dir(slug) / "build" / "tts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def render(slug, only=None, force=False):
    """speak every line of the episode (or just `only`); returns the manifest {id: {...}}"""
    cast = script.load_cast(slug)
    ids = speaker_ids()
    out = build_dir(slug)
    manifest = json.loads((out / "tts.json").read_text()) if (out / "tts.json").exists() else {}
    t0, done = time.time(), 0
    for sc in script.load(slug):
        for ln in sc.lines:
            if only and ln.id not in only:
                continue
            c = cast[ln.speaker]
            want = dict(speaker=ln.speaker, character=c["character"], voice=c["voice"], speed=c.get("speed", 1.0), text=ln.text)
            old = manifest.get(ln.id)
            if old and not force and all(old.get(k) == v for k, v in want.items()) and (out / f"{ln.id}.wav").exists():
                continue
            x = speak(ln.text, c["voice"], c.get("speed", 1.0), ids)
            sf.write(out / f"{ln.id}.wav", x, SR, subtype="PCM_16")
            manifest[ln.id] = dict(want, scene=ln.scene, file=f"{ln.id}.wav", seconds=round(len(x) / SR, 3), sample_rate=SR)
            done += 1
            print(f"{ln.id} {ln.speaker:8s} {len(x) / SR:5.2f}s  {ln.text[:60]}", file=sys.stderr, flush=True)
    (out / "tts.json").write_text(json.dumps(manifest, indent=1))
    print(f"{done} spoken in {time.time() - t0:.0f}s; {len(manifest)} lines in {out}", file=sys.stderr)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--lines", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    render(a.slug, set(a.lines) if a.lines else None, a.force)


if __name__ == "__main__":
    main()
