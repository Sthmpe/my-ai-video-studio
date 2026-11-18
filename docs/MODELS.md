# Model selection

> **v2 (2026-11-18):** the router (`engine/studio/modes.py`) now picks per mode. Anime/superhuman/story → **Counterfeit-V2.5 keyframe (18-step) → AnimateDiff-Lightning image-to-video + camera LoRA + IP-Adapter identity**; documentary/explainer → ToonYou text-to-video (unchanged, regression-safe). Evidence: [QUALITY_EXPERIMENTS.md](QUALITY_EXPERIMENTS.md). Every video's choice is explained in its `GENERATION_REPORT.md`.

| Component | Chosen | Tested? | Why over alternatives |
|---|---|---|---|
| Anime look | Counterfeit-V2.5 fp16 | ✅ exp 1–2 | sharper anime line-art than ToonYou; fp16 single file (2.1 GB) fits RAM/disk; MeinaMix/AAM need 3.4–4.2 GB fp32 |
| Motion | AnimateDiff-Lightning 4-step | ✅ | only distilled SD1.5 motion model fast enough on CPU; AnimateLCM/SparseCtrl researched, not benchmarked yet |
| Image→video | AnimateDiff v2v from keyframe (strength 0.65) | ✅ exp 2 | keeps keyframe detail + scene; t2v at 4 steps washes out (contrast 40) |
| Identity | IP-Adapter-Plus SD1.5 (scale 0.4 on keyframes) | 🧪 | at 0.6 on t2v it copied the reference background (exp 1); 0.4 on keyframes is the working setting |
| Camera | guoyww motion LoRAs | ✅ | real zoom/pan/tilt/roll; ~74 MB each |
| JA voice | Kokoro jf_/jm_ voices + misaki JA G2P | ✅ CER 0.00 | same engine as EN, offline; espeak `ja` IPA does not match Kokoro's training phonemes |
| Speech QA | Whisper-base | ✅ | local, MIT, EN+JA |


Decision driver: **the hardware that actually exists** — a 4 vCPU Xeon (AVX-512, BF16/FP16), 15 GB RAM, **no GPU**, 30 GB free disk (see [ENVIRONMENT.md](ENVIRONMENT.md)).

| Candidate | Licence | Quality | Needs | Verdict on this machine |
|---|---|---|---|---|
| **AnimateDiff-Lightning (4-step) + ToonYou β6** | Apache-2.0 / OpenRAIL-M | Stylised, great for cartoons | ~4 GB RAM | ✅ **Chosen.** 16 frames @ 288×512 in ~40 s on CPU (bf16) |
| Wan 2.1 T2V-1.3B | Apache-2.0 | Best open realism at its size | 8 GB+ VRAM recommended | ⚠ CPU: tens of minutes per 5 s clip. Supported by the architecture (swap `videogen.py`), recommended when a GPU runner exists |
| CogVideoX-2B / 5B | Apache-2.0 / CogVideoX licence | Good | 12–24 GB VRAM | ❌ impractical on CPU |
| LTX-Video 2B | OpenRAIL | Fast on GPU | GPU | ❌ impractical on CPU |
| HunyuanVideo / Mochi-1 | custom / Apache-2.0 | High | 40 GB+ VRAM | ❌ out of reach |
| SVD (image→video) | non-commercial | Photo-real | GPU | ❌ licence + hardware |

Why AnimateDiff-Lightning: it is *distilled* — 4 denoising steps instead of 25–50 — which is the only reason text-to-video is practical without a GPU. A cartoon base checkpoint plays to its strength (stylised motion hides temporal artefacts, which is also what the target audience wants: funny, cartoony, not uncanny).

## Other models

| Role | Model | Licence | Notes |
|---|---|---|---|
| Narration | **Kokoro-82M v1.0** (ONNX, int8) | Apache-2.0 | Local, ~1.3× real-time on CPU, 6 voices bundled (`af_heart`, `bf_emma`, `bm_george`, …) |
| Music | Procedural synth (`music.py`) | original / CC0 by construction | No samples → no licence risk. Seeded, so each video gets a unique score |
| Script (offline) | Qwen2.5-3B-Instruct | Apache-2.0 | Keyless fallback in `llm_local.py` |
| Interpolation | FFmpeg `minterpolate` (MCI) | LGPL | 8 → 24 fps, 2× slow-motion |

## Honest limits
* Clips are **2 s (16 frames @ 8 fps)** natively; the editor stretches them 1.5–2.5× with motion interpolation and boomerangs them when a shot must last longer. Fast action looks soft; calm/comic shots look great.
* Output resolution is generated at 288×512 and upscaled to 1080×1920 (Lanczos + unsharp). On a GPU runner, raise `dims` in `pipeline.py` to 512×896 or swap in Wan 2.1.
* Character consistency comes from a fixed character descriptor in every prompt + a fixed style suffix, not from identity-locking (no IP-Adapter/LoRA yet).
