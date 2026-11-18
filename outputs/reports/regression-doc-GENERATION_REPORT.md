# Generation report — Regression: Sloth Short

Mode: **documentary** · created 2026-11-18T12:17:12Z

## Models used
* **video_motion**: id=ByteDance/AnimateDiff-Lightning, variant=4-step diffusers, licence=Apache-2.0
* **image_base**: id=frankjoshua/toonyou_beta6, style=3D cartoon / Pixar-like, licence=CreativeML OpenRAIL-M
* **vae**: id=baked into checkpoint
* **camera_motion**: id=guoyww/animatediff-motion-lora-*, used=[]
* **voice**: id=Kokoro-82M v1.0 (ONNX int8), voices=['bf_emma'], languages=['en'], licence=Apache-2.0
* **script**: author=unknown
* **music**: id=studio.music procedural synth, licence=original
* **sfx**: id=studio.sfx procedural synth, licence=original
* **interpolation**: id=FFmpeg minterpolate (MCI), note=8 fps -> 24 fps
* **speech_check**: id=openai/whisper-base, licence=MIT

## Why these models
* mode 'documentary' prefers toonyou (3D cartoon / Pixar-like)
* native 384x672 chosen for cpu/bfloat16 with 4 cores
* GPU-tier models (Wan, LTX, CogVideoX) skipped: no CUDA device

## Generation method
* t2v: 4 shots — text-to-video: AnimateDiff-Lightning, 4 denoising steps, 16 frames

## Technical specifications
* Native 288x512 → export 1080x1920 (upscale ×3.75, not native detail)
* 4 shots · 16 frames @ 8 fps → 24 fps · steps {'t2v': 4, 'keyframe': 18, 'i2v': '3-4 (strength-scaled)'}
* Mean 67.8 s per shot on {'device': 'cpu', 'dtype': 'bfloat16', 'cpus': 4, 'gpu': None}
* Stage timings (s): {'total': 319.0}

## Quality checks
* Final validation: {'has_video': True, 'has_audio': True, 'resolution_ok': True, 'duration_matches': True, 'audio_audible': True, 'codec_h264': True}
* Clip-gate retries: 0

## Limitations
* Generated at 288x512 and upscaled 3.8x (Lanczos+unsharp) — export resolution is NOT native detail.
* 2-second clips (16 frames @ 8 fps) are motion-interpolated to 24 fps; fast action can smear.
* 4-step distilled motion model on CPU: fine details (hands, small accessories) can warp between frames.
* Character identity is guided by a reference image (IP-Adapter/keyframes), not locked; faces can drift in action shots.
* No GPU: higher-fidelity open models (Wan, LTX-Video, CogVideoX) were not run.

## Alternatives considered (researched, not run here)
* **Wan 2.1/2.2 T2V/I2V (1.3B–14B)** (Apache-2.0): needs a CUDA GPU (8–24 GB+) and a ~22 GB UMT5-XXL text encoder; impractical on 4 vCPU/15 GB RAM. Needs: GPU runner (e.g. 24 GB) — plug into model_router via diffusers WanPipeline
* **LTX-Video 2B/13B** (LTXV Open Weights): T5-XXL encoder + GPU memory; minutes per clip only on GPU. Needs: GPU with 12 GB+
* **CogVideoX-2B/5B** (Apache-2.0 / CogVideoX): 12–24 GB VRAM; very slow on CPU. Needs: GPU
* **HunyuanVideo / Mochi-1** (custom / Apache-2.0): 40 GB+ VRAM. Needs: datacenter GPU
* **AnimateDiff SparseCtrl / AnimateLCM** (Apache-2.0): not yet benchmarked here; candidate for next CPU iteration. Needs: ~1–2 GB extra weights

## Cost
* $0.00 — no paid services; compute: local CPU (this machine)

## Recommendations
* Run on a GPU runner and switch the router to Wan 2.x I2V for native 480p/720p motion.
* Increase native resolution to 512x896 when time allows; add RIFE interpolation instead of minterpolate.
* Use pose/ControlNet keyframes for complex action; train a small character LoRA for stronger identity.

## Reproducibility
* story/storyboard.json (per shot: prompt, seed, camera, method)
* bf16 vs fp32 and CPU vs GPU produce slightly different pixels for identical seeds.
