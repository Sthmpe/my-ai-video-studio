# Tools & models — what this studio uses and how to get them

**Why the weights are not in this GitHub repo:** they total **≈ 9 GB** (single files up to 2.5 GB). GitHub rejects files > 100 MB and Git LFS on a free account has a 1 GB storage/bandwidth quota, so pushing them would fail or break the repo for everyone who clones it. Instead, everything is downloaded **automatically and reproducibly** from its official source:

```bash
scripts/setup.sh                       # Python venv + all packages + base models
QUALITY_PACK=1 scripts/download_models.sh   # (default) anime/identity/camera/upscale/speech-check models
WITH_LLM=1 scripts/download_models.sh       # optional: local script-writer LLM (~6 GB)
```
Downloads use plain `curl` against `https://huggingface.co/<repo>/resolve/main/<file>` (resumable). Set `STUDIO_MODELS=/path` to choose where they go.

## Models
| Role | Model (Hugging Face repo → file) | Size | Licence |
|---|---|---|---|
| Motion (video) | `ByteDance/AnimateDiff-Lightning` → `animatediff_lightning_4step_diffusers.safetensors` | 0.9 GB | Apache-2.0 |
| Anime base | `gsdf/Counterfeit-V2.5` → `Counterfeit-V2.5_fp16.safetensors` | 2.1 GB | CreativeML OpenRAIL-M |
| Cartoon base (documentary) | `frankjoshua/toonyou_beta6` → `toonyou_beta6.safetensors` | 2.3 GB | CreativeML OpenRAIL-M |
| SD1.5 configs/tokenizer | `stable-diffusion-v1-5/stable-diffusion-v1-5` → `*.json`, `tokenizer/*` | <5 MB | CreativeML OpenRAIL-M |
| Sharper VAE | `stabilityai/sd-vae-ft-mse` | 0.3 GB | MIT |
| Character identity | `h94/IP-Adapter` → `models/ip-adapter-plus_sd15.safetensors` + `models/image_encoder/*` | 2.6 GB | Apache-2.0 |
| Camera motion | `guoyww/animatediff-motion-lora-{zoom-in,zoom-out,pan-left,pan-right,tilt-up,tilt-down,rolling-clockwise}` | 7 × 74 MB | Apache-2.0 |
| Voice EN/JA | `onnx-community/Kokoro-82M-v1.0-ONNX` → `onnx/model_quantized.onnx`, `voices/*.bin`, `tokenizer.json` | 92 MB | Apache-2.0 |
| Speech check | `openai/whisper-base` | 0.3 GB | MIT |
| Upscaler (optional) | `ai-forever/Real-ESRGAN` → `RealESRGAN_x2.pth` | 67 MB | BSD-3 |
| Script writer (optional) | `Qwen/Qwen2.5-3B-Instruct` | 6.2 GB | Apache-2.0 (Qwen licence) |

## Software (all free / open source, installed by `scripts/setup.sh` or apt)
| Tool | Purpose | Install |
|---|---|---|
| Python 3.12 + `uv` | runtime / installer | `pip install uv` |
| PyTorch | inference | `pip install torch` (CPU wheel on PyPI or `--index-url https://download.pytorch.org/whl/cpu`) |
| diffusers, transformers, accelerate, peft, safetensors | model pipelines, LoRA, IP-Adapter | `engine/requirements.txt` |
| onnxruntime | Kokoro TTS | requirements |
| espeakng-loader + phonemizer-fork | English phonemes (bundled espeak-ng, no apt) | requirements |
| misaki[ja] + unidic-lite | Japanese phonemes (OpenJTalk + bundled dictionary) | requirements |
| FFmpeg ≥ 6 (libx264, libass) | interpolation, editing, subtitles, mixing | `apt-get install ffmpeg` |
| Fonts: Inter, IPAGothic | EN / JA subtitles | `apt-get install fonts-inter fonts-ipafont-gothic` |
| FastAPI + uvicorn | engine HTTP API | requirements |
| Node 22 (Vercel functions) | website API routes | Vercel runtime |

## GPU upgrade path (researched, not run here)
Wan 2.1/2.2 (`Wan-AI/*-Diffusers`), LTX-Video (`Lightricks/LTX-Video`), CogVideoX (`THUDM/CogVideoX-*`) — need a CUDA GPU; see MODELS.md for requirements.
