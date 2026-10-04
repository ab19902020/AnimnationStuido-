# Audio

Everything you can hear. The recordings drive the animation (the voices set the timing, the mouths follow them),
so this is where they live and how they are named.

```
library/audio/
  voiceovers/<character id>/   the voice bank: one folder per character (20 ready)
  sfx/<category>/              sound effects, e.g. crowd/, footsteps/, whoosh/
  music/                       songs, stings and beds
episodes/<episode slug>/voiceovers/   the recordings for ONE episode (not here)
```

## Voiceovers

**Episode recordings go with the episode**, in `episodes/<slug>/voiceovers/`, because they are that episode's
source material. Name them for who speaks and in what order, so a character is never a guess:

```
01-gary-neville.wav        02-roy-keane.wav        03-jamie-carragher.wav
```

Use the character ids from `library/characters/` (full names in kebab-case, so the two Garys can never be
mixed up: `gary-neville`, `gary-lineker`). One file per speaker line or per speaker per scene, whichever the
recording gives you; a single file with several speakers in it is fine too, name it for the scene
(`scene-03-studio-argument.wav`): the diarizer (`tools/fetch_models.sh diarize`) works out who speaks when.

**The voice bank, `voiceovers/<character id>/`, is for voice material that is reused across episodes:**

- `reference-*.wav`: clean solo samples of that voice (10-30 seconds, no music, no one talking over), for
  matching speakers when several voices share one recording.
- `lines/<what-it-is>.wav`: lines worth reusing: catchphrases, laughs, groans, reactions.

Formats: WAV or FLAC for anything you record yourself; MP3 or M4A is fine too. Keep the originals untouched: the
recording sets the timing, so don't trim or retime it before it goes in.

## Sound effects and music

- `sfx/<category>/<what-it-is>.wav`, lower-case kebab-case: `sfx/crowd/stadium-roar.wav`.
- `music/<artist>-<title>.mp3`. If a track needs a credit or a licence note, put it in `music/CREDITS.md`.
