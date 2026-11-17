"""Research stage: gather source text for a topic from legitimate free sources."""
from __future__ import annotations
from . import providers


def research(topic: str) -> dict:
    notes, tried = [], []
    w = providers.wikipedia_summary(topic)
    tried.append({"provider": "wikipedia", "ok": bool(w)})
    if w:
        notes.append(w)
    return {"topic": topic, "sources": notes, "tried": tried, "errors": list(providers.LOG)}
