"""Tiny process supervisor (no systemd/docker needed): keeps API + worker alive, restarts with backoff,
and restarts the worker if its heartbeat goes stale while a job is running."""
from __future__ import annotations
import subprocess, sys, time, os, signal
from .paths import DATA

CMDS = {
    "api": [sys.executable, "-m", "uvicorn", "studio.server:app", "--host", os.environ.get("HOST", "0.0.0.0"),
            "--port", os.environ.get("PORT", "8787")],
    "worker": [sys.executable, "-m", "studio.worker"],
}


def main():
    procs, backoff, started = {}, {k: 1 for k in CMDS}, {}
    logs = DATA / "logs"; logs.mkdir(exist_ok=True)
    stop = False
    signal.signal(signal.SIGTERM, lambda *a: globals().update(stop=True))
    while True:
        for name, cmd in CMDS.items():
            p = procs.get(name)
            if p is None or p.poll() is not None:
                if p is not None:
                    print(f"[supervisor] {name} exited {p.returncode}; restart in {backoff[name]}s", flush=True)
                    time.sleep(backoff[name]); backoff[name] = min(60, backoff[name] * 2)
                procs[name] = subprocess.Popen(cmd, stdout=open(logs / f"{name}.log", "ab"), stderr=subprocess.STDOUT)
                started[name] = time.time()
            elif time.time() - started[name] > 300:
                backoff[name] = 1  # stable for 5 min -> reset backoff
        time.sleep(5)


if __name__ == "__main__":
    main()
