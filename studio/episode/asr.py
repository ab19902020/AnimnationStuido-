"""Speech recognition (Whisper large-v3-turbo via sherpa-onnx; `tools/fetch_models.sh whisper`), used to check that
a take says what the script says: for text-to-speech stand-ins, and later for recordings.

    from studio.episode.asr import transcribe, wer"""
import re

import numpy as np
import soundfile as sf

from studio.paths import MODELS

_rec = None
WHISPER = MODELS / "sherpa-onnx-whisper-turbo"


def recognizer():
    global _rec
    if _rec is None:
        import sherpa_onnx as so
        _rec = so.OfflineRecognizer.from_whisper(
            encoder=str(WHISPER / "turbo-encoder.int8.onnx"), decoder=str(WHISPER / "turbo-decoder.int8.onnx"),
            tokens=str(WHISPER / "turbo-tokens.txt"), language="en", task="transcribe", num_threads=4)
    return _rec


def transcribe(path):
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(1)
    if sr != 16000:
        import librosa
        x = librosa.resample(x, orig_sr=sr, target_sr=16000)
    # whisper wants a little silence round speech
    x = np.concatenate([np.zeros(4000, np.float32), x, np.zeros(8000, np.float32)])
    s = recognizer().create_stream()
    s.accept_waveform(16000, x)
    recognizer().decode_stream(s)
    return s.result.text.strip()


ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen").split()
TENS = "x x twenty thirty forty fifty sixty seventy eighty ninety".split()


def spell(n):
    """a whole number 0-9999 in words, the way it is said aloud: 2298 -> two thousand two hundred ninety eight"""
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (spell(n % 100) if n % 100 else [])
    return spell(n // 1000) + ["thousand"] + (spell(n % 1000) if n % 1000 else [])


def digits_to_words(text):
    """numerals as words, so '115' and 'a hundred and fifteen' compare equal; four-digit numbers from 1100 to 2099 are
    read as years (1999: nineteen ninety nine)"""
    def one(m):
        n = int(m.group(0).replace(",", ""))
        if 1100 <= n <= 2099:
            return " ".join(spell(n // 100) + (spell(n % 100) if n % 100 else ["hundred"]))
        return " ".join(spell(n)) if n < 10000 else m.group(0)
    return re.sub(r"\d[\d,]*", one, text)


def words(text):
    text = text.lower().replace("\u2019", "'").replace("-", " ")
    text = digits_to_words(text)
    # "a hundred and fifteen" and "one hundred fifteen" are the same number: ignore the filler words
    ws = [w for w in re.sub(r"[^a-z0-9' ]+", " ", text).split() if w not in ("and", "a")]
    return [w for i, w in enumerate(ws) if not (w == "one" and i + 1 < len(ws) and ws[i + 1] in ("hundred", "thousand"))]


def wer(ref, hyp):
    """word error rate of hyp against ref (edit distance over words / words in ref)"""
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, b in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (a != b))
    return d[len(h)] / max(1, len(r))
