"""Where everything lives. All paths are absolute, resolved from the repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "library"
CHARACTERS = LIBRARY / "characters"
BACKGROUNDS = LIBRARY / "backgrounds"     # <setting>/<name>.png, indexed in backgrounds.yaml
PROPS = LIBRARY / "props"                 # <set>/<name>.png (cut out), indexed in props.yaml
EXTRAS = LIBRARY / "extras"               # background cast: crowds, crew
REFERENCE = LIBRARY / "reference"         # finished artwork kept for the look, not animation assets
AUDIO = LIBRARY / "audio"
VOICES = AUDIO / "voiceovers"             # <character id>/ : the voice bank (episode recordings live in the episode)
SFX = AUDIO / "sfx"
MUSIC = AUDIO / "music"
FONTS = LIBRARY / "fonts"
EPISODES = ROOT / "episodes"
SHOWS = ROOT / "shows"                    # <slug>/show.json: a show's cast, sets and voices; pack/: its directive
MODELS = ROOT / "models"
BUILD = ROOT / "build"

VIEWS = ("front", "three_quarter", "side", "back")     # drawn views; left-facing ones are mirrors
SHEETS = VIEWS + ("hands",)


def character_dir(cid):
    return CHARACTERS / cid


def voice_dir(cid):
    return VOICES / cid


def build_dir(*parts):
    p = BUILD.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
