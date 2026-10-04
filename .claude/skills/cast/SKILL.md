---
name: cast
description: Prepare a library character to be filmed by the film engine (studio/film) - write their film.yaml, build their drawings and check the face landmarks. Use when a new character is needed for an episode, when a kit is re-delivered, or when a character's face animates wrongly (eyes, mouth or size off).
---

# Casting a character for film

The film engine animates **whole drawings**: a view's assembled guide figure (or any drawing on a model or pose
sheet), cut out complete, upscaled 4x, with face landmarks so the mouth, eyes, brows and head can be animated by
warping the drawing itself. Nothing is chopped into limbs.

## 1. The character must be in the library

`library/characters/<id>/` with its kit (`kit/<outfit>/<view>.png` plus `<view>.yaml`, imported and labelled as in
the README "Adding characters") or at least a model sheet in `reference/`. Check `character.yaml`: if it says
`style: provisional`, tell the user the character is a stand-in.

## 2. Write `library/characters/<id>/film.yaml`

```yaml
# Drawings this character is filmed in (studio/film/art.py): each is cut whole from its sheet, upscaled 4x and
# given face landmarks. Check build/film/<id>_check.jpg after any change.
drawings:
  front: {kit: casual/front, faces: F}
  q34:   {kit: casual/three_quarter, faces: R}
  side:  {kit: casual/side, faces: R}
```

Keys (full list in the `studio/film/art.py` docstring):

- `kit: <outfit>/<view>` takes the guide figure. `sheet: reference/<file>.png` with `box: [x0, y0, x1, y1]` cuts any
  drawing (read coordinates with `python3 -m studio.qc.grid <sheet> <out.jpg> --step 100`).
- `faces`: F, L, R or B, the way the drawing faces. A three-quarter view facing the viewer's right is R; mirroring
  in a shot flips it.
- `ed`: the eye distance it is sized by, in sheet px, when the automatic one is wrong. Some drawings have eyes set
  wide, so the character looks small next to the others in a two-shot.
- `close_mouth: [cx, cy, rx, ry]`: a drawing with an open, shouting mouth, painted shut so the lip sync can drive
  it. Prefer a drawing with a closed mouth for talking.
- `marks: {eyes: [[x, y, w, h], ...], mouth: [x, y, w, h], chin: [x, y], neck: [x, y]}`: hand-set landmarks when
  detection fails (beards, glasses, hair over the eyes). `head: [x0, y0, x1, y1]` if the head box is wrong.
- `extend: 0.4` continues a waist-up drawing's body down, so it never ends in mid-air. `x8: true` adds a second
  upscale pass for small drawings filmed large. `plain: true` means no face to animate (backs).

## 3. Build and check

```bash
python3 -m studio.film.art <id>            # all drawings; name some to rebuild only those; --force to redo
```

Open `build/film/<id>_check.jpg`. Each drawing is shown on magenta with its landmarks. Check:

- the cut is complete: no missing hands or feet, no paper left round it, no neighbouring drawing included;
- the eye boxes sit on the eyes (pupils inside), the mouth box on the mouth, the chin dot on the chin, and the neck
  dot where the head meets the body (head turns fade out there);
- the resting mouth is closed.

Then render one still of the character in a close single and in a two-shot (`produce` skill, step 5) and look at
the eyes moving, a blink and a mouth shape before using them in a cut.

The first render or still of an episode builds any missing drawings automatically (`prepare` in
`studio/film/__main__.py`), but check them as above before relying on them.
