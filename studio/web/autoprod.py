"""From a production pack to a web episode, with nobody choosing anything: the director's script, the characters'
pictures, the sets and the voice recordings, dropped together into episodes/<slug>/pack/, are read, filed and cast.

    python3 -m studio.web.autoprod SLUG        -> episodes/<slug>/studio.json, script.md, voiceovers/;
                                                  the report: episodes/<slug>/build/import.json

  * zips are unpacked
  * the script is the document with the most dialogue in it (.md, .txt, .fountain, .docx, .pdf). Scenes start at
    "## SCENE ..." headings or INT. / EXT. sluglines; lines are "[L001] NAME: text" (or "NAME: text"); the actor
    sheets that repeat lines are skipped; a stage direction between two lines is a beat (a pause); "(dry)" before a
    line is its delivery
  * every speaker is a character: a picture named for them (a new character, or a new drawing of one in the
    library), else the library character of that name (the script's full names tell the two Garys apart)
  * pictures that aren't characters are sets (landscape, no transparency): filed in the library, and each scene
    gets the set whose name best matches its slugline or heading (else the next uploaded set, else the last one)
  * each recording is given to the speaker it is named for (01-gary-neville.mp3, Roy.wav, L012.wav), else to the
    speaker whose lines Whisper hears in it; speakers with no recording get a stand-in voice
  * everyone who speaks in a scene stands in it, spread across the set in the order they first speak

What can't be worked out (a speaker with no picture and no library character) stops the import with a report
saying what to upload."""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from studio.paths import BACKGROUNDS, CHARACTERS, EPISODES, SHOWS
from studio.web import projects as P
from studio.web.auto import normalize

DOCS = (".md", ".txt", ".fountain", ".docx", ".pdf")
STAND_IN = ["bm_george", "bm_lewis", "bm_daniel", "am_michael", "bm_fable", "am_adam", "am_eric", "am_liam",
            "am_onyx", "am_puck"]
STAND_IN_F = ["bf_emma", "bf_isabella", "bf_alice", "af_heart", "af_bella", "bf_lily"]


def titled(s):
    """Title Case that leaves the letter after an apostrophe alone (Barry's, not Barry'S)"""
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split())


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2]


# ---------------------------------------------------------------- reading documents
def text_of(p):
    ext = p.suffix.lower()
    if ext == ".docx":
        xml = zipfile.ZipFile(p).read("word/document.xml").decode("utf8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        t = re.sub(r"<[^>]+>", "", xml)
        return re.sub(r"&amp;", "&", re.sub(r"&lt;", "<", re.sub(r"&gt;", ">", re.sub(r"&quot;", '"', re.sub(r"&apos;", "'", t)))))
    if ext == ".pdf":
        r = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True)
        return r.stdout
    return p.read_text(errors="replace")


NUMBERED = re.compile(r"^\s*[-*>]*\s*\[(L?\d+[a-z]?)\]\s*(?:\*\*)?([A-Za-z][\w .'’\-]{0,40}?)(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.+?)\s*$")
PLAIN = re.compile(r"^\s*(?:\*\*)?([A-Z][A-Z0-9 .'’\-]{0,30}?)(?:\*\*)?\s*(?:\(([^)]*)\))?\s*:\s*(?:\*\*)?\s*(.+?)\s*$")
SLUG = re.compile(r"^\s*(?:\*\*)?\s*((?:INT|EXT|INT\./EXT|I/E)\.?\s+.+?)\s*(?:\*\*)?\s*$")
SCENE_HEAD = re.compile(r"^\s*#{1,4}\s*(?:\*\*)?\s*(scene\b.*?)\s*(?:\*\*)?\s*$", re.I)
NOT_NAMES = {"NOTE", "NOTES", "INT", "EXT", "CUT TO", "FADE IN", "FADE OUT", "TITLE", "SUPER", "CAPTION", "TARGET",
             "SCENE", "GUIDE TIME", "THE STORY", "SPEAKING CAST", "TIMING GUIDE", "LOCATION", "SETTING"}


def clean_line(text):
    """the spoken words: no stage business in brackets or italics, no markdown"""
    tone = ""
    m = re.match(r"^\(([^)]*)\)\s*(.*)$", text)
    if m:
        tone, text = m.group(1).strip().lower(), m.group(2)
    text = re.sub(r"\*[^*]+\*", " ", text.replace("**", ""))
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
    return re.sub(r"\s+", " ", text).strip(), tone


