# Animation Studio: working notes for Claude

See `README.md` for what this is. The user directs; you produce. Quality bar: a South Park / Simpsons episode,
right first time. The user's best previous work (All or Something, Episode 1) is the benchmark for lip sync and
timing.

- Everything runs from the repo root as modules: `python3 -m studio.<package>.<module>`.
- Dependencies come from `.claude/hooks/session-start.sh` (pip `requirements.txt`, apt `libegl1` for Skia).
  Big speech models are fetched on first use by `tools/fetch_models.sh` (GitHub releases only: HuggingFace is
  unreachable from cloud sessions). `models/realesrgan_x4_anime6b.onnx` (upscaler) is committed.
- Source files are committed (`library/`, episode audio and scripts); everything under `build/` is regenerated.
  Never commit build products; finished episode videos are committed, each file under 100 MB.
- House style is the bold dark-outline kit look (Haaland's kit is the reference). Characters with
  `style: provisional` in `character.yaml` are off-style stand-ins until their new kit arrives.
- Kit sheets: every sheet has a `<view>.yaml` of part labels. After `label`, look at
  `build/ingest/<id>_charts.jpg`; fix mistakes with `python3 -m studio.ingest.kit swap ...` or by editing the YAML
  (`split` lines for touching drawings, `erase` polygons for doubled noses or title text), then `check` the sheet:
  `kit check` takes ONE character (`check CHARACTER [VIEW ...]`); a second name is read as a view and nothing is
  checked. Use `python3 -m studio.qc.grid` to read sheet coordinates.
- Filing uploads: the library layout and naming are in `library/README.md`. Characters are `library/characters/<id>/`
  (id = full name in kebab-case, e.g. `gary-neville`, so the two Garys never clash), other art for them goes in
  `reference/` and is described in `character.yaml`. Voice recordings for an episode go in
  `episodes/<slug>/voiceovers/` as `01-<character id>.wav`; reusable voice material in
  `library/audio/voiceovers/<character id>/`. Unzip uploads to the scratchpad, compare sha256 with what is already
  in the library (a re-delivered kit is usually byte-identical: don't duplicate it), and copy files byte for byte.
- After adding anything to `library/`, run `python3 tools/index_library.py --check`: it rewrites
  `library/INDEX.md` (commit it) and lists anything unfiled, undescribed or unchecked. Backgrounds must be landscape
  16:9 to be used full-frame; the index marks portrait ones.
- Paired parts are anatomical: `_R` is the character's own right. In right-facing views the near side is the
  character's right.
- Episodes: `studio/episode/` makes them from `episodes/<slug>/` (steps in the README, "Making an episode"). Commit the
  episode's sources (`script.md`, `pack/`, `cast.yaml`, `beats.yaml`, `cues.yaml`, `staging.yaml`, `shots.yaml`); never
  `build/` or the preview mp4 (both git-ignored). For a talking shot use the kit's assembled guide figure as the body
  with the head, eyes and mouth drawn over it (`Puppet`): the rig's loose limbs show their joints and look wrong.
  Review by rendering stills (`render --stills T ...`) and looking, then `check --video`.
- Keep the repo root clean: no loose uploads or scratch files (use the session scratchpad).
