"""The library and the episodes on disk, as the web studio sees them: listing, uploading and filing (the rules in
CLAUDE.md and library/README.md), and writing a web episode's folder from its studio.json."""
import hashlib
import io
import json
import re
import shutil

import yaml
from PIL import Image

from studio.paths import BACKGROUNDS, BUILD, CHARACTERS, EPISODES, ROOT

SETTINGS = ["stadiums", "training-ground", "club", "tv-and-media", "home", "spa-and-pool", "pub-and-restaurant",
            "nightlife", "street", "concert"]
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_TYPES = (".wav", ".mp3", ".m4a", ".flac", ".ogg")


def kebab(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


# ---------------------------------------------------------------- characters
def film_spec(cid):
    f = CHARACTERS / cid / "film.yaml"
    return yaml.safe_load(f.read_text()) if f.exists() else {"drawings": {}}


def built(cid, name):
    mf = BUILD / "film" / cid / "meta.json"
    return (BUILD / "film" / cid / f"{name}.png").exists() and mf.exists() and name in json.loads(mf.read_text())


def face_found(cid, name):
    kf = BUILD / "film" / cid / "marks.json"
    if not kf.exists():
        return None
    mk = json.loads(kf.read_text()).get(name)
    if mk is None:
        return None
    return dict(eyes=len(mk.get("eyes", [])), mouth=bool(mk.get("mouth")))


def characters():
    out = []
    for d in sorted(CHARACTERS.iterdir()):
        y = d / "character.yaml"
        if not y.exists():
            continue
        c = yaml.safe_load(y.read_text()) or {}
        sp = film_spec(d.name)
        draws = []
        for name, dd in (sp.get("drawings") or {}).items():
            draws.append(dict(name=name, faces=dd.get("faces", "F"), source=dd.get("kit") or dd.get("sheet") or dd.get("image"),
                              box=dd.get("box"), built=built(d.name, name), face=face_found(d.name, name)))
        out.append(dict(id=d.name, name=c.get("name", d.name), short=c.get("short", ""), role=c.get("role", ""),
                        style=c.get("style", ""), drawings=draws, uploaded=bool(c.get("uploaded")),
                        check=f"build/film/{d.name}_check.jpg" if (BUILD / "film" / f"{d.name}_check.jpg").exists() else None))
    return out


def sheets(cid):
    """every picture of a character a drawing can be cut from: kit sheets and reference art"""
    d = CHARACTERS / cid
    out = []
    for p in sorted(list((d / "reference").glob("*")) + list((d / "kit").glob("*/*.png"))):
        if p.suffix.lower() in IMAGE_TYPES:
            w, h = Image.open(p).size
            out.append(dict(path=rel(p), sheet=str(p.relative_to(d)), size=[w, h]))
    return out


def thumb(path, h=320, alpha=False):
    """a small JPEG of any image, or a PNG keeping its transparency (cached in build/web/thumbs)"""
    src = ROOT / path
    key = sha(f"{path}:{src.stat().st_mtime}:{h}:{alpha}".encode())[:16]
    out = BUILD / "web" / "thumbs" / f"{key}.{'png' if alpha else 'jpg'}"
    if alpha and not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGBA")
        im.thumbnail((h * 3, h))
        im.save(out, "PNG")
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (236, 232, 226, 255))
            bg.alpha_composite(im)
            im = bg
        im = im.convert("RGB")
        im.thumbnail((h * 3, h))
        im.save(out, "JPEG", quality=84)
    return out


def character_thumb(cid):
    """the first built drawing, else the first kit front or reference picture"""
    sp = film_spec(cid)
    for name in (sp.get("drawings") or {}):
        if built(cid, name):
            return thumb(rel(BUILD / "film" / cid / f"{name}.png"))
    d = CHARACTERS / cid
    for p in sorted(d.glob("kit/*/front.png")) + sorted(d.glob("reference/*")):
        if p.suffix.lower() in IMAGE_TYPES:
            return thumb(rel(p))
    for dd in (sp.get("drawings") or {}).values():         # a drawing boxed on a shared sheet (the squad sheet)
        if dd.get("sheet") and dd.get("box"):
            src = (d / dd["sheet"]).resolve()
            out = BUILD / "web" / "thumbs" / f"{cid}-box-{sha(str(dd['box']).encode())[:8]}.jpg"
            if src.exists() and not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                im = Image.open(src).convert("RGB").crop(tuple(dd["box"]))
                im.thumbnail((960, 320))
                im.save(out, "JPEG", quality=84)
            if out.exists():
                return out
    return None


