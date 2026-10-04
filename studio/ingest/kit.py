"""Kit sheets -> labelled pieces.

    python3 -m studio.ingest.kit label [CHARACTER ...] [--force]   # auto-label sheets that have no YAML yet
    python3 -m studio.ingest.kit show  [CHARACTER ...]             # redraw the named overviews from the YAML
    python3 -m studio.ingest.kit swap  CHARACTER VIEW PART_A PART_B # fix a mix-up (e.g. mouth neck)
    python3 -m studio.ingest.kit check CHARACTER [VIEW ...]        # mark sheets as checked by eye

Each sheet library/characters/<id>/kit/<outfit>/<view>.png gets <view>.yaml beside it: which drawing is which
part, as a point inside the drawing (sheet pixels). The auto-labeller writes a first draft with `checked: false`;
look at build/ingest/<id>/<outfit>/<view>_parts.jpg, correct the YAML by hand and set `checked: true`.
Optional per-sheet fixes in the same YAML:
    split:  [[x0, y0, x1, y1], ...]      cut a drawing in two along this line (touching drawings)
    erase:  [[[x, y], [x, y], ...], ...]  polygons painted out before slicing (a doubled nose, a stray label)"""
import argparse
import sys

import cv2
import numpy as np
import yaml
from scipy import ndimage

from studio.ingest import classify, sheet
from studio.paths import CHARACTERS, build_dir

HEADER = ("# Which drawing on {view}.png is which puppet part: a point inside each drawing (sheet pixels).\n"
          "# Draft from the auto-labeller. Check build/ingest/{cid}/{outfit}/{view}_parts.jpg, fix by hand,\n"
          "# then set checked: true. Paired parts are anatomical: _R is the character's own right.\n")


def sheets(cids=None):
    for yml in sorted(CHARACTERS.glob("*/character.yaml")):
        cid = yml.parent.name
        if cids and cid not in cids:
            continue
        for png in sorted((yml.parent / "kit").glob("*/*.png")):
            yield cid, png.parent.name, png.stem, png


def inside(p):
    """the deepest point of a drawing: inside it even for thin or curved shapes"""
    m = p.mask[p.y0:p.y1, p.x0:p.x1]
    d = ndimage.distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1]
    y, x = np.unravel_index(np.argmax(d), d.shape)
    return [int(p.x0 + x), int(p.y0 + y)]


def prepare(png, spec=None):
    """the cleaned sheet with the YAML's erase polygons painted out and split lines cut, and its pieces"""
    rgba = sheet.clean(sheet.load_rgba(png))
    spec = spec or {}
    for poly in spec.get("erase", []) or []:
        m = np.zeros(rgba.shape[:2], np.uint8)
        cv2.fillPoly(m, [np.array(poly, np.int32)], 1)
        rgba[m > 0] = 0
    for x0, y0, x1, y1 in spec.get("split", []) or []:
        cv2.line(rgba, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 0, 0), 3)
    return rgba, sheet.pieces(rgba, gap=3)


def skin_of(cid, outfit):
    hp = CHARACTERS / cid / "kit" / outfit / "hands.png"
    if not hp.exists():
        hp = next((CHARACTERS / cid / "kit").glob("*/hands.png"), None)
    rgba, ps = prepare(hp)
    _, poses = classify.hands(rgba, ps)
    return classify.skin_tone(rgba, [p for pr in poses.values() for p in pr.values()])


def auto(cid, outfit, view, png, skin, fixes=None):
    """Draft labels for one sheet. `fixes` (the split/erase lists of an existing YAML) are applied first and kept."""
    fixes = {k: v for k, v in (fixes or {}).items() if k in ("split", "erase") and v}
    rgba, ps = prepare(png, fixes)
    cuts = []
    if view == "hands":
        guide, poses = classify.hands(rgba, ps, cuts)
        named = {f"{pose}_{s}": [p] for pose, pr in poses.items() for s, p in pr.items()}
    else:
        guide, named = classify.body(rgba, ps, skin, view)
    doc = dict(checked=False, guide=inside(guide),
               parts={k: [inside(p) for p in v] for k, v in sorted(named.items())})
    split = list(fixes.get("split", [])) + [c for c in cuts if c not in fixes.get("split", [])]
    if split:
        doc["split"] = split
    if fixes.get("erase"):
        doc["erase"] = fixes["erase"]
    return doc


