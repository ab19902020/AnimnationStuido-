"""Make an episode the All or Something way.

    python3 -m studio.film SLUG lines                 cut every line from its take: build/lines/, lines.json
    python3 -m studio.film SLUG song                  a music video's song: beats, hits, singing (build/song.json)
    python3 -m studio.film SLUG timeline              print the dialogue edit (marks, line times)
    python3 -m studio.film SLUG sound                 the mix: build/episode_audio.wav
    python3 -m studio.film SLUG still T [T ...]       single frames: build/stills/
    python3 -m studio.film SLUG render [--jobs N]     the film: episodes/<slug>/<slug>.mp4 (with the mix); N = cores
                      [--chunks K]      in K pieces, N at a time, the most crowded first (default 6 per job),
                                        as many at once as FILM_MEM_GB (default 12.5) allows
                      [--resume]        keep the pieces a failed render finished
                      [--range A B]     only seconds A to B, to look at: build/preview.mp4
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
                keys.update(a["draw"] if isinstance(a, dict) else a[1] for a in val)
            if kind == "sticks" and val.get("fist"):
                keys.add(val["fist"])
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


def fit(path, limit_mb=95.0):
    """a finished film is committed, and the repository takes files under 100 MB: if the encode came out bigger
    (lights, haze and moving crowds cost bits), the full-quality master is kept as build/master.mp4 and the film is
    re-encoded in two passes to fit"""
    size = path.stat().st_size / 1e6
    if size <= limit_mb:
        return
    master = ep.path("master.mp4")
    path.replace(master)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(master)], capture_output=True, text=True, check=True).stdout)
    kbps = int(limit_mb * 8000 * 0.97 / dur) - 192                  # the video's share, the audio at 192k
    log = str(ep.path("fit"))
    common = ["-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-b:v", f"{kbps}k", "-passlogfile", log]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(master)] + common + ["-pass", "1", "-an", "-f", "mp4",
                                                                                         os.devnull], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(master)] + common
                   + ["-pass", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                      str(path)], check=True)
    print(f"{path}: {size:.0f} MB encode refitted to {path.stat().st_size / 1e6:.0f} MB (master: {master})")


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
        if (d / "song-timing.json").exists():
            ep.path("song.json").write_bytes((d / "song-timing.json").read_bytes())
            print("Using the checked-in merged performance timing")
            return
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
        f0 = 0
        preview = "--range" in args                     # a stretch only: --range A B (seconds) -> build/preview.mp4
        if preview:
            i = args.index("--range")
            f0, n = int(float(args[i + 1]) * FPS), int(float(args[i + 2]) * FPS)
        # the film in many short chunks, `jobs` of them rendering at a time: shots differ a lot in cost (a crowd of
        # twenty faces against a close-up), and short chunks keep every core busy to the end
        nch = int(args[args.index("--chunks") + 1]) if "--chunks" in args else (6 * jobs if not preview else jobs)
        q = (n - f0 + nch - 1) // nch
        ranges = [(f0 + k * q, min(n, f0 + (k + 1) * q)) for k in range(nch) if f0 + k * q < n]
        # one thread per job: the jobs share the cores instead of fighting over them
        env = dict(os.environ, FILM_EPISODE=slug, PYTHONPATH=f"{d}:{os.getcwd()}", OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", FILM_THREADS="1")
        import time
        D = importlib.import_module("film.direction")

        def people(a, b):                                # the most people any frame of a stretch has on screen
            return max(sum(len(v) for kd, v in D.shot_at(f / FPS).get("layers", []) if kd == "actors")
                       for f in range(a, b, 15))

        def cost(a, b):                                  # a frame costs more the more people are in it
            return sum(1 + 0.12 * sum(len(v) for kd, v in D.shot_at(f / FPS).get("layers", []) if kd == "actors")
                       for f in range(a, b, 15))

        def peak_gb(a, b):                               # what a chunk grows to: every drawing it meets stays loaded
            return 1.6 + 0.15 * people(a, b)              # (measured: 3.6 GB for a crowd of fourteen)

        budget = float(os.environ.get("FILM_MEM_GB", 12.5))   # the session's limit is 14.3 GB, encoders included
        # resume: a chunk already rendered (its part and a .done for the same frames) is not rendered again
        done = set()
        if "--resume" in args:
            for k, (a, b) in enumerate(ranges):
                dk = ep.path(f"part{k}.done")
                if dk.exists() and dk.read_text().split() == [str(a), str(b)] and ep.path(f"part{k}.mp4").exists():
                    done.add(k)
            if done:
                print(f"resuming: {len(done)} of {len(ranges)} chunks already rendered")
        for k in range(len(ranges)):
            if k not in done:
                ep.path(f"part{k}.done").unlink(missing_ok=True)
        # the heaviest chunks first, so the cores finish together, as many at once as the cores and the memory allow
        waiting = sorted(((k, r) for k, r in enumerate(ranges) if k not in done), key=lambda kr: -cost(*kr[1]))
        running, failed = [], []
        while waiting or running:
            while waiting and len(running) < jobs:
                use = sum(g for _, _, g in running)
                pick = next((i for i, (k, r) in enumerate(waiting) if use + peak_gb(*r) <= budget), None)
                if pick is None:
                    if running:
                        break
                    pick = 0                             # alone it must run whatever it costs
                k, (a, b) = waiting.pop(pick)
                log = open(ep.path(f"render{k}.log"), "w")
                running.append((k, subprocess.Popen([sys.executable, "-m", "studio.film.render", "chunk", str(a), str(b),
                                                     str(ep.path(f"part{k}.mp4"))], env=env, stdout=log, stderr=log),
                                peak_gb(a, b)))
            time.sleep(2)
            for item in list(running):
                k, p, _ = item
                if p.poll() is not None:
                    running.remove(item)
                    if p.returncode:
                        failed.append(k)
                    else:
                        ep.path(f"part{k}.done").write_text(f"{ranges[k][0]} {ranges[k][1]}")
            if failed:
                for _, p, _ in running:
                    p.kill()
                break
        if failed:
            raise SystemExit("render failed: see " + ", ".join(str(ep.path(f"render{k}.log")) for k in failed))
        ep.path("parts.txt").write_text("".join(f"file 'part{k}.mp4'\n" for k in range(len(ranges))))
        out = ep.path("preview.mp4") if preview else d / f"{slug}.mp4"
        audio = ep.path("episode_audio.wav")
        a_in = ["-ss", f"{f0 / FPS:.3f}", "-i", str(audio)] if preview else ["-i", str(audio)]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(ep.path("parts.txt"))]
                       + a_in + ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", os.environ.get("FILM_CRF", "20"),
                                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags",
                                 "+faststart", str(out)], check=True)
        if not preview:
            fit(out)
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
