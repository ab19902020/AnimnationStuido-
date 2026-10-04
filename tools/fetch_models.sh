#!/usr/bin/env bash
# Downloads the speech models the first time they are needed, into models/ (git-ignored).
# GitHub releases only: HuggingFace is unreachable from cloud sessions.
#   tools/fetch_models.sh whisper|rhubarb|diarize|tts|all
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
GH=https://github.com
SHERPA=$GH/k2-fsa/sherpa-onnx/releases/download

get() { curl -sSL --fail --retry 4 --retry-delay 3 "$@"; }

whisper() {   # Whisper large-v3-turbo (int8 ONNX, ~540 MB): transcription
  [ -f models/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx ] && return
  echo "fetching Whisper turbo..." >&2
  get "$SHERPA/asr-models/sherpa-onnx-whisper-turbo.tar.bz2" | tar xj -C models
}

rhubarb() {   # Rhubarb Lip Sync 1.14: mouth-shape timing from the voice + the known words
  [ -x models/rhubarb/rhubarb ] && return
  echo "fetching Rhubarb Lip Sync..." >&2
  get -o models/rhubarb.zip "$GH/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Linux.zip"
  rm -rf models/Rhubarb-Lip-Sync-1.14.0-Linux models/rhubarb
  unzip -q -o models/rhubarb.zip -d models && mv models/Rhubarb-Lip-Sync-1.14.0-Linux models/rhubarb && rm models/rhubarb.zip
}

diarize() {   # who-speaks-when, for recordings with several voices in one file
  [ -f models/sherpa-onnx-pyannote-segmentation-3-0/model.onnx ] || \
    get "$SHERPA/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2" | tar xj -C models
  [ -f models/nemo_en_titanet_small.onnx ] || \
    get -o models/nemo_en_titanet_small.onnx "$SHERPA/speaker-recongition-models/nemo_en_titanet_small.onnx"
}

tts() {   # Kokoro v1.0 multi-language (53 voices, ~350 MB): text to speech, for test runs made before the voices are recorded
  [ -f models/kokoro-multi-lang-v1_0/model.onnx ] && return
  echo "fetching Kokoro TTS..." >&2
  get "$SHERPA/tts-models/kokoro-multi-lang-v1_0.tar.bz2" | tar xj -C models
}

case "${1:-all}" in
  whisper) whisper ;; rhubarb) rhubarb ;; diarize) diarize ;; tts) tts ;;
  all) whisper; rhubarb; diarize; tts ;;
  *) echo "usage: $0 whisper|rhubarb|diarize|tts|all" >&2; exit 2 ;;
esac
