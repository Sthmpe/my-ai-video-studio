"""Script + storyboard authoring.

Order of authors:
  1. A pre-written script.json (e.g. authored by Claude Code in the interactive session).
  2. Any configured free LLM API (providers.LLMS, rotated with cooldowns).
  3. Local open-weights LLM (Qwen2.5 via transformers, llm_local.py) so topic-only jobs work with no keys.

Script schema (see docs/ARCHITECTURE.md):
  {title, topic, mood, voice, scenes:[{narration, shots:[{prompt}]}], style_suffix, credits}
"""
from __future__ import annotations
import json, re
from . import providers

SYSTEM = """You are an award-winning documentary writer with a dry, witty David-Attenborough-style voice.
Write a factual, funny, story-driven short documentary. Respond with ONLY JSON:
{"title": str, "character": "ONE reusable visual description of the main character/subject (species, colors, features)", "mood": "playful"|"wonder"|"tense",
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
    try:
        txt, who = providers.chat(msgs, json_mode=True)
        s = _extract_json(txt)
    except Exception as e:  # noqa: BLE001 - no key / rate-limited / bad JSON -> local model
        providers.LOG.append(f"llm apis unavailable ({str(e)[:80]}); using local model")
        from . import llm_local
        who, s = "local:" + llm_local.MODEL, None
        for _ in range(3):
            try:
                s = _extract_json(llm_local.chat(msgs)); finalize(dict(s)); break
            except Exception:  # noqa: BLE001
                s = None
        if s is None:
            raise RuntimeError("local LLM could not produce a valid script after 3 tries")
    s["author"] = who
    return s


def finalize(s: dict, topic: str = "") -> dict:
    s.setdefault("topic", topic)
    s.setdefault("mood", "playful")
    s.setdefault("voice", "af_heart")
    s.setdefault("style_suffix", STYLE)
    s.setdefault("credits", [])
    ch = (s.get("character") or "").strip()
    for sc in s["scenes"]:
        assert sc["narration"].strip() and sc["shots"], "scene needs narration and >=1 shot"
        for sh in sc["shots"]:   # keep the main character consistent across shots
            if ch and ch.lower() not in sh["prompt"].lower():
                sh["prompt"] = f"{ch}, {sh['prompt']}"
    return s


STORY_SYSTEM = """You are an anime/short-film writer for TikTok and YouTube Shorts. Write an ORIGINAL story (no existing
characters or franchises). Respond with ONLY JSON in this schema:
{"title": str, "characters": [{"id": "lowercase-id", "name": str, "prompt": "visual description: gender, age, hair, eyes, outfit, signature item",
   "voice": {"en": "am_puck|am_michael|bm_george|af_bella|af_heart|bf_emma"}, "personality": str, "powers": [str]}],
 "scenes": [{"lines": [{"speaker": "character id or narrator", "text": "spoken line, max 18 words"}],
             "ambience": "rain|wind|city|forest|null",
             "shots": [{"prompt": "ONE moving shot: action, setting, camera framing", "characters": ["ids in shot"],
                        "camera": "zoom-in|zoom-out|pan-left|pan-right|tilt-up", "sfx": ["whoosh|impact|electricity|time_freeze|clock|footsteps|riser|heartbeat"]}]}],
 "end_card": "short line", "social": {"titles": [str, str], "description": str, "hashtags": [str], "hooks": [str, str, str]}}
Rules: the FIRST line is a strong hook; build conflict and a visible reveal; end with a cliffhanger or satisfying ending;
about {n} scenes for {secs} seconds; 1-2 shots per scene; sound effects only where the action shows them."""


def write_story(idea: str, mode: str = "anime_action", seconds: int = 45, language: str = "en") -> dict:
    n = max(4, seconds // 5)
    msgs = [{"role": "system", "content": STORY_SYSTEM.replace("{n}", str(n)).replace("{secs}", str(seconds))},
            {"role": "user", "content": f"Idea: {idea}\nStyle/mode: {mode}"}]
    try:
        txt, who = providers.chat(msgs, json_mode=True); s = _extract_json(txt)
    except Exception as e:  # noqa: BLE001
        providers.LOG.append(f"llm apis unavailable ({str(e)[:80]}); using local model")
        from . import llm_local
        who, s = "local:" + llm_local.MODEL, None
        for _ in range(3):
            try:
                s = _extract_json(llm_local.chat(msgs, max_new_tokens=1800))
                assert s["scenes"] and all(sc.get("shots") for sc in s["scenes"]); break
            except Exception:  # noqa: BLE001
                s = None
        if s is None:
            raise RuntimeError("could not write a valid story script")
    s.update(author=who, mode=mode, language=language, subtitle_language=language)
    s.setdefault("characters", []); s.setdefault("narrator", {"voice": {"en": "bf_emma", "ja": "jf_alpha"}})
    for c in s["characters"]:
        c.setdefault("voice", {}).setdefault("ja", "jm_kumo"); c.setdefault("seed", abs(hash(c["id"])) % 10000)
    for sc in s["scenes"]:
        sc.setdefault("lines", [])
        for ln in sc["lines"]:
            ln.setdefault("speaker", "narrator")
    return s
