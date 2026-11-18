"""Episode continuation: import a previous `.studio.zip`, carry characters/refs/voices/style, generate the next episode."""
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
from .bundle import import_bundle


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def continue_episode(bundle_zip: Path, script: dict, job_dir: Path, progress=None) -> dict:
    job_dir = Path(job_dir); prev = job_dir / "previous"
    manifest = import_bundle(bundle_zip, prev)                      # verified (checksums, safe paths)
    prev_script = json.loads((prev / "script.json").read_text())
    prev_series = prev_script.get("series") or {"id": prev_script.get("project_id", "series"), "episode": 1}

    # 1) characters: everything known from the previous episode is inherited; the new script may add or override
    prev_chars = {c["id"]: c for c in prev_script.get("characters", [])}
    for f in (prev / "characters").glob("*.json"):
        rec = json.loads(f.read_text()); prev_chars.setdefault(rec["id"], {}).update(rec)
    merged, reused = [], {}
    for c in script.get("characters", []):
        base = dict(prev_chars.get(c["id"], {}))
        base.update({k: v for k, v in c.items() if k != "from_previous"})
        merged.append(base)
        src = prev / "characters" / c["id"]
        if src.is_dir() and c.get("from_previous", True):
            dst = job_dir / "characters" / c["id"]; dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True)
            reused[c["id"]] = {p.name: _sha(p) for p in sorted(dst.glob("ref_*.png"))}
    script = dict(script); script["characters"] = merged

    # 2) style continuity: same mode/aspect/narrator unless explicitly changed
    for k in ("mode", "aspect", "narrator", "language", "subtitle_language", "music_mood"):
        script.setdefault(k, prev_script.get(k))
    previously = " ".join(l["text"] for sc in prev_script["scenes"] for l in sc.get("lines", []))
    script["series"] = {**prev_series, **(script.get("series") or {}),
                        "episode": (script.get("series") or {}).get("episode", prev_series.get("episode", 1) + 1),
                        "previous": {"title": prev_script.get("title"), "bundle_sha256": _sha(Path(bundle_zip)),
                                     "engine_commit": manifest.get("engine_commit"), "summary": previously[:600]}}
    script.setdefault("project_id", prev_script.get("project_id"))

    from .story import StoryPipeline
    r = StoryPipeline(job_dir, script, progress).run()

    # 3) continuity verification: reference images must be byte-identical to the previous episode's
    check = {}
    for cid, refs in reused.items():
        for name, h in refs.items():
            now = job_dir / "characters" / cid / name
            orig = prev / "characters" / cid / name
            check[f"{cid}/{name}"] = {"identical_to_previous": now.exists() and _sha(now) == h == _sha(orig)}
    cont = {"previous_title": prev_script.get("title"), "episode": script["series"]["episode"],
            "inherited_characters": sorted(reused), "reference_checks": check,
            "inherited_settings": {k: script.get(k) for k in ("mode", "aspect", "narrator")}}
    (job_dir / "continuity_report.json").write_text(json.dumps(cont, indent=2, ensure_ascii=False))
    from .bundle import export_bundle
    r["bundle"] = str(export_bundle(job_dir))   # re-export so continuity_report is inside
    r["continuity"] = cont
    return r
