"""Video generation backends.

Baseline (CPU-capable): AnimateDiff-Lightning 4-step motion module on an SD1.5 checkpoint, with
  * selectable base checkpoint (ToonYou β6 cartoon, Counterfeit-V2.5 anime) — see BASES
  * camera-motion LoRAs (zoom/pan/tilt/roll) for real camera movement
  * IP-Adapter-Plus image conditioning, so a character reference image keeps identity across shots
  * keyframe / character-sheet generation (txt2img) with the same base model

GPU-tier models (Wan, LTX, CogVideoX) plug in through model_router.py; they are not loaded here.
"""
from __future__ import annotations
import ctypes, gc, os, time, threading
from pathlib import Path
import numpy as np
import torch
from .paths import MODELS

_lock = threading.Lock()


def _trim():
    """Return freed heap to the OS. Building UNetMotionModel makes a temporary fp32 copy (~5 GB) that glibc
    otherwise keeps resident; without this, 384x672 runs thrash memory (measured 67 s/step vs ~12 s)."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass
_state: dict = {"key": None, "pipe": None, "base": None, "loras": set(), "ip": False}

NEGATIVE = ("blurry, low quality, deformed, extra limbs, extra eyes, text, watermark, logo, "
            "ugly, disfigured, bad anatomy, cropped, jpeg artifacts, worst quality")

BASES = {
    "toonyou": {"file": "toonyou/toonyou_beta6.safetensors", "vae": None,
                "license": "CreativeML OpenRAIL-M", "id": "frankjoshua/toonyou_beta6",
                "style": "3D cartoon / Pixar-like", "extra_negative": "realistic photo, human, person, monkey"},
    "counterfeit": {"file": "counterfeit/Counterfeit-V2.5_fp16.safetensors", "vae": "vae-ft-mse",
                    "license": "CreativeML OpenRAIL-M", "id": "gsdf/Counterfeit-V2.5 (fp16)",
                    "style": "2D anime", "extra_negative": "3d, realistic photo, nsfw"},
}
CAMERA = ["zoom-in", "zoom-out", "pan-left", "pan-right", "tilt-up", "tilt-down", "rolling-clockwise"]
LIGHTNING = "lightning/animatediff_lightning_4step_diffusers.safetensors"
IP_WEIGHT = "ip-adapter-plus_sd15.safetensors"


def device_and_dtype():
    if torch.cuda.is_available():
        return "cuda", torch.float16
    # bf16 is only fast with native support (AVX512-BF16 / AMX). Elsewhere (e.g. GitHub-hosted runners)
    # it is emulated and ~100x slower, so use float32 there.
    try:
        flags = open("/proc/cpuinfo").read()
    except OSError:
        flags = ""
    native_bf16 = "avx512_bf16" in flags or "amx_bf16" in flags
    return "cpu", torch.bfloat16 if native_bf16 else torch.float32


def available_bases() -> list[str]:
    return [k for k, v in BASES.items() if (MODELS / v["file"]).exists()]


def has_ip_adapter() -> bool:
    return (MODELS / "ip-adapter/models" / IP_WEIGHT).exists() and \
        (MODELS / "ip-adapter/models/image_encoder/model.safetensors").exists()


def _build(base: str, ip: bool):
    from diffusers import (AnimateDiffPipeline, MotionAdapter, EulerDiscreteScheduler,
                           StableDiffusionPipeline, AutoencoderKL)
    from safetensors.torch import load_file
    dev, dt = device_and_dtype()
    torch.set_num_threads(os.cpu_count() or 4)
    spec = BASES[base]
    adapter = MotionAdapter().to(dt)  # default config matches Lightning (incl. mid-block motion)
    adapter.load_state_dict(load_file(str(MODELS / LIGHTNING)))
    kw = {}
    if spec["vae"] and (MODELS / spec["vae"]).exists():
        kw["vae"] = AutoencoderKL.from_pretrained(str(MODELS / spec["vae"]), torch_dtype=dt)
    sd = StableDiffusionPipeline.from_single_file(
        str(MODELS / spec["file"]), config=str(MODELS / "sd15"), torch_dtype=dt, local_files_only=True,
        safety_checker=None, feature_extractor=None, requires_safety_checker=False, **kw)
    pipe = AnimateDiffPipeline(vae=sd.vae, text_encoder=sd.text_encoder, tokenizer=sd.tokenizer, unet=sd.unet,
                               motion_adapter=adapter, scheduler=sd.scheduler, feature_extractor=None,
                               image_encoder=None)
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing", beta_schedule="linear")
    pipe.register_modules(motion_adapter=None)  # already merged into pipe.unet; the copy wastes ~0.9 GB
    del adapter
    if ip:
        pipe.load_ip_adapter(str(MODELS / "ip-adapter"), subfolder="models", weight_name=IP_WEIGHT,
                             image_encoder_folder="image_encoder", torch_dtype=dt)
        pipe.image_encoder.to(dt)
    pipe.to(dev)
    pipe.vae.enable_slicing()
    # SD VAEs ship force_upcast=True, which silently runs encode/decode in fp32 (measured ~3.5x slower on CPU).
    if dt == torch.bfloat16:
        pipe.vae.register_to_config(force_upcast=False)
    return pipe, sd


def load_pipe(base: str = "toonyou", ip: bool = False):
    """Load (or reuse) the pipeline for a base checkpoint. Only one base is resident at a time (RAM)."""
    if base not in BASES:
        raise ValueError(f"unknown base {base}; have {list(BASES)}")
    ip = ip and has_ip_adapter()
    with _lock:
        key = (base, ip)
        if _state["key"] != key:
            _state.update(key=None, pipe=None, base=None, loras=set()); _trim()
            _state.update(v2v=None, v2v_key=None)
            pipe, sd = _build(base, ip)
            del sd  # the separate UNet2DConditionModel would double resident memory (measured 9.1 GB)
            _trim()
            _state.update(key=key, pipe=pipe, base=None, loras=set(), ip=ip)
        return _state["pipe"]


def unload():
    with _lock:
        _state.update(key=None, pipe=None, base=None, loras=set(), ip=False, v2v=None, v2v_key=None)
    gc.collect()


def load_image_pipe(base: str = "counterfeit", ip: bool = False):
    """Still-image pipeline (keyframes / character sheets). Mutually exclusive with the video pipeline in RAM."""
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler, AutoencoderKL
    ip = ip and has_ip_adapter()
    with _lock:
        key = ("image", base, ip)
        if _state["key"] == key:
            return _state["pipe"]
        _state.update(key=None, pipe=None, base=None, loras=set(), v2v=None, v2v_key=None); _trim()
        dev, dt = device_and_dtype()
        spec = BASES[base]; kw = {}
        if spec["vae"] and (MODELS / spec["vae"]).exists():
            kw["vae"] = AutoencoderKL.from_pretrained(str(MODELS / spec["vae"]), torch_dtype=dt)
        sd = StableDiffusionPipeline.from_single_file(
            str(MODELS / spec["file"]), config=str(MODELS / "sd15"), torch_dtype=dt, local_files_only=True,
            safety_checker=None, feature_extractor=None, requires_safety_checker=False, **kw)
        sd.scheduler = DPMSolverMultistepScheduler.from_config(sd.scheduler.config, use_karras_sigmas=True)
        if ip:
            sd.load_ip_adapter(str(MODELS / "ip-adapter"), subfolder="models", weight_name=IP_WEIGHT,
                               image_encoder_folder="image_encoder", torch_dtype=dt)
            sd.image_encoder.to(dt)
        sd.to(dev)
        _trim()
        if dt == torch.bfloat16:
            sd.vae.register_to_config(force_upcast=False)
        _state.update(key=key, pipe=sd, ip=ip)
        return sd


def _set_camera(pipe, camera: str | None, strength: float):
    if camera and camera in CAMERA and (MODELS / "motion-lora" / camera).exists():
        if camera not in _state["loras"]:
            pipe.load_lora_weights(str(MODELS / "motion-lora" / camera), adapter_name=camera)
            _state["loras"].add(camera)
        pipe.enable_lora()
        pipe.set_adapters([camera], [strength])
        return True
    if _state["loras"]:
        pipe.disable_lora()
    return False


def generate_clip(prompt: str, seed: int, width: int, height: int, frames: int = 16, steps: int = 4,
                  guidance: float = 1.0, negative: str = NEGATIVE, base: str = "toonyou",
                  camera: str | None = None, camera_strength: float = 0.8,
                  ip_image=None, ip_scale: float = 0.6) -> list[np.ndarray]:
    """Text-to-video (optionally reference-conditioned). Returns list of HxWx3 uint8 frames."""
    pipe = load_pipe(base, ip=ip_image is not None)
    _set_camera(pipe, camera, camera_strength)
    kw = {}
    if ip_image is not None and _state["ip"]:
        pipe.set_ip_adapter_scale(ip_scale)
        kw["ip_adapter_image"] = ip_image
    neg = negative + ", " + BASES[base]["extra_negative"]
    g = torch.Generator("cpu").manual_seed(seed)
    out = pipe(prompt=prompt, negative_prompt=neg, num_frames=frames, guidance_scale=guidance,
               num_inference_steps=steps, width=width, height=height, generator=g, output_type="np", **kw)
    arr = (out.frames[0] * 255).clip(0, 255).astype(np.uint8)
    return [f for f in arr]


def generate_keyframe(prompt: str, seed: int, width: int = 512, height: int = 768, steps: int = 22,
                      base: str = "counterfeit", negative: str = NEGATIVE, guidance: float = 7.0,
                      ip_image=None, ip_scale: float = 0.45):
    """Still image (character sheet / shot keyframe). With ip_image, IP-Adapter-Plus keeps the character identity."""
    # If an IP-Adapter pipeline is already resident, reuse it at scale 0 for shots without a character
    # instead of reloading (~20 s per switch).
    keep_ip = _state["key"] == ("image", base, True)
    pipe = load_image_pipe(base, ip=ip_image is not None or keep_ip)
    kw = {}
    if _state["ip"]:
        from PIL import Image as _I
        pipe.set_ip_adapter_scale(ip_scale if ip_image is not None else 0.0)
        kw["ip_adapter_image"] = ip_image if ip_image is not None else _I.new("RGB", (224, 224))
    g = torch.Generator("cpu").manual_seed(seed)
    neg = negative + ", " + BASES[base]["extra_negative"]
    return pipe(prompt=prompt, negative_prompt=neg, width=width, height=height, num_inference_steps=steps,
                guidance_scale=guidance, generator=g, **kw).images[0]


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
    fr = generate_clip("a cute cartoon sloth hanging from a tree branch in a lush jungle", 1, w, h)
    print("gen", round(time.time() - t, 1), len(fr), fr[0].shape, flush=True)
    save_frames_mp4(fr, Path("/tmp/bench.mp4"))


def _seed_motion(img, frames: int, camera: str | None, amount: float = 0.10):
    """Build an init video from one keyframe with a programmatic camera move, which the motion model then
    re-animates (adds secondary motion: hair, cloth, particles, parallax)."""
    from PIL import Image
    w, h = img.size
    out = []
    for i in range(frames):
        p = i / max(1, frames - 1)
        z = 1 + amount * (p if camera != "zoom-out" else 1 - p)
        cw, ch = w / z, h / z
        dx = {"pan-left": -1, "pan-right": 1}.get(camera, 0) * amount * w * (p - 0.5)
        dy = {"tilt-up": -1, "tilt-down": 1}.get(camera, 0) * amount * h * (p - 0.5)
        cx, cy = w / 2 + dx, h / 2 + dy
        box = (max(0, cx - cw / 2), max(0, cy - ch / 2), min(w, cx + cw / 2), min(h, cy + ch / 2))
        out.append(img.crop(box).resize((w, h), Image.LANCZOS))
    return out


def animate_keyframe(image, prompt: str, seed: int, frames: int = 16, strength: float = 0.7,
                     base: str = "counterfeit", camera: str | None = "zoom-in", camera_strength: float = 0.6,
                     negative: str = NEGATIVE, steps: int = 4) -> list[np.ndarray]:
    """Image-to-video: keyframe -> AnimateDiff-Lightning video-to-video (reference-conditioned by the init frames)."""
    from diffusers import AnimateDiffVideoToVideoPipeline
    pipe = load_pipe(base, ip=False)
    _set_camera(pipe, camera, camera_strength)
    v2v = _state.get("v2v")
    if v2v is None or _state.get("v2v_key") != _state["key"]:
        # from_pipe silently casts the shared UNet to float32 unless torch_dtype is given (measured 15.5 -> 74.6 s/step)
        v2v = AnimateDiffVideoToVideoPipeline.from_pipe(pipe, torch_dtype=device_and_dtype()[1])
        _state.update(v2v=v2v, v2v_key=_state["key"])
    g = torch.Generator("cpu").manual_seed(seed)
    init = _seed_motion(image, frames, camera)
    out = v2v(video=init, prompt=prompt, negative_prompt=negative + ", " + BASES[base]["extra_negative"],
              strength=strength, num_inference_steps=steps, guidance_scale=1.0,
              generator=g, output_type="np", decode_chunk_size=2)  # chunked VAE: 16 frames at once OOMs 15 GB
    arr = (out.frames[0] * 255).clip(0, 255).astype(np.uint8)
    return [f for f in arr]
