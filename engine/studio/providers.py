"""Free-API provider registry with quota-aware rotation.

Nothing here assumes a key exists: a provider is only *eligible* when its key env var is set
(or it needs no key). Providers that return HTTP 429 / quota errors are put on cooldown and the
next one is tried. We never retry a rate-limited provider before its cooldown expires, and never
rotate accounts/keys to bypass a single provider's quota.
"""
from __future__ import annotations
import os, time, json, threading
from dataclasses import dataclass, field
import requests

TIMEOUT = 40


@dataclass
class Provider:
    name: str
    kind: str                      # llm | research | image | tts | music
    env_key: str | None = None     # None => keyless
    base_url: str = ""
    model: str = ""
    cooldown_s: int = 60
    notes: str = ""
    _until: float = field(default=0.0, repr=False)

    def eligible(self) -> bool:
        return time.time() >= self._until and (self.env_key is None or bool(os.environ.get(self.env_key)))

    def penalize(self, seconds: int | None = None):
        self._until = time.time() + (seconds or self.cooldown_s)


# OpenAI-compatible chat endpoints with free tiers (limits change; see docs/PROVIDERS.md).
LLMS = [
    Provider("groq", "llm", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    Provider("gemini", "llm", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai",
             "gemini-2.0-flash"),
    Provider("openrouter", "llm", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
             "meta-llama/llama-3.3-70b-instruct:free"),
    Provider("mistral", "llm", "MISTRAL_API_KEY", "https://api.mistral.ai/v1", "mistral-small-latest"),
]

_lock = threading.Lock()
LOG: list[str] = []


def chat(messages: list[dict], json_mode: bool = False) -> tuple[str, str]:
    """Try each eligible LLM provider in order. Returns (text, provider_name). Raises if none work."""
    errors = []
    for p in LLMS:
        with _lock:
            ok = p.eligible()
        if not ok:
            continue
        try:
            body = {"model": p.model, "messages": messages, "temperature": 0.8}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            r = requests.post(p.base_url + "/chat/completions", json=body, timeout=TIMEOUT,
                              headers={"Authorization": f"Bearer {os.environ[p.env_key]}"})
            if r.status_code == 429:
                p.penalize(int(r.headers.get("retry-after", p.cooldown_s)))
                errors.append(f"{p.name}: 429 rate limited -> cooldown")
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"], p.name
        except Exception as e:  # noqa: BLE001
            p.penalize()
            errors.append(f"{p.name}: {type(e).__name__}: {str(e)[:100]}")
    raise RuntimeError("no LLM provider available: " + "; ".join(errors or ["no API keys configured"]))


def wikipedia_summary(topic: str, lang: str = "en") -> dict | None:
    """Keyless. Wikimedia REST API: polite use, send a descriptive User-Agent, ~200 req/s soft limit."""
    h = {"User-Agent": "MyAIVideoStudio/0.1 (open-source documentary generator)"}
    try:
        s = requests.get(f"https://{lang}.wikipedia.org/w/api.php", timeout=15, headers=h, params={
            "action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1}).json()
        title = s["query"]["search"][0]["title"]
        e = requests.get(f"https://{lang}.wikipedia.org/w/api.php", timeout=15, headers=h, params={
            "action": "query", "prop": "extracts", "explaintext": 1, "exintro": 0, "titles": title,
            "format": "json", "exchars": 6000}).json()
        page = next(iter(e["query"]["pages"].values()))
        return {"provider": "wikipedia", "title": title, "text": page.get("extract", ""),
                "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "license": "CC BY-SA 4.0"}
    except Exception as e:  # noqa: BLE001
        LOG.append(f"wikipedia: {type(e).__name__}: {str(e)[:100]}")
        return None
