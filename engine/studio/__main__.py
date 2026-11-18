"""CLI: python -m studio generate --topic "..." [--script script.json] [--orientation vertical|landscape]"""
import argparse, json, sys, time
from pathlib import Path
from .paths import JOBS


def main():
    ap = argparse.ArgumentParser(prog="studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="run the full pipeline in the foreground")
    g.add_argument("--topic", default="")
    g.add_argument("--script", help="pre-written script.json (skips research/LLM)")
    g.add_argument("--orientation", default="vertical", choices=["vertical", "landscape"])
    g.add_argument("--seconds", type=int, default=150)
    g.add_argument("--job", default=None, help="job id/dir name (resume if it exists)")
    g.add_argument("--seed", type=int, default=1000)
    st = sub.add_parser("story", help="story/anime pipeline (script v2)")
    st.add_argument("--script"); st.add_argument("--job", required=True)
    st.add_argument("--idea", default=""); st.add_argument("--mode", default="anime_action")
    st.add_argument("--seconds", type=int, default=45); st.add_argument("--aspect", default="9:16")
    st.add_argument("--language", default="en")
    st.add_argument("--quality", default="balanced", choices=["fast", "balanced"])
    ex = sub.add_parser("export", help="write <job>/<title>.studio.zip"); ex.add_argument("--job", required=True)
    im = sub.add_parser("import", help="verify + unpack a .studio.zip into a job dir")
    im.add_argument("--bundle", required=True); im.add_argument("--job", required=True)
    co = sub.add_parser("continue", help="next episode from a previous .studio.zip")
    co.add_argument("--bundle", required=True); co.add_argument("--script"); co.add_argument("--job", required=True)
    co.add_argument("--idea", default="")
    du = sub.add_parser("dub", help="re-voice a finished story job in another language (reuses all visuals)")
    du.add_argument("--job", required=True); du.add_argument("--lang", default="ja")
    a = ap.parse_args()
    cb = lambda st_, i, n, m: print(f"[{st_} {i}/{n}] {m}", flush=True)  # noqa: E731
    if a.cmd == "story":
        from .story import StoryPipeline
        if a.script:
            scr = json.loads(Path(a.script).read_text())
        else:
            from .scriptwriter import write_story
            scr = write_story(a.idea, a.mode, a.seconds, a.language)
        scr.setdefault("aspect", a.aspect); scr.setdefault("mode", a.mode)
        r = StoryPipeline(JOBS / a.job, scr, cb, a.quality).run()
        print(json.dumps(r, indent=2)); sys.exit(0 if r["final"]["ok"] else 2)
    if a.cmd == "export":
        from .bundle import export_bundle
        print(export_bundle(JOBS / a.job)); return
    if a.cmd == "import":
        from .bundle import import_bundle
        m = import_bundle(Path(a.bundle), JOBS / a.job); print(json.dumps({k: m[k] for k in ("schema", "title", "project_id")})); return
    if a.cmd == "continue":
        from .continuation import continue_episode
        if a.script:
            scr = json.loads(Path(a.script).read_text())
        else:   # write the next episode from an idea, telling the writer who the recurring cast is
            import zipfile
            from .scriptwriter import write_story
            prev = json.loads(zipfile.ZipFile(a.bundle).read("story/script.json"))
            cast = "; ".join(f"{c['id']} ({c.get('name')}): {c.get('prompt', '')[:120]}" for c in prev.get("characters", []))
            scr = write_story(f"Next episode of '{prev.get('title')}'. Recurring characters (reuse these ids): {cast}. "
                              f"New episode idea: {a.idea}", prev.get("mode", "anime_action"), 30, prev.get("language", "en"))
            ids = {c["id"] for c in scr["characters"]}
            for c in prev.get("characters", []):
                if c["id"] in ids:
                    scr["characters"] = [{"id": c["id"], "from_previous": True} if x["id"] == c["id"] else x for x in scr["characters"]]
                else:
                    scr["characters"].append({"id": c["id"], "from_previous": True})
        r = continue_episode(Path(a.bundle), scr, JOBS / a.job, cb)
        print(json.dumps(r, indent=2)); sys.exit(0 if r["final"]["ok"] else 2)
    if a.cmd == "dub":
        from .dub import dub
        print(json.dumps(dub(JOBS / a.job, a.lang), indent=2)); return
    from .pipeline import Pipeline
    spec = {"topic": a.topic, "orientation": a.orientation, "target_seconds": a.seconds, "seed": a.seed}
    if a.script:
        spec["script"] = json.loads(Path(a.script).read_text())
        spec["topic"] = spec["topic"] or spec["script"].get("topic", "")
    job = a.job or time.strftime("%Y%m%d-%H%M%S")
    p = Pipeline(JOBS / job, spec, progress=lambda st, i, n, m: print(f"[{st} {i}/{n}] {m}", flush=True))
    rep = p.run()
    print(json.dumps({k: v for k, v in rep.items() if k != "log"}, indent=2))
    print("OUTPUT:", JOBS / job / "output.mp4")
    sys.exit(0 if rep["ok"] else 2)


main()
