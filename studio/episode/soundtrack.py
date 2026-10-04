"""Mix the episode's soundtrack from its timeline: the voice takes where the timeline puts them, the sound cues
from cues.yaml placed against their beats, and room tone cut dead where the cues say.

    python3 -m studio.episode.soundtrack SLUG
        episodes/<slug>/build/master.wav       48 kHz mono, the whole film
        episodes/<slug>/build/captions.srt     the spoken lines, timed"""
import json
import sys

import numpy as np
import soundfile as sf
import yaml
from scipy.signal import resample_poly

from studio.episode import script, sfx

SR = sfx.SR


def db(x):
    return 10 ** (x / 20.0)


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def beat_time(items, beat, frm, offset):
    it = items[beat]
    return (it["start"] if frm == "start" else it["end"]) + offset


def mix(slug):
    ep = script.episode_dir(slug)
    tl = json.loads((ep / "build" / "timeline.json").read_text())
    cues = yaml.safe_load((ep / "cues.yaml").read_text())
    items = {i["id"]: i for i in tl["items"]}
    total = tl["total"] + 0.5
    out = np.zeros(int(total * SR) + SR, np.float32)

    def put(x, t, gain=1.0):
        i = int(round(t * SR))
        n = min(len(x), len(out) - i)
        if n > 0 and i >= 0:
            out[i:i + n] += x[:n] * gain

    rt = cues["room_tone"]
    cut = beat_time(items, rt["cut_at"], rt["cut_from"], rt["cut_offset"])
    tone = sfx.room_tone(cut) * db(rt["gain_db"])
    fade = int(0.01 * SR)
    tone[-fade:] *= np.linspace(1, 0, fade)           # cut dead, not faded: just enough to avoid a click
    put(tone, 0.0)
    for it in tl["items"]:
        if it["kind"] == "line":
            x, sr = sf.read(ep / "build" / "tts" / it["file"], dtype="float32")
            put(resample_poly(x, SR // sr, 1).astype(np.float32), it["start"])
    for c in cues["cues"]:
        put(sfx.SFX[c["sfx"]](), beat_time(items, c["at"], c["from"], c["offset"]), db(c["gain_db"]))
    peak = float(np.abs(out).max())
    if peak > 0.95:
        out *= 0.95 / peak
    out = out[:int(total * SR)]
    sf.write(ep / "build" / "master.wav", out, SR, subtype="PCM_16")
    lines = [i for i in tl["items"] if i["kind"] == "line"]
    srt = "\n".join(f"{n}\n{srt_time(i['start'])} --> {srt_time(i['end'])}\n{i['speaker'].title()}: {i['text']}\n"
                    for n, i in enumerate(lines, 1))
    (ep / "build" / "captions.srt").write_text(srt, encoding="utf-8")
    return total, peak


def main():
    total, peak = mix(sys.argv[1])
    print(f"master.wav {total:.1f}s, peak {peak:.2f}")


if __name__ == "__main__":
    main()
