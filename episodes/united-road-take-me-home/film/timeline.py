"""The song's own timeline: no dialogue edit, the marks are the song's (build/song.json, python3 -m studio.film SLUG
song): every bar (bar0, bar1, ...) and the sections, from the timed lyrics. Shots, dancing and lights hang off
these, so they land on the music."""
import json

from studio.film import ep

S = json.loads(ep.path("song.json").read_text())
DOWN = S["downbeats"]


def bar(n):
    """the time of bar n's downbeat (bars counted from the first downbeat of the song)"""
    if n < len(DOWN):
        return DOWN[n]
    per = 4 * (DOWN[-1] - DOWN[-2]) / 4 if len(DOWN) > 1 else 2.0
    return DOWN[-1] + (n - len(DOWN) + 1) * per


def bar_at(t):
    """the bar a time falls in"""
    n = 0
    while n + 1 < len(DOWN) and DOWN[n + 1] <= t:
        n += 1
    return n


LINES = S["lines"]                                    # [[start, end, text]] the lyric lines in order
marks = {f"bar{n}": round(b, 3) for n, b in enumerate(DOWN)}
marks.update({f"line{n}": round(l[0], 3) for n, l in enumerate(LINES)})
marks.update({f"line{n}_end": round(l[1], 3) for n, l in enumerate(LINES)})
SONG_END = S["duration"]
TAIL = 5.0                                            # the end card, over the crowd's cheering
marks["song_end"] = SONG_END
marks["end"] = SONG_END + TAIL
TL = dict(total=round(SONG_END + TAIL, 3), lines={}, marks=marks)
