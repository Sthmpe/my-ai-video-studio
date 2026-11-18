"""`.studio.zip` project bundles (schema studio-bundle/1): export, verified import, continuation seed.

See docs/PROJECT_BUNDLE_SPEC.md.
"""
from __future__ import annotations
import hashlib, json, os, platform, shutil, subprocess, time, zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "studio-bundle/1"
MAX_FILES, MAX_BYTES = 5000, 4 * 1024**3

# job-dir relative path -> bundle path, role
LAYOUT = [
    ("script.json", "story/script.json", "script"),
    ("timeline.json", "story/timeline.json", "timeline"),
    ("storyboard.json", "story/storyboard.json", "storyboard"),
    ("research.json", "story/research.json", "research"),
    ("series.json", "series/series.json", "series"),
    ("report.json", "reports/report.json", "validation"),
    ("clip_reports.json", "reports/clip_reports.json", "clip_quality"),
    ("speech_report.json", "reports/speech_report.json", "speech_quality"),
    ("GENERATION_REPORT.md", "GENERATION_REPORT.md", "generation_report"),
    ("generation_report.json", "generation_report.json", "generation_report"),
    ("work/subs.ass", "subtitles/subs.ass", "subtitles"),
    ("work/subs.srt", "subtitles/subs.srt", "subtitles"),
    ("output.mp4", "final/output.mp4", "final_video"),
    ("work/subs_ja.ass", "subtitles/subs_ja.ass", "subtitles_ja"),   # JA master is rebuilt with `studio dub`
    ("dub_ja_report.json", "reports/dub_ja_report.json", "dub_quality"),
    ("continuity_report.json", "reports/continuity_report.json", "continuity"),
    ("identity_report.json", "reports/identity_report.json", "identity_quality"),
    ("sync_report.json", "reports/sync_report.json", "sync_quality"),
    ("social.json", "story/social.json", "social"),
    ("sfx_events.json", "story/sfx_events.json", "sfx_timeline"),
]
DIRS = [("clips", "clips", "clip"), ("keyframes", "keyframes", "keyframe"), ("audio", "audio", "audio"),
        ("characters", "characters", "character")]


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _env() -> dict:
    out = {"python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count()}
    for mod in ("torch", "diffusers", "transformers", "onnxruntime"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            pass
    return out


LICENSES = """# Asset licences & attribution
* Video model: AnimateDiff-Lightning (ByteDance) — Apache-2.0.
* Base image models: ToonYou β6 / Counterfeit-V2.5 — CreativeML OpenRAIL-M (use restrictions apply; see model cards).
* VAE: stabilityai/sd-vae-ft-mse — MIT. IP-Adapter (h94) — Apache-2.0. Motion LoRAs (guoyww) — Apache-2.0.
* Voice: Kokoro-82M — Apache-2.0. Japanese G2P: misaki + pyopenjtalk + unidic-lite (BSD/MIT-style).
* Music & sound effects: procedurally synthesised by this engine — original, no third-party samples.
* Script: as recorded in story/script.json (`author`, `credits`). Wikipedia-derived text is CC BY-SA 4.0.
* Characters: original unless story/script.json `rights_note` says user-supplied references were used.
"""


def export_bundle(job_dir: Path, out: Path | None = None) -> Path:
    job_dir = Path(job_dir)
    script = json.loads((job_dir / "script.json").read_text())
    slug = "".join(c if c.isalnum() else "-" for c in script.get("title", job_dir.name).lower()).strip("-")[:60]
    out = out or job_dir / f"{slug or job_dir.name}.studio.zip"
    entries = []
    for src, dst, role in LAYOUT:
        if (job_dir / src).exists():
            entries.append((job_dir / src, dst, role))
    for src, dst, role in DIRS:
        d = job_dir / src
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file() and not f.is_symlink():
                    entries.append((f, f"{dst}/{f.relative_to(d).as_posix()}", role))
    files = [{"path": dst, "role": role, "bytes": src.stat().st_size, "sha256": _sha(src)} for src, dst, role in entries]
    manifest = {
        "schema": SCHEMA, "project_id": script.get("project_id", job_dir.name), "title": script.get("title"),
        "mode": script.get("mode", "documentary"), "series": script.get("series"), "episode": script.get("episode"),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "engine_commit": _commit(),
        "environment": _env(), "files": files,
        "reproducibility": "Same weights+seeds+settings reproduce clips closely on the same backend; bf16 vs fp32, "
                           "CPU vs GPU and library versions change pixels. See generation_report.json.",
    }
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        z.writestr("LICENSES.md", LICENSES)
        for src, dst, _ in entries:
            ctype = zipfile.ZIP_STORED if dst.endswith((".mp4", ".png", ".zip")) else zipfile.ZIP_DEFLATED
            z.write(src, dst, compress_type=ctype)
    tmp.replace(out)
    return out


class BundleError(ValueError):
    pass


def _safe(name: str) -> PurePosixPath:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or name.startswith(("/", "\\")) or ":" in p.parts[0] or "\\" in name:
        raise BundleError(f"unsafe path in bundle: {name!r}")
    return p


def import_bundle(zip_path: Path, dest_job_dir: Path) -> dict:
    """Verify and unpack a bundle into a job dir layout. Returns the manifest. Raises BundleError."""
    dest = Path(dest_job_dir); dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise BundleError("bundle too large")
        for i in infos:
            _safe(i.filename)
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise BundleError(f"symlink not allowed: {i.filename}")
        try:
            manifest = json.loads(z.read("manifest.json"))
        except KeyError as e:
            raise BundleError("manifest.json missing") from e
        if not str(manifest.get("schema", "")).startswith("studio-bundle/1"):
            raise BundleError(f"unsupported schema {manifest.get('schema')}")
        listed = {f["path"]: f for f in manifest["files"]}
        names = {i.filename for i in infos} - {"manifest.json", "LICENSES.md"}
        if names - set(listed):
            raise BundleError(f"files not in manifest: {sorted(names - set(listed))[:5]}")
        back = {dst: src for src, dst, _ in LAYOUT}
        for path, meta in listed.items():
            data = z.read(path)
            if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise BundleError(f"checksum mismatch: {path}")
            if path in back:
                rel = back[path]
            else:
                top, _, rest = path.partition("/")
                rel = next((s + "/" + rest for s, d, _ in DIRS if d == top), None)
                if rel is None:
                    continue
            target = (dest / rel).resolve()
            if dest.resolve() not in target.parents:
                raise BundleError(f"path escapes destination: {path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    (dest / "imported_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest
