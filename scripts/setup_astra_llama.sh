#!/usr/bin/env bash
# Build the local scriptwriter and verify its quantized weights.
set -euo pipefail
root="${ASTRA_TOOLS:-/workspace/.studio-env}"
source_dir="$root/tools/llama.cpp"
revision=2cbfc3cf34f94c8ada67eb8766efe7374a3d2db6
checksum=626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d
weights="$root/gguf/qwen.gguf"
mkdir -p "$root/tools" "$root/gguf"
if [[ ! -d "$source_dir/.git" ]]; then
  git init "$source_dir"
  git -C "$source_dir" remote add origin https://github.com/ggml-org/llama.cpp.git
fi
if ! git -C "$source_dir" cat-file -e "$revision^{commit}" 2>/dev/null; then
  git -C "$source_dir" fetch --depth 1 origin "$revision"
fi
git -C "$source_dir" checkout --detach "$revision"
uv pip install --python "$root/venv/bin/python" cmake ninja
export PATH="$root/venv/bin:$PATH"
cmake -S "$source_dir" -B "$source_dir/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON -DGGML_OPENMP=ON
cmake --build "$source_dir/build" --target llama-bench llama-server llama-cli -j "${ASTRA_BUILD_JOBS:-3}"
if [[ -f "$weights" ]] && echo "$checksum  $weights" | sha256sum --check --status; then
  exit 0
fi
url=https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/7dabda4d13d513e3e842b20f0d435c732f172cbe/qwen2.5-3b-instruct-q4_k_m.gguf
curl -fLsS --retry 3 -o "$weights.partial" "$url"
echo "$checksum  $weights.partial" | sha256sum --check
mv "$weights.partial" "$weights"
