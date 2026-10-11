# Gary Neville × Mark Goldbridge — animation-ready production handoff

This pack is for Claude Code operating **inside the user's existing GitHub projects**. It is not a replacement drawing pack and does not include any newly generated character artwork. **Use the original repo's real animation drawings, rather than the off-style contact sheets previously supplied.**

## Correct source of truth

1. Main production/source rigs: `ab19902020/Passmic`, `main`, `series/ep01/` — Episode 1: International Break Emergency. This includes **Mark Goldbridge and Gary Neville**, their real sheets, mouth shapes, rig corrections and studio views.
2. Later related production: `ab19902020/TV-show-`, branch `claude/animated-episode-production-yvajlc`, `overcrap-daily-ronaldo-vs-messi/` — reuses Mark's and the studio's original Passmic art/engine, adding direction and polish. Study that episode before modifying anything; preserve its upgrades.
3. Do **not** take Gary from `AnimnationStuido-` as a final replacement unless the character has been explicitly restyled. Its library labels Gary Neville as an off-style stand-in, and the Mark Goldbridge entry is reference-only with no four-view kit yet.

**Goal:** animate the 35–40 second studio sketch using the exact existing Goldbridge/Neville character art, cutouts and viseme assets, without rebuilding/reinterpreting the faces or costumes. A short 16:9 master fits these engines; frame a separate 9:16 version only after the landscape master passes QC, protecting both faces from cropping.

## Production route

- Open the repo and source branch; inspect the latest usable `overcrap-daily-ronaldo-vs-messi` production as the finish target. Pull the original Gary and Mark assets from `Passmic/series/ep01`, keeping every existing anchor and mouth fit.
- Prefer the existing `front_a`, `wide`, and `reverse` studio plates and their seated positions/foreground mattes. Don't replace these with the generated studio illustration.
- Reuse exact provided expression/bust/upper-body sprites; add animation as drawing swaps, blinks, short nods and timed pointing/shrugging poses.
- Align voice clips to words, then map phonemes to the characters' original mouth banks. Do not create a new AI likeness or a new mouth in a different style.
- Build a contact sheet and 720p review render, inspect mouths on several stressed words, then render final only after approval.

**Files included:** director's scene and dialogue, separate actor scripts, exact known assets/rig notes, engine cue plan, QC checklist and a local asset-audit script. The asset-audit script is run from within the checked-out `Passmic` repo to confirm source drawings before work begins.

## Important limitation

This ZIP is **production instructions, not an exported finished puppet kit**. It intentionally does not include fake cutouts from the off-style artwork. Original PNG assets must be read directly from the existing repositories by Claude so their pixel geometry and rig placements are preserved.
