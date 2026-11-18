"""Model-transparency report: GENERATION_REPORT.md + generation_report.json for every video."""
from __future__ import annotations
import json, time
from pathlib import Path
from . import videogen, modes


def build(job_dir: Path, script: dict, sel: dict, shots: list[dict], clip_reports: dict, final: dict,
          speech: list[dict], timings: dict) -> dict:
    base = videogen.BASES[sel["base"]]
    methods = sorted({sh.get("method", sel["method"]) for sh in shots})
    shot_secs = [r.get("secs", 0) for r in clip_reports.values()]
    langs = sorted({s.get("lang", "en") for s in speech}) or [script.get("language", "en")]
    tlf = job_dir / "timeline.json"
    tl = json.loads(tlf.read_text()) if tlf.exists() else {}
    voices = sorted({l["voice"] for sc in tl.get("scenes", []) for l in sc.get("lines", []) if l.get("voice")}) \
        or [script.get("voice", "af_heart")]
    # timings persist across resumed runs (a cached stage reports ~0 s on resume)
    tf = job_dir / "timings.json"
    prev = json.loads(tf.read_text()) if tf.exists() else {}
    timings = {k: (v if v > 1 or k not in prev else prev[k]) for k, v in {**prev, **timings}.items()}
    tf.write_text(json.dumps(timings, indent=1))
    extra = {}
    for name in ("sync_report", "identity_report", "continuity_report", "dub_ja_report"):
        f = job_dir / f"{name}.json"
        if f.exists():
            d = json.loads(f.read_text())
            extra[name] = ({k: d[k] for k in ("median_abs_offset_s", "within_0_5s", "total_lines") if k in d}
                           if name == "sync_report" else
                           {k: d[k] for k in ("intelligible_ratio",) if k in d} if name == "dub_ja_report" else d)
    rep = {
        "title": script.get("title"), "mode": sel["mode"], "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models": {
            "video_motion": {"id": "ByteDance/AnimateDiff-Lightning", "variant": "4-step diffusers", "licence": "Apache-2.0"},
            "image_base": {"id": base["id"], "style": base["style"], "licence": base["license"]},
            "vae": {"id": "stabilityai/sd-vae-ft-mse" if base["vae"] else "baked into checkpoint"},
            "character_conditioning": ({"id": "h94/IP-Adapter ip-adapter-plus-face_sd15 (scale 0.5, keyframes)", "licence": "Apache-2.0"}
                                       if sel.get("ip_adapter") else None),
            "camera_motion": {"id": "guoyww/animatediff-motion-lora-*", "used": sorted({s.get("camera") for s in shots if s.get("camera")})},
            "voice": {"id": "Kokoro-82M v1.0 (ONNX int8)", "voices": voices, "languages": langs, "licence": "Apache-2.0"},
            "script": {"author": script.get("author", "unknown")},
            "music": {"id": "studio.music procedural synth", "licence": "original"},
            "sfx": {"id": "studio.sfx procedural synth", "licence": "original"},
            "interpolation": {"id": "FFmpeg minterpolate (MCI)", "note": "8 fps -> 24 fps"},
            "speech_check": {"id": "openai/whisper-base", "licence": "MIT"},
        },
        "selection_reasons": sel["reasons"],
        "generation_method": {m: sum(1 for s in shots if s.get("method", sel["method"]) == m) for m in methods},
        "method_explained": {
            "t2v": "text-to-video: AnimateDiff-Lightning, 4 denoising steps, 16 frames",
            "i2v": "image-to-video: 18-step keyframe (optionally IP-Adapter-conditioned on the character reference) "
                   "animated by AnimateDiff-Lightning video-to-video; camera move seeded programmatically, re-animated by the model",
        },
        "specs": {
            "native_resolution": f"{sel['native'][0]}x{sel['native'][1]}",
            "export_resolution": f"{sel['export'][0]}x{sel['export'][1]}",
            "upscale_factor": round(sel["export"][1] / sel["native"][1], 2),
            "native_fps": 8, "export_fps": 24, "frames_per_clip": 16, "shots": len(shots),
            "inference_steps": {"t2v": 4, "keyframe": 18, "i2v": "3 (6-step Lightning schedule x strength 0.65)"},
            "seconds_per_shot_mean": round(sum(shot_secs) / max(1, len(shot_secs)), 1),
            "hardware": sel["hardware"], "timings_s": timings,
        },
        "quality": {"final_validation": final, "speech_intelligibility": speech, **extra,
                    "speech_metric_note": "error rate compares Whisper text to the script; number formatting "
                                          "(e.g. 'seven forty-two' vs '7:42') and kana/kanji variants inflate it",
                    "clip_gate_retries": sum(1 for r in clip_reports.values() if r.get("attempt", 0) > 0)},
        "limitations": [
            f"Generated at {sel['native'][0]}x{sel['native'][1]} and upscaled {round(sel['export'][1] / sel['native'][1], 1)}x (Lanczos+unsharp) — export resolution is NOT native detail.",
            "2-second clips (16 frames @ 8 fps) are motion-interpolated to 24 fps; fast action can smear.",
            "4-step distilled motion model on CPU: fine details (hands, small accessories) can warp between frames.",
            "Character identity is guided by a reference image (IP-Adapter/keyframes), not locked; faces can drift in action shots.",
            "No GPU: higher-fidelity open models (Wan, LTX-Video, CogVideoX) were not run.",
        ],
        "alternatives_considered": modes.ALTERNATIVES,
        "cost": {"usd": 0.0, "paid_services": [], "free_tier_apis": [], "compute": "local CPU (this machine)"},
        "recommendations": [
            "Run on a GPU runner and switch the router to Wan 2.x I2V for native 480p/720p motion.",
            "Increase native resolution to 512x896 when time allows; add RIFE interpolation instead of minterpolate.",
            "Use pose/ControlNet keyframes for complex action; train a small character LoRA for stronger identity.",
        ],
        "reproducibility": {
            "seeds_and_prompts": "story/storyboard.json (per shot: prompt, seed, camera, method)",
            "settings": {"guidance": 1.0, "scheduler": "Euler trailing (Lightning)", "keyframe_sampler": "DPM++ Karras"},
            "note": "bf16 vs fp32 and CPU vs GPU produce slightly different pixels for identical seeds.",
        },
    }
    (job_dir / "generation_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    (job_dir / "GENERATION_REPORT.md").write_text(to_markdown(rep))
    return rep


def to_markdown(r: dict) -> str:
    m, s = r["models"], r["specs"]
    L = [f"# Generation report — {r['title']}", "", f"Mode: **{r['mode']}** · created {r['created']}", "",
         "## Models used"]
    for k, v in m.items():
        if v:
            L.append(f"* **{k}**: " + ", ".join(f"{a}={b}" for a, b in v.items()))
    L += ["", "## Why these models"] + [f"* {x}" for x in r["selection_reasons"]]
    L += ["", "## Generation method"] + [f"* {k}: {n} shots — {r['method_explained'].get(k, '')}" for k, n in r["generation_method"].items()]
    L += ["", "## Technical specifications",
          f"* Native {s['native_resolution']} → export {s['export_resolution']} (upscale ×{s['upscale_factor']}, not native detail)",
          f"* {s['shots']} shots · {s['frames_per_clip']} frames @ {s['native_fps']} fps → {s['export_fps']} fps · steps {s['inference_steps']}",
          f"* Mean {s['seconds_per_shot_mean']} s per shot on {s['hardware']}", f"* Stage timings (s): {s['timings_s']}"]
    q = r["quality"]
    L += ["", "## Quality checks", f"* Final validation: {q['final_validation'].get('checks')}",
          f"* Clip-gate retries: {q['clip_gate_retries']}"]
    if q.get("sync_report"):
        L.append(f"* Audio/subtitle sync on the final mix (Whisper word timestamps): {q['sync_report']}")
    if q.get("identity_report"):
        L.append(f"* Character identity (CLIP ViT-H similarity of shots to their reference): {q['identity_report']}")
    if q.get("continuity_report"):
        c = q["continuity_report"]
        L.append(f"* Continuity: episode {c.get('episode')} inherits {c.get('inherited_characters')} — reference checks {c.get('reference_checks')}")
    if q.get("dub_ja_report"):
        L.append(f"* Japanese dub intelligibility: {q['dub_ja_report']}")
    L.append(f"* Note: {q['speech_metric_note']}")
    for sp in q["speech_intelligibility"][:12]:
        L.append(f"* Speech ({sp['lang']}) error {sp['error_rate']}: expected “{sp['expected'][:60]}” heard “{sp['heard'][:60]}”")
    L += ["", "## Limitations"] + [f"* {x}" for x in r["limitations"]]
    L += ["", "## Alternatives considered (researched, not run here)"] + \
         [f"* **{a['model']}** ({a['licence']}): {a['why_not']}. Needs: {a['needs']}" for a in r["alternatives_considered"]]
    L += ["", "## Cost", f"* ${r['cost']['usd']:.2f} — no paid services; compute: {r['cost']['compute']}",
          "", "## Recommendations"] + [f"* {x}" for x in r["recommendations"]]
    L += ["", "## Reproducibility", f"* {r['reproducibility']['seeds_and_prompts']}", f"* {r['reproducibility']['note']}", ""]
    return "\n".join(L)
