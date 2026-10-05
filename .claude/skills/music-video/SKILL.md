---
name: music-video
description: Make a music video for a song with the film engine - a band of library characters on a stage and a crowd, singing, playing and dancing to the beat (studio/film/song.py, stage.py). Use when the user gives a song (and lyrics) and asks for a music video, a performance, a band or a sing-along.
---

# Making a music video

The music video is made the house way (whole drawings, faces that act, the camera and the edit carrying it), with
everything locked to the song. `episodes/united-road-take-me-home/` is the worked example: copy its `film/` package.

## 1. File the song

`episodes/<slug>/song.mp3` (or .wav), untouched, and `lyrics.md` with the lyrics as supplied (section headings in
square brackets are skipped). New sets go in `library/backgrounds/` (+ `backgrounds.yaml`), instruments and other
props in `library/props/<set>/` (cut with `tools/cut_props.py`), new characters with their `film.yaml` (the `cast`
skill; a group sheet like `library/reference/squad/` can hold many characters, each `film.yaml` pointing at its box).

## 2. Analyse the song

```bash
tools/fetch_models.sh separate whisper
python3 -m studio.film SLUG song        # build/song.json and build/stems/
```

`song.json` holds the beat grid, the bars (`downbeats`), the kick, snare and crash hits, the loudness, the lyrics
timed line by line and word by word, and the singers' mouths per frame (`lead`: the aligned phones where the
aligner could follow the singing, shapes read off the separated voice everywhere else). Check the printed bar
count and look at the timed lines (`timeline.LINES`): every section of the film hangs off them.

## 3. The film package

- `timeline.py`: the song's bars and lyric lines as marks (`bar(n)`, `LINES`), `TL` with a tail for the end card.
- `perf.py`: who sings what (`sing(PERF, who, spans, gain=...)`: the lead takes every note at gain 1; backing
  singers the choruses at 0.8; a crowd singing along at 0.7, a frame late), and the dancing
  (`GROOVE = Groove({who: [(t0, t1, move, amount)]})`: bounce, sway, headbang, jump, hop, rock, nod, pump, shuffle,
  lean), section by section. Give the dancing an arc: small in the verses, big in the choruses, everything in the
  last chorus. Faces: `BASE` and `EXPR` (one character's change of heart is a story).
- `direction.py`: `PLATES`, `OCCL` (what is in front of whom: the drum kit, the monitors), `LAMPS` (beams),
  the band's blocking by feet and height in plate px (`BAND_F`; an instrument with `inst`, a mic with `mic`, the
  drummer's `DRUMS` with his fist drawing), and the shot list, cut on the bars: wides and stage wides, close shots
  with the lens on one player and everyone else out of focus (`on`), two-shots, and crowd shots from the stage
  (`crowd`, people placed by their eyes and eye distance so heads match, a front row of fans in silhouette).
  Lighting per section (`CALM`, `VERSE`, `CHORUS`, `ANTHEM`), a follow spot for a solo or a quiet bridge, a strobe.
- `props.py`: plates cleaned for the band (the stand painted out), the fans cut from a crowd plate, overlays.
- `sound.py`: the song as supplied plus a crowd before and after it.

## 4. Look, render, check

Stills of every kind of shot (`EP_RES=960x540 python3 -m studio.film SLUG still T ...`, then full size), a preview
of one section with sound (`render --range A B`, then frame strips a quarter beat apart), then the full render
(`render`), `sheet` and `lips`. Go through `.claude/skills/produce/checklist.md` and the music-video points:

- every cut on a bar line (or a beat inside a bar), never in the middle of a beat;
- the lead's mouth closed in the gaps between lines and on the M of every "home"; nobody mouths in a silence;
- dancing on the beat, everyone a few milliseconds apart, nobody frozen in a chorus;
- the drummer's sticks hit on the hits; strumming on the eighths; keys pressed on the beat;
- no sharp prop or hand in front of a blurred player (blur the layer with the player);
- crowd: heads of matching size, a front row in silhouette, nobody floating full-body.
