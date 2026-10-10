"""The steps of a web episode the engine's own CLI (python3 -m studio.film) doesn't have.

    python3 -m studio.web.steps SHOW show-cast  a show's cast cut out (shows/<slug>/show.json)
    python3 -m studio.web.steps SLUG cast       cut, upscale and measure every drawing the cast is filmed in
                                                (studio.film.art); fetch the speech models the voices need
    python3 -m studio.web.steps SLUG voices     the stand-in voices (Kokoro) for characters with no recording, then
                                                every line cut word-exact from its take or recording, with its
                                                phones for the lip sync -> build/lines/, build/lines.json
    python3 -m studio.web.steps SLUG stills [T ...]   frames at T s (default: the middle of every shot)
    python3 -m studio.web.steps SLUG finish --draft   after a draft render: build/preview.mp4 -> <slug>_preview.mp4"""
import hashlib
import json
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

from studio.film import ep
from studio.paths import ROOT

MAXGAP = 0.22


def load(slug):
    d = ep.use(slug)
    from studio.web.auto import normalize
    sp = normalize(json.loads((d / "studio.json").read_text()))
    cast = {c["id"]: c for c in sp["cast"]}
    lines = [ln for ln in sp["lines"] if ln.get("text", "").strip() and ln.get("who") in cast]
    return d, sp, cast, lines


def voice_of(c):
    return c.get("voice") or dict(kind="tts", voice="bm_george", speed=1.0)


def cast(slug):
    from studio.film import art
    d, sp, cast, lines = load(slug)
    if not cast:
        raise SystemExit("nobody is cast: add characters to the scene")
    if not lines:
        raise SystemExit("there are no lines: write the script")
    for cid, c in cast.items():
        name = c.get("drawing") or "front"
        print(f"{cid}: {name}", flush=True)
        art.build(cid, [name])
    kinds = {voice_of(cast[ln["who"]])["kind"] for ln in lines}
    need = (["tts"] if "tts" in kinds else []) + (["whisper"] if "recording" in kinds else [])
    if need:
        subprocess.run(["bash", str(ROOT / "tools" / "fetch_models.sh")] + need, check=True)


# ---------------------------------------------------------------- words the aligner doesn't know
LETTERS = [("tion", "SH AH N"), ("sion", "ZH AH N"), ("ough", "AO"), ("ight", "AY T"), ("igh", "AY"), ("tch", "CH"),
           ("sch", "S K"), ("ph", "F"), ("sh", "SH"), ("ch", "CH"), ("th", "TH"), ("ck", "K"), ("ng", "NG"),
           ("qu", "K W"), ("wh", "W"), ("kn", "N"), ("wr", "R"), ("ee", "IY"), ("ea", "IY"), ("oo", "UW"),
           ("ou", "AW"), ("ow", "OW"), ("oi", "OY"), ("oy", "OY"), ("ai", "EY"), ("ay", "EY"), ("au", "AO"),
           ("aw", "AO"), ("ie", "IY"), ("ei", "EY"), ("er", "ER"), ("ir", "ER"), ("ur", "ER"), ("ar", "AA R"),
           ("or", "AO R"), ("a", "AE"), ("e", "EH"), ("i", "IH"), ("o", "AA"), ("u", "AH"), ("y", "IY"), ("b", "B"),
           ("c", "K"), ("d", "D"), ("f", "F"), ("g", "G"), ("h", "HH"), ("j", "JH"), ("k", "K"), ("l", "L"),
           ("m", "M"), ("n", "N"), ("p", "P"), ("q", "K"), ("r", "R"), ("s", "S"), ("t", "T"), ("v", "V"),
           ("w", "W"), ("x", "K S"), ("z", "Z")]
DIGITS = {"0": "Z IH R OW", "1": "W AH N", "2": "T UW", "3": "TH R IY", "4": "F AO R", "5": "F AY V", "6": "S IH K S",
          "7": "S EH V AH N", "8": "EY T", "9": "N AY N"}


def guess(word):
    """a rough pronunciation from the spelling: enough for forced alignment to find the word's edges"""
    w = re.sub(r"e$", "", word) if len(word) > 3 else word
    out, i = [], 0
    while i < len(w):
        if w[i] in DIGITS:
            out.append(DIGITS[w[i]])
            i += 1
            continue
        for a, b in LETTERS:
            if w.startswith(a, i):
                out.append(b)
                i += len(a)
                break
        else:
            i += 1
        if out and len(out) > 1 and out[-1] == out[-2]:
            out.pop()
    return " ".join(out) or "AH"


def extra_words(texts):
    from pocketsphinx import Decoder
    from studio.film.voices import EXTRA, words_of
    d = Decoder(samprate=16000, loglevel="FATAL")
    out = {}
    for t in texts:
        for w in words_of(t):
            if w not in EXTRA and w not in out and d.lookup_word(w) is None:
                out[w] = guess(w)
    if out:
        print("pronunciations guessed for: " + ", ".join(f"{w} ({p})" for w, p in out.items()), flush=True)
    return out


