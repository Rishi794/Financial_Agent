#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/models" "$ROOT/runtime"

MODEL_FILE="$ROOT/models/Qwen3.5-4B-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/b5044a21d7238b86a4e8825f7f8327902b37cec6/Qwen3.5-4B-Q4_K_M.gguf"
EXPECTED="00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"

LLAMA_BUILD="b11386"
LLAMA_ARCHIVE="$ROOT/runtime/llama-${LLAMA_BUILD}-bin-ubuntu-x64.tar.gz"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_BUILD}/llama-${LLAMA_BUILD}-bin-ubuntu-x64.tar.gz"

if [[ ! -f "$MODEL_FILE" ]]; then
  echo "Downloading Qwen3.5-4B Q4_K_M..."
  curl -fL --retry 5 --retry-all-errors --retry-delay 5 --progress-bar "$MODEL_URL" -o "$MODEL_FILE.part"
  mv "$MODEL_FILE.part" "$MODEL_FILE"
fi

actual="$(sha256sum "$MODEL_FILE" | awk '{print $1}')"
[[ "$actual" == "$EXPECTED" ]] || { echo "Model SHA256 mismatch: $actual" >&2; exit 1; }

if [[ ! -f "$LLAMA_ARCHIVE" ]]; then
  echo "Downloading llama.cpp runtime..."
  curl -fL --retry 5 --retry-all-errors --retry-delay 5 --progress-bar "$LLAMA_URL" -o "$LLAMA_ARCHIVE.part"
  mv "$LLAMA_ARCHIVE.part" "$LLAMA_ARCHIVE"
fi

echo "Extracting llama.cpp runtime..."
# The release tarball has a top-level llama-<build>/ directory. Keep the
# complete release together instead of copying only llama-server.
find "$ROOT/runtime" -mindepth 1 -maxdepth 1 \
  ! -name "$(basename "$LLAMA_ARCHIVE")" \
  ! -name "$(basename "$LLAMA_ARCHIVE").part" \
  -exec rm -rf {} +

tar -xzf "$LLAMA_ARCHIVE" -C "$ROOT/runtime" --strip-components=1

[[ -x "$ROOT/runtime/llama-server" ]] || {
  echo "llama-server not found after extraction" >&2
  exit 1
}

chmod +x "$ROOT/runtime/llama-server"
export LD_LIBRARY_PATH="$ROOT/runtime:${LD_LIBRARY_PATH:-}"

echo "Runtime contents:"
find "$ROOT/runtime" -maxdepth 1 -type f -printf '%f\n' | sort

echo "Unresolved shared libraries:"
missing="$(ldd "$ROOT/runtime/llama-server" | awk '/not found/ {print}')"
if [[ -n "$missing" ]]; then
  printf '%s\n' "$missing" >&2
  exit 1
fi

"$ROOT/runtime/llama-server" --version

echo "Model and llama.cpp ready."

