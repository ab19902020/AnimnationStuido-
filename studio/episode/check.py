"""Check a rendered animatic against its script.

    python3 -m studio.episode.check SLUG [--video]

  timeline   lines in order with no overlap; every beat of the script is on it
  cues       no sound cue lands on top of speech (the whistle is never played)
  words      every line is cut out of the final mix (build/master.wav) at its place on the timeline, run through
             speech recognition, and compared with the script's words: a wrong or missing take, a take in the wrong
             place, or a cue masking a word shows up as a high error rate on that line
  mouths     in the picture's own state, the speaker's mouth moves for most of their line and nobody else's moves
  video      (--video) the file's size, frame rate and length against the soundtrack"""
import argparse
import json
import subprocess
import sys

import numpy as np
import soundfile as sf
import yaml

from studio.episode import asr, script, sfx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--no-words", action="store_true")
    a = ap.parse_args()
    ep = script.episode_dir(a.slug)
    tl = json.loads((ep / "build" / "timeline.json").read_text())
    items = tl["items"]
    problems = []

    scenes = script.load(a.slug)
    want = [b.id for sc in scenes for b in sc.beats]
    got = [i["id"] for i in items]
    if want != got:
        problems.append(f"timeline beats differ from the script: missing {sorted(set(want) - set(got))[:5]}")
    for x, y in zip(items, items[1:]):
        if y["start"] < x["end"] - 1e-6:
            problems.append(f"{x['id']} overlaps {y['id']}")
    print(f"timeline: {len(items)} beats, story {tl['end_of_story']:.1f}s, total {tl['total']:.1f}s", file=sys.stderr)

    cues = yaml.safe_load((ep / "cues.yaml").read_text())["cues"]
    byid = {i["id"]: i for i in items}
    lines = [i for i in items if i["kind"] == "line"]
    for c in cues:
        t = byid[c["at"]]["start" if c["from"] == "start" else "end"] + c["offset"]
        dur = len(sfx.SFX[c["sfx"]]()) / sfx.SR
        for l in lines:
            if l["start"] < t + dur and t < l["end"]:
                problems.append(f"cue {c['sfx']} at {t:.2f}s ({c['at']}) overlaps {l['id']}")
    print(f"cues: {len(cues)} placed, {sum('overlaps' in p for p in problems)} overlap speech", file=sys.stderr)

    from studio.episode.stage import FPS, Stage
    stage = Stage(a.slug)
    dead, talkers = [], 0
    for l in lines:
        frames = np.arange(l["start"] + 0.05, l["end"] - 0.05, 1 / FPS)
        states = [stage.at(t)["chars"] for t in frames]
        moving = np.mean([s[l["speaker"]]["mouth"] not in ("X", "A") for s in states])
        others = max(np.mean([s[n]["mouth"] != "X" for s in states]) for n in stage.names if n != l["speaker"])
        if moving < 0.5:
            dead.append(f"{l['id']} {l['speaker']}: mouth open only {moving * 100:.0f}% of the line")
        if others > 0:
            talkers += 1
            dead.append(f"{l['id']}: another character's mouth moves during {l['speaker']}'s line")
    problems += dead
    print(f"mouths: {len(lines) - len(dead)}/{len(lines)} lines have the right mouth moving", file=sys.stderr)

    if not a.no_words:
        x, sr = sf.read(ep / "build" / "master.wav", dtype="float32")
        import tempfile
        worst = []
        errs = []
        for l in lines:
            seg = x[int(max(0, l["start"] - 0.05) * sr):int((l["end"] + 0.05) * sr)]
            with tempfile.NamedTemporaryFile(suffix=".wav") as f:
                sf.write(f.name, seg, sr)
                hyp = asr.transcribe(f.name)
            e = asr.wer(l["text"], hyp)
            errs.append(e)
            worst.append((e, l["id"], l["text"], hyp))
        worst.sort(reverse=True)
        print(f"words: mean error {np.mean(errs) * 100:.1f}%, {sum(e == 0 for e in errs)}/{len(errs)} lines exact; worst:", file=sys.stderr)
        for e, i, ref, hyp in worst[:6]:
            print(f"   {i} {e * 100:4.0f}%  said {hyp!r}   (script {ref!r})", file=sys.stderr)
        problems += [f"{i}: {e * 100:.0f}% of the words wrong in the mix" for e, i, _, _ in worst if e > 0.35]

    if a.video:
        f = ep / f"{a.slug.replace('-', '_')}_preview_tts.mp4"
        pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(f)],
                                       capture_output=True, text=True, check=True).stdout)
        v = next(s for s in pr["streams"] if s["codec_type"] == "video")
        au = next(s for s in pr["streams"] if s["codec_type"] == "audio")
        n, d = map(int, v["r_frame_rate"].split("/"))
        dur = float(pr["format"]["duration"])
        print(f"video: {v['width']}x{v['height']} {n / d:g} fps, {dur:.1f}s, audio {au['codec_name']} {au['sample_rate']} Hz, "
              f"{int(pr['format']['size']) / 1e6:.0f} MB", file=sys.stderr)
        if (v["width"], v["height"]) != (1920, 1080) or abs(n / d - 24) > 0.01:
            problems.append("video is not 1920x1080 at 24 fps")
        if abs(dur - (tl["total"] + 0.5)) > 0.2:
            problems.append(f"video length {dur:.1f}s differs from the soundtrack {tl['total'] + 0.5:.1f}s")
    print("OK" if not problems else f"{len(problems)} problem(s):", file=sys.stderr)
    for p in problems:
        print("  " + p, file=sys.stderr)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
