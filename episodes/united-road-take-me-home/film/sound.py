"""The soundtrack: the song as supplied (untouched, it is mastered), with a real pub crowd round it: murmuring and
whistling in the dark before the band starts, roaring as the lights come up, and cheering over the end card after
the last chord. python3 -m studio.film united-road-take-me-home sound -> build/episode_audio.wav"""
import numpy as np

from studio.film import audio as A
from studio.film import ep
from film.timeline import SONG_END, TL, bar


def song():
    import librosa
    y, _ = librosa.load(str(ep.DIR / "song.mp3"), sr=A.SR, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return y.T.astype(np.float32)


def main():
    total = TL["total"]
    mus, crowd = A.Bus(total), A.Bus(total)
    y = song()
    mus.add(y, 0.0)
    # before the band: a full pub, murmuring; it swells as the lights come up on bar 2 and falls under the music
    a, b = 0.0, bar(4)
    def env(tt):
        return np.where(tt < bar(2), 0.55 + 0.45 * np.clip(tt / bar(2), 0, 1),
                        np.clip(1 - (tt - bar(2)) / (b - bar(2)), 0, 1))
    A.bed(crowd, "crowd/crowd-large", a, b, -27, lowpass=5000, fin=0.6, fout=0.8, gain_fn=env)
    A.ev(crowd, "crowd/applause-big", bar(2) - 0.3, -25, dur=3.0)
    # after the last chord: the roar and the applause, over the end card
    A.ev(crowd, "crowd/applause-big", SONG_END - 1.2, -20, dur=total - SONG_END + 1.2)
    A.bed(crowd, "crowd/crowd-large", SONG_END - 1.5, total, -24, lowpass=7000, fin=0.8, fout=1.2)
    mix = mus.x + crowd.x
    peak = np.abs(mix).max()
    if peak > A.db(-1):
        mix *= A.db(-1) / peak
    import soundfile as sf
    out = ep.path("episode_audio.wav")
    sf.write(str(out), mix.astype(np.float32), A.SR, subtype="PCM_24")
    print(f"{out}  {len(mix) / A.SR:.2f}s  {A.lufs(mix):.1f} LUFS  peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS")
