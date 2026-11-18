# Generation report — The Boy Who Stole Time — Ep. 1

Mode: **anime_action** · created 2026-11-18T14:05:20Z

## Models used
* **video_motion**: id=ByteDance/AnimateDiff-Lightning, variant=4-step diffusers, licence=Apache-2.0
* **image_base**: id=gsdf/Counterfeit-V2.5 (fp16), style=2D anime, licence=CreativeML OpenRAIL-M
* **vae**: id=stabilityai/sd-vae-ft-mse
* **character_conditioning**: id=h94/IP-Adapter ip-adapter-plus-face_sd15 (scale 0.5, keyframes), licence=Apache-2.0
* **camera_motion**: id=guoyww/animatediff-motion-lora-*, used=['pan-left', 'pan-right', 'rolling-clockwise', 'tilt-up', 'zoom-in', 'zoom-out']
* **voice**: id=Kokoro-82M v1.0 (ONNX int8), voices=['am_puck', 'bf_emma', 'bm_george'], languages=['en'], licence=Apache-2.0
* **script**: author=Claude Code (interactive session), original story
* **music**: id=studio.music procedural synth, licence=original
* **sfx**: id=studio.sfx procedural synth, licence=original
* **interpolation**: id=FFmpeg minterpolate (MCI), note=8 fps -> 24 fps
* **speech_check**: id=openai/whisper-base, licence=MIT

## Why these models
* mode 'anime_action' prefers counterfeit (2D anime)
* image-to-video: a full-quality keyframe (18-step DPM++) is animated by AnimateDiff-Lightning video-to-video; measured sharper/more on-prompt than 4-step text-to-video (QUALITY_EXPERIMENTS.md)
* native 384x672 chosen for cpu/bfloat16 with 4 cores
* GPU-tier models (Wan, LTX, CogVideoX) skipped: no CUDA device

## Generation method
* i2v: 20 shots — image-to-video: 18-step keyframe (optionally IP-Adapter-conditioned on the character reference) animated by AnimateDiff-Lightning video-to-video; camera move seeded programmatically, re-animated by the model

## Technical specifications
* Native 384x672 → export 1080x1920 (upscale ×2.86, not native detail)
* 20 shots · 16 frames @ 8 fps → 24 fps · steps {'t2v': 4, 'keyframe': 18, 'i2v': '3 (6-step Lightning schedule x strength 0.65)'}
* Mean 110.2 s per shot on {'device': 'cpu', 'dtype': 'bfloat16', 'cpus': 4, 'gpu': None}
* Stage timings (s): {'characters': 0.0, 'keyframes': 0.0, 'clips': 2221.0, 'edit': 173.2, 'total': 2394.9}

## Quality checks
* Final validation: {'has_video': True, 'has_audio': True, 'resolution_ok': True, 'duration_matches': True, 'audio_audible': True, 'codec_h264': True}
* Clip-gate retries: 0
* Audio/subtitle sync on the final mix (Whisper word timestamps): {'median_abs_offset_s': 0.19, 'within_0_5s': 7, 'total_lines': 8}
* Japanese dub intelligibility: {'intelligible_ratio': 0.88}
* Note: error rate compares Whisper text to the script; number formatting (e.g. 'seven forty-two' vs '7:42') and kana/kanji variants inflate it
* Speech (en) error 0.385: expected “At seven forty-two on a rainy Tuesday, Kai Arata broke the u” heard “At 742 on a rainy Tuesday, Kairata broke the universe.”
* Speech (en) error 0.0: expected “Just once... I wish everything would stop.” heard “Just once, I wish everything would stop.”
* Speech (en) error 0.0: expected “No way... the rain is just... floating.” heard “No way the rain is just floating.”
* Speech (en) error 0.0: expected “Every clock. Every heartbeat. Every person. Frozen.” heard “Every clock, every heartbeat, every person frozen.”
* Speech (en) error 0.0: expected “You shouldn't be able to do that.” heard “You shouldn't be able to do that.”
* Speech (en) error 0.143: expected “Who are you? Why can you move?” heard “Who are you? Why can't you move?”
* Speech (en) error 0.0: expected “Because I hunt people who steal time. And you just rang the ” heard “Because I hunt people who steal time and you just rang the b”
* Speech (en) error 0.0: expected “Kai had stolen time. Now, time wanted it back.” heard “Kai had stolen time, now time wanted it back.”

## Limitations
* Generated at 384x672 and upscaled 2.9x (Lanczos+unsharp) — export resolution is NOT native detail.
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
