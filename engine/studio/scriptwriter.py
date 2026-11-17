"""Script + storyboard authoring.

Order of authors:
  1. A pre-written script.json (e.g. authored by Claude Code in the interactive session).
  2. Any configured free LLM API (providers.LLMS, rotated with cooldowns).
  3. Local open-weights LLM (Qwen2.5 via transformers) so the system works fully offline of paid/keyed APIs.

Script schema (see docs/ARCHITECTURE.md):
  {title, topic, mood, voice, scenes:[{narration, shots:[{prompt}]}], style_suffix, credits}
"""
from __future__ import annotations
import json, re
from . import providers

SYSTEM = """You are an award-winning documentary writer with a dry, witty David-Attenborough-style voice.
Write a factual, funny, story-driven short documentary. Respond with ONLY JSON:
{"title": str, "mood": "playful"|"wonder"|"tense",
 "scenes":[{"narration": "1-2 sentences, max 32 words, spoken aloud, no stage directions",
            "shots":[{"prompt":"visual description of ONE moving cartoon scene: subject, action, setting, camera"}]}]}
Rules: every fact must be true; ~{n} scenes; each scene has 1-3 shots (one shot per ~4 seconds of narration);
shot prompts describe a CONSISTENT main character and use concrete action verbs; no text/logos in images."""

STYLE = ("pixar style 3d cartoon, vibrant colors, soft cinematic lighting, highly detailed, "
         "masterpiece, best quality")


def _extract_json(txt: str) -> dict:
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0))


def write_with_llm(topic: str, research_text: str, target_seconds: int) -> dict:
    n = max(6, target_seconds // 9)
    msgs = [{"role": "system", "content": SYSTEM.replace("{n}", str(n))},
            {"role": "user", "content": f"Topic: {topic}\nTarget length: {target_seconds}s of narration.\n"
                                        f"Source material (facts you may use):\n{research_text[:5000]}"}]
    txt, who = providers.chat(msgs, json_mode=True)
    s = _extract_json(txt)
    s["author"] = who
    return s


def finalize(s: dict, topic: str = "") -> dict:
    s.setdefault("topic", topic)
    s.setdefault("mood", "playful")
    s.setdefault("voice", "af_heart")
    s.setdefault("style_suffix", STYLE)
    s.setdefault("credits", [])
    for sc in s["scenes"]:
        assert sc["narration"].strip() and sc["shots"], "scene needs narration and >=1 shot"
    return s
