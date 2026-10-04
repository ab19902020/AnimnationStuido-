"""Which recording each scripted line comes from, and how tight the delivery is. The actors read their sheets
(pack/Voice_Lines) into one file per character, Gary and Roy in two parts: episodes/<slug>/voiceovers/. Every line is
found in its recording and cut word-exact (studio.film.voices.from_recordings).
-> build/lines/<id>.wav and build/lines.json"""
import re

from studio.film import ep

SPEAKER = {"GARY": "gary", "ROY": "roy", "MICAH": "micah", "PEP": "pep", "RONALDO": "ronaldo"}
SCRIPT = ep.DIR / "script.md"
VO = ep.DIR / "voiceovers"
RECORDINGS = [(VO / "01-gary-neville-1.mp3", "gary"), (VO / "01-gary-neville-2.mp3", "gary"),
              (VO / "02-roy-keane-1.mp3", "roy"), (VO / "02-roy-keane-2.mp3", "roy"),
              (VO / "03-micah-richards.mp3", "micah"), (VO / "04-pep-guardiola.mp3", "pep"),
              (VO / "05-cristiano-ronaldo.mp3", "ronaldo")]
# the test: Scene 1 and the start of Scene 2
IDS = [f"L{n:03d}" for n in range(1, 15)]
MAXGAP = 0.22          # pauses inside a line are trimmed to this
GAPS = {}              # per-line overrides
TEMPO = 1.0            # the performances as recorded
EXTRA = {"cris": "K R IH S", "ted": "T EH D"}


def script():
    """every scripted line in order: [(id, speaker, text)]"""
    return [(lid, SPEAKER[spk], text) for lid, spk, text in
            re.findall(r"^\[(L\d+)\]\s+([A-Z]+):\s*(.+)$", SCRIPT.read_text(), re.M)]
