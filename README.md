# Animation Studio

A South Park-style cut-out animation studio. You upload character kits, backgrounds and voiceovers and give a
directive; Claude cuts the puppets, lip-syncs the voices, acts, stages and shoots the scenes, and renders the
episode (landscape 16:9).

**Status: being built.** Done so far: the character library and kit ingest (every part of every sheet found,
named and checked). Next: the puppet rigs, the shared mouth/eye library, the voice pipeline, the renderer.

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
| `library/characters/<id>/` | `character.yaml` (name, height, outfits) and `kit/<outfit>/<view>.png` (the kit sheets as uploaded), each with a `<view>.yaml` saying which drawing is which part |
| `library/backgrounds/`, `library/sfx/`, `library/music/`, `library/fonts/` | sets, sound effects, music, fonts |
| `episodes/<slug>/` | one folder per episode: your directive, the voiceovers, the production script, the finished video |
| `studio/` | the engine |
| `tools/` | importing kits, fetching models |

## Characters

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
| Roy Keane | casual | stand-in (off-style; a dark-outline kit is coming) |
| Gary Neville | casual | stand-in (off-style; a dark-outline kit is coming) |
| Jamie Carragher | casual | stand-in (off-style; a dark-outline kit is coming) |

## Adding characters

Upload the kit zips (front, three-quarter, side and hands sheets, like the United Road kits). Claude runs

```bash
python3 tools/import_kit.py KIT.zip --outfit home      # copies the sheets into the library
python3 -m studio.ingest.kit label CHARACTER           # finds and names every part
python3 -m studio.ingest.chart CHARACTER               # build/ingest/<id>_charts.jpg: every part in one fixed layout
```

and checks the chart by eye before the character is used.
