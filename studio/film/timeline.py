"""The dialogue edit: every line in script order with the beats between them, and the named marks the shots, the
acting and the sound hang off. An episode's timeline.py gives SEQ:

    ("gap", seconds[, "mark"])   room tone before the next item; the mark names its start (a cut, a look...)
    ("line", id)                 the line, its length from build/lines.json
    ("mark", "name")             a named point at the current time

-> TL = {"total": s, "lines": {id: {start, end, speaker}}, "marks": {name: t}}"""


def build(seq, lines):
    t, out, marks = 0.0, {}, {}
    for it in seq:
        kind = it[0]
        if kind == "gap":
            if len(it) > 2:
                marks[it[2]] = round(t, 3)
            t += it[1]
        elif kind == "mark":
            marks[it[1]] = round(t, 3)
        elif kind == "line":
            d = lines[it[1]]
            out[it[1]] = dict(start=round(t, 3), end=round(t + d["dur"], 3), speaker=d["speaker"])
            t += d["dur"]
    marks["end"] = round(t, 3)
    return dict(total=round(t, 3), lines=out, marks=marks)
