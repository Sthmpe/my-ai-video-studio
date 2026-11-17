import json, sys, subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from studio import compose, validate, queue, music, providers, scriptwriter


def test_chunking_and_punctuation():
    c = compose.chunk_words("Deep in the rainforests of Central and South America lives an animal.", 4)
    assert all(len(x.split()) <= 4 for x in c) and " ".join(c).startswith("Deep in")


def test_clip_validator_rejects_black_and_static_accepts_motion():
    black = [np.zeros((64, 64, 3), np.uint8)] * 16
    assert not validate.clip_report(black)["ok"]
    x = np.linspace(0, 6 * np.pi, 64)
    base = np.tile((127 + 100 * np.sin(x))[None, :, None], (64, 1, 3)).astype(np.uint8)
    static = [base] * 16
    assert not validate.clip_report(static)["ok"]
    moving = [np.roll(base, i, axis=1) for i in range(16)]
    assert validate.clip_report(moving)["ok"]


def test_queue_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "DB", tmp_path / "q.db")
    jid = queue.submit({"topic": "x"})
    j = queue.claim(); assert j["id"] == jid and j["status"] == "running"
    assert queue.recover() == 1 and queue.get(jid)["status"] == "queued"   # crash recovery
    queue.update(jid, status="done", report={"ok": True})
    assert queue.get(jid)["report"]["ok"]


def test_music_is_original_and_audible(tmp_path):
    p = music.compose(4, tmp_path / "m.wav", "playful", seed=1)
    import soundfile as sf
    a, sr = sf.read(str(p)); assert len(a) / sr > 3.9 and np.abs(a).max() > 0.3


def test_provider_rotation_skips_keyless(monkeypatch):
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    try:
        providers.chat([{"role": "user", "content": "hi"}]); assert False
    except RuntimeError as e:
        assert "no API keys configured" in str(e)


def test_script_finalize_requires_shots():
    import pytest
    with pytest.raises(AssertionError):
        scriptwriter.finalize({"title": "t", "scenes": [{"narration": "hi", "shots": []}]})


def test_example_script_valid():
    s = json.loads((Path(__file__).resolve().parents[1] / "examples/sloth.json").read_text())
    scriptwriter.finalize(s); assert len(s["scenes"]) >= 10


def test_subtitles_do_not_strand_function_words_or_orphans():
    c = compose.chunk_words("Deep in the rainforests of Central and South America lives an animal that has turned doing nothing into a fine art.", 4)
    assert all(len(x.split()) >= 2 for x in c)
    assert all(x.split()[-1].lower() not in {"a", "the", "of", "and", "an"} for x in c[:-1])
