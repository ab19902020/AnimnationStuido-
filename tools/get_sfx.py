"""Fetch and trim the sound effects listed in library/audio/sfx/manifest.json into library/audio/sfx/<category>/
<name>.ogg (48 kHz Vorbis, 5 ms fades). A clip is a BigSoundBank sound ("id", CC0) or any file by "url" (Wikimedia
Commons CC0 recordings, with their "license"), trimmed from "start" to "end" seconds. Clips already present are
skipped; --force rebuilds them. To add a sound: find a CC0 recording, add its entry, run this.

    python3 tools/get_sfx.py [--force] [category/name ...]"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SFX = Path(__file__).resolve().parent.parent / "library" / "audio" / "sfx"


def main():
    man = json.loads((SFX / "manifest.json").read_text())
    force = "--force" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    cache = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, c in man.items():
            if name.startswith("_") or (only and name not in only):
                continue
            out = SFX / f"{name}.ogg"
            if out.exists() and not force:
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            key = c.get("url") or c["id"]
            src = cache.get(key)
            if src is None:
                src = str(Path(tmp) / (f"src{len(cache)}" + Path(key.split("?")[0]).suffix))
                url = c.get("url") or f"https://bigsoundbank.com/UPLOAD/mp3/{c['id']}.mp3"
                subprocess.run(["curl", "-sSL", "--fail", "--retry", "4", "--retry-delay", "5", "--max-time", "180",
                                "-A", "AnimationStudioTool/1.0 (cartoon production)", "-o", src, url], check=True)
                cache[key] = src
            d = c["end"] - c["start"]
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(c["start"]), "-t", str(d), "-i", src,
                            "-af", f"afade=t=in:d=0.005,afade=t=out:st={max(0, d - 0.005):.3f}:d=0.005",
                            "-ar", "48000", "-c:a", "libvorbis", "-q:a", "6", str(out)], check=True)
            print(name, f"{d:.2f}s", c["title"])


if __name__ == "__main__":
    main()
