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
  (`split` lines for touching drawings, `erase` polygons for doubled noses), then `check` the sheet. Use
  `python3 -m studio.qc.grid` to read sheet coordinates.
- Paired parts are anatomical: `_R` is the character's own right. In right-facing views the near side is the
  character's right.
- Keep the repo root clean: no loose uploads or scratch files (use the session scratchpad).
