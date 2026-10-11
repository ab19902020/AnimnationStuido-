"""Which recording each scripted line comes from: Mark read his three lines into one file, Gary his four. Every line is
found in its recording and cut word-exact (studio.film.voices.from_recordings).
-> build/lines/<id>.wav and build/lines.json"""
import re

from studio.film import ep

SPEAKER = {"MARK": "mark", "GARY": "gary"}
SCRIPT = ep.DIR / "script.md"
VO = ep.DIR / "voiceovers"
RECORDINGS = [(VO / "01-mark-goldbridge.mp3", "mark"), (VO / "02-gary-neville.mp3", "gary")]
IDS = [f"L{n:03d}" for n in range(1, 8)]
MAXGAP = 0.16          # pauses inside a line are trimmed to this: quick-fire
GAPS = {"L005": 0.42}  # "Still... at least": the hopeful pause stays
TEMPO = 1.0            # the performances as recorded: never sped up
EXTRA = {}


def script():
    """every scripted line in order: [(id, speaker, text)]"""
    return [(lid, SPEAKER[spk], text) for lid, spk, text in
            re.findall(r"^\[(L\d+)\]\s+([A-Z]+):\s*(.+)$", SCRIPT.read_text(), re.M)]
