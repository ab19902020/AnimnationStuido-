# Production checklist

Go through all of it, on stills first and then on the finished film. A "no" anywhere means fix it and look again.
These are the rules All or Something was made by.

## Drawings

- [ ] Every character is a whole drawing from their own kit (`build/film/<id>_check.jpg` checked): no cut limbs,
      no visible joins, no loose parts.
- [ ] The face landmarks are right: the eye boxes sit on the eyes, the mouth on the mouth, the chin and neck where
      they are. A wrong mark warps the wrong place.
- [ ] The resting mouth is closed. Drawings with an open, shouting mouth are not used for talking (or are closed
      with `close_mouth`).
- [ ] The same character is the same size in every shot of the same size: shots ask for an eye distance (`ed`),
      not a scale. Some sheets need an `ed:` in film.yaml (eyes drawn wide apart).
- [ ] Characters marked `style: provisional` are flagged to the user as stand-ins.

## Framing (every shot)

- [ ] Close singles: the wall is out of focus, the character's eyes are about 40 % down the frame, there is look
      room on the side they look to, and the furniture edge in front hides their hands. A standing drawing must
      never show that it isn't sitting.
- [ ] The foreground is clean: no plant or prop in front of a chest. Clean the plate in `props.plate_image`, and
      blend any repair into what is round it (look at a full-resolution frame: a patch shows as a seam or a step
      in an edge line). Trace occluder polygons to the real outline (`studio.qc.grid` at zoom 10 on the corners),
      measured, not fitted: a curve fitted across a hidden stretch drifts.
- [ ] Two-shots: both behind the same furniture line, a similar size, their eyelines meeting.
- [ ] Nobody floats: anything held is held by a drawn hand; nothing hangs in the air.
- [ ] Text is readable: signs, screens and captions are inside their boxes, large enough, and on screen long
      enough to read twice (an insert's text needs at least 1 s after it appears).
- [ ] 16:9, 1920 x 1080, 30 fps; nothing important within 40 px of an edge.

## Screen direction and eyes

- [ ] Write down the seating. Everyone looks the way the seating says: a character to the screen left of another
      looks right to them, in every shot. Off-screen looks use `EYES`, consistent with the seating.
- [ ] Listeners look at the speaker, a beat after they start. The speaker looks at the person the line is said to
      (`META`).
- [ ] Looks the script asks for (the door, the prop, the lens) happen on the beat, and in every shot that sees
      that character.
- [ ] Blinks: never two characters at once, never in a held look into the lens, never in the first frames after a
      cut (it reads as a bad edit: pass `cuts=[s["t"] for s in SHOTS]` to the Performance, and put cued blinks
      0.3 to 0.4 s after the cut); a cued blink on big beats.

## Lip sync and acting

- [ ] Frame grabs at three stressed words per close-up: the mouth shape matches the sound (open vowels open, M/B/P
      closed, F/V on the lip). Closures hold at least 2 frames. The mouth leads the sound by a frame, not after it.
- [ ] Nobody's mouth moves when their voice isn't speaking, and the speaker's mouth stops when the line stops.
- [ ] Every line has a delivery tag, and the faces read: the salesman's smile, the deadpan, the indignant brow.
- [ ] Small nods land on stressed words; nothing jitters; the idle drift is slow.

## The edit

- [ ] Cuts land on the end of a line (marks name the gap's start), with 0.1 to 0.3 s of the new shot before its
      line. No dead air: pauses inside lines are trimmed (`MAXGAP`), and gaps are there only where the script asks.
- [ ] Every silent beat the script asks for is long enough to read: a look 1.2 to 1.5 s, an insert at least 1.5 s
      plus its reading time, a final look into the lens about 1 s before the cut to the title.
- [ ] The sequence makes sense with the sound off: who speaks, who reacts, what the prop says.
- [ ] Contact sheet (`studio.film SLUG sheet`): every shot is different from its neighbours (size or angle). No
      jump cuts between two near-identical frames of the same character.

## Sound

- [ ] Every line is heard as scripted in the final mix: `studio.film SLUG check` (word error rate per line). Look
      into anything flagged: a clipped word means re-cut it; a voice that says it differently means tell the user.
- [ ] Room tone under every scene, cut dead on hard cuts to titles or black.
- [ ] Foley on every visible action (a prop turned over, a tap, steps, a door) in sync with the picture's marks;
      real recordings, no whooshes; electronic sounds (beeps) can be synthesised.
- [ ] Dialogue clear above everything; music ducked under it; -16 LUFS integrated, peaks under -1 dBFS.

## Delivery

- [ ] The finished video is committed under 100 MB, with the sources (`film/`, `voiceovers/`, film.yaml files,
      library additions plus `library/INDEX.md`). `build/` is never committed.
- [ ] Compared with All or Something, Episode 1: lip sync as tight, cuts as well timed, frames as clean. If not,
      it isn't finished.
