"""Reference import: turn a previous video or user images into character references for a job.

Rights: original characters are the default. For third-party characters or user-supplied references, the caller
must assert usage rights (`rights_note`); it is recorded in the character record and the generation report.
"""
from __future__ import annotations
import json, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image


def _sharpness(img: Image.Image) -> float:
    a = np.asarray(img.convert("L"), dtype=np.float32)
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    return float(lap.var())


def frames_from_video(video: Path, n: int = 3, candidates: int = 24, at: list[float] | None = None,
                      skip_head: float = 4.0, skip_tail: float = 3.0) -> list[Image.Image]:
    """Pick the n sharpest, mutually distinct frames (or exact timestamps via `at`). Title/end-card segments are
    skipped and the top 18% / bottom 30% (title and burned-in subtitle bands) are cropped away."""
    tmp = Path(tempfile.mkdtemp())
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", str(video)]).strip())
    span = max(1.0, dur - skip_head - skip_tail)
    times = at or [skip_head + span * (i + 0.5) / candidates for i in range(candidates)]
    for i, t in enumerate(times):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        str(tmp / f"f{i:03d}.png")], check=True)
    imgs = []
    for p in sorted(tmp.glob("*.png")):
        im = Image.open(p).convert("RGB"); w, h = im.size
        imgs.append(im.crop((0, int(h * 0.18), w, int(h * 0.70))) if h > w else im.crop((0, int(h * 0.1), w, int(h * 0.75))))
    if at:
        shutil.rmtree(tmp, ignore_errors=True)
        return imgs
    ranked = sorted(imgs, key=_sharpness, reverse=True)
    picked: list[Image.Image] = []
    for im in ranked:
        small = np.asarray(im.resize((32, 56)), dtype=np.float32)
        if all(np.abs(small - np.asarray(p.resize((32, 56)), dtype=np.float32)).mean() > 18 for p in picked):
            picked.append(im)
        if len(picked) >= n:
            break
    shutil.rmtree(tmp, ignore_errors=True)
    return picked


def add_reference(job_dir: Path, character: dict, images: list[Image.Image], rights_note: str = "") -> dict:
    """Store images as characters/<id>/ref_N.png (ref_0 is what IP-Adapter uses) and write the record."""
    cdir = Path(job_dir) / "characters" / character["id"]; cdir.mkdir(parents=True, exist_ok=True)
    refs = []
    for i, im in enumerate(images):
        im.thumbnail((768, 768)); p = cdir / f"ref_{i}.png"; im.save(p); refs.append(f"characters/{character['id']}/ref_{i}.png")
    rec = dict(character, references=refs, reference_source="user/video import",
               rights_note=rights_note or "user-supplied reference — publishing rights are the user's responsibility")
    (Path(job_dir) / "characters" / f"{character['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec
