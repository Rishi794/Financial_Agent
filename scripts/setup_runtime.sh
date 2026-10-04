#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT/models" "$ROOT/runtime"

MODEL_FILE="$ROOT/models/Qwen3.5-4B-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/b5044a21d7238b86a4e8825f7f8327902b37cec6/Qwen3.5-4B-Q4_K_M.gguf"
EXPECTED="00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"

LLAMA_ARCHIVE="$ROOT/runtime/llama-b11382-bin-ubuntu-x64.tar.gz"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/b11382/llama-b11382-bin-ubuntu-x64.tar.gz"

if [[ ! -f "$MODEL_FILE" ]]; then
  echo "Downloading Qwen3.5-4B Q4_K_M..."
  curl -fL --retry 5 --retry-all-errors --retry-delay 5 --progress-bar "$MODEL_URL" -o "$MODEL_FILE.part"
  mv "$MODEL_FILE.part" "$MODEL_FILE"
fi

actual="$(sha256sum "$MODEL_FILE" | awk '{print $1}')"
[[ "$actual" == "$EXPECTED" ]] || { echo "Model SHA256 mismatch: $actual" >&2; exit 1; }

# Always ensure the runtime shared libraries are installed, even when the
# llama-server executable came from an existing GitHub Actions cache.
if [[ ! -f "$LLAMA_ARCHIVE" ]]; then
  echo "Downloading llama.cpp runtime..."
  curl -fL --retry 5 --retry-all-errors --retry-delay 5 --progress-bar "$LLAMA_URL" -o "$LLAMA_ARCHIVE.part"
  mv "$LLAMA_ARCHIVE.part" "$LLAMA_ARCHIVE"
fi

rm -rf "$ROOT/runtime/extract"
mkdir -p "$ROOT/runtime/extract"
tar -xzf "$LLAMA_ARCHIVE" -C "$ROOT/runtime/extract"

bin="$(find "$ROOT/runtime/extract" -type f -name llama-server -perm -111 | head -1)"
[[ -n "$bin" ]] || { echo "llama-server not found in release archive" >&2; exit 1; }

# Copy the server AND all shared libraries from the release payload.
cp "$bin" "$ROOT/runtime/llama-server"
find "$ROOT/runtime/extract" -type f \( -name '*.so' -o -name '*.so.*' \) -exec cp -f {} "$ROOT/runtime/" \;
chmod +x "$ROOT/runtime/llama-server"

# Fail here rather than in the later server step if the release still has
# unresolved dependencies.
missing="$(LD_LIBRARY_PATH="$ROOT/runtime:${LD_LIBRARY_PATH:-}" ldd "$ROOT/runtime/llama-server" | grep 'not found' || true)"
if [[ -n "$missing" ]]; then
  echo "Unresolved shared libraries:"
  echo "$missing"
  exit 1
fi

echo "Model and llama.cpp ready."
echo "Runtime contents:"
ls -lah "$ROOT/runtime"

