"""Text-to-video with AnimateDiff-Lightning (distilled, 4 steps) on a cartoon SD1.5 checkpoint.

Runs on CPU (bfloat16 / AVX512-BF16) or CUDA when present.
"""
from __future__ import annotations
import os, time, threading
from pathlib import Path
import numpy as np
import torch
from .paths import MODELS

_lock = threading.Lock()
_pipe = None

NEGATIVE = ("blurry, low quality, deformed, extra limbs, extra eyes, text, watermark, logo, "
            "realistic photo, human, person, woman, monkey, ugly, disfigured, bad anatomy, cropped, jpeg artifacts")


def device_and_dtype():
    if torch.cuda.is_available():
        return "cuda", torch.float16
    # bf16 is only fast with native support (AVX512-BF16 / AMX). Elsewhere (e.g. GitHub-hosted runners)
    # it is emulated and ~100x slower, so use float32 there. Measured: see docs/OPERATIONS.md.
    try:
        flags = open("/proc/cpuinfo").read()
    except OSError:
        flags = ""
    native_bf16 = "avx512_bf16" in flags or "amx_bf16" in flags
    return "cpu", torch.bfloat16 if native_bf16 else torch.float32


def load_pipe():
    global _pipe
    with _lock:
        if _pipe is not None:
            return _pipe
        from diffusers import AnimateDiffPipeline, MotionAdapter, EulerDiscreteScheduler, StableDiffusionPipeline
        from safetensors.torch import load_file
        dev, dt = device_and_dtype()
        torch.set_num_threads(os.cpu_count() or 4)
        adapter = MotionAdapter().to(dt)  # default config matches Lightning (incl. mid-block motion)
        adapter.load_state_dict(load_file(str(MODELS / "lightning/animatediff_lightning_4step_diffusers.safetensors")))
        base = StableDiffusionPipeline.from_single_file(
            str(MODELS / "toonyou/toonyou_beta6.safetensors"),
            config=str(MODELS / "sd15"), torch_dtype=dt, local_files_only=True, safety_checker=None, feature_extractor=None, requires_safety_checker=False)
        pipe = AnimateDiffPipeline(
            vae=base.vae, text_encoder=base.text_encoder, tokenizer=base.tokenizer, unet=base.unet,
            motion_adapter=adapter, scheduler=base.scheduler, feature_extractor=None, image_encoder=None)
        pipe.scheduler = EulerDiscreteScheduler.from_config(
            pipe.scheduler.config, timestep_spacing="trailing", beta_schedule="linear")
        pipe.to(dev)
        pipe.vae.enable_slicing()
        _pipe = pipe
        return pipe


def generate_clip(prompt: str, seed: int, width: int, height: int, frames: int = 16,
                  steps: int = 4, guidance: float = 1.0, negative: str = NEGATIVE) -> list[np.ndarray]:
    """Returns list of HxWx3 uint8 frames."""
    pipe = load_pipe()
    g = torch.Generator("cpu").manual_seed(seed)
    out = pipe(prompt=prompt, negative_prompt=negative, num_frames=frames, guidance_scale=guidance,
               num_inference_steps=steps, width=width, height=height, generator=g, output_type="np")
    arr = (out.frames[0] * 255).clip(0, 255).astype(np.uint8)
    return [f for f in arr]


def save_frames_mp4(frames: list[np.ndarray], path: Path, fps: int = 8):
    import imageio
    with imageio.get_writer(str(path), fps=fps, codec="libx264", quality=9, macro_block_size=1) as w:
        for f in frames:
            w.append_data(f)


if __name__ == "__main__":
    import sys
    w, h = int(sys.argv[1]), int(sys.argv[2])
    t = time.time(); load_pipe(); print("load", round(time.time() - t, 1), flush=True)
    t = time.time()
    fr = generate_clip("a cute cartoon sloth hanging from a tree branch in a lush jungle, big round eyes, "
                       "pixar style, vibrant colors, soft light", 1, w, h)
    print("gen", round(time.time() - t, 1), len(fr), fr[0].shape, flush=True)
    save_frames_mp4(fr, Path("/tmp/bench.mp4"))
