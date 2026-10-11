# Ronaldo — You Can't Suspend Greatness

This is a new **unrendered**, fictional animated Ronaldo/Bruno comedy episode for the existing Animation Studio house engine. Use the user-approved Goldbridge–Carragher "Fraud Off" clip's rapid dialogue/reaction direction as reference, NOT its actual cast or dialogue.

## Produce

1. Use the existing `studio.film` engine and `studio/web/autoprod.py`.
2. Import the production director script plus 4 new standalone empty 1920x1080 background plates from the companion local production ZIP `Ronaldo_Director_And_BGS.zip` supplied in ChatGPT. The PNGs are not in this branch.
3. Use character libraries `cristiano-ronaldo`, `bruno-fernandes`; do not replace their approved likenesses. Import optional Ronaldo new mouth and expression PNGs only after registering head anchors. Existing source-art exports are available in two separate asset packs supplied earlier.
4. Use the two actor sheets to make real voiceovers individually. The autoproducer can use stand-in TTS for rough timing but those must not be misrepresented as finished character performances.
5. `python3 -m studio.web.autoprod ronaldo-you-cant-suspend-greatness` imports the pack when staged; then `EP_RES=960x540 python3 -m studio.film ronaldo-you-cant-suspend-greatness still 3.5 21 46` for review and `python3 -m studio.film ronaldo-you-cant-suspend-greatness render` when prepared; check CLI version and episode files before executing.
6. Deliver 720p preview first. Inspect the mouth, face and ground-contact QA, voice timing, short physical-gag holds. Only produce the 4K master once user approves the preview.

**Status:** production script and character voice sheets committed to this branch; new scene plates attached as downloadable ZIP, not committed; no MP4 rendered.
**Premise:** fictional parody, not confirmed actual national-team discipline.
**No Runway.**