def parse_script(text):
    """-> dict(title, show, scenes: [{name, location}], lines: [{id, name, text, tone, scene, beat}])"""
    from studio.film.perf import TAGS
    rows = text.splitlines()
    numbered = sum(1 for r in rows if NUMBERED.match(r)) >= 2
    title = show = ""
    scenes, lines, seen = [], [], set()
    beat = False
    started = False

    def new_scene(name="", loc=""):
        nonlocal beat
        if scenes and not any(ln["scene"] == len(scenes) - 1 for ln in lines):
            sc = scenes[-1]                                   # nothing said in it yet: it's still the same scene
            sc["name"] = sc["name"] or name
            sc["location"] = sc["location"] or loc
            return
        scenes.append(dict(name=name, location=loc))
        beat = False

    for r in rows:
        s = r.strip()
        if not s:
            continue
        if re.match(r"^#\s+\S", s):                               # a top-level heading
            if started:
                break                                             # the director's notes, the actor sheets
            if not title:
                title = s.lstrip("#").strip().strip("*")
            continue
        m = SCENE_HEAD.match(s)
        if m:
            started = True
            new_scene(re.sub(r"^scene\s*\d+\s*[—–:\-.]*\s*", "", m.group(1), flags=re.I).strip())
            continue
        m = SLUG.match(s)
        if m and len(s) < 90:
            started = True
            if scenes:
                new_scene(loc=m.group(1).strip(" .*"))
                scenes[-1]["location"] = scenes[-1]["location"] or m.group(1).strip(" .*")
            else:
                new_scene(loc=m.group(1).strip(" .*"))
            continue
        m = NUMBERED.match(s) if numbered else PLAIN.match(s)
        if m:
            if numbered:
                lid, name, raw = m.group(1), m.group(2), m.group(3)
                tone0 = ""
            else:
                name, tone0, raw = m.group(1), (m.group(2) or ""), m.group(3)
                lid = None
                if name.strip().upper() in NOT_NAMES or len(name.split()) > 3:
                    beat = True
                    continue
            if lid and lid in seen:
                continue                                          # an actor sheet repeating the line
            spoken, tone = clean_line(raw)
            if not spoken:
                continue
            if not scenes:
                scenes.append(dict(name="", location=""))
            started = True
            tone = (tone or tone0).strip().lower()
            lines.append(dict(id=lid, name=name.strip().upper(), text=spoken, tone=tone if tone in TAGS else "",
                              scene=len(scenes) - 1, beat=beat))
            if lid:
                seen.add(lid)
            beat = False
            continue
        if started and not s.startswith("#"):
            beat = True                                           # a stage direction: a beat before the next line
    if title:
        parts = re.split(r"\s+[—–:\-]\s+", title, maxsplit=1)
        if len(parts) == 2:
            show, title = parts[0].strip(), parts[1].strip()
    return dict(title=titled(title) if title.isupper() else title, show=titled(show) if show.isupper() else show,
                scenes=[sc for k, sc in enumerate(scenes) if any(ln["scene"] == k for ln in lines)] or [dict(name="", location="")],
                lines=_renumber_scenes(scenes, lines))


def _renumber_scenes(scenes, lines):
    used = sorted({ln["scene"] for ln in lines})
    for ln in lines:
        ln["scene"] = used.index(ln["scene"])
    return lines


# ---------------------------------------------------------------- what each picture is
def looks_like_set(p):
    """a set fills its frame (landscape, opaque, no paper round it); a character is drawn on paper or transparent"""
    im = Image.open(p)
    w, h = im.size
    if im.mode in ("RGBA", "LA", "P"):
        a = np.asarray(im.convert("RGBA"))[..., 3]
        if (a < 128).mean() > 0.02:
            return False
    if w < 1.2 * h:
        return False
    g = np.asarray(im.convert("L").resize((200, max(2, int(200 * h / w)))), np.float32)
    edge = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
    paper = (edge > 225).mean()
    return paper < 0.6


