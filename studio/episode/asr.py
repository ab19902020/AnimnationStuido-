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


def words(text):
    text = text.lower().replace("’", "'").replace("-", " ")
    return re.sub(r"[^a-z0-9' ]+", " ", text).split()


def wer(ref, hyp):
    """word error rate of hyp against ref (edit distance over words / words in ref)"""
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, b in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (a != b))
    return d[len(h)] / max(1, len(r))