# ---------------------------------------------------------------- the lines
def signature(d, cast, lines):
    """what the cut lines depend on: the words, who says them, the voices and the recordings"""
    rec = sorted((p.name, p.stat().st_size, p.stat().st_mtime) for p in (d / "voiceovers").glob("*")) \
        if (d / "voiceovers").exists() else []
    what = [(ln["id"], ln["who"], ln["text"], voice_of(cast[ln["who"]])) for ln in lines]
    return hashlib.sha256(json.dumps([what, rec], sort_keys=True).encode()).hexdigest()


def voices(slug, force=False):
    from studio.film import voices as V
    d, sp, cast, lines = load(slug)
    sig = signature(d, cast, lines)
    if not force and ep.path("lines.json").exists() and ep.path("lines.sig").exists() \
            and ep.path("lines.sig").read_text() == sig:
        print("the lines are already cut (nothing they depend on has changed)")
        return
    extra = extra_words([ln["text"] for ln in lines])
    out = {}
    # stand-in voices: one take per line, spoken by Kokoro and cached by what was said and how
    tts = [ln for ln in lines if voice_of(cast[ln["who"]])["kind"] == "tts"]
    if tts:
        from studio.episode import tts as K
        ids = K.speaker_ids()
        tdir = ep.path("tts")
        tdir.mkdir(parents=True, exist_ok=True)
        takes = []
        for ln in tts:
            v = voice_of(cast[ln["who"]])
            voice = v.get("voice") if v.get("voice") in ids else "bm_george"
            speed = float(v.get("speed") or 1.0)
            key = hashlib.sha256(f"{voice}|{speed}|{ln['text']}".encode()).hexdigest()[:16]
            f = tdir / f"{ln['id']}-{key}.wav"
            if not f.exists():
                x = K.speak(ln["text"], voice, speed, ids)
                sf.write(f, x, K.SR, subtype="PCM_16")
            print(f"{ln['id']} {ln['who']}: spoken by {voice}", flush=True)
            takes.append((ln["id"], ln["who"], ln["text"], f, None, 1))
        out.update(V.build(ep.BUILD, takes, MAXGAP, {}, 1.0, extra))
    # recordings: each character's lines read in order into one file, found and cut word-exact
    recs = []
    for cid, c in cast.items():
        v = voice_of(c)
        if v["kind"] == "recording":
            files = v.get("files") or ([v["file"]] if v.get("file") else [])
            fs = [d / "voiceovers" / f for f in files]
            if not fs or not all(f.exists() for f in fs):
                raise SystemExit(f"{cid}: their recording is missing; upload it or give them a stand-in voice")
            recs += [(f, cid) for f in fs]
    if recs:
        want = {ln["id"] for ln in lines if voice_of(cast[ln["who"]])["kind"] == "recording"}
        script = [(ln["id"], ln["who"], ln["text"]) for ln in lines]
        out.update(V.from_recordings(ep.BUILD, recs, script, want, MAXGAP, {}, 1.0, extra))
    ordered = {ln["id"]: out[ln["id"]] for ln in lines if ln["id"] in out}
    ep.path("lines.json").write_text(json.dumps(ordered, indent=1))
    ep.path("lines.sig").write_text(sig)
    print(f"{len(ordered)} lines, {sum(v['dur'] for v in ordered.values()):.1f} s of dialogue", flush=True)


def finish(slug, draft):
    """a draft is rendered as the engine's preview (render --range: the finished film is left alone) and kept
    beside the episode as <slug>_preview.mp4 (git-ignored)"""
    d = ep.use(slug)
    if draft and ep.path("preview.mp4").exists():
        ep.path("preview.mp4").replace(d / f"{slug}_preview.mp4")
        print(d / f"{slug}_preview.mp4")


def stills(slug, ts):
    """frames to look at (960 x 540 by default): the moments given, or one in the middle of every shot"""
    import importlib
    d = ep.use(slug)
    sys.path.insert(0, str(d))
    from studio.film.__main__ import prepare
    prepare()
    if not ts:
        D = importlib.import_module("film.direction")
        ts = [round((s["t"] + s["end"]) / 2, 2) for s in D.SHOTS][:16]
    from studio.film import render
    for p in render.still(ts, ep.path("stills")):
        print(p, flush=True)


def show_cast(slug):
    """a show's cast cut out as soon as the show is read, so its first episode starts sooner"""
    from studio.film import art
    from studio.paths import SHOWS
    sh = json.loads((SHOWS / slug / "show.json").read_text())
    for c in sh.get("cast", []):
        print(f"{c['id']}: {c.get('drawing') or 'front'}", flush=True)
        try:
            art.build(c["id"], [c.get("drawing") or "front"])
        except Exception as e:  # noqa: BLE001  (one bad drawing doesn't stop the rest; the episode will say)
            print(f"{c['id']}: could not be cut out: {e}", flush=True)


def main():
    slug, cmd = sys.argv[1], sys.argv[2]
    if cmd == "show-cast":
        return show_cast(slug)
    if cmd == "cast":
        cast(slug)
    elif cmd == "voices":
        voices(slug, "--force" in sys.argv)
    elif cmd == "stills":
        stills(slug, [float(t) for t in sys.argv[3:]])
    elif cmd == "finish":
        finish(slug, "--draft" in sys.argv)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
