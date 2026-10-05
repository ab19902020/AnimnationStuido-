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
aligner could follow the singing, shapes read off the separated voice everywhere else, two frames ahead of the
voice as an animator leads the sound). Check the printed lines:

- `onto the attacks`: the beat tracker and the band onsets each report their windows' centres, tens of ms off the
  real hits; everything is moved by its measured median offset onto the drums' true attacks (printed per kind);
- `bar line`: the bar starts where the chords change (a rock kick lands on 1 and 3 alike, so the kick only breaks a
  tie): one beat of the four should stand clearly above the others;
- the bar count, then the timed lines (`timeline.LINES`): every section of the film hangs off them.

Where an instrument plays (a harmonica bit, a sax solo): look for the bars where the voice is silent and a lead
line carries the tune (a log-frequency spectrogram of `build/stems/accompaniment.wav` shows it), and ask the audio
tagger (`tools/fetch_models.sh tagging`: CED, AudioSet's classes, per bar). The tagger is weak on heavily produced
mixes; when it cannot say, put the instrument where the evidence points and tell the user the time, so they can
move it.

## 3. The film package

- `timeline.py`: the song's bars and lyric lines as marks (`bar(n)`, `LINES`), `TL` with a tail for the end card.
- `perf.py`: who sings what (`sing(PERF, who, spans, gain=...)`: the lead takes every note at gain 1; backing
  singers every line at 0.85 (anyone shown at a mic sings); players without a mic the choruses at 0.55; a crowd
  singing along with every word at 0.7, a frame late; `PLAYS = {who: spans}` for an instrument that only plays in
  its bits, like a harmonica), and the dancing
  (`GROOVE = Groove({who: [(t0, t1, move, amount)]})`: bounce, sway, headbang, jump, hop, rock, nod, pump, shuffle,
  lean), section by section. Give the dancing an arc: small in the verses, big in the choruses, everything in the
  last chorus. Faces: `BASE` and `EXPR` (one character's change of heart is a story). Someone the song is not for
  (a villain of the piece) stands still with a sour face while everyone jumps, never sings, nods out of time
  (`awkward`), stares into the lens, and gets a cutaway under a rain cloud (`cloud=True`) with a caption.
- `direction.py`: `PLATES`, `OCCL` (what is in front of whom: the drum kit, the monitors), `LAMPS` (beams),
  the band's blocking by feet and height in plate px (`BAND_F`; an instrument with `inst`, a mic with `mic`, the
  drummer's `DRUMS` with his fist drawing), and the shot list, cut on the bars: wides and stage wides, close shots
  with the lens on one player and everyone else out of focus (`on`), two-shots (only of neighbours: two players far
  apart make a shot of whoever stands between them), and crowd shots from the stage (`crowd`, `reverse`).
  Lighting per section (`CALM`, `VERSE`, `CHORUS`, `ANTHEM`), a follow spot for a solo or a quiet bridge, a strobe.
- Crowd shots are taken from the stage, so everything in them must say so: behind the people the back of the room
  (never the stage: a plate showing the stage behind a crowd makes them look away from the band), the stage's own
  floor and lit edge across the bottom of the frame (`stage_edge`), the people placed by their eyes and eye distance
  so heads match, with `look_at` on the band (`person` does it: eyes up at the stage, converging on the lens), the
  stage's moving lights sweeping over them (`sweep`). Never a front row in silhouette there: dark backs of heads
  put the camera behind the crowd.
- A busy floor: the wides and stage wides have a row of fans in silhouette between the lens and the stage
  (`fg_fans`: the camera is behind the crowd there), and every crowd shot a far row of small faces behind its
  people. Instruments a whole drawing cannot hold with its hands down go on a rack: the harmonica in a neck rack
  (`inst="harmonica"`), up at the lips while he plays.
- `props.py`: plates cleaned for the band (the stand painted out), the room behind the crowd made night (dark
  windows, the room's own lamps glowing, the stage's red spill), the fans cut from a crowd plate, overlays.
- `sound.py`: the song as supplied plus a crowd before and after it.

## 4. Look, render, check

Stills of every kind of shot (`EP_RES=960x540 python3 -m studio.film SLUG still T ...`, then full size), a preview
of one section with sound (`render --range A B`, then frame strips a quarter beat apart), then the full render
(`render`), `sheet` and `lips`. Go through `.claude/skills/produce/checklist.md` and the music-video points:

- every cut on a bar line (or a beat inside a bar), never in the middle of a beat, landing on the frame nearest
  it (direction.py moves every cut half a frame early); no jump cuts: consecutive shots of the same player change
  size clearly (1.4x or more) or angle;
- the lead's mouth closed in the gaps between lines and on the M of every "home"; nobody mouths in a silence; plot
  the mouth against the voice for a few lines: the mouth opens with the voice, not after it;
- dancing on the beat (the dip of a bounce, the landing of a jump on the beat), everyone a few milliseconds apart,
  nobody frozen in a chorus; a headbang carried by the body, the face's nod held small (a big one squashes the face);
- everything facing the right way: a right-handed guitarist's neck to his left (the viewer's right); the keyboard
  seen from behind, the hands on the keys out of sight; the hi-hat on the drummer's left;
- the drummer plays what the song plays: pull the frames at each eighth of a bar (the hat on every eighth, the
  snare on 2 and 4 where the song's snare is); strumming down through the strings on the beat;
- no sharp prop or hand in front of a blurred player (blur the layer with the player); no paper-white left between
  an arm and the body (the cut grows each hole into its pale fringe; check white shorts survive it, or set
  `auto_holes: false`);
- crowd: heads of matching size, eyes on the band, the back of the room behind them, the stage's edge in front,
  nobody floating full-body.