def find_figure(p):
    """the box of the first whole figure on a sheet (from the left): on a model sheet the front view comes first"""
    im = Image.open(p).convert("RGBA")
    rgb = np.asarray(Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("L"))
    h, w = rgb.shape
    import cv2
    ink = (rgb < 200).astype(np.uint8)
    ink = cv2.dilate(ink, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    figs = [st[k] for k in range(1, n) if st[k, 3] > 0.45 * h and st[k, 2] < 0.6 * w]
    if not figs:
        return [0, 0, w, h]
    x, y, ww, hh, _ = min(figs, key=lambda s: s[0])
    pad = 12
    return [int(max(0, x - pad)), int(max(0, y - pad)), int(min(w, x + ww + pad)), int(min(h, y + hh + pad))]


# ---------------------------------------------------------------- who is who
def library():
    out = []
    for y in sorted(CHARACTERS.glob("*/character.yaml")):
        c = yaml.safe_load(y.read_text()) or {}
        sp = P.film_spec(y.parent.name)
        nm = c.get("name") or y.parent.name
        out.append(dict(id=y.parent.name, name=nm, short=c.get("short", ""), drawings=list((sp.get("drawings") or {})),
                        keys={norm(y.parent.name), norm(nm), norm(c.get("short", "")), norm(nm.split()[0]),
                              norm(nm.split()[-1])} - {""}))
    return out


def full_name(name, text):
    """the speaker's full name as the script writes it (GARY -> Gary Neville), if it does"""
    t = name.title()
    m = re.findall(rf"\b{re.escape(t)}\s+((?:[A-Z][a-z’']+[ -]?){{1,2}})", text)
    if m:
        cnt = {}
        for x in m:
            x = x.strip()
            if x.lower() not in ("and", "the", "has", "is", "was", "says", "turns", "looks"):
                cnt[x] = cnt.get(x, 0) + 1
        if cnt:
            return f"{t} {max(cnt, key=cnt.get)}"
    return t


def match_library(name, full, text, lib):
    k = norm(name)
    cands = [c for c in lib if k in c["keys"] or norm(full) == norm(c["name"])]
    if not cands:
        return None
    exact = [c for c in cands if norm(c["name"]) == norm(full)]
    if exact:
        return exact[0]
    nt = norm(text)
    named = [c for c in cands if norm(c["name"]) in nt]
    pool = named or cands
    return max(pool, key=lambda c: (len(c["drawings"]) > 0, len(c["drawings"])))


def named_for(stem, name, full):
    s = norm(stem)
    return norm(full) in s or (len(norm(name)) > 2 and norm(name) in s)


# ---------------------------------------------------------------- the import
def unpack(pack):
    """zips in a pack unpacked beside it (and removed); -> every file in the pack"""
    for z in list(pack.rglob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir() and not Path(i.filename).name.startswith(".")
                     and "__MACOSX" not in Path(i.filename).parts]
            tops = {Path(i.filename).parts[0] for i in infos if len(Path(i.filename).parts) > 1}
            strip = len(tops) == 1 and all(len(Path(i.filename).parts) > 1 for i in infos)   # one folder inside
            for info in infos:
                name = Path(*Path(info.filename).parts[1:]) if strip else Path(info.filename)
                out = (pack / z.stem / name).resolve()
                if not str(out).startswith(str(pack.resolve())):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zf.read(info))
        z.unlink()
        print(f"unpacked {z.name}", flush=True)
    return [p for p in sorted(pack.rglob("*")) if p.is_file() and not p.name.startswith(".")]


