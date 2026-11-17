#!/usr/bin/env bash
# Downloads all model weights (~3 GB) from Hugging Face via plain HTTPS (curl: resumable, proxy-friendly).
set -euo pipefail
d="${STUDIO_MODELS:-/opt/studio/models}"
g(){ mkdir -p "$d/$2/$(dirname "$3")"; [ -s "$d/$2/$3" ] || curl -fsSL --retry 5 -C - -o "$d/$2/$3" "https://huggingface.co/$1/resolve/main/$3"; echo "ok $2/$3"; }
# Motion: AnimateDiff-Lightning (Apache-2.0)   Base: ToonYou beta6 cartoon SD1.5 checkpoint (CreativeML OpenRAIL-M)
g ByteDance/AnimateDiff-Lightning lightning animatediff_lightning_4step_diffusers.safetensors
g frankjoshua/toonyou_beta6 toonyou toonyou_beta6.safetensors
# Voice: Kokoro-82M ONNX (Apache-2.0)
g onnx-community/Kokoro-82M-v1.0-ONNX kokoro onnx/model_quantized.onnx
g onnx-community/Kokoro-82M-v1.0-ONNX kokoro tokenizer.json
for v in af_heart af_bella am_michael am_puck bm_george bf_emma; do g onnx-community/Kokoro-82M-v1.0-ONNX kokoro voices/$v.bin; done
# SD1.5 configs/tokenizer only
for f in model_index.json tokenizer/merges.txt tokenizer/special_tokens_map.json tokenizer/tokenizer_config.json tokenizer/vocab.json scheduler/scheduler_config.json text_encoder/config.json vae/config.json unet/config.json; do g stable-diffusion-v1-5/stable-diffusion-v1-5 sd15 "$f"; done
python3 - <<PY
import json,pathlib
p=pathlib.Path("$d/sd15/model_index.json"); m=json.loads(p.read_text())
m.update(feature_extractor=[None,None], safety_checker=[None,None], requires_safety_checker=False)
p.write_text(json.dumps(m,indent=1))
PY
echo "models ready in $d"
