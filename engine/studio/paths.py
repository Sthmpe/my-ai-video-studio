"""Filesystem locations. Override with STUDIO_MODELS / STUDIO_DATA."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = Path(os.environ.get("STUDIO_MODELS", "/opt/studio/models"))
DATA = Path(os.environ.get("STUDIO_DATA", ROOT / "data"))
JOBS = DATA / "jobs"
for p in (JOBS,):
    p.mkdir(parents=True, exist_ok=True)
