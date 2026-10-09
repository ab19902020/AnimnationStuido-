# Broken Tele

*Boy Parent Problems.* A short family comedy, about 1 min 54 s, 1920 x 1080, 30 fps, made the All or Something
way with `studio/film`. The script is `script.md`; the storyboard it grew from is `pack/storyboard.png`.

A boy of very few words breaks the telly with his toy car. Dad buys the same one again (£799), toys are banned,
then let back in, soft ones only. Two minutes later the soft ball goes through the new one. The parents give up
on tellies and get a projector, and the boy looks up at it.

## Voices

- **The boy** is the real recording, `voiceovers/01-family-boy.m4a`: three takes of "TV's broken". The first
  (flat) is the first telly, the third (long, drawn out) the second, the second (rising, a question) the gag after
  the title. His words are timed by hand (`film/lines.py` `KID_WORDS`); the aligner can't follow a toddler.
- **Mum, Dad and the shop assistant** are text-to-speech stand-ins (Kokoro: `bf_emma`, `bm_george`, `bm_lewis`).
  Real recordings replace them: put each actor's read of their lines in `voiceovers/` and switch `film/lines.py`
  to `RECORDINGS` (see `episodes/the-appeals-department/film/lines.py`).

## Making it

From the repository root:

    python3 -m studio.film broken-tele lines      # cut every line: build/lines/, lines.json
    python3 -m studio.film broken-tele sound      # the mix: build/episode_audio.wav
    EP_RES=960x540 python3 -m studio.film broken-tele still 16.6 21.9
    python3 -m studio.film broken-tele render     # -> broken-tele.mp4
    python3 -m studio.film broken-tele sheet      # build/contact.jpg

The family are library characters (`library/characters/family-boy`, `family-mum`, `family-dad`), cut whole from
their pose and expression sheets (`film.yaml`). The sets are their own rooms (`library/backgrounds/home/family-*`,
`street/family-car-interior`, `street/electronics-shop-tv-aisle`) and the props `library/props/household/`.
`film/props.py` does the action: the drawn cracked and smashed screens warped onto the telly and revealed from
where the toy hits, the toys in the air, the glass, the flash and shake, the projector, and the inserts.
