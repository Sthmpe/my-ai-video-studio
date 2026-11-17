"""Durable SQLite job queue (WAL). Survives crashes/restarts; running jobs are re-queued on boot."""
from __future__ import annotations
import json, sqlite3, time, uuid, threading
from .paths import DATA

DB = DATA / "queue.db"
_lock = threading.Lock()


def _c():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id TEXT PRIMARY KEY, status TEXT, spec TEXT, stage TEXT, done INT DEFAULT 0, total INT DEFAULT 0,
        message TEXT DEFAULT '', error TEXT, report TEXT, created REAL, updated REAL, attempts INT DEFAULT 0)""")
    return c


def submit(spec: dict) -> str:
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    with _lock, _c() as c:
        c.execute("INSERT INTO jobs(id,status,spec,created,updated) VALUES(?,?,?,?,?)",
                  (jid, "queued", json.dumps(spec), time.time(), time.time()))
    return jid


def get(jid: str) -> dict | None:
    with _c() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    return _row(r)


def _row(r):
    if not r:
        return None
    d = dict(r)
    d["spec"] = json.loads(d["spec"]); d["report"] = json.loads(d["report"]) if d["report"] else None
    return d


def list_jobs(limit=50) -> list[dict]:
    with _c() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def claim() -> dict | None:
    with _lock, _c() as c:
        r = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not r:
            return None
        c.execute("UPDATE jobs SET status='running', attempts=attempts+1, updated=? WHERE id=?", (time.time(), r["id"]))
    return get(r["id"])


def update(jid: str, **kw):
    kw["updated"] = time.time()
    for k in ("report",):
        if k in kw and kw[k] is not None:
            kw[k] = json.dumps(kw[k])
    with _lock, _c() as c:
        c.execute(f"UPDATE jobs SET {','.join(k+'=?' for k in kw)} WHERE id=?", (*kw.values(), jid))


def recover(max_attempts=3) -> int:
    """On boot: jobs left 'running' by a crash go back to the queue (stages are resumable)."""
    with _lock, _c() as c:
        c.execute("UPDATE jobs SET status='failed', error='too many attempts' WHERE status='running' AND attempts>=?",
                  (max_attempts,))
        cur = c.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        return cur.rowcount