def resolve(png, spec):
    """YAML spec -> (cleaned sheet, {name: [pieces]}, guide piece, unused pieces)"""
    rgba, ps = prepare(png, spec)
    lab = np.full(rgba.shape[:2], -1, np.int32)
    for p in ps:
        lab[p.mask] = p.idx

    def at(pt):
        x, y = int(pt[0]), int(pt[1])
        i = lab[y, x]
        if i < 0:   # the point fell in a hole (inside an eye ring): take the nearest drawing
            ys, xs = np.nonzero(lab >= 0)
            k = np.argmin((xs - x) ** 2 + (ys - y) ** 2)
            i = lab[ys[k], xs[k]]
        return ps[i]

    named = {k: [at(pt) for pt in v] for k, v in (spec.get("parts") or {}).items()}
    guide = at(spec["guide"]) if spec.get("guide") else None
    used = {id(p) for v in named.values() for p in v} | {id(guide)}
    unused = [p for p in ps if id(p) not in used and p.kind == "part"]
    return rgba, named, guide, unused


def show(cid, outfit, view, png, spec):
    rgba, named, guide, unused = resolve(png, spec)
    names = {}
    for k, v in named.items():
        for p in v:
            names[p.idx] = k
    if guide is not None:
        names[guide.idx] = "GUIDE"
    for p in unused:
        names[p.idx] = "UNUSED"
    shown = [p for v in named.values() for p in v] + ([guide] if guide is not None else []) + unused
    out = build_dir("ingest", cid, outfit) / f"{view}_parts.jpg"
    sheet.overview(rgba, shown, out, names=names, scale=0.75)
    return out


def save(yml, spec, cid, outfit, view):
    yml.write_text(HEADER.format(view=view, cid=cid, outfit=outfit) +
                   yaml.safe_dump(spec, sort_keys=False, default_flow_style=None, width=110))


def fix(argv):
    """python3 -m studio.ingest.kit swap  CHARACTER VIEW PART_A PART_B [OUTFIT]   swap two labels
       python3 -m studio.ingest.kit check CHARACTER [VIEW ...]                    mark sheets as checked by eye"""
    cmd, cid = argv[0], argv[1]
    if cmd == "swap":
        view, a, b = argv[2:5]
        outfit = argv[5] if len(argv) > 5 else None
        for c, o, v, png in sheets([cid]):
            if v == view and (outfit is None or o == outfit):
                yml = png.with_suffix(".yaml")
                spec = yaml.safe_load(yml.read_text())
                p = spec["parts"]
                p[a], p[b] = p.get(b), p.get(a)
                spec["parts"] = {k: v for k, v in p.items() if v is not None}
                save(yml, spec, c, o, v)
                print(f"{c} {o} {v}: swapped {a} <-> {b}", file=sys.stderr)
    elif cmd == "check":
        views = argv[2:]
        for c, o, v, png in sheets([cid]):
            if not views or v in views:
                yml = png.with_suffix(".yaml")
                spec = yaml.safe_load(yml.read_text())
                spec["checked"] = True
                save(yml, spec, c, o, v)
                print(f"{c} {o} {v}: checked", file=sys.stderr)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("swap", "check"):
        return fix(sys.argv[1:])
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["label", "show"])
    ap.add_argument("chars", nargs="*")
    ap.add_argument("--force", action="store_true", help="relabel even sheets that already have a YAML")
    a = ap.parse_intermixed_args()
    skins = {}
    for cid, outfit, view, png in sheets(a.chars):
        yml = png.with_suffix(".yaml")
        if a.cmd == "label":
            old = yaml.safe_load(yml.read_text()) if yml.exists() else None
            if old and (not a.force or old.get("checked")):
                spec = old          # a checked sheet is never relabelled
            else:
                if (cid, outfit) not in skins:
                    skins[cid, outfit] = skin_of(cid, outfit)
                spec = auto(cid, outfit, view, png, skins[cid, outfit], old)
                save(yml, spec, cid, outfit, view)
        else:
            spec = yaml.safe_load(yml.read_text())
        out = show(cid, outfit, view, png, spec)
        n = sum(len(v) for v in spec["parts"].values())
        miss = sorted(set(_expected(view)) - set(spec["parts"]))
        print(f"{cid:17s} {outfit:7s} {view:14s} {n:2d} pieces  missing={miss}  -> {out.name}", file=sys.stderr)


def _expected(view):
    if view == "hands":
        return [f"{p}_{s}" for p in classify.HAND_POSES for s in "RL"]
    return ["head", "eyes", "mouth", "neck", "torso", "pelvis"] + \
        [f"{p}_{s}" for p in classify.PAIRED for s in "RL"]


if __name__ == "__main__":
    main()
