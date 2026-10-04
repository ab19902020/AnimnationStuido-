"""Lay an episode out in time: spoken lines (from the voice takes) and stage-direction holds.

    python3 -m studio.episode.timeline SLUG       # writes episodes/<slug>/build/timeline.json and prints the scenes

Every beat of the script, in order, gets a start and end: a line lasts as long as its take; a stage direction is a
silent hold sharing out its scene's allowance (pack/Scene_Timing.csv) by the weights and minimums in beats.yaml,
so every insert is held long enough to read. Lines follow each other with a short gap (longer for the same speaker),
plus any reaction pause beats.yaml asks for. Nothing overlaps: the recordings decide the pace, and this is only
the order and the room round them."""
import csv
import json
import sys

import yaml

from studio.episode import script
from studio.episode.script import Direction, Line


def allowances(slug):
    with open(script.episode_dir(slug) / "pack" / "Scene_Timing.csv", encoding="utf-8") as f:
        return {int(r["scene"]): float(r["visual_and_reaction_allowance_seconds"]) for r in csv.DictReader(f)}


def build(slug):
    ep = script.episode_dir(slug)
    scenes = script.load(slug)
    tts = json.loads((ep / "build" / "tts" / "tts.json").read_text())
    cfg = yaml.safe_load((ep / "beats.yaml").read_text())
    allow = allowances(slug)
    cast = script.load_cast(slug)
    items, t = [], cfg["lead_in"]
    scene_span = {}
    for sc in scenes:
        start = t
        holds = {b.id: cfg["holds"].get(b.id, {"w": 1.0, "min": 1.0}) for b in sc.beats if isinstance(b, Direction)}
        total_w = sum(h["w"] for h in holds.values()) or 1.0
        hold_s = {i: max(h.get("min", 0.0), allow.get(sc.n, 0.0) * h["w"] / total_w) for i, h in holds.items()}
        for k, b in enumerate(sc.beats):
            if isinstance(b, Line):
                d = tts[b.id]["seconds"]
                items.append(dict(id=b.id, kind="line", scene=sc.n, start=round(t, 3), end=round(t + d, 3), speaker=b.speaker,
                                  character=cast[b.speaker]["character"], text=b.text, file=tts[b.id]["file"]))
                t += d
                nxt = sc.beats[k + 1] if k + 1 < len(sc.beats) else None
                if isinstance(nxt, Line):
                    t += cfg["gap"]["same_speaker" if nxt.speaker == b.speaker else "other_speaker"]
                elif nxt is not None:
                    t += 0.15
                t += cfg["pauses"].get(b.id, 0.0)
            else:
                d = hold_s[b.id]
                items.append(dict(id=b.id, kind="hold", scene=sc.n, start=round(t, 3), end=round(t + d, 3), text=b.text))
                t += d
        scene_span[sc.n] = (round(start, 3), round(t, 3))
    end = round(t, 3)
    out = dict(slug=slug, speech_seconds=round(sum(i["end"] - i["start"] for i in items if i["kind"] == "line"), 2),
               end_of_story=end, end_card=cfg["end_card"], total=round(end + cfg["end_card"], 3),
               scenes={n: dict(start=a, end=b, guide=list(next(s for s in scenes if s.n == n).guide)) for n, (a, b) in scene_span.items()},
               items=items)
    (ep / "build").mkdir(exist_ok=True)
    (ep / "build" / "timeline.json").write_text(json.dumps(out, indent=1))
    return out


def main():
    tl = build(sys.argv[1])
    print(f"speech {tl['speech_seconds']:.1f}s  story {tl['end_of_story']:.1f}s  with end card {tl['total']:.1f}s "
          f"({int(tl['total'] // 60)}:{tl['total'] % 60:04.1f})   guide 333.9s")
    for n, s in tl["scenes"].items():
        print(f"  scene {n}: {s['start']:6.1f}-{s['end']:6.1f}  ({s['end'] - s['start']:5.1f}s)   guide {s['guide'][0]}-{s['guide'][1]}  ({s['guide'][1] - s['guide'][0]}s)")


if __name__ == "__main__":
    main()
