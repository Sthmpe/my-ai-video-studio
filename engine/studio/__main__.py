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
    a = ap.parse_args()
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
