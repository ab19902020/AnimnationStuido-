"""Read an episode's director script (episodes/<slug>/script.md) into scenes made of spoken lines and stage directions.

    python3 -m studio.episode.script SLUG        # prints the structure and checks it against pack/Dialogue.json

The markdown has `## SCENE N — TITLE` headings, an optional `**Guide time: ...**` line, `**INT. ...**` slug lines,
italic paragraphs that are stage directions, and dialogue lines `[L001] GARY: text`. Everything from the first
`---` rule after `**END.**` is production material, not script. Speaker names (GARY) map to library characters in
episodes/<slug>/cast.yaml."""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from studio.paths import EPISODES

LINE = re.compile(r"^\[(L\d+)\]\s+([A-Z]+):\s*(.+)$")
SCENE = re.compile(r"^##\s+SCENE\s+(\d+)\s+[—-]\s+(.+?)\s*$")
GUIDE = re.compile(r"Guide time:\s*(\d+):(\d+)\s*[–-]\s*(\d+):(\d+)")


@dataclass
class Line:
    id: str
    scene: int
    speaker: str
    text: str


@dataclass
class Direction:
    id: str            # D<scene>.<n>, counted within the scene
    scene: int
    text: str


@dataclass
class Scene:
    n: int
    title: str
    location: str = ""
    guide: tuple = (0.0, 0.0)
    beats: list = field(default_factory=list)

    @property
    def lines(self):
        return [b for b in self.beats if isinstance(b, Line)]


def tidy(s):
    return s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').strip()


def episode_dir(slug):
    return EPISODES / slug


def load_cast(slug):
    """{SPEAKER: {character, outfit, voice, speed}} from episodes/<slug>/cast.yaml"""
    return yaml.safe_load((episode_dir(slug) / "cast.yaml").read_text())


def load(slug):
    """the episode's scenes, in order"""
    scenes, cur = [], None
    for raw in (episode_dir(slug) / "script.md").read_text().splitlines():
        s = raw.strip()
        m = SCENE.match(s)
        if m:
            cur = Scene(int(m.group(1)), tidy(m.group(2)))
            scenes.append(cur)
            continue
        if cur is None:
            continue
        if s == "**END.**":
            break
        g = GUIDE.search(s)
        if g:
            a, b, c, d = map(int, g.groups())
            cur.guide = (a * 60 + b, c * 60 + d)
        elif s.startswith("**INT.") or s.startswith("**EXT."):
            cur.location = s.strip("*").strip()
        elif LINE.match(s):
            i, who, text = LINE.match(s).groups()
            cur.beats.append(Line(i, cur.n, who, tidy(text)))
        elif s.startswith("*") and s.endswith("*") and len(s) > 2:
            n = sum(isinstance(b, Direction) for b in cur.beats) + 1
            cur.beats.append(Direction(f"D{cur.n}.{n}", cur.n, tidy(s.strip("*"))))
    return scenes


def check(slug, scenes):
    """compare with the pack's Dialogue.json: same lines, same speakers, same words. Returns a list of problems."""
    pack = json.loads((episode_dir(slug) / "pack" / "Dialogue.json").read_text())
    want = {l["id"]: l for l in pack["lines"]}
    got = {l.id: l for sc in scenes for l in sc.lines}
    problems = [f"{i}: in the pack, not in the script" for i in sorted(set(want) - set(got))]
    problems += [f"{i}: in the script, not in the pack" for i in sorted(set(got) - set(want))]
    for i in sorted(set(want) & set(got)):
        w, g = want[i], got[i]
        if w["character"] != g.speaker or tidy(w["text"]) != g.text or int(w["scene"]) != g.scene:
            problems.append(f"{i}: differs ({w['character']} {w['text']!r} vs {g.speaker} {g.text!r})")
    return problems


def main():
    slug = sys.argv[1]
    scenes = load(slug)
    for sc in scenes:
        print(f"Scene {sc.n}: {sc.title}  [{sc.location}]  guide {sc.guide}  {len(sc.lines)} lines, "
              f"{sum(isinstance(b, Direction) for b in sc.beats)} directions")
    problems = check(slug, scenes)
    print(f"{sum(len(s.lines) for s in scenes)} lines;", "matches pack/Dialogue.json" if not problems else f"{len(problems)} problems")
    for p in problems:
        print("  ", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