def run(slug):
    d = EPISODES / slug
    pack = d / "pack"
    build = d / "build"
    build.mkdir(parents=True, exist_ok=True)
    report = dict(script=None, characters={}, sets=[], scenes=[], voices={}, warnings=[], missing=[])
    files = unpack(pack)
    docs = [p for p in files if p.suffix.lower() in DOCS]
    pics = [p for p in files if p.suffix.lower() in P.IMAGE_TYPES]
    auds = [p for p in files if p.suffix.lower() in P.AUDIO_TYPES]

    # the script
    best = None
    texts = {}
    for p in docs:
        try:
            t = text_of(p)
        except Exception as e:  # noqa: BLE001
            report["warnings"].append(f"could not read {p.name}: {e}")
            continue
        texts[p] = t
        sc = parse_script(t)
        if sc["lines"] and (best is None or len(sc["lines"]) > len(best[1]["lines"])):
            best = (p, sc, t)
    if not best:
        raise SystemExit("no script found: upload the director's script (.md, .txt, .docx or .pdf) with lines like "
                         "'GARY: text' or '[L001] GARY: text'")
    sp_path, script, text = best
    notes = "\n".join(t for p, t in texts.items() if p != sp_path)     # the production notes, the director's notes
    report["notes"] = [p.name for p in texts if p != sp_path]
    text = text + "\n" + notes                    # full names and cast lists in the notes tell people apart
    old = json.loads((d / "studio.json").read_text()) if (d / "studio.json").exists() else {}
    show = _show(old.get("show_id"))
    if show:
        text = text + "\n" + show["directive"]                 # the show's full names help tell people apart
        report["show"] = show["title"]
    report["script"] = str(sp_path.relative_to(d))
    print(f"script: {sp_path.name}: {len(script['lines'])} lines in {len(script['scenes'])} scenes", flush=True)
    if sp_path.suffix.lower() in (".md", ".txt", ".fountain"):
        (d / "script.md").write_bytes(sp_path.read_bytes())       # the director's script, as delivered
    else:
        (d / "script.md").write_text(text)
    names = []
    for ln in script["lines"]:
        if ln["name"] not in names:
            names.append(ln["name"])

    # the pictures: characters named for a speaker, and sets
    lib = library()
    cast_of = {}                                                  # NAME -> (character id, drawing)
    fulls = {n: full_name(n, text) for n in names}
    char_pics, set_pics = [], []
    for p in pics:
        hit = next((n for n in names if named_for(p.stem, n, fulls[n])), None)
        if hit:
            char_pics.append((p, hit))
        elif looks_like_set(p):
            set_pics.append(p)
        else:
            char_pics.append((p, None))
    unnamed = [p for p, n in char_pics if n is None]
    for p, n in char_pics:
        if n is None or n in cast_of:
            continue
        cast_of[n] = _file_character(p, n, fulls[n], text, lib, report)
    # speakers with no picture: the library, then any unnamed pictures in order
    for n in names:
        if n in cast_of:
            continue
        c = (match_library(n, fulls[n], text, [x for x in lib if x["id"] in show["by_id"]]) if show else None) \
            or match_library(n, fulls[n], text, lib)
        if c and show and c["id"] in show["by_id"] and show["by_id"][c["id"]].get("drawing"):
            cast_of[n] = (c["id"], show["by_id"][c["id"]]["drawing"])
            report["characters"][n] = dict(id=c["id"], name=c["name"], source="the show's cast")
        elif c and c["drawings"]:
            cast_of[n] = (c["id"], "front" if "front" in c["drawings"] else c["drawings"][0])
            report["characters"][n] = dict(id=c["id"], name=c["name"], source="library")
        elif unnamed:
            cast_of[n] = _file_character(unnamed.pop(0), n, fulls[n], text, lib, report, guessed=True)
        else:
            report["missing"].append(n)
    for p in unnamed:
        report["warnings"].append(f"{p.name}: a picture not named for anyone in the script; not used")

    # the sets
    sets = []
    for p in set_pics:
        bid = _file_set(p, report)
        sets.append(bid)
    bgs = P.backgrounds()
    land = [b for b in bgs if b["orientation"] == "landscape"]
    scenes = []
    spare = list(sets)
    prev = None
    for k, sc in enumerate(script["scenes"]):
        want = words(sc["location"] + " " + sc["name"]) if (sc["location"] or sc["name"]) else []
        want = [w for w in want if w not in ("int", "ext", "day", "night", "the", "and", "continuous", "later")]
        said = _notes_on_scene(notes, k + 1, sc["name"])           # what the notes say about this scene

        def score(b):
            have = set(words(b["title"] + " " + b["id"].replace("/", " ").replace("-", " ")))
            return sum(1 for w in want if w in have or (w.endswith("s") and w[:-1] in have))
        pool = [b for b in land if b["id"] in sets or (show and b["id"] in show["sets"])] or []
        rank = lambda b: (score(b), b["added"])                     # ties go to the set added most recently
        pick = max(pool, key=rank) if pool and want and score(max(pool, key=rank)) > 0 else None
        if not pick and want and land:
            lb = max(land, key=rank)
            pick = lb if score(lb) > 0 else None
        if not pick and said:                                         # the heading names no set: the notes might
            want = [w for w in words(said) if len(w) > 3]
            cands = [b for b in (pool or []) + land]
            lb = max(cands, key=lambda b: (score(b), b["added"])) if cands else None
            pick = lb if lb and score(lb) >= 2 else None
            if pick:
                report["warnings"].append(f"scene {k + 1}: set {pick['id']} chosen from the production notes")
        if not pick and sc["location"] == "" and prev:            # no slugline: the same place as before
            bid = prev
        elif pick:
            bid = pick["id"]
        elif spare:
            bid = spare[0]
        else:
            # nothing named: the set added most recently (the one just uploaded for this production)
            bid = prev or (sets[0] if sets else (show["sets"][0] if show and show["sets"] else
                                                 (land[0]["id"] if land else "")))
            if not prev:
                report["warnings"].append(f"scene {k + 1}: no set matched '{sc['location'] or sc['name']}'; using {bid}")
        if bid in spare:
            spare.remove(bid)
        place = re.sub(r"^(INT|EXT|I/E|INT\./EXT)\.?\s+", "", sc["location"], flags=re.I)
        place = titled(re.split(r"\.\s+|\s+[—–-]\s+", place)[0].strip(" .")) if place else ""
        if place and bid == prev and not sc["location"]:
            place = ""
        scenes.append(dict(name=titled(sc["name"]) if sc["name"].isupper() else sc["name"], background=bid,
                           place=place if bid != prev else "", stage={}))
        report["scenes"].append(dict(name=sc["name"], location=sc["location"], set=bid))
        prev = bid
    if not any(s["background"] for s in scenes):
        raise SystemExit("no set to film on: upload a background (landscape)")

    if report["missing"]:
        _report(build, report)
        raise SystemExit("no picture or library character for: " + ", ".join(report["missing"])
                         + ". Upload a picture of each, named for them (e.g. " + report["missing"][0].title() + ".png)")

    # the recordings
    lines_of = {}
    for ln in script["lines"]:
        lines_of.setdefault(ln["name"], []).append(ln["text"])
    rec = {}
    vo = d / "voiceovers"
    vo.mkdir(exist_ok=True)
    order = {n: i + 1 for i, n in enumerate(names)}
    ids_by_line = {ln["id"]: ln["name"] for ln in script["lines"] if ln["id"]}
    for p in auds:
        who = next((n for n in names if named_for(p.stem, n, fulls[n]) or norm(cast_of[n][0]) in norm(p.stem)), None)
        if who is None:
            m = re.search(r"\b(L?\d{2,4})\b", p.stem.replace("_", " ").replace("-", " "))
            if m and m.group(1) in ids_by_line:
                who = ids_by_line[m.group(1)]
        how = "named"
        other = next((c for c in lib if c["id"] not in [cast_of[n][0] for n in names]
                      and (norm(c["id"]) in norm(p.stem) or norm(c["name"]) in norm(p.stem))), None)
        if who is None and other:
            report["warnings"].append(f"{p.name}: {other['name']} has no lines in this script; not used")
            continue
        if who is None:
            who, how = _heard_as(p, lines_of, build), "heard"
        if who is None:
            report["warnings"].append(f"{p.name}: couldn't tell whose voice this is; not used")
            continue
        cid = cast_of[who][0]
        k = len(rec.get(who, [])) + 1
        dst = vo / f"{order[who]:02d}-{cid}-{k}{p.suffix.lower()}"
        shutil.move(str(p), dst)                               # byte for byte; the pack keeps the documents
        rec.setdefault(who, []).append(dst.name)
        report["voices"].setdefault(who, []).append(dict(file=p.name, filed=dst.name, by=how))
        print(f"recording {p.name}: {who} ({how}) -> voiceovers/{dst.name}", flush=True)
    # a speaker's files in the order they were uploaded as (…-1, …-2 by name)
    for who in rec:
        rec[who] = [f for _, f in sorted(zip([r["file"] for r in report["voices"][who]], rec[who]))]
    # recordings filed by an earlier import (the pack gives them up when they are filed) stay theirs
    before = {c["id"]: (c.get("voice") or {}).get("files") or [] for c in old.get("cast", [])}
    for n in names:
        fs = [f for f in before.get(cast_of[n][0], []) if (vo / f).exists()]
        if fs and n not in rec:
            rec[n] = fs
            report["voices"][n] = [dict(file=f, filed=f, by="filed before") for f in fs]

    # the episode
    cast, k_m, k_f = [], 0, 0
    for n in names:
        cid, drawing = cast_of[n]
        if n in rec:
            voice = dict(kind="recording", files=rec[n])
        elif show and (show["by_id"].get(cid) or {}).get("voice"):
            voice = dict(show["by_id"][cid]["voice"])            # the voice they always have in this show
            report["voices"][n] = [dict(stand_in=voice["voice"], show=True)]
        else:
            female = _female(cid)
            if female:
                voice = dict(kind="tts", voice=STAND_IN_F[k_f % len(STAND_IN_F)], speed=1.0)
                k_f += 1
            else:
                voice = dict(kind="tts", voice=STAND_IN[k_m % len(STAND_IN)], speed=1.0)
                k_m += 1
            report["voices"][n] = [dict(stand_in=voice["voice"])]
        if show:
            _remember(show, cid, drawing, voice if voice["kind"] == "tts" else None)
        cast.append(dict(id=cid, drawing=drawing, voice=voice, caption="", mood=""))
    lines = []
    for i, ln in enumerate(script["lines"]):
        lines.append(dict(who=cast_of[ln["name"]][0], to="", text=ln["text"], tone=ln["tone"],
                          pause=0.9 if ln["beat"] and i and script["lines"][i - 1]["scene"] == ln["scene"] else "",
                          scene=ln["scene"]))
    _stage(scenes, lines)
    sp = dict(title=old.get("title") or script["title"] or slug.replace("-", " ").title(),
              show=old.get("show") or (show["title"] if show else script["show"]),
              tagline=old.get("tagline", ""), scenes=scenes, cast=cast, show_id=old.get("show_id", ""),
              lines=lines, open=2.2, hold=1.3, script_file="script.md")
    P.save_episode(slug, normalize(sp))
    _report(build, report)
    print(f"cast: {', '.join(f'{n} = {cast_of[n][0]}' for n in names)}", flush=True)
    print(f"sets: {', '.join(s['background'] for s in scenes)}", flush=True)
    for w in report["warnings"]:
        print("warning: " + w, flush=True)


