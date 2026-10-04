"""Face test cards, to check the face rigs by eye.

    python3 -m studio.face.card CHARACTER [OUTFIT]        -> build/face/<id>_card.jpg
        one character's heads in every view, acting (blinks, glances, expressions) and in every lip-sync shape
    python3 -m studio.face.card --overview [CHARACTER ...] -> build/face/overview_<n>.jpg
        every character's views side by side, resting and talking: where each mouth and eye sits"""
import sys

import cv2
import numpy as np
import skia
import yaml

from studio.face import draw as fd
from studio.face import mouth as mouths
from studio.paths import BUILD, CHARACTERS, build_dir

STATES = [
    ("neutral", fd.expression("neutral")),
    ("blink .5", fd.expression("neutral", blink=0.5)),
    ("blink", fd.expression("neutral", blink=1.0)),
    ("look L", fd.expression("neutral", gaze=(-1.0, 0.0))),
    ("look R", fd.expression("neutral", gaze=(1.0, 0.0))),
    ("look up", fd.expression("neutral", gaze=(0.0, -1.0))),
    ("happy", fd.expression("happy")),
    ("angry", fd.expression("angry")),
    ("sad", fd.expression("sad")),
    ("surprised", fd.expression("surprised", mouth=mouths.shape("o"))),
    ("skeptical", fd.expression("skeptical")),
    ("smug", fd.expression("smug")),
] + [(f"mouth {k}", fd.expression("neutral", mouth=mouths.shape(k))) for k in "XABCDEFGH"]


def card(cid, outfit=None):
    c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text())
    outfit = outfit or next(iter(c["outfits"]))
    views = [v for v in ("front", "three_quarter", "side") if (BUILD / "rig" / cid / outfit / v / "face").exists()]
    cell = 260
    surf = skia.Surface(cell * len(STATES), (cell + 24) * len(views))
    cv = surf.getCanvas()
    cv.clear(skia.Color(200, 200, 200))
    font = skia.Font(skia.Typeface("DejaVu Sans"), 15)
    ink = skia.Paint(AntiAlias=True, Color=skia.Color(150, 0, 0))
    for r, view in enumerate(views):
        d = BUILD / "rig" / cid / outfit / view
        head = fd.skimage(d / "head_face.png")
        face = fd.Face(d / "face")
        s = (cell - 20) / max(head.width(), head.height())
        for i, (name, st) in enumerate(STATES):
            cv.save()
            cv.translate(i * cell + 10, r * (cell + 24) + 28)
            cv.scale(s, s)
            cv.drawImage(head, 0, 0, fd.SAMPLING, skia.Paint(AntiAlias=True))
            face.draw(cv, st)
            cv.restore()
            cv.drawString(f"{view[:5]} {name}", i * cell + 6, r * (cell + 24) + 18, font, ink)
    img = surf.makeImageSnapshot().toarray()[..., :3]
    out = build_dir("face") / f"{cid}_card.jpg"
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


OVERVIEW = [("rest", fd.expression("neutral")), ("talk C", fd.expression("neutral", mouth=mouths.shape("C"))),
            ("D", fd.expression("happy", mouth=mouths.shape("D"))), ("F", fd.expression("neutral", mouth=mouths.shape("F")))]


def overview(cids, per_sheet=6):
    """one row per character: each view resting and talking"""
    cell = 200
    rows = []
    for cid in cids:
        c = yaml.safe_load((CHARACTERS / cid / "character.yaml").read_text())
        outfit = next(iter(c["outfits"]))
        surf = skia.Surface(cell * len(OVERVIEW) * 3, cell + 20)
        cv = surf.getCanvas()
        cv.clear(skia.Color(200, 200, 200))
        font = skia.Font(skia.Typeface("DejaVu Sans"), 13)
        ink = skia.Paint(AntiAlias=True, Color=skia.Color(150, 0, 0))
        for v, view in enumerate(("front", "three_quarter", "side")):
            d = BUILD / "rig" / cid / outfit / view
            if not (d / "face" / "face.json").exists():
                continue
            head = fd.skimage(d / "head_face.png")
            face = fd.Face(d / "face")
            s = (cell - 10) / max(head.width(), head.height())
            for i, (name, st) in enumerate(OVERVIEW):
                x = (v * len(OVERVIEW) + i) * cell
                cv.save()
                cv.translate(x + 5, 18)
                cv.scale(s, s)
                cv.drawImage(head, 0, 0, fd.SAMPLING, skia.Paint(AntiAlias=True))
                face.draw(cv, st)
                cv.restore()
                label = f"{cid[:16]} {view[:5]} {face.f['mouth']['found']}" if i == 0 else name
                cv.drawString(label, x + 4, 14, font, ink)
        rows.append(surf.makeImageSnapshot().toarray()[..., :3])
    outs = []
    for k in range(0, len(rows), per_sheet):
        out = build_dir("face") / f"overview_{k // per_sheet}.jpg"
        cv2.imwrite(str(out), np.vstack(rows[k:k + per_sheet]), [cv2.IMWRITE_JPEG_QUALITY, 85])
        outs.append(out)
    return outs


if __name__ == "__main__":
    if sys.argv[1:2] == ["--overview"]:
        cids = sys.argv[2:] or sorted(p.name for p in CHARACTERS.iterdir() if (p / "character.yaml").exists())
        for o in overview(cids):
            print(o)
    else:
        print(card(*sys.argv[1:3]))
