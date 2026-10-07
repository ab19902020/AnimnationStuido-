# United Road — combined performance edition

This production continues from repository commit `870e192` (6 October 2026) and the supplied `United_Road_Take_Me_Home_FINAL_720p_LATEST-3.mp4`. It merges the approved guitar, bass and seated drumming artwork from the earlier ChatGPT 1080p edition into the latest source.

## Preserve these improvements

- The latest individual dance styles, eye darts, facial acting, opening edit, beat-reactive lighting, fireworks, flags and confetti remain.
- Šeško and Cunha use their approved whole-character instrument poses. Their own connected hands move over the strings and neck; do not restore the old floating-hand instrument overlays.
- Maguire uses his approved seated pose. His own fists grip the sticks, the continuous forearms move, and the kit occludes the performance. The corrected eye landmarks exclude the eyebrow, with brow deformation disabled on this pose.
- Faces travel rigidly with the dancing body; the additional face-nod compression is disabled.
- Bruno takes the vocal track throughout the song. Backing singers and fans follow it too. The band joins the complete final chorus, repeated anthem and Glory Glory build. Instrumental rests remain closed.
- Lineker, Shearer, Richards and Carragher stay excluded. Youri Tielemans stays included by explicit user instruction.

## Source map

`film/direction.py`: cameras, instrument framing, layers, kit occlusion and show effects.
`film/perf.py`: individual dance styles, expressions, singing and the final chorus coverage.
`song-timing.json`: latest checked vocal, word, beat and drum timing, recovered from the successful latest render cache.
`studio/film/concert.py`: continuous wrist motion on the instrument poses.
`library/characters/{benjamin-sesko,matheus-cunha,harry-maguire}/`: approved concert artwork and pose landmarks.

## Render at native 1080p

Run from the repository root with the dependencies in `requirements.txt` and FFmpeg installed.

```sh
python -m studio.film united-road-take-me-home song
python -m studio.film united-road-take-me-home sound
EP_RES=1920x1080 FILM_THREADS=1 python -m studio.film united-road-take-me-home still 7.5 12.8 99 106.4 160 170 212
EP_RES=1920x1080 FILM_THREADS=1 FILM_CRF=17 FILM_MEM_GB=7.5 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -u -m studio.film united-road-take-me-home render --jobs 3 --chunks 36
```

The full quality master is retained in `build/master.mp4` when the repository delivery is compressed below 100 MB. `build/` is a temporary cache and must not be committed. Use `--resume` only when source, resolution and chunk boundaries have not changed.

Source checks are recorded in `source-validation.json`: cast exclusions, final chorus coverage, soundtrack alignment and pixel-identical character-compositing optimization.

## Finished combined edition

`united-road-take-me-home.mp4` is the combined 1920×1080, 30 fps repository delivery (3:54.6). The full-quality CRF 17 master is `United_Road_Combined_1080p.mp4` in the final Actions artifact. The delivered `United_Road_Final_1080p.mp4` is a high-bitrate CRF 18 encode sized for the download limit. The repository MP4 is a smaller two-pass encode to stay under GitHub's file-size limit.

The 12 completed sections from [render run 37540964194](https://github.com/ab19902020/AnimnationStuido-/actions/runs/37540964194) use source commit `0de9cd33c2fd86cc3604bf4de0ab32c9b7cead68`. The render itself succeeded; only its original assembly command failed. [Assembly run 37574237104](https://github.com/ab19902020/AnimnationStuido-/actions/runs/37574237104) resumes those exact sections without rerendering. Its `united-road-combined-1080p` artifact contains the master, smaller copy and validation record. Actions artifacts expire after 14 days; the checked-in delivery persists.

`render-validation.json` records the full-decode and frame-count checks. Additional delivery review confirmed continuous frame timestamps, no soundtrack timing shift in samples crossing 20, 100, 160 and 220 seconds, and inspected the complete shot sequence plus guitar, drum and chorus close-ups.

Do not restart the old full render to recover this delivery. Use the committed video, the final assembly artifact, or the saved section artifacts with `.github/workflows/assemble-united-road-final.yml` while they are retained. The assembly workflow strips section audio before concatenation and muxes the complete soundtrack once, preserving the video bitstream and avoiding cumulative AAC boundary offsets.