def _write_film_yaml(cid, sp):
    f = CHARACTERS / cid / "film.yaml"
    head = ("# Drawings this character is filmed in (studio/film/art.py): each is cut whole from its sheet, upscaled 4x and\n"
            f"# given face landmarks. Check build/film/{cid}_check.jpg after any change.\n")
    if f.exists():
        lines = f.read_text().splitlines(keepends=True)
        head = "".join(ln for ln in lines[:4] if ln.startswith("#")) or head
    f.write_text(head + yaml.safe_dump(sp, sort_keys=False, default_flow_style=None, width=118))


def set_drawing(cid, name, d):
    """add or replace one drawing in film.yaml (and forget its old build)"""
    name = kebab(name).replace("-", "_") or "front"
    sp = film_spec(cid)
    sp.setdefault("drawings", {})
    sp["drawings"] = sp["drawings"] or {}
    old = sp["drawings"].get(name, {})
    keep = {k: v for k, v in old.items() if k in ("ed", "look0", "jaw", "brow_gain", "holes", "auto_holes")}
    sp["drawings"][name] = {**d, **keep} if old.get("sheet") == d.get("sheet") and old.get("box") == d.get("box") else d
    _write_film_yaml(cid, sp)
    forget(cid, name)
    return name


def forget(cid, name):
    """drop a drawing's build so it is cut again"""
    out = BUILD / "film" / cid
    (out / f"{name}.png").unlink(missing_ok=True)
    for j in ("meta.json", "marks.json"):
        f = out / j
        if f.exists():
            m = json.loads(f.read_text())
            m.pop(name, None)
            f.write_text(json.dumps(m, indent=1))


def set_face(cid, name, eyes, mouth):
    """hand-set face landmarks for a drawing where detection failed. eyes = [[x, y], [x, y]], mouth = [x, y], in the
    built drawing's own px; written to film.yaml `marks` in sheet px"""
    meta = json.loads((BUILD / "film" / cid / "meta.json").read_text())[name]
    ox, oy = meta["off"]
    K = meta["scale"]

    def sheet(x, y):
        return [round(x / K + ox, 1), round(y / K + oy, 1)]

    E = sorted([sheet(*e) for e in eyes])
    mx, my = sheet(*mouth)
    ed = abs(E[1][0] - E[0][0]) if len(E) == 2 else 30.0
    ey = sum(e[1] for e in E) / len(E)
    kf = BUILD / "film" / cid / "marks.json"
    found = json.loads(kf.read_text()).get(name, {}).get("eyes", []) if kf.exists() else []

    def eye(x, y):           # a detected eye where the click is keeps its own size; else cartoon proportions
        near = [e for e in found if abs(e[0] - x) < 0.4 * ed and abs(e[1] - y) < 0.4 * ed]
        return [x, y] + (near[0][2:4] if near else [round(0.3 * ed, 2), round(0.26 * ed, 2)])

    marks = dict(eyes=[eye(x, y) for x, y in E],
                 mouth=[round(mx - 0.28 * ed, 1), my, round(mx + 0.28 * ed, 1), my, mx, my])
    chin = round(my + 0.5 * (my - ey), 1)
    marks["chin"] = chin
    marks["neck"] = [mx, round(chin + 0.28 * (chin - ey), 1)]
    sp = film_spec(cid)
    sp["drawings"][name]["marks"] = marks
    _write_film_yaml(cid, sp)
    return marks


def add_character(name, data, filename, role=""):
    """a new character from one uploaded picture (a single drawing, or a model sheet to cut drawings from)"""
    cid = kebab(name)
    if not cid:
        raise ValueError("a character needs a name")
    d = CHARACTERS / cid
    if (d / "character.yaml").exists():
        raise ValueError(f"{cid} is already in the library: add a drawing to it instead")
    ext = (re.search(r"\.[a-z0-9]+$", filename.lower()) or [".png"])[0]
    if ext not in IMAGE_TYPES:
        raise ValueError(f"not a picture: {filename}")
    (d / "reference").mkdir(parents=True, exist_ok=True)
    ref = "model-sheet" + ext if Image.open(io.BytesIO(data)).size[0] > 1.6 * Image.open(io.BytesIO(data)).size[1] else "drawing" + ext
    (d / "reference" / ref).write_bytes(data)                 # byte for byte, as uploaded
    c = dict(name=name.strip(), short=name.strip().split()[0], role=role or "character", style="upload",
             uploaded=True, reference={ref: f"Uploaded in the web studio ({filename})."})
    (d / "character.yaml").write_text(yaml.safe_dump(c, sort_keys=False, width=118))
    w, h = Image.open(d / "reference" / ref).size
    set_drawing(cid, "front", dict(sheet=f"reference/{ref}", box=[0, 0, w, h], faces="F"))
    index()
    return cid


def add_reference(cid, data, filename):
    """another picture for an existing character (a pose sheet, a model sheet) -> reference/<name>"""
    d = CHARACTERS / cid
    base = kebab(re.sub(r"\.[a-z0-9]+$", "", filename.lower())) or "sheet"
    ext = (re.search(r"\.[a-z0-9]+$", filename.lower()) or [".png"])[0]
    if ext not in IMAGE_TYPES:
        raise ValueError(f"not a picture: {filename}")
    digest = sha(data)
    for p in (d / "reference").glob("*"):
        if p.is_file() and sha(p.read_bytes()) == digest:
            return str(p.relative_to(d))                       # already filed: don't duplicate it
    p = d / "reference" / f"{base}{ext}"
    k = 2
    while p.exists():
        p = d / "reference" / f"{base}-{k}{ext}"
        k += 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    y = d / "character.yaml"
    c = yaml.safe_load(y.read_text()) or {}
    c.setdefault("reference", {})
    c["reference"] = c["reference"] or {}
    c["reference"][p.name] = f"Uploaded in the web studio ({filename})."
    y.write_text(yaml.safe_dump(c, sort_keys=False, width=118, allow_unicode=True))
    index()
    return str(p.relative_to(d))


# ---------------------------------------------------------------- backgrounds
def backgrounds():
    idx = yaml.safe_load((BACKGROUNDS / "backgrounds.yaml").read_text()) or {}
    return [dict(id=k, title=v.get("title", k), size=v.get("size"), orientation=v.get("orientation"),
                 path=f"library/backgrounds/{k}.png") for k, v in idx.items()]


def add_background(title, setting, data, filename, crop=True):
    """a set, filed as library/backgrounds/<setting>/<name>.png; a landscape picture that isn't 16:9 is cropped to
    16:9 about its centre (the episodes are 16:9), a portrait one is kept as it is and marked"""
    setting = kebab(setting) or "street"
    name = kebab(title)
    if not name:
        raise ValueError("a background needs a name")
    bid = f"{setting}/{name}"
    idx_f = BACKGROUNDS / "backgrounds.yaml"
    idx = yaml.safe_load(idx_f.read_text()) or {}
    if bid in idx:
        raise ValueError(f"{bid} is already in the library")
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGB")
    w, h = im.size
    if crop and w >= h and abs(w / h - 16 / 9) > 0.01:
        if w / h > 16 / 9:
            nw = int(round(h * 16 / 9))
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(round(w * 9 / 16))
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    out = BACKGROUNDS / f"{bid}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if filename.lower().endswith(".png") and im.size == (w, h) and Image.open(io.BytesIO(data)).mode == "RGB":
        out.write_bytes(data)                                    # byte for byte when it needs no change
    else:
        im.save(out, "PNG", optimize=True)
    w, h = im.size
    idx[bid] = dict(title=title.strip(), size=[w, h], orientation="landscape" if w >= h else "portrait", source=filename)
    text = idx_f.read_text()
    idx_f.write_text(text.rstrip("\n") + "\n" + yaml.safe_dump({bid: idx[bid]}, sort_keys=False, width=118, allow_unicode=True, default_flow_style=None))
    index()
    return bid


def index():
    """library/INDEX.md, rebuilt after anything is filed (tools/index_library.py)"""
    import subprocess
    import sys
    subprocess.run([sys.executable, str(ROOT / "tools" / "index_library.py")], cwd=ROOT, capture_output=True)


# ---------------------------------------------------------------- episodes
SHIM = '''"""{what}: worked out by the web studio's auto-director from ../studio.json. Replace this line with the module's
own code (studio/web/auto/{mod}.py) to direct it by hand."""
from studio.web.auto.{mod} import *  # noqa: F401,F403
'''
SHIMS = {"timeline": "The dialogue edit", "direction": "The shot list", "perf": "The acting", "sound": "The mix"}


def episodes():
    out = []
    for d in sorted(EPISODES.iterdir()):
        if not d.is_dir():
            continue
        f = d / "studio.json"
        sp = json.loads(f.read_text()) if f.exists() else None
        mp4 = d / f"{d.name}.mp4"
        prev = d / f"{d.name}_preview.mp4"
        out.append(dict(slug=d.name, title=(sp or {}).get("title") or d.name.replace("-", " ").title(), web=sp is not None,
                        video=rel(mp4) if mp4.exists() else None, preview=rel(prev) if prev.exists() else None))
    return out


def new_episode(title):
    slug = kebab(title)
    if not slug:
        raise ValueError("an episode needs a title")
    base, k = slug, 2
    while (EPISODES / slug).exists():
        slug = f"{base}-{k}"
        k += 1
    bg = next((b["id"] for b in backgrounds() if b["orientation"] == "landscape"), "")
    sp = dict(title=title.strip(), show="", tagline="", place="", background=bg, cast=[], lines=[], open=2.2, hold=1.3)
    save_episode(slug, sp)
    return slug


def load_episode(slug):
    d = EPISODES / slug
    f = d / "studio.json"
    if not f.exists():
        raise ValueError(f"{slug} is directed by hand (episodes/{slug}/film/): it can be watched, not edited, here")
    sp = json.loads(f.read_text())
    vo = d / "voiceovers"
    sp["_files"] = sorted(p.name for p in vo.glob("*")) if vo.exists() else []
    return sp


def save_episode(slug, sp):
    """studio.json, script.md (the lines as a director's script) and the film/ shims"""
    d = EPISODES / slug
    (d / "film").mkdir(parents=True, exist_ok=True)
    sp = {k: v for k, v in sp.items() if not k.startswith("_")}
    n = 0
    for ln in sp.get("lines", []):                 # line ids in order: L001, L002...
        n += 1
        ln["id"] = f"L{n:03d}"
    (d / "studio.json").write_text(json.dumps(sp, indent=1, ensure_ascii=False) + "\n")
    names = {}
    for c in sp.get("cast", []):
        y = CHARACTERS / c["id"] / "character.yaml"
        info = yaml.safe_load(y.read_text()) if y.exists() else {}
        names[c["id"]] = kebab(info.get("short") or c["id"]).replace("-", "").upper()
    script = [f"# {sp.get('title', slug)}", "", f"Made in the web studio: the set is `{sp.get('background', '')}`; "
              "the production is `studio.json` (the cast, where they stand, their voices and the lines).", ""]
    for ln in sp.get("lines", []):
        if ln.get("text", "").strip():
            script.append(f"[{ln['id']}] {names.get(ln['who'], ln['who'].upper())}: {ln['text'].strip()}")
    (d / "script.md").write_text("\n".join(script) + "\n")
    f = d / "film" / "__init__.py"
    if not f.exists():
        f.write_text(f'"""{sp.get("title", slug)}, made in the web studio (studio/web): the film/ modules come from the\n'
                     'auto-director (studio/web/auto) and studio.json."""\n')
    for mod, what in SHIMS.items():
        p = d / "film" / f"{mod}.py"
        if not p.exists() or "studio.web.auto" in p.read_text():
            p.write_text(SHIM.format(what=what, mod=mod))
    return sp


def add_voice(slug, cid, data, filename):
    """a character's recording for an episode: voiceovers/NN-<id>.<ext>, NN the character's place in the cast"""
    d = EPISODES / slug / "voiceovers"
    d.mkdir(parents=True, exist_ok=True)
    ext = (re.search(r"\.[a-z0-9]+$", filename.lower()) or [".wav"])[0]
    if ext not in AUDIO_TYPES:
        raise ValueError(f"not a recording: {filename}")
    sp = load_episode(slug)
    order = [c["id"] for c in sp["cast"]]
    n = order.index(cid) + 1 if cid in order else len(order) + 1
    for p in d.glob(f"*-{cid}.*"):
        p.unlink()
    p = d / f"{n:02d}-{cid}{ext}"
    p.write_bytes(data)
    for c in sp["cast"]:
        if c["id"] == cid:
            c["voice"] = dict(kind="recording", file=p.name)
    save_episode(slug, sp)
    return p.name


def delete_episode(slug):
    d = EPISODES / slug
    if not (d / "studio.json").exists():
        raise ValueError("only web episodes can be deleted here")
    shutil.rmtree(d)
