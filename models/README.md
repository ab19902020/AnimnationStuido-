# Models

- `realesrgan_x4_anime6b.onnx` (committed, 18 MB): Real-ESRGAN x4 anime 6B, converted to ONNX from the official
  release weights (github.com/xinntao/Real-ESRGAN, BSD-3-Clause), so upscaling needs only onnxruntime.
- Everything else is fetched on first use by `tools/fetch_models.sh` and is git-ignored: Whisper large-v3-turbo
  (sherpa-onnx int8), Rhubarb Lip Sync 1.14, the speaker-diarization models.
