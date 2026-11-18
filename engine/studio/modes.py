"""Content modes, aspect ratios and the automatic model router (with explanations)."""
from __future__ import annotations
import os
import torch
from . import videogen
from .paths import MODELS

ASPECTS = {  # native generation size (multiple of 8, SD1.5-friendly) -> export size
    "9:16": {"native": (384, 672), "export": (1080, 1920), "native_fast": (288, 512)},
    "16:9": {"native": (672, 384), "export": (1920, 1080), "native_fast": (512, 288)},
    "1:1": {"native": (512, 512), "export": (1080, 1080), "native_fast": (384, 384)},
}

MODES = {
    "documentary": {"base": "toonyou", "method": "t2v", "max_shot": 5.0, "music": "playful", "camera": None,
                    "style": "pixar style 3d cartoon, vibrant colors, soft cinematic lighting, highly detailed, masterpiece, best quality",
                    "ambience": "forest", "desc": "informative, funny narrated documentaries"},
    "anime_action": {"base": "counterfeit", "method": "i2v", "max_shot": 2.6, "music": "tense", "camera": "zoom-in",
                     "style": "anime, cinematic lighting, dynamic angle, detailed background, masterpiece, best quality, vivid colors, high contrast",
                     "ambience": "city", "desc": "original anime heroes, battles, powers, transformations"},
    "superhuman": {"base": "counterfeit", "method": "i2v", "max_shot": 2.6, "music": "tense", "camera": "zoom-in",
                   "style": "anime, futuristic city, glowing energy effects, motion blur, cinematic, masterpiece, best quality, high contrast",
                   "ambience": "city", "desc": "extraordinary abilities, mysterious characters, futuristic cities"},
    "anime_edit": {"base": "counterfeit", "method": "i2v", "max_shot": 1.6, "music": "tense", "camera": "zoom-in",
                   "style": "anime, dramatic lighting, speed lines, intense, masterpiece, best quality, high contrast",
                   "ambience": None, "desc": "fast dramatic cuts synced to music"},
    "cinematic": {"base": "toonyou", "method": "t2v", "max_shot": 4.0, "music": "wonder", "camera": "pan-right",
                  "style": "cinematic film still, realistic lighting, volumetric light, shallow depth of field, highly detailed",
                  "ambience": "wind", "desc": "closer-to-real look (limited by available CPU checkpoints)"},
    "story": {"base": "counterfeit", "method": "i2v", "max_shot": 3.2, "music": "wonder", "camera": "zoom-in",
              "style": "anime, cinematic, atmospheric lighting, detailed background, masterpiece, best quality",
              "ambience": "wind", "desc": "mystery, sci-fi, fantasy, horror, comedy, episodic narrative"},
    "explainer": {"base": "toonyou", "method": "t2v", "max_shot": 4.0, "music": "playful", "camera": "zoom-in",
                  "style": "clean 3d cartoon, bright colors, simple background, highly detailed, best quality",
                  "ambience": None, "desc": "educational and promotional explainers"},
}

# researched-only alternatives (GPU tier). Kept here so reports can explain why they were not used.
ALTERNATIVES = [
    {"model": "Wan 2.1/2.2 T2V/I2V (1.3B–14B)", "licence": "Apache-2.0",
     "why_not": "needs a CUDA GPU (8–24 GB+) and a ~22 GB UMT5-XXL text encoder; impractical on 4 vCPU/15 GB RAM",
     "needs": "GPU runner (e.g. 24 GB) — plug into model_router via diffusers WanPipeline"},
    {"model": "LTX-Video 2B/13B", "licence": "LTXV Open Weights", "why_not": "T5-XXL encoder + GPU memory; minutes per clip only on GPU",
     "needs": "GPU with 12 GB+"},
    {"model": "CogVideoX-2B/5B", "licence": "Apache-2.0 / CogVideoX", "why_not": "12–24 GB VRAM; very slow on CPU", "needs": "GPU"},
    {"model": "HunyuanVideo / Mochi-1", "licence": "custom / Apache-2.0", "why_not": "40 GB+ VRAM", "needs": "datacenter GPU"},
    {"model": "AnimateDiff SparseCtrl / AnimateLCM", "licence": "Apache-2.0", "why_not": "not yet benchmarked here; candidate for next CPU iteration",
     "needs": "~1–2 GB extra weights"},
]


def hardware() -> dict:
    dev, dt = videogen.device_and_dtype()
    return {"device": dev, "dtype": str(dt).replace("torch.", ""), "cpus": os.cpu_count(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


def select(mode: str, aspect: str = "9:16", quality: str = "balanced") -> dict:
    """Pick base model / method / resolution for a mode + hardware, and say why."""
    m = MODES.get(mode, MODES["documentary"])
    hw = hardware()
    have = videogen.available_bases()
    base = m["base"] if m["base"] in have else (have[0] if have else "toonyou")
    reasons = [f"mode '{mode}' prefers {m['base']} ({videogen.BASES[m['base']]['style']})"]
    if base != m["base"]:
        reasons.append(f"{m['base']} weights missing -> fell back to {base}")
    method = m["method"]
    if method == "i2v":
        reasons.append("image-to-video: a full-quality keyframe (18-step DPM++) is animated by AnimateDiff-Lightning "
                       "video-to-video; measured sharper/more on-prompt than 4-step text-to-video (QUALITY_EXPERIMENTS.md)")
    fast = quality == "fast" or (hw["device"] == "cpu" and hw["dtype"] == "float32")
    native = ASPECTS[aspect]["native_fast" if fast else "native"]
    reasons.append(f"native {native[0]}x{native[1]} chosen for {hw['device']}/{hw['dtype']} with {hw['cpus']} cores"
                   + (" (fast tier: no native bf16 or quality=fast)" if fast else ""))
    if hw["device"] == "cpu":
        reasons.append("GPU-tier models (Wan, LTX, CogVideoX) skipped: no CUDA device")
    return {"mode": mode, "base": base, "method": method, "native": native, "export": ASPECTS[aspect]["export"],
            "aspect": aspect, "max_shot": m["max_shot"], "style": m["style"], "music": m["music"],
            "camera": m["camera"], "ambience": m["ambience"], "ip_adapter": videogen.has_ip_adapter() and method == "i2v",
            "hardware": hw, "reasons": reasons}
