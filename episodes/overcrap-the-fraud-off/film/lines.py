"""Which recording each scripted line comes from. Each actor read his lines into one file: Jamie's four lines (with a
laugh before the first), Mark's four (his long ones run together). Every line is found in its recording and cut
word-exact (studio.film.voices.from_recordings).
-> build/lines/<id>.wav and build/lines.json"""
import re

from studio.film import ep

SPEAKER = {"JAMIE": "jamie", "MARK": "mark"}
SCRIPT = ep.DIR / "script.md"
VO = ep.DIR / "voiceovers"
RECORDINGS = [(VO / "01-jamie-carragher.mp3", "jamie"), (VO / "02-mark-goldbridge.mp3", "mark")]
IDS = [f"L{n:03d}" for n in range(1, 9)]
MAXGAP = 0.16          # pauses inside a line are trimmed to this: quick-fire banter
GAPS = {}
TEMPO = 1.0            # the performances as recorded: never sped up
# what Whisper mishears (Jamie's stretched shout: "Froooots!", "FROTS!"), so the line can be placed (the words are then force-aligned as scripted)
HEARD = {"01-jamie-carragher.mp3": {r"fro+t?s!*": "FRAUD!"}}
EXTRA = {"goldbridge": "G OW L D B R IH JH", "brent": "B R EH N T", "payslip": "P EY S L IH P"}


def script():
    """every scripted line in order: [(id, speaker, text)]"""
    return [(lid, SPEAKER[spk], text) for lid, spk, text in
            re.findall(r"^\[(L\d+)\]\s+([A-Z]+):\s*(.+)$", SCRIPT.read_text(), re.M)]
