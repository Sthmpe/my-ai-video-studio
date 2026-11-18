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


# ---- speech intelligibility (automatic "listening") ------------------------------------------------
_asr = {}


def transcribe(wav_path: str, lang: str = "en") -> str:
    """Local Whisper-base transcription (MIT weights). Used as an objective intelligibility check."""
    import soundfile as sf, numpy as np
    from .paths import MODELS
    if "m" not in _asr:
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        _asr["p"] = WhisperProcessor.from_pretrained(str(MODELS / "whisper-base"))
        _asr["m"] = WhisperForConditionalGeneration.from_pretrained(str(MODELS / "whisper-base")).eval()
    a, sr = sf.read(wav_path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(1)
    if sr != 16000:
        idx = np.linspace(0, len(a) - 1, int(len(a) * 16000 / sr)); a = np.interp(idx, np.arange(len(a)), a)
    import torch
    feats = _asr["p"](a, sampling_rate=16000, return_tensors="pt").input_features
    with torch.no_grad():
        ids = _asr["m"].generate(feats, language=lang, task="transcribe", max_new_tokens=200)
    return _asr["p"].batch_decode(ids, skip_special_tokens=True)[0].strip()


def _norm(s: str, lang: str) -> list[str]:
    import re
    s = s.lower()
    if lang == "ja":   # character-level for Japanese
        return [c for c in re.sub(r"[\s、。！？!?.,…「」]", "", s)]
    return re.findall(r"[a-z0-9']+", s)


def speech_check(wav_path: str, expected: str, lang: str = "en") -> dict:
    """Word (EN) / character (JA) error rate between Whisper's transcript and the script line."""
    hyp = transcribe(wav_path, lang)
    r, h = _norm(expected, lang), _norm(hyp, lang)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    err = d[len(h)] / max(1, len(r))
    return {"expected": expected, "heard": hyp, "error_rate": round(err, 3), "intelligible": err < 0.35, "lang": lang}