# ---------------------------------------------------------------- shows
def _show(slug):
    """a show's cast, sets, voices and directive text (for an episode made in it)"""
    if not slug:
        return None
    f = SHOWS / slug / "show.json"
    if not f.exists():
        return None
    sh = json.loads(f.read_text())
    sh["slug"] = slug
    sh["by_id"] = {c["id"]: c for c in sh.get("cast", [])}
    sh["sets"] = sh.get("sets", [])
    pack = SHOWS / slug / "pack"
    sh["directive"] = "\n".join(text_of(p) for p in sorted(pack.rglob("*")) if p.suffix.lower() in DOCS) if pack.exists() else ""
    return sh


def _remember(show, cid, drawing, voice):
    """a show keeps the voice and drawing each character first got in it, so every episode sounds the same"""
    f = SHOWS / show["slug"] / "show.json"
    sh = json.loads(f.read_text())
    cast = sh.setdefault("cast", [])
    c = next((x for x in cast if x["id"] == cid), None)
    if c is None:
        c = dict(id=cid)
        cast.append(c)
    c.setdefault("drawing", drawing)
    if voice and not c.get("voice"):
        c["voice"] = voice
    f.write_text(json.dumps(sh, indent=1, ensure_ascii=False) + "\n")
    show["by_id"][cid] = c


