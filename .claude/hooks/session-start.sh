#!/bin/bash
# Installs the studio's dependencies in Claude Code on the web sessions (every container starts fresh).
# Big models (Whisper, Rhubarb) are not fetched here: tools/fetch_models.sh gets them the first time they are needed.
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
apt_get() { apt-get install -y -q "$@" >/dev/null 2>&1 || { apt-get update -q >/dev/null && apt-get install -y -q "$@" >/dev/null; }; }
command -v ffmpeg >/dev/null || apt_get ffmpeg
ldconfig -p | grep -q 'libEGL.so.1 ' || apt_get libegl1
python3 -c "import numpy, scipy, PIL, cv2, yaml, skia, librosa, soundfile, sherpa_onnx, pocketsphinx, onnxruntime" 2>/dev/null \
  || pip install -q -r requirements.txt
