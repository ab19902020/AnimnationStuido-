# Exact existing rig source — do not redraw

Source: https://github.com/ab19902020/Passmic/tree/main/series/ep01

## Existing art and layout
- `series/ep01/sheets/mark.png` and `series/ep01/sheets/gary.png` — **the real source character drawings**.
- `series/ep01/sheets/layout.json` — true 1672×941 sheet bands, crop boxes and sprite names; preserve the data, never use coordinates from our generated contact sheets.
- `series/ep01/characters/mark/rig.json` — custom Goldbridge mouth anchors; notably `expressions/angry_rant`, `expressions/shouting`, `expressions/sad`, `expressions/confused`, `upper/crossed_arms`.
- `series/ep01/characters/gary/rig.json` — Gary's original `_mouth_ratio`: 0.28.
- `series/ep01/characters/<name>/<panel>/<drawing>.png` — actual cut sprites created by the pipeline; full source sheets are on top.
- `series/ep01/characters_x16/` — existing high-resolution bust/body sprite upgrades where available.

### Drawing names already supported on both source sheets
- Expressions: `neutral`, `angry_rant`, `shouting`, `smug`, `sad`, `shocked`, `confused`, `laughing`, `facepalm`.
- Upper-body: `arms_down`, `pointing`, `both_hands_out`, `crossed_arms`, `shrug`, `fist_pump`, `holding_phone`, `holding_mic`, `desk_rant`.
- Mouths: `rest`, `a`, `e`, `i`, `o`, `u`, `smile`, `frown`, `wide_shout`.
- Head views: `front`, `three_quarter`, `side`.
- Body: `stand_neutral`, `lean_forward_ranting`, several walking poses and `run`.

### Engine references
- `series/ep01/episode.py` — cameras `M`, `Mc`, `G`, `Gc`, `2`, `W`, plus per-line STAGE with pose and face changes keyed to words.
- `tools/ep/epengine.py` — animation and lips/shot renderer, using existing sprites.
- `tools/ep/render.py` — still and video render commands.
- `series/ep01/backgrounds/{front_a,wide,reverse}.json` — room and occlusion configs; reuse their matching plates from `backgrounds/src/` and `x4/`.
- `series/ep01/README.md` — full instructions, 4x and 16x image upscale pipeline, phone-based mouth sync and background mattes.

### Recommended animation edits for THIS short
1. Mark's furious opening: `upper/both_hands_out`, `expressions/angry_rant`; for “WORST” use his original shout face while lip syncing over the original mouth.
2. Gary's “three weeks ago”: `upper/crossed_arms` + `expressions/sad` / `neutral`, then the original deadpan-looking neutral face.
3. Mark's rock-bottom line: `upper/pointing` and `upper/shrug`. No invented shovel prop is necessary.
4. Final Gary line: `upper/arms_down` + `expressions/neutral`, mouth low energy, a motionless eye hold.

### Image quality rules
New imagery, *if absolutely required*, must match the **existing sprite edges and geometry**, not merely the thumbnail. No pre-rendered caption/contact-sheet graphics as character layers. Alpha-transparent sprites on consistent scale, no duplicate face or hands, preserve collar, body placement, mouth anchor and skin tone. Never treat a finished thumbnail as an animation rig.

### Source verification
- https://github.com/ab19902020/Passmic/blob/main/series/ep01/sheets/layout.json
- https://github.com/ab19902020/Passmic/blob/main/series/ep01/characters/mark/rig.json
- https://github.com/ab19902020/Passmic/blob/main/series/ep01/episode.py
- https://github.com/ab19902020/TV-show-/blob/claude/animated-episode-production-yvajlc/overcrap-daily-ronaldo-vs-messi/README.md
