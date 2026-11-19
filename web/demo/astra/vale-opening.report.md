# Generation report — Vale and the Storm Engine — opening cut

Mode: **anime_edit** · created 2026-11-19T12:06:04Z

## Models used
* **video_motion**: id=ByteDance/AnimateDiff-Lightning, variant=4-step diffusers, licence=Apache-2.0
* **image_base**: id=gsdf/Counterfeit-V2.5 (fp16), style=2D anime, licence=CreativeML OpenRAIL-M
* **vae**: id=stabilityai/sd-vae-ft-mse
* **character_conditioning**: id=h94/IP-Adapter ip-adapter-plus-face_sd15 (scale 0.5, keyframes), licence=Apache-2.0
* **camera_motion**: id=guoyww/animatediff-motion-lora-*, used=['pan-right', 'zoom-in']
* **voice**: id=None (instrumental edit)
* **script**: author=Astra
* **music**: id=studio.music procedural synth, licence=original, bpm=120
* **sfx**: id=studio.sfx procedural synth, licence=original
* **interpolation**: id=FFmpeg minterpolate (MCI), note=8 fps to 48 fps before retiming and 24 fps export
* **keyframe_adapter**: id=latent-consistency/lcm-lora-sdv1-5

## Why these models
* mode 'anime_edit' prefers counterfeit (2D anime)
* native 288x512 chosen for cpu/bfloat16 with 5 cores (fast tier: no native bf16 or quality=fast)
* GPU-tier models (Wan, LTX, CogVideoX) skipped: no CUDA device
* Six-step latent consistency keyframes reduce CPU denoising work.

## Generation method
* i2v: 2 shots — Six-step LCM keyframe, reference conditioning where available, followed by AnimateDiff-Lightning video-to-video.

## Technical specifications
* Native 288x512 → export 1080x1920 (upscale ×3.75, not native detail)
* 2 shots · 16 frames @ 8 fps → 24 fps · steps {'t2v': 4, 'keyframe': 6, 'i2v': '3 (6-step Lightning schedule x strength 0.65)'}
* Mean 222.9 s per shot on {'device': 'cpu', 'dtype': 'bfloat16', 'cpus': 5, 'gpu': None}
* Stage timings (s): {'characters': 0.0, 'keyframes': 0.0, 'clips': 447.1, 'edit': 21.6, 'total': 469.7}

## Quality checks
* Final validation: {'has_video': True, 'has_audio': True, 'resolution_ok': True, 'duration_matches': True, 'audio_audible': True, 'codec_h264': True}
* Clip-gate retries: 0
* Note: error rate compares Whisper text to the script; number formatting (e.g. 'seven forty-two' vs '7:42') and kana/kanji variants inflate it

## Frame inspection
* Vale's pale hair, dark collar and silhouette are recognizable across the two shots.
* The first shot changes eye highlights and the surrounding light. The second changes framing and rain highlights while the running pose stays similar.
* Face detail is soft at full export size, the eye color drifts, and the rooftop shot does not show a complete running stride.

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
