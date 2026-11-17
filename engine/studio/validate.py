"""Quality gates: per-clip checks (drive scene retries) and final-video checks."""
from __future__ import annotations
import json, subprocess
import numpy as np


def clip_report(frames: list[np.ndarray]) -> dict:
    a = np.stack([f.astype(np.float32) for f in frames])
    mean = float(a.mean())
    contrast = float(a.std())
    motion = float(np.abs(np.diff(a, axis=0)).mean())   # mean abs frame-to-frame change
    ok = (not np.isnan(a).any()) and 25 < mean < 235 and contrast > 22 and motion > 0.35 and motion < 30
    return {"ok": bool(ok), "mean": round(mean, 1), "contrast": round(contrast, 1), "motion": round(motion, 2)}


def probe(path: str) -> dict:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                   "-show_format", path])
    return json.loads(out)


def final_report(path: str, expect_seconds: float, min_w=720) -> dict:
    p = probe(path)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    dur = float(p["format"]["duration"])
    vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean_db = None
    for line in vol.splitlines():
        if "mean_volume" in line:
            mean_db = float(line.split("mean_volume:")[1].split("dB")[0])
    checks = {
        "has_video": True, "has_audio": bool(a),
        "resolution_ok": int(v["width"]) >= min_w or int(v["height"]) >= min_w,
        "duration_matches": abs(dur - expect_seconds) < 3.0,
        "audio_audible": mean_db is not None and mean_db > -45,
        "codec_h264": v["codec_name"] == "h264",
    }
    return {"ok": all(checks.values()), "checks": checks, "duration": round(dur, 2),
            "size": f'{v["width"]}x{v["height"]}', "mean_volume_db": mean_db}
