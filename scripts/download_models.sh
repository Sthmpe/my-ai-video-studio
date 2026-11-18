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
echo "base models ready in $d"

# Optional keyless script-writer LLM (Qwen2.5-3B-Instruct, Apache-2.0, ~6 GB): WITH_LLM=1 scripts/download_models.sh
if [ "${WITH_LLM:-0}" = "1" ]; then
  for f in config.json generation_config.json model.safetensors.index.json model-00001-of-00002.safetensors model-00002-of-00002.safetensors tokenizer.json tokenizer_config.json vocab.json merges.txt; do g Qwen/Qwen2.5-3B-Instruct qwen "$f"; done
fi

# --- Quality pack (anime/action, character consistency, camera motion). Disable with QUALITY_PACK=0
if [ "${QUALITY_PACK:-1}" = "1" ]; then
  g gsdf/Counterfeit-V2.5 counterfeit Counterfeit-V2.5_fp16.safetensors          # anime base (CreativeML OpenRAIL-M)
  g stabilityai/sd-vae-ft-mse vae-ft-mse config.json
  g stabilityai/sd-vae-ft-mse vae-ft-mse diffusion_pytorch_model.safetensors     # sharper decoder (MIT)
  g h94/IP-Adapter ip-adapter models/ip-adapter-plus_sd15.safetensors            # character reference conditioning (Apache-2.0)
  g h94/IP-Adapter ip-adapter models/image_encoder/config.json
  g h94/IP-Adapter ip-adapter models/image_encoder/model.safetensors
  for m in zoom-in zoom-out pan-left pan-right tilt-up tilt-down rolling-clockwise; do
    g guoyww/animatediff-motion-lora-$m motion-lora/$m diffusion_pytorch_model.safetensors   # camera motion (Apache-2.0)
  done
  g ai-forever/Real-ESRGAN realesrgan RealESRGAN_x2.pth                           # optional upscaler (BSD-3)
fi
