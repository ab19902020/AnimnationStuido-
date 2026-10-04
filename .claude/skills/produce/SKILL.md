---
name: produce
description: Produce an episode from a director's script the All or Something way (studio/film). Use when the user gives a script, a production pack or voice recordings and asks for an episode, a scene or a test to be made, re-cut or fixed.
---

# Producing an episode

The user directs; you produce. The benchmark is All or Something, Episode 1: every movement right, every cut right,
lip sync exact. The house method is the one that made it (`studio/film`). Follow it, then go through
`checklist.md` (next to this file) before you show anyone anything.

## The method in one paragraph

Characters are **whole drawings** from their kit (the assembled guide figure of a view), never chopped into limbs.
They act with their **faces and heads**: the mouth, eyes, brows, smile and head are animated by warping the drawn
face. Bodies don't move, so the **camera and the edit** carry the scene, like a documentary. Use close singles with
the set blurred behind and a piece of furniture in front (a table's edge or a chair back hiding the hands), two-shots
of a pair behind the table, inserts on the props that change the story, an opening move along the set, and hard cuts
on the line. Real recorded **foley and room tone** go under a tight **dialogue edit**.

## Steps (from the repo root; SLUG = the episode folder)

1. **File what arrived** (see CLAUDE.md "Filing uploads"). The script goes to `episodes/SLUG/script.md` with lines
   `[L001] NAME: text`, and the pack to `pack/`. Voice recordings go to `episodes/SLUG/voiceovers/` named in
   speaking order: `01-<character id>.mp3`, or `01-<id>-1.mp3` and `01-<id>-2.mp3` when an actor's sheet comes in
   parts. Copy them byte for byte and compare sha256 with what is already there. Identify every file by
   transcribing it (see "Hearing a recording" below); never trust upload names.
2. **Cast**: every speaking character needs `library/characters/<id>/film.yaml` and built drawings. Use the `cast`
   skill. Check `build/film/<id>_check.jpg` for each.
3. **The film package**: `episodes/SLUG/film/`. Copy `episodes/the-appeals-department/film/` as the template and
   rewrite every file for the new script:
   - `lines.py`: `RECORDINGS` [(file, speaker)], `IDS` (the lines in this cut), `MAXGAP` (0.22), `TEMPO` (1.0 for
     real performances), `EXTRA` (ARPAbet for words the aligner lacks), `script()`.
   - `timeline.py`: `SEQ`, the dialogue edit. `("gap", s, "mark")`: **the mark names the gap's START**, so a cut
     mark sits on the end of the previous line and the gap is the new shot's lead-in before its line. For a silent
     beat (an insert, a look) of length d after a line, write `("gap", 0.3), ("gap", d, "cut_x")`.
   - `perf.py`: the acting. `META` per line (delivery tag from `studio/film/perf.py` TAGS, who it is said to,
     stressed words), resting faces (`BASE`), and the script's beats: `GAZE` (looks at the door, a prop, the lens),
     `EXPR` (reactions), `NODS`, `TURN`, `FORCED` blinks, `NOBLINK` holds. Pass the cut times
     (`cuts=[s["t"] for s in SHOTS]`) so no blink lands just after a cut.
   - `direction.py`: the shot list. `PLATES` (sets from `library/backgrounds/`), `OCCL` (furniture polygons in 1x
     plate px, traced with `python3 -m studio.qc.grid`), `EYES` (off-screen eyelines that match the seating),
     `DRAW`, `SET` (each single's blurred wall and foreground edge), `SHOTS`, `TITLE`, `CAPTIONS`.
   - `props.py`: set dressing (`plate_image`, e.g. a sign on the wall, a plate cleaned of clutter) and the inserts,
     drawn in the house look: flat colours, the kit's ink outline, hands built from the characters' skin colours.
   - `sound.py`: ambience beds, foley on the picture's marks, beeps for electronics, the title boom.
4. `python3 -m studio.film SLUG lines`: finds every line in the recordings (Whisper places each stretch, then
   pocketsphinx force-aligns it word by word) and cuts it. It fails loudly if a line is missing or a word is not in
   the dictionary: add the word to `EXTRA`.
5. `python3 -m studio.film SLUG timeline`, then stills: `EP_RES=960x540 python3 -m studio.film SLUG still T ...`
   at least once inside every shot, plus the inserts' key moments. Look at every one (tile them into one image in
   the scratchpad). Fix and repeat until the checklist passes.
6. `python3 -m studio.film SLUG sound` (the mix is -16 LUFS), then `check` (Whisper hears every line in the mix).
7. `python3 -m studio.film SLUG render`, which renders `episodes/SLUG/SLUG.mp4` at 1920x1080 and 30 fps with the
   mix, one job per core. Then `sheet` makes `build/contact.jpg` (three frames of every shot) and `lips` makes
   `build/lips.jpg` (the speaker's mouth at each line's stressed words and its first M/B/P). Look at both, and fix
   and re-render until they are right.
8. Commit the sources (`film/`, `voiceovers/`, film.yaml files, anything added to `library/` plus
   `library/INDEX.md` from `python3 tools/index_library.py --check`) and the finished mp4. It must be under 100 MB;
   if not, re-encode with a higher crf. Never commit `build/`. Push, then send the video with SendUserFile.

## Hearing a recording

```python
from studio.film.voices import heard, stretches   # Whisper on every stretch between pauses
from studio.episode.asr import transcribe, wer      # one file; word error rate against the script
```

`heard(path, y16, cache_dir)` returns `[[start, end, text]]` and is cached by the file's hash. Match the texts
against the script's actor sheets to know whose voice and which lines a file holds.

## Where things are

- `studio/film/`: `engine.py` (plates, drawings, compositing), `face.py` (the face warps, visemes), `perf.py`
  (acting), `shots.py` and `render.py` (shot kinds and the frame), `graphics.py` (captions, title card, grade),
  `voices.py` (cutting lines), `timeline.py`, `audio.py` (the mix, loudness, `check_words`), `art.py` and
  `cast.py` (drawings).
- Sound effects: `library/audio/sfx/<category>/<name>.ogg` (CC0, sources in `manifest.json`). To add one, add an
  entry to the manifest and run `python3 tools/get_sfx.py <category/name>`.
- Fonts for captions and titles: `library/fonts/` (Bebas Neue, Inter, Montserrat; OFL).
- The older cut-out pipeline (`studio/episode/`) is retired for episodes. Its speech tools (`asr.py`, `tts.py`,
  `upscale.py`) are still used.
