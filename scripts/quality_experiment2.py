"""Experiment 2 (same scene/seed as experiment 1): fix wash-out of B and test multi-stage keyframe -> i2v (E)."""
import json, sys, time
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from studio import videogen
from studio.paths import MODELS
from PIL import Image

OUT = Path("/tmp/qexp")
CH = ("1boy, young man, messy silver hair, glowing blue eyes, black high-collar jacket with gold clock emblem, red scarf")
SCENE = f"{CH}, raising his hand as time freezes, floating raindrops, neon city street at night, dramatic, anime"
Q = ", masterpiece, best quality, vivid colors, high contrast"
SEED = 4242

def motion(fr):
    a = np.stack([f.astype(np.float32).mean(-1) for f in fr]); return float(np.abs(np.diff(a, axis=0)).mean())
def stats(fr):
    a = np.stack(fr).astype(np.float32); return round(float(a.std()), 1), round(float(a.reshape(-1, 3).std(0).mean()), 1)

from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor
enc = CLIPVisionModelWithProjection.from_pretrained(str(MODELS / "ip-adapter/models/image_encoder"), torch_dtype=torch.bfloat16).eval(); proc = CLIPImageProcessor()
def embed(img):
    with torch.no_grad():
        e = enc(pixel_values=proc(images=img, return_tensors="pt").pixel_values.to(torch.bfloat16)).image_embeds[0].float()
    return e / e.norm()
ref = Image.open(OUT / "ref.png"); ref_e = embed(ref)
res = json.loads((OUT / "results.json").read_text())

def record(name, fr, secs, native):
    videogen.save_frames_mp4(fr, OUT / f"{name}.mp4")
    Image.fromarray(fr[0]).save(OUT / f"{name}_f0.png"); Image.fromarray(fr[-1]).save(OUT / f"{name}_f15.png")
    c, _ = stats(fr)
    res[name] = {"secs": round(secs, 1), "motion": round(motion(fr), 2), "contrast": c,
                 "id_sim_to_ref": round(float(embed(Image.fromarray(fr[8])) @ ref_e), 3), "native": native}
    print(name, res[name], flush=True)

res["D_counterfeit_cam0.5_tags"] = {"secs": 169.4, "motion": 27.77, "contrast": 40.0, "id_sim_to_ref": 0.61, "native": "384x672"}
# E: multi-stage — keyframe for THIS shot (scene prompt), then image-to-video
t = time.time()
key = videogen.generate_keyframe(SCENE + Q, SEED, 384, 672, steps=18) if not (OUT / "E_keyframe.png").exists() else Image.open(OUT / "E_keyframe.png").convert("RGB")
kt = time.time() - t; key.save(OUT / "E_keyframe.png")
t2 = time.time()
fr = videogen.animate_keyframe(key, SCENE + Q, SEED, strength=0.65, camera="zoom-in", camera_strength=0.5)
record("E_keyframe_i2v_s0.65", fr, time.time() - t, "384x672")
res["E_keyframe_i2v_s0.65"]["keyframe_secs"] = round(kt, 1); res["E_keyframe_i2v_s0.65"]["animate_secs"] = round(time.time() - t2, 1)
# F: like E but stronger animation
t = time.time()
fr = videogen.animate_keyframe(key, SCENE + Q, SEED, strength=0.8, camera="zoom-in", camera_strength=0.6)
record("F_keyframe_i2v_s0.8", fr, time.time() - t + kt, "384x672")
(OUT / "results.json").write_text(json.dumps(res, indent=2))
