#!/usr/bin/env bash
# Runs the web studio on a server (the Dockerfile's command). With STUDIO_DATA set (a persistent disk), everything
# the studio makes and files (library/, episodes/, shows/, build/, models/) lives there and survives redeploys: the
# first start copies the image's library in, and later starts add whatever the image has that the disk doesn't
# (new library characters, sets, sounds), never overwriting what is already on the disk.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA="${STUDIO_DATA:-}"
if [ -n "$DATA" ]; then
  mkdir -p "$DATA"
  for d in library episodes shows build models; do
    if [ ! -L "$d" ]; then
      mkdir -p "$DATA/$d"
      if [ -d "$d" ]; then cp -an "$d/." "$DATA/$d/"; rm -rf "$d"; fi
      ln -s "$DATA/$d" "$d"
    fi
  done
fi
exec python3 -m studio.web --host 0.0.0.0 --port "${PORT:-8000}"
