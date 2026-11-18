"""A/B/C experiment: the same scene through different generation approaches.
Measures wall time, motion (mean abs frame diff) and identity similarity to a character reference
(cosine similarity of CLIP ViT-H image embeddings — the IP-Adapter encoder)."""
import json, sys, time
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from studio import videogen
from studio.paths import MODELS

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/qexp"); OUT.mkdir(parents=True, exist_ok=True)
CH = ("1boy, young man, messy silver hair, glowing blue eyes, black high-collar jacket with gold clock emblem, "
      "red scarf")
SCENE = f"{CH}, raising his hand as time freezes, floating raindrops, neon city street at night, dramatic, anime"
SEED = 4242

def motion(fr):
    a = np.stack([f.astype(np.float32).mean(-1) for f in fr]); return float(np.abs(np.diff(a, axis=0)).mean())

_enc = {}
def embed(img):
    from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor
    if not _enc:
        _enc["m"] = CLIPVisionModelWithProjection.from_pretrained(str(MODELS / "ip-adapter/models/image_encoder")).eval()
        _enc["p"] = CLIPImageProcessor()
    with torch.no_grad():
        e = _enc["m"](**_enc["p"](images=img, return_tensors="pt")).image_embeds[0]
    return e / e.norm()

from PIL import Image
results = {}
ref_path = OUT / "ref.png"
t = time.time()
ref = videogen.generate_keyframe(f"{CH}, upper body portrait, looking at viewer, simple background, anime, masterpiece, best quality", SEED, 512, 768)
ref.save(ref_path); results["keyframe_secs"] = round(time.time() - t, 1)
runs = {
    "A_baseline_toonyou_288x512": dict(base="toonyou", width=288, height=512),
    "B_counterfeit_384x672_zoom": dict(base="counterfeit", width=384, height=672, camera="zoom-in"),
    "C_B_plus_ipadapter": dict(base="counterfeit", width=384, height=672, camera="zoom-in", ip_image=ref, ip_scale=0.6),
}
ref_e = embed(ref)
for name, kw in runs.items():
    t = time.time()
    fr = videogen.generate_clip(SCENE + ", masterpiece, best quality", SEED, **kw)
    secs = time.time() - t
    videogen.save_frames_mp4(fr, OUT / f"{name}.mp4")
    Image.fromarray(fr[0]).save(OUT / f"{name}_f0.png"); Image.fromarray(fr[-1]).save(OUT / f"{name}_f15.png")
    sim = float(embed(Image.fromarray(fr[8])) @ ref_e)
    results[name] = {"secs": round(secs, 1), "motion": round(motion(fr), 2), "id_sim_to_ref": round(sim, 3),
                     "native": f"{kw['width']}x{kw['height']}"}
    print(name, results[name], flush=True)
(OUT / "results.json").write_text(json.dumps(results, indent=2))