CAST_HEAD = re.compile(r"(cast|characters|starring|regulars|who's who)", re.I)
FILLER = {"kit", "final", "sheet", "model", "character", "char", "front", "full", "body", "png", "jpg", "new", "v",
          "copy", "img", "image", "drawing", "art", "turnaround", "pose"}


def _picture_name(stem):
    ws = [w for w in re.split(r"[\s_\-.]+", stem) if w and not w.isdigit() and w.lower().rstrip("0123456789") not in FILLER]
    return " ".join(w.capitalize() if w.islower() or w.isupper() else w for w in ws)


def cast_list(text):
    """the names a show directive casts: bullets or bold names under a Cast / Characters heading, and any
    'Speaking cast:' / 'Cast:' line"""
    names = []

    def add(n):
        n = re.sub(r"[*_`]", "", n).strip(" .:-—–")
        if 1 <= len(n.split()) <= 4 and n[:1].isupper() and n not in names and len(n) < 40:
            names.append(n)
    rows = text.splitlines()
    under = False
    for r in rows:
        s = r.strip()
        m = re.match(r"^(?:\*\*)?(?:speaking )?(?:cast|characters|starring)(?:\*\*)?\s*:\s*(.+)$", s, re.I)
        if m:
            for part in re.split(r",| and ", re.sub(r"\*\*", "", m.group(1))):
                add(re.split(r"\s+[(—–-]\s*|\.\s", part.strip())[0])
            continue
        if s.startswith("#"):
            under = bool(CAST_HEAD.search(s))
            continue
        if under:
            m = re.match(r"^(?:[-*•]|\d+[.)])\s+(?:\*\*)?([^*:—–(]+?)(?:\*\*)?\s*(?:[:—–(]|\s-\s|$)", s) \
                or re.match(r"^\*\*([^*]+?)\*\*", s)
            if m:
                add(m.group(1))
    return names


