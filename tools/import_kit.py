"""Import character kit zips (or unzipped folders) into the library.

    python3 tools/import_kit.py KIT.zip [KIT2.zip ...] [--outfit NAME] [--outfit-map id=outfit,...]
                                [--style house|provisional]

Each kit sheet lands byte-for-byte at library/characters/<id>/kit/<outfit>/<view>.png, where <view> is front,
three_quarter, side, back or hands. The character id is the kebab-cased full name from the kit's
asset_manifest.json ("gary" -> "gary-neville"), so the two Garys never collide. character.yaml is created, or
extended with the new outfit; existing fields are never overwritten."""
import argparse, io, json, re, shutil, sys, zipfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio.paths import CHARACTERS  # noqa: E402

VIEW_ALIASES = {"front": "front", "three_quarter": "three_quarter", "threequarter": "three_quarter",
                "3q": "three_quarter", "34": "three_quarter", "side": "side", "profile": "side",
                "back": "back", "rear": "back", "hands": "hands", "hand": "hands"}


def kebab(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def view_of(name):
    stem = Path(name).stem.lower()
    for alias in sorted(VIEW_ALIASES, key=len, reverse=True):
        if stem.endswith("_" + alias) or stem == alias:
            return VIEW_ALIASES[alias]
    return None


class Source:
    """A kit as a set of files: a zip archive or a directory tree."""

    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_dir():
            self.files = {str(p.relative_to(self.path)): p for p in self.path.rglob("*") if p.is_file()}
            self.zip = None
        else:
            self.zip = zipfile.ZipFile(self.path)
            self.files = {n: n for n in self.zip.namelist() if not n.endswith("/")}

    def read(self, name):
        return self.zip.read(self.files[name]) if self.zip else Path(self.files[name]).read_bytes()


def manifest_people(src):
    """slug -> {name, likeness, outfit} from any asset_manifest.json in the kit"""
    people = {}
    for n in src.files:
        if Path(n).name != "asset_manifest.json":
            continue
        m = json.loads(src.read(n))
        for c in m.get("characters", []):
            slug = c.get("id") or c.get("slug")
            people[slug] = dict(name=c.get("name", slug), likeness=c.get("likeness") or c.get("identity"),
                                outfit=c.get("outfit"))
    return people


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kits", nargs="+")
    ap.add_argument("--outfit", default=None, help="outfit id for every character in these kits")
    ap.add_argument("--outfit-map", default="", help="per-character outfit ids: haaland=home,pep=casual")
    ap.add_argument("--style", default="house", choices=["house", "provisional"])
    a = ap.parse_args()
    omap = dict(kv.split("=") for kv in a.outfit_map.split(",") if kv)

    for kit in a.kits:
        src = Source(kit)
        people = manifest_people(src)
        for n in sorted(src.files):
            if not n.lower().endswith(".png") or "receipt" in n:
                continue
            view = view_of(n)
            slug = Path(n).parent.name
            if view is None:
                print(f"  skip {n}: no view in the file name", file=sys.stderr)
                continue
            info = people.get(slug, dict(name=slug.replace("-", " ").title(), likeness=None, outfit=None))
            cid = kebab(info["name"])
            outfit = omap.get(slug) or omap.get(cid) or a.outfit or "default"
            cdir = CHARACTERS / cid
            dst = cdir / "kit" / outfit / f"{view}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read(n))

            yml = cdir / "character.yaml"
            c = yaml.safe_load(yml.read_text()) if yml.exists() else {}
            c.setdefault("name", info["name"])
            c.setdefault("short", info["name"].split()[-1])
            c.setdefault("style", a.style)
            c.setdefault("height_cm", 180)
            if info.get("likeness"):
                c.setdefault("likeness", info["likeness"])
            outfits = c.setdefault("outfits", {})
            o = outfits.setdefault(outfit, {})
            if info.get("outfit"):
                o.setdefault("description", info["outfit"])
            views = o.setdefault("sheets", [])
            if view not in views:
                views.append(view)
                views.sort(key=lambda v: ("front", "three_quarter", "side", "back", "hands").index(v))
            yml.write_text(yaml.safe_dump(c, sort_keys=False, allow_unicode=True, width=110))
            print(f"{cid:20s} {outfit:10s} {view:14s} <- {n}")


if __name__ == "__main__":
    main()
