# Animation Studio

A cartoon studio for football comedy. You upload character kits, backgrounds and voiceovers and give a director's
script; Claude produces the episode (16:9, 1920 x 1080, 30 fps): the dialogue edit, the acting, the camera, the
sound and the finish. Give Claude the script and say "produce it" (the `produce` skill).

**Latest United Road production:** [combined performance edition](episodes/united-road-take-me-home/README.md).
Continue from this edition, which combines the latest show and vocal timing with the approved connected guitar,
bass and seated drum poses. The [finished 1080p video](episodes/united-road-take-me-home/united-road-take-me-home.mp4) is checked in beside its validation record. Its production notes identify the source files and improvements to preserve.

**Status.** Done: the character library and kit ingest, and the film engine (`studio/film`, the method All or
Something was made with). A 60-second test of *The Appeals Department* is made with the actors' recordings:
`episodes/the-appeals-department/the-appeals-department.mp4` (Scene 1 and the start of Scene 2). A music video,
*United Road (Take Me Home)*: `episodes/united-road-take-me-home/` (the `music-video` skill). Not done: the rest of
The Appeals Department. Gary Neville, Roy Keane and Jamie Carragher are still on off-style stand-in kits.

## The web studio

```bash
python3 -m studio.web            # then open http://localhost:8000   (--host 0.0.0.0 --port N to share it)
```

**Produce from a director's pack** (the Episodes page): drop in the director's script, a picture of each
character, the sets and the voice recordings (or one zip), press *Produce*, and the studio makes the film with
nobody choosing anything (`studio/web/autoprod.py`):

- the script (.md, .txt, .fountain, .docx, .pdf) is read for its title, scenes (`## SCENE` headings or
  `INT.`/`EXT.` sluglines), lines (`[L001] GARY: ...` or `GARY: ...`; actor sheets repeating them are skipped),
  deliveries (`(dry)` before a line) and stage directions (a beat before the next line);