def run_show(slug):
    """a show's directive and assets -> shows/<slug>/show.json: its title, tagline, cast (characters filed from
    the pictures, or found in the library), sets, and a stand-in voice for each of them, kept for every episode"""
    d = SHOWS / slug
    pack, build = d / "pack", d / "build"
    build.mkdir(parents=True, exist_ok=True)
    report = dict(directive=[], characters={}, sets=[], warnings=[], missing=[])
    files = unpack(pack)
    docs = [p for p in files if p.suffix.lower() in DOCS]
    pics = [p for p in files if p.suffix.lower() in P.IMAGE_TYPES]
    text = ""
    for p in docs:
        try:
            text += text_of(p) + "\n"
            report["directive"].append(p.name)
        except Exception as e:  # noqa: BLE001
            report["warnings"].append(f"could not read {p.name}: {e}")
    sh = json.loads((d / "show.json").read_text())
    if not sh.get("title"):
        m = re.search(r"^#\s+(.+)$", text, re.M)
        first = next((ln.strip(" #*") for ln in text.splitlines() if ln.strip()), "")
        sh["title"] = (m.group(1) if m else first or slug.replace("-", " ")).strip(" *")
        parts = re.split(r"\s+[—–:\-]\s+", sh["title"], maxsplit=1)
        if len(parts) == 2 and re.search(r"(show )?bible|directive|series|show", parts[1], re.I):
            sh["title"] = parts[0]
        if sh["title"].isupper():
            sh["title"] = titled(sh["title"])
    m = re.search(r"^(?:\*\*)?tag ?line(?:\*\*)?\s*:\s*(.+)$", text, re.I | re.M)
    if m and not sh.get("tagline"):
        sh["tagline"] = m.group(1).strip(" *")
    lib = library()
    names = cast_list(text)
    cast = {c["id"]: c for c in sh.get("cast", [])}
    sets = list(sh.get("sets", []))
    placed = set()
    for p in pics:
        if looks_like_set(p) and not any(named_for(p.stem, n.split()[0], n) for n in names):
            bid = _file_set(p, report)
            if bid not in sets:
                sets.append(bid)
            continue
        guess = _picture_name(p.stem)
        full = next((n for n in names if named_for(p.stem, n.split()[0], n) or norm(n) == norm(guess)), None)
        if not full and guess:
            full = full_name(guess.split()[0], text) if len(guess.split()) == 1 else guess
        if not full:
            report["warnings"].append(f"{p.name}: couldn't tell who this is; name the file after them")
            continue
        cid, drawing = _file_character(p, full.split()[0].upper(), full, text, lib, report)
        cast.setdefault(cid, dict(id=cid))["drawing"] = drawing
        placed.add(norm(full))
        lib = library()
    for n in names:                                   # named in the directive, no picture: the library
        if norm(n) in placed:
            continue
        c = match_library(n.split()[0].upper(), n, text, lib)
        if c and c["drawings"] and (norm(c["name"]) == norm(n) or len(n.split()) == 1):
            cast.setdefault(c["id"], dict(id=c["id"], drawing="front" if "front" in c["drawings"] else c["drawings"][0]))
            report["characters"][n] = dict(id=c["id"], name=c["name"], source="library")
        else:
            report["missing"].append(n)
    k_m = k_f = 0
    for c in cast.values():                           # a stand-in voice each, for as long as they have no recording
        if not c.get("voice"):
            if _female(c["id"]):
                c["voice"] = dict(kind="tts", voice=STAND_IN_F[k_f % len(STAND_IN_F)], speed=1.0)
                k_f += 1
            else:
                c["voice"] = dict(kind="tts", voice=STAND_IN[k_m % len(STAND_IN)], speed=1.0)
                k_m += 1
    sh["cast"] = list(cast.values())
    sh["sets"] = sets
    (d / "show.json").write_text(json.dumps(sh, indent=1, ensure_ascii=False) + "\n")
    _report(build, report)
    print(f"show: {sh['title']}", flush=True)
    print("cast: " + ", ".join(c["id"] for c in sh["cast"]), flush=True)
    print("sets: " + ", ".join(sets), flush=True)
    for w in report["warnings"]:
        print("warning: " + w, flush=True)
    if report["missing"]:
        print("not found (upload a picture named after them): " + ", ".join(report["missing"]), flush=True)


def _notes_on_scene(notes, n, name):
    """the paragraphs of the notes about scene n (by its number or its name)"""
    if not notes:
        return ""
    keys = [rf"\bscene\s*{n}\b"] + ([re.escape(name.lower())] if len(name) > 4 else [])
    out = [para for para in re.split(r"\n\s*\n", notes) if any(re.search(k, para.lower()) for k in keys)]
    return " ".join(out)[:4000]


def _stage(scenes, lines):
    """where everyone stands: the scene's speakers spread across the set in the order they first speak; a scene on
    the same set as the one before keeps everyone where they were (continuity) and puts newcomers in the gaps"""
    prev = None
    for k, sc in enumerate(scenes):
        who = []
        for ln in lines:
            if ln["scene"] == k and ln["who"] not in who:
                who.append(ln["who"])
        keep = {c: dict(v) for c, v in prev["stage"].items()} if prev and prev["background"] == sc["background"] else {}
        stage = {c: keep[c] for c in who if c in keep}
        new = [c for c in who if c not in stage]
        if new:
            n = len(stage) + len(new)
            slots = [0.5] if n == 1 else [round(0.18 + 0.64 * i / (n - 1), 3) for i in range(n)]
            free = sorted(slots, key=lambda x: -min([abs(x - v["x"]) for v in stage.values()] or [1]))
            for c, x in zip(new, sorted(free[:len(new)])):
                stage[c] = dict(x=x, floor=0.93, height=0.62)
        if keep:                                       # who was there and stays silent is still in the room
            for c, v in keep.items():
                stage.setdefault(c, v)
        sc["stage"] = stage
        prev = sc


def _report(build, report):
    (build / "import.json").write_text(json.dumps(report, indent=1))


def _female(cid):
    c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text()) or {}
    t = " ".join(str(c.get(k, "")) for k in ("likeness", "gender", "pronouns", "role")).lower()
    return bool(re.search(r"\b(she|her|woman|female|girl|actress|mrs|ms)\b", t))


