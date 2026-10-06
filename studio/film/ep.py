"""The episode being made: set by `python3 -m studio.film SLUG ...` before the episode's own modules
(episodes/<slug>/film/*.py) are imported, so they can find their files."""
import os
from pathlib import Path

from studio.paths import EPISODES

SLUG = os.environ.get("FILM_EPISODE", "")
DIR = EPISODES / SLUG if SLUG else None
BUILD = DIR / "build" if SLUG else None


def use(slug):
    global SLUG, DIR, BUILD
    SLUG = slug
    os.environ["FILM_EPISODE"] = slug
    DIR = EPISODES / slug
    BUILD = DIR / "build"
    BUILD.mkdir(parents=True, exist_ok=True)
    return DIR


def path(*p):
    return Path(BUILD).joinpath(*p)


def song_path():
    checked = DIR / "song-timing.json"
    return checked if checked.exists() else path("song.json")
