# Animation Studio

A South Park-style cut-out animation studio. You upload character kits, backgrounds and voiceovers and give a
directive; Claude cuts the puppets, lip-syncs the voices, acts, stages and shoots the scenes, and renders the
episode (landscape 16:9).

**Status: being built.** Done: the character library and kit ingest, the puppet rigs, and a first end-to-end
episode pipeline, run as a test on *The Appeals Department* with text-to-speech voices (see "Making an episode"). Not
done: limb animation that looks right (the rigs' joints show; walks need art drawn for it), real recordings in
place of the stand-in voices, final props.

## How it works (the South Park way)

- **One library, reused everywhere.** Every character is a puppet built once from their kit and kept in
  `library/characters/`. Episodes only reference them, like South Park's character library.
- **Every body part moves.** Each view (front, three-quarter, side) is a separate puppet: head, neck, torso,
  pelvis, upper arms, forearms, hands, thighs, shins and feet, each on its own joint.
- **Replacement animation.** Mouths, eyes, brows and hands are swapped instantly, the way South Park's rigs swap
  drawings with a slider; the joints move smoothly, with anticipation and settle.
- **Voices first.** The recordings set the timing: Whisper hears the words, forced alignment times every word and
  sound, and the mouths follow them.

## Layout

| Folder | What's in it |
|---|---|
| `library/INDEX.md` | **start here to find anything**: every character, background, prop and clip (generated). `library/README.md` explains how the library is organised and named |
| `library/characters/<id>/` | `character.yaml` (name, height, outfits, reference sheets), `kit/<outfit>/<view>.png` (the kit sheets as uploaded), each with a `<view>.yaml` saying which drawing is which part, and `reference/` (model sheets, outfit line-ups, expression and pose sheets). The id is the full name in kebab-case |
| `library/backgrounds/<setting>/` | empty sets by setting (stadiums, training-ground, club, tv-and-media, home, spa-and-pool, pub-and-restaurant, nightlife, street, concert), indexed in `backgrounds.yaml` |
| `library/props/<set>/`, `library/extras/` | cut-out props; background cast (crowds, crew) |
| `library/audio/` | `voiceovers/<character id>/` (the voice bank), `sfx/`, `music/` |
| `library/reference/`, `library/fonts/` | finished artwork kept for the look; fonts |
| `episodes/<slug>/` | one folder per episode: `script.md` and `pack/` (the production pack as delivered), `cast.yaml`, `beats.yaml`, `cues.yaml`, `staging.yaml`, `shots.yaml` (see "Making an episode"), the voiceovers (`voiceovers/`, named `01-<character id>.wav`), the finished video. `build/` and `*_preview*.mp4` are regenerated and git-ignored |
| `studio/` | the engine |
| `tools/` | importing kits, fetching models, `index_library.py` (rebuilds the index and checks the library is tidy) |

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

## Making an episode

An episode is a folder `episodes/<slug>/` with the director's `script.md` (scenes, stage directions and lines
`[L001] GARY: ...`) and these files, all read by `studio/episode/`:

| File | What it says |
|---|---|
| `cast.yaml` | who speaks, which library character plays them, and (for test runs) their text-to-speech voice |
| `beats.yaml` | timing: how each scene's allowance is shared between its stage directions, gaps, reaction pauses |
| `cues.yaml` | sound cues placed against beats (card tap, door squeak, chime...) and the room tone |
| `staging.yaml` | who stands where, entrances and exits, props and who holds them, anchored to beats |
| `shots.yaml` | the camera (wide, singles, two-shots, pans, pushes) and the full-frame insert cards |

Everything is anchored to script beats (a line id like `L031`, or a direction like `D3.2`), so when the voices change
the picture retimes with them. The steps, from the repo root:

```bash
tools/fetch_models.sh tts rhubarb whisper               # once: voices (test runs), lip sync, speech recognition
python3 -m studio.episode.script SLUG                   # parse the script; checks it against pack/Dialogue.json
python3 -m studio.episode.tts SLUG                      # a take of every line (test run: text-to-speech)
python3 -m studio.episode.timeline SLUG                 # when everything happens
python3 -m studio.episode.lipsync SLUG                  # mouth shapes for every take
python3 -m studio.episode.soundtrack SLUG               # the mix: voices, cues, room tone; captions.srt
python3 -m studio.episode.render SLUG --stills 5 52     # PNGs of those moments, to review
python3 -m studio.episode.render SLUG --video           # the film, 1920x1080 at 24 fps, with sound
python3 -m studio.episode.check SLUG --video            # words in the final mix, cues, timeline, the file
```

How a frame is made: the kit sheet's own assembled figure is the body (clean, correct), cut at the neck; the head,
eyes and mouth are drawn over it so they can nod, look, blink and talk (`studio/episode/puppet.py`, the mouth shapes
in `mouths.py`). Replacement animation only: no arm or leg moves, entrances and exits are bobbing slides, held props
float at the hand, and the props and cards are plain stand-ins (`graphics.py`). **Real recordings** are not wired in
yet: `timeline`, `lipsync`, `soundtrack` and `render` read `build/tts/<line id>.wav` and `tts.json`, so an import step
that cuts a recording into those files is all it takes.