def _file_character(p, name, full, text, lib, report, guessed=False):
    """a picture of a speaker -> (character id, drawing): a new character, or a new drawing of a library one"""
    data = p.read_bytes()
    c = match_library(name, full, text, lib)
    if c and (norm(c["name"]) == norm(full) or not c["drawings"]):
        cid = c["id"]
        sheet = P.add_reference(cid, data, p.name)
        w, h = Image.open(CHARACTERS / cid / sheet).size
        box = find_figure(CHARACTERS / cid / sheet) if w > 1.6 * h else [0, 0, w, h]
        existing = P.film_spec(cid).get("drawings") or {}
        same = next((k for k, v in existing.items() if v.get("sheet") == sheet and v.get("box") == box), None)
        drawing = same or P.set_drawing(cid, "front" if not existing else "upload", dict(sheet=sheet, box=box, faces="F"))
        report["characters"][name] = dict(id=cid, name=c["name"], source=f"{p.name} (new drawing of a library character)")
        print(f"picture {p.name}: {name} = {cid} (a new drawing: {drawing})", flush=True)
        return cid, drawing
    cid = P.kebab(full)
    if (CHARACTERS / cid / "character.yaml").exists():           # the same name already filed (an earlier import)
        sheet = P.add_reference(cid, data, p.name)
        existing = P.film_spec(cid).get("drawings") or {}
        drawing = next((k for k, v in existing.items() if v.get("sheet") == sheet), None)
        if not drawing:
            w, h = Image.open(CHARACTERS / cid / sheet).size
            box = find_figure(CHARACTERS / cid / sheet) if w > 1.6 * h else [0, 0, w, h]
            drawing = P.set_drawing(cid, "front" if not existing else "upload", dict(sheet=sheet, box=box, faces="F"))
    else:
        cid = P.add_character(full, data, p.name, role="")
        ref = next(iter((yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text()) or {}).get("reference", {})))
        w, h = Image.open(CHARACTERS / cid / "reference" / ref).size
        if w > 1.6 * h:                                            # a model sheet: its first figure
            P.set_drawing(cid, "front", dict(sheet=f"reference/{ref}", box=find_figure(CHARACTERS / cid / "reference" / ref), faces="F"))
        drawing = "front"
    report["characters"][name] = dict(id=cid, name=full, source=p.name + (" (the only unnamed picture left)" if guessed else ""))
    print(f"picture {p.name}: {name} = {cid}" + (" (guessed: name the file after them to be sure)" if guessed else ""), flush=True)
    return cid, drawing


def _file_set(p, report):
    data = p.read_bytes()
    digest = P.sha(data)
    idx = yaml.safe_load((BACKGROUNDS / "backgrounds.yaml").read_text()) or {}
    for bid, v in idx.items():                                    # delivered before: the same file
        f = BACKGROUNDS / f"{bid}.png"
        if v.get("source") == p.name and f.exists() and (P.sha(f.read_bytes()) == digest or list(v.get("size", [])) ==
                                                         list(_cropped_size(Image.open(p).size))):
            report["sets"].append(dict(file=p.name, id=bid, new=False))
            return bid
    title = re.sub(r"[_\-]+", " ", p.stem).strip() or "set"
    ws = set(words(title))
    setting = P.guess_setting(title)
    bid = f"{setting}/{P.kebab(title)}"
    k = 2
    while bid in idx:
        bid = f"{setting}/{P.kebab(title)}-{k}"
        title = f"{re.sub(r'[_-]+', ' ', p.stem).strip()} {k}"
        k += 1
    bid = P.add_background(title, setting, data, p.name)
    report["sets"].append(dict(file=p.name, id=bid, new=True))
    print(f"set {p.name} -> library/backgrounds/{bid}.png", flush=True)
    return bid


def _cropped_size(wh):
    w, h = wh
    if w >= h and abs(w / h - 16 / 9) > 0.01:
        return (int(round(h * 16 / 9)), h) if w / h > 16 / 9 else (w, int(round(w * 9 / 16)))
    return (w, h)


def _heard_as(p, lines_of, build):
    """whose lines Whisper hears in a recording: the speaker with the most of their own lines found in it (a line
    is found when most of its words are heard), and clearly more than anyone else"""
    import librosa
    from studio.film.voices import heard, words_of
    subprocess.run(["bash", str(Path(__file__).resolve().parents[2] / "tools" / "fetch_models.sh"), "whisper"], check=True)
    y16, _ = librosa.load(str(p), sr=16000, mono=True)
    said = set(words_of(" ".join(t for _, _, t in heard(p, y16, build / "asr"))))
    if not said:
        return None
    score = {}
    for n, ls in lines_of.items():
        found = 0
        for t in ls:
            ws = words_of(t)
            if len(ws) >= 3 and sum(w in said for w in ws) >= 0.7 * len(ws):
                found += 1
        score[n] = found / max(1, sum(1 for t in ls if len(words_of(t)) >= 3))
    best = max(score, key=score.get)
    rest = max([v for k, v in score.items() if k != best] or [0.0])
    return best if score[best] >= 0.3 and score[best] > 1.5 * rest else None


if __name__ == "__main__":
    # python3 -m studio.web.autoprod SLUG            an episode's pack
    # python3 -m studio.web.autoprod --show SLUG     a show's directive and assets
    if sys.argv[1] == "--show":
        run_show(sys.argv[2])
    else:
        run(sys.argv[1])