- every speaker becomes a character: a picture named for them (`Roy.png`; a model sheet's first figure is used),
  else the library character of that name (the script's full names tell the two Garys apart);
- pictures that aren't characters (landscape, filling the frame) are sets, filed in the library; each scene gets
  the set its slugline or heading names best, and keeps the last one when it names none;
- each recording goes to the speaker it is named for (`02-roy-keane.mp3`, `Roy take 2.wav`, `L012.wav`), else to
  the speaker whose lines Whisper hears in it; speakers without one get a stand-in voice;
- everyone who speaks in a scene stands in it (on the same set as the scene before, where they stood before);
- then the drawings are cut out, the lines found and cut word-exact for the lip sync, and the film directed,
  mixed and rendered (final 1920 x 1080 with contact and lip sheets, or a quick 960 x 540 draft).

The episode page then shows what was worked out (and anything missing, such as a speaker with no picture) and
everything stays editable: per-scene sets and staging (drag the characters), the cast's drawings and voices, the
lines (who, to whom, delivery, pauses), stills, drafts and the final. **Characters** and **Backgrounds** can also
be added one at a time: a drawing on white or transparent, or a sheet with a box dragged round the drawing; *Fix
face* sets the eyes and mouth by three clicks if detection misses.

A web episode is an ordinary episode folder: `studio.json` (what the page edits), `script.md`, `pack/` (the
documents as delivered), `voiceovers/` and a `film/` package of shims onto the auto-director (`studio/web/auto/`),
which works out the edit, the shots (each scene's establishing wide with a place caption, close singles framed
away from who they talk to with the set blurred behind at its true scale, two-shots, reaction cuts, name
captions, the title card), the acting and the mix. So `python3 -m studio.film SLUG ...` runs it like any other,
and to direct it by hand you replace a shim with real code. Kit zips (four-sheet puppet kits) still go through
Claude (`tools/import_kit.py`).

## How it works (the All or Something method)

- **Whole drawings, never chopped.** A character is filmed as the drawings in their kit (each view's assembled
  figure, or a pose from a model sheet), cut out complete and upscaled 4x (Real-ESRGAN). No limbs are cut, so no
  joins can show.
- **The face acts.** The mouth, eyes, brows, smile and head are animated by warping the drawn face itself: the jaw
  drops for each mouth shape over a painted mouth, the pupils move, the lids blink in skin colour, and the head nods
  and turns. The lip sync comes from the recordings: every word and sound force-aligned, the mouth a frame ahead.
- **The camera and the edit carry the scene,** like a documentary: close singles with the set out of focus and a
  table edge in front, two-shots behind the table, inserts on the props that matter, a move along the set, hard
  cuts on the line, captions and a title card.
- **Real sound.** A tight dialogue edit (pauses trimmed), recorded room tone and foley on every action (CC0
  library in `library/audio/sfx`), loudness to -16 LUFS. Whisper checks every line in the final mix.
- **One library, reused everywhere.** Characters, sets, props and sounds live in `library/` and episodes refer to
  them.

The rules are written down as a checklist (`.claude/skills/produce/checklist.md`) and every episode is checked
against it.

## Layout

| Folder | What's in it |
|---|---|
| `library/INDEX.md` | **start here to find anything**: every character, background, prop and clip (generated). `library/README.md` explains how the library is organised and named |
| `library/characters/<id>/` | `character.yaml` (name, height, outfits, reference sheets), `kit/<outfit>/<view>.png` (the kit sheets as uploaded), each with a `<view>.yaml` saying which drawing is which part, and `reference/` (model sheets, outfit line-ups, expression and pose sheets). The id is the full name in kebab-case |
| `library/backgrounds/<setting>/` | empty sets by setting (stadiums, training-ground, club, tv-and-media, home, spa-and-pool, pub-and-restaurant, nightlife, street, concert), indexed in `backgrounds.yaml` |
| `library/props/<set>/`, `library/extras/` | cut-out props; background cast (crowds, crew) |
| `library/audio/` | `voiceovers/<character id>/` (the voice bank), `sfx/`, `music/` |
| `library/reference/`, `library/fonts/` | finished artwork kept for the look; fonts |
| `episodes/<slug>/` | one folder per episode: `script.md` and `pack/` (the production pack as delivered), the voiceovers (`voiceovers/`, named `01-<character id>.mp3`), the production (`film/`, see "Making an episode"), the finished video. `build/` and `*_preview*.mp4` are regenerated and git-ignored |
| `studio/` | the engine: `film/` (the house method), `web/` (the web studio and its auto-director), `ingest/` (kit sheets), `qc/` (grids and checks), `episode/` (speech tools, and the retired cut-out pipeline with its `rig/`, `anim/` and `face/`) |
| `tools/` | importing kits, fetching models and sound effects (`get_sfx.py`), `index_library.py` (rebuilds the index and checks the library is tidy) |

## Characters

Full list with ids, roles and what each has: `library/INDEX.md`.

| Character | Outfit | Style |
|---|---|---|
| Erling Haaland | home | house |
| Pep Guardiola | casual | house |
| Michael Carrick | casual | house |
| Bruno Fernandes | home | house |
| Matheus Cunha | home | house |
| Jim Ratcliffe | casual | house |
| Patrice Evra | home | house |
| Micah Richards | suit | house |
| Alan Shearer | casual | house |
| Gary Lineker | suit | house |
| Rio Ferdinand | casual | house |
| Cristiano Ronaldo | home | house |
| Wayne Rooney | casual (young cartoon) | house |
| Roy Keane | casual | stand-in (off-style; a dark-outline kit is coming) |
| Gary Neville | casual | stand-in (off-style; a dark-outline kit is coming) |
| Jamie Carragher | casual | stand-in (off-style; a dark-outline kit is coming) |

In the library with reference art only, no puppet kit yet: Carlos Baleba, Youri Tielemans, Andrey Santos
(front-view three-outfit atlases) and 50 Cent (model sheets).

## Adding characters

Upload the kit zips (front, three-quarter, side and hands sheets, like the United Road kits). Claude runs

```bash
python3 tools/import_kit.py KIT.zip --outfit home      # copies the sheets into the library
python3 -m studio.ingest.kit label CHARACTER           # finds and names every part
python3 -m studio.ingest.chart CHARACTER               # build/ingest/<id>_charts.jpg: every part in one fixed layout
```

and checks the chart by eye before the character is used.

## Filming a character

Every character an episode uses needs `library/characters/<id>/film.yaml`, which lists the drawings they are filmed
in, then `python3 -m studio.film.art <id>` and a look at `build/film/<id>_check.jpg` (the face landmarks). The
`cast` skill (`.claude/skills/cast/SKILL.md`) has the details.

## Making an episode

An episode is a folder `episodes/<slug>/`:

| What | |
|---|---|
| `script.md`, `pack/` | the director's script (scenes, stage directions, lines `[L001] GARY: ...`) and the production pack as delivered |
| `voiceovers/` | the actors' recordings, in speaking order: `01-gary-neville-1.mp3`... (one file can hold many lines) |
| `film/` | the production, as Python: `lines.py` (which recording, which lines), `timeline.py` (the dialogue edit and its marks), `perf.py` (the acting), `direction.py` (sets, seating, the shot list, captions), `props.py` (set dressing and inserts), `sound.py` (the mix) |
| `<slug>.mp4` | the finished film (committed, under 100 MB); `build/` is regenerated and git-ignored |

Every cut, look, reaction and sound hangs off the dialogue edit's marks, so when a recording changes the whole film
retimes with it. The steps, from the repo root (the `produce` skill has the whole procedure):

```bash
tools/fetch_models.sh whisper                                    # once: speech recognition
python3 -m studio.film SLUG lines                                # find and cut every line in the recordings
python3 -m studio.film SLUG timeline                             # the edit: marks and line times
EP_RES=960x540 python3 -m studio.film SLUG still 4.5 12 33       # quick frames to look at: build/stills/
python3 -m studio.film SLUG sound                                # the mix: build/episode_audio.wav (-16 LUFS)
python3 -m studio.film SLUG check                                # Whisper hears every line in the mix
python3 -m studio.film SLUG render                               # episodes/SLUG/SLUG.mp4, 1920 x 1080, 30 fps
python3 -m studio.film SLUG sheet                                # build/contact.jpg: three frames of every shot
python3 -m studio.film SLUG lips                                 # build/lips.jpg: the mouths at the stressed words
```

A **music video** is an episode with `song.mp3` and `lyrics.md` in place of the voiceovers: `python3 -m studio.film
SLUG song` works out the beat grid, the bars, the drum hits, the lyrics' timing and the singers' mouths
(`studio/film/song.py`), and stage shots (`studio/film/stage.py`) put a band and a crowd on a set, playing, singing
and dancing to it. The steps are in `.claude/skills/music-video/SKILL.md`.

The earlier cut-out pipeline (`studio/episode/`, read from `cast.yaml`, `beats.yaml`, `cues.yaml`, `staging.yaml`
and `shots.yaml`) is retired for episodes: its loose-limbed rigs showed their joints. Its speech tools
(`studio/episode/asr.py`, `tts.py` for text-to-speech stand-ins, and `upscale.py`) are used by the film engine.
