"""Make an episode the All or Something way.

    python3 -m studio.film SLUG lines                 cut every line from its take: build/lines/, lines.json
    python3 -m studio.film SLUG timeline              print the dialogue edit (marks, line times)
    python3 -m studio.film SLUG sound                 the mix: build/episode_audio.wav
    python3 -m studio.film SLUG still T [T ...]       single frames: build/stills/
    python3 -m studio.film SLUG render [--jobs N]     the film: episodes/<slug>/<slug>.mp4 (with the mix)
    python3 -m studio.film SLUG check                 re-hear every line in the finished mix (Whisper)
EP_RES=960x540 makes quick low-resolution stills and previews."""
import json
import math
import os
import subprocess
import sys

from studio.film import ep


def main():
    slug, cmd, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    d = ep.use(slug)
    sys.path.insert(0, str(d))
    if cmd == "lines":
        import importlib
        from studio.film import voices
        L = importlib.import_module("film.lines")
        if hasattr(L, "RECORDINGS"):           # the actors' recordings, many lines to a file
            voices.from_recordings(ep.BUILD, L.RECORDINGS, L.script(), set(L.IDS), L.MAXGAP, L.GAPS, L.TEMPO,
                                   getattr(L, "EXTRA", None))
        else:                                  # one take per line (text-to-speech stand-ins)
            voices.build(ep.BUILD, L.lines(), L.MAXGAP, L.GAPS, L.TEMPO, getattr(L, "EXTRA", None))
    elif cmd == "timeline":
        import importlib
        TL = importlib.import_module("film.timeline").TL
        print("total", TL["total"])
        for k, v in sorted(TL["marks"].items(), key=lambda kv: kv[1]):
            print(f"  mark {v:7.2f} {k}")
        for k, v in TL["lines"].items():
            print(f"  line {v['start']:7.2f} {v['end']:7.2f} {k} {v['speaker']}")
    elif cmd == "sound":
        import importlib
        importlib.import_module("film.sound").main()
    elif cmd == "still":
        from studio.film import render
        for p in render.still([float(a) for a in args], ep.path("stills")):
            print(p)
    elif cmd == "render":
        import importlib
        from studio.film.engine import FPS
        TL = importlib.import_module("film.timeline").TL
        jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 3
        n = int(math.ceil(TL["total"] * FPS))
        q = (n + jobs - 1) // jobs
        procs = []
        env = dict(os.environ, FILM_EPISODE=slug, PYTHONPATH=f"{d}:{os.getcwd()}")
        for k in range(jobs):
            a, b = k * q, min(n, (k + 1) * q)
            log = open(ep.path(f"render{k}.log"), "w")
            procs.append(subprocess.Popen([sys.executable, "-m", "studio.film.render", "chunk", str(a), str(b),
                                           str(ep.path(f"part{k}.mp4"))], env=env, stdout=log, stderr=log))
        for p in procs:
            p.wait()
        ep.path("parts.txt").write_text("".join(f"file 'part{k}.mp4'\n" for k in range(jobs)))
        out = d / f"{slug}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(ep.path("parts.txt")),
                        "-i", str(ep.path("episode_audio.wav")), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                        "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
        print(out)
    elif cmd == "check":
        from studio.film import audio
        audio.check_words()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
