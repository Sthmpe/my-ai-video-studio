"""HTTP API (FastAPI): submit jobs, poll status, download finished videos. Auth via STUDIO_API_KEY."""
from __future__ import annotations
import os, time, hmac
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import queue
from .paths import JOBS, DATA

app = FastAPI(title="My AI Video Studio engine", version="0.1.0")
KEY = os.environ.get("STUDIO_API_KEY", "")


def auth(authorization: str | None):
    if not KEY:
        raise HTTPException(503, "STUDIO_API_KEY not configured on the engine")
    tok = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(tok, KEY):
        raise HTTPException(401, "bad or missing API key")


class JobIn(BaseModel):
    topic: str = ""
    script: dict | None = None
    orientation: str = "vertical"
    target_seconds: int = 150
    seed: int = 1000


@app.get("/health")
def health():
    hb = DATA / "worker.heartbeat"
    age = time.time() - float(hb.read_text()) if hb.exists() else None
    return {"ok": True, "worker_heartbeat_age_s": age, "worker_alive": age is not None and age < 120,
            "queued": sum(1 for j in queue.list_jobs(200) if j["status"] == "queued")}


@app.post("/jobs", status_code=202)
def create(job: JobIn, authorization: str | None = Header(None)):
    auth(authorization)
    if not job.topic and not job.script:
        raise HTTPException(422, "provide topic or script")
    return {"id": queue.submit(job.model_dump())}


@app.get("/jobs")
def jobs(authorization: str | None = Header(None)):
    auth(authorization)
    return [{k: v for k, v in j.items() if k not in ("spec", "report")} for j in queue.list_jobs()]


@app.get("/jobs/{jid}")
def status(jid: str, authorization: str | None = Header(None)):
    auth(authorization)
    j = queue.get(jid)
    if not j:
        raise HTTPException(404, "no such job")
    j["video_ready"] = (JOBS / jid / "output.mp4").exists()
    j["spec"] = {k: v for k, v in j["spec"].items() if k != "script"}
    return j


@app.get("/jobs/{jid}/video")
def video(jid: str, authorization: str | None = Header(None)):
    auth(authorization)
    f = JOBS / jid / "output.mp4"
    if not f.exists():
        raise HTTPException(404, "video not ready")
    return FileResponse(f, media_type="video/mp4", filename=f"{jid}.mp4")
