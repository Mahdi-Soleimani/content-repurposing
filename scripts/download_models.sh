#!/usr/bin/env bash
# ============================================================
# Content Repurposing Platform — Model Downloader
# ============================================================
# Downloads the offline Persian speech recognition model
# (Shenava Koochik v1.5 FastConformer RNNT for sherpa-onnx)
# from HuggingFace Hub.
# ============================================================

set -euo pipefail

MODEL_DIR="models/shenava-koochik"
HF_REPO="https://huggingface.co/Reza2kn/Shenava-Koochik-v1.5-RNNT-sherpa-onnx/resolve/main"

echo "============================================================"
echo "Downloading Shenava Koochik v1.5 ASR Model..."
echo "Target directory: ${MODEL_DIR}"
echo "============================================================"

mkdir -p "${MODEL_DIR}"

FILES=(
  "encoder.int8.onnx"
  "decoder.int8.onnx"
  "joiner.int8.onnx"
  "tokens.txt"
)

for file in "${FILES[@]}"; do
  TARGET="${MODEL_DIR}/${file}"
  if [ -f "${TARGET}" ]; then
    echo " [OK] ${file} already exists, skipping."
  else
    echo " [DOWNLOADING] ${file}..."
    curl -L --progress-bar "${HF_REPO}/${file}?download=true" -o "${TARGET}"
  fi
done

echo "============================================================"
echo " Model download complete!"
echo "You can now run local offline Persian transcription."
echo "============================================================"
