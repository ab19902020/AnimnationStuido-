"""Make an episode the All or Something way.

    python3 -m studio.film SLUG lines                 cut every line from its take: build/lines/, lines.json
    python3 -m studio.film SLUG song                  a music video's song: beats, hits, singing (build/song.json)
    python3 -m studio.film SLUG timeline              print the dialogue edit (marks, line times)
    python3 -m studio.film SLUG sound                 the mix: build/episode_audio.wav
    python3 -m studio.film SLUG still T [T ...]       single frames: build/stills/
    python3 -m studio.film SLUG render [--jobs N]     the film: episodes/<slug>/<slug>.mp4 (with the mix); N = cores
    python3 -m studio.film SLUG check                 re-hear every line in the finished mix (Whisper)
    python3 -m studio.film SLUG sheet                 a contact sheet of every shot: build/contact.jpg
    python3 -m studio.film SLUG lips                  the mouths at the stressed words and closures: build/lips.jpg
EP_RES=960x540 makes quick low-resolution stills and previews."""
import json
import math
import os
import subprocess
import sys

from studio.film import ep


def prepare():
    """what the picture needs that is built once and cached: every drawing the shots use (studio.film.art: cut,
    upscaled, face landmarks) and every plate's 4x upscale. Run before the parallel render jobs start."""
    import importlib
    from studio.film import art, render
    from studio.paths import BUILD
    D = importlib.import_module("film.direction")
    keys = set()
    for s in D.SHOTS:
        if ":" in str(s.get("draw", "")):
            keys.add(s["draw"])
        keys.update(a[1] for a in s.get("actors", []))
        for kind, val in s.get("layers", []):
            if kind == "actors":
                keys.update(a[1] for a in val)
    keys.update(getattr(D, "DRAW", {}).values())
    need = {}
    for k in sorted(keys):
        cid, name = k.split(":")
        mf = BUILD / "film" / cid / "meta.json"
        if not (BUILD / "film" / cid / f"{name}.png").exists() or name not in (json.loads(mf.read_text()) if mf.exists() else {}):
            need.setdefault(cid, []).append(name)
    for cid, names in need.items():
        print(f"preparing {cid}: {' '.join(names)} (check build/film/{cid}_check.jpg)")
        art.build(cid, names)
    for k in D.PLATES:
        render.plate(k)


def contact_sheet(slug, d):
    """every shot of the finished film as three frames (just after the cut, the middle, just before the next cut),
    two shots to a row, labelled with the shot's number and times -> build/contact.jpg"""
    import importlib
    import cv2
    import numpy as np
    D = importlib.import_module("film.direction")
    cap = cv2.VideoCapture(str(d / f"{slug}.mp4"))
    W, H = 320, 180
    tiles = []
    for s in D.SHOTS:
        for t in (s["t"] + 0.12, (s["t"] + s["end"]) / 2, s["end"] - 0.1):
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
            ok, fr = cap.read()
            fr = cv2.resize(fr, (W, H), interpolation=cv2.INTER_AREA) if ok else np.zeros((H, W, 3), np.uint8)
            label = f"{s['i'] + 1:02d} {s['kind']} {s.get('who') or ''} {t:5.2f}s"
            cv2.putText(fr, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(fr, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 240, 255), 1, cv2.LINE_AA)
            tiles.append(fr)
    while len(tiles) % 6:
        tiles.append(np.zeros((H, W, 3), np.uint8))
    rows = [np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]
    out = ep.path("contact.jpg")
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(out)


def lip_sheet(slug, d):
    """the mouths of the finished film at the words that test them: each line's stressed words (open shapes) and
    its first M / B / P (a closed mouth), cropped to the speaker's face in close singles -> build/lips.jpg"""
    import importlib
    import cv2
    import numpy as np
    from studio.film.engine import OW
    D = importlib.import_module("film.direction")
    P = importlib.import_module("film.perf")
    TL = importlib.import_module("film.timeline").TL
    L = json.loads(ep.path("lines.json").read_text())
    cap = cv2.VideoCapture(str(d / f"{slug}.mp4"))
    vw = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or OW
    k = vw / 1920.0
    tiles = []
    for lid, v in TL["lines"].items():
        stressed = set(P.META.get(lid, ("", "", []))[2])
        ws = L[lid]["words"]
        pick = [w for w in ws if w["w"] in stressed][:3]
        pick += [w for w in ws if w["w"][0] in "mbp"][:1]
        for w in pick:
            t = v["start"] + (w["s"] + w["e"]) / 2 if w["w"] in stressed else v["start"] + w["s"] + 0.03
            s = D.shot_at(t)
            if s["kind"] != "single" or s["who"] != v["speaker"]:
                continue
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            ex, ey, ed = s["eye"][0] * k, s["eye"][1] * k, s["ed"] * k
            x0, x1 = int(max(0, ex - 2.0 * ed)), int(min(fr.shape[1], ex + 2.0 * ed))
            y0, y1 = int(max(0, ey - 1.2 * ed)), int(min(fr.shape[0], ey + 2.8 * ed))
            tile = cv2.resize(fr[y0:y1, x0:x1], (240, 240), interpolation=cv2.INTER_AREA)
            label = f"{lid} {w['w']} {t:.2f}"
            cv2.putText(tile, label, (5, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(tile, label, (5, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 240, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
    while len(tiles) % 8:
        tiles.append(np.zeros((240, 240, 3), np.uint8))
    out = ep.path("lips.jpg")
    cv2.imwrite(str(out), np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, len(tiles), 8)]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(out)


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
    elif cmd == "song":                        # a music video: the beat grid, hits and singing mouths
        from studio.film import song
        src = next(p for p in (d / "song.wav", d / "song.mp3", d / "song.flac") if p.exists())
        song.analyse(src, ep.BUILD)
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
        prepare()
        from studio.film import render
        for p in render.still([float(a) for a in args], ep.path("stills")):
            print(p)
    elif cmd == "render":
        import importlib
        from studio.film.engine import FPS
        prepare()
        TL = importlib.import_module("film.timeline").TL
        jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else (os.cpu_count() or 4)
        n = int(math.ceil(TL["total"] * FPS))
        q = (n + jobs - 1) // jobs
        procs = []
        # one thread per job: the jobs share the cores instead of fighting over them
        env = dict(os.environ, FILM_EPISODE=slug, PYTHONPATH=f"{d}:{os.getcwd()}", OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", FILM_THREADS="1")
        for k in range(jobs):
            a, b = k * q, min(n, (k + 1) * q)
            log = open(ep.path(f"render{k}.log"), "w")
            procs.append(subprocess.Popen([sys.executable, "-m", "studio.film.render", "chunk", str(a), str(b),
                                           str(ep.path(f"part{k}.mp4"))], env=env, stdout=log, stderr=log))
        for p in procs:
            p.wait()
        failed = [k for k, p in enumerate(procs) if p.returncode]
        if failed:
            raise SystemExit("render failed: see " + ", ".join(str(ep.path(f"render{k}.log")) for k in failed))
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
    elif cmd == "sheet":
        contact_sheet(slug, d)
    elif cmd == "lips":
        lip_sheet(slug, d)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
