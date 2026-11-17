"""Worker loop: claims jobs from the queue and runs the pipeline. Writes heartbeat for health checks."""
from __future__ import annotations
import time, traceback, os
from . import queue
from .paths import JOBS, DATA

HEARTBEAT = DATA / "worker.heartbeat"


def beat():
    HEARTBEAT.write_text(str(time.time()))


def run_forever(poll=3.0):
    n = queue.recover()
    print(f"worker up; re-queued {n} interrupted jobs", flush=True)
    from .pipeline import Pipeline
    while True:
        beat()
        job = queue.claim()
        if not job:
            time.sleep(poll); continue
        jid = job["id"]
        print("claimed", jid, flush=True)

        def cb(stage, i, n, msg, jid=jid):
            queue.update(jid, stage=stage, done=i, total=n, message=msg); beat()
        try:
            rep = Pipeline(JOBS / jid, job["spec"], cb).run()
            queue.update(jid, status="done" if rep["ok"] else "done_with_warnings", report=rep)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            queue.update(jid, status="failed", error=f"{type(e).__name__}: {e}"[:500])


if __name__ == "__main__":
    run_forever()
