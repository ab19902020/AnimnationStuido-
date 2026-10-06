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

The final delivery and validation record will be added after rendering completes.
