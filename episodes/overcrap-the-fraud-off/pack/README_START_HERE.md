# THE FRAUD OFF — Overcrap Daily | Studio handoff

**What this is:** a fictional, animated football-pundit parody of Mark Goldbridge and Jamie Carragher. The dialogue is newly scripted comedy, **not** a transcript or a genuine recording. Tone: playful confrontation; nobody actually comes to blows.

## Start here (production studio)
1. Read `DIRECTORS_SCRIPT_30_SECONDS.md` **before** opening assets. Treat its 30-second version and timeline as the production edit.
2. Reuse the studio set/backgrounds, seated base models, mouth libraries and animation engine from the existing project. No replacement backgrounds are needed.
3. Import 6 transparent character sheets from `Character_Sheets/` **or** 24 pre-isolated cutouts from `Individual_Poses/`. Mapping is in `POSE_MANIFEST.csv`.
4. Generate/load each actor's voice **separately** using files under `Voice_Lines/`. Expression tags are delivery directions, not words to be spoken.
5. Align dialogue at the word/phoneme level, animate gestures/cuts to *actual* timing, and deliver a 720p review preview with proper synced audio. Do not render an expensive 4K final before approval.
6. After approval, render full-quality final and return a reproducible project package (source, audio, images, timeline, fonts/SFX rights information).

## Contents
- `DIRECTORS_SCRIPT_30_SECONDS.md`: timed dialogue, shot list, acting notes, edit/audio/animation rules, quality bar
- `ORIGINAL_UNCUT_DIALOGUE.md`: the exact earlier script before trimming; a fallback if voice recordings already exist
- `Voice_Lines/`: separate per-character lines for the 30-second cut and the full original
- `Character_Sheets/`: three sheets each, four poses per sheet
- `Individual_Poses/`: the 24 full-body cartoon poses separated into independent transparent PNG assets
- `POSE_MANIFEST.csv`: pose ID to PNG mapping
- `SHOT_TIMELINE.csv`: machine-friendly draft timings (revise against recorded voices)

**NOTE ON ASSET CONSISTENCY:** The new pose sheets are additional reaction/gesture art. If existing hero characters in the project are a closer visual match, preserve those for base shots and swap in the new gestures where consistent. Avoid unexpected face/outfit changes between cuts.

**Intended delivery:** 30-second version (target 30.0s); social 9:16 crop where feasible, with 16:9 wide master compatible with the established studio project if available. Do not stretch/distort widescreen backgrounds or characters.
