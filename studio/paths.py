"""Where everything lives. All paths are absolute, resolved from the repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "library"
CHARACTERS = LIBRARY / "characters"
BACKGROUNDS = LIBRARY / "backgrounds"
SFX = LIBRARY / "sfx"
MUSIC = LIBRARY / "music"
FONTS = LIBRARY / "fonts"
EPISODES = ROOT / "episodes"
MODELS = ROOT / "models"
BUILD = ROOT / "build"

VIEWS = ("front", "three_quarter", "side", "back")     # drawn views; left-facing ones are mirrors
SHEETS = VIEWS + ("hands",)


def character_dir(cid):
    return CHARACTERS / cid


def build_dir(*parts):
    p = BUILD.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
