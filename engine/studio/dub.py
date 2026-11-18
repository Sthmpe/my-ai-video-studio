"""Re-voice a finished story job in another language. Reuses all visuals, music and SFX; lines are placed at the
original timestamps and time-fitted (Kokoro speed) so lip-free anime timing and the cut stay intact."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from . import tts, compose, validate
from .story import _ja_chunks, JA_FONT


def dub(job_dir: Path, lang: str = "ja") -> dict:
    job_dir = Path(job_dir)
    s = json.loads((job_dir / "script.json").read_text())
    tl = json.loads((job_dir / "timeline.json").read_text())
    chars = {c["id"]: c for c in s.get("characters", [])}
    narr_voice = (s.get("narrator", {}).get("voice", {}) or {}).get(lang, tts.LANG_VOICES[lang][0])
    sr = tts.SR
    track = np.zeros(int(tl["total"] * sr) + sr, np.float32)
    flat = [(sc_i, ln) for sc_i, sc in enumerate(tl["scenes"]) for ln in sc["lines"]]
    cues, speech, adir = [], [], job_dir / "audio" / f"dub_{lang}"
    adir.mkdir(exist_ok=True)
    for k, (sc_i, ln) in enumerate(flat):
        src_line = next(l for l in s["scenes"][sc_i]["lines"] if (l.get("text") == ln["text"] or l.get("ja") == ln["text"]))
        text = src_line.get(lang)
        if not text:
            raise ValueError(f"line has no '{lang}' text: {ln['text']}")
        voice = chars.get(ln["speaker"], {}).get("voice", {}).get(lang) if ln["speaker"] in chars else narr_voice
        nxt = flat[k + 1][1]["start"] if k + 1 < len(flat) else tl["total"] - 1.5
        room = max(0.8, nxt - ln["start"] - 0.1)
        wav = adir / f"l{k:02d}.wav"
        dur = tts.synth(text, wav, voice=voice)
        speed = 1.0
        if dur > room:                       # time-fit, capped so speech stays natural
            speed = min(1.35, dur / room); dur = tts.synth(text, wav, voice=voice, speed=speed)
        a, _ = sf.read(str(wav), dtype="float32")
        i = int(ln["start"] * sr); track[i:i + len(a)] += a[: len(track) - i]
        chunks = _ja_chunks(text) if lang == "ja" else compose.chunk_words(text, 4)
        wts = [max(1, len(c)) for c in chunks]; cur = ln["start"]
        for c, wt in zip(chunks, wts):
            d = dur * wt / sum(wts); cues.append((cur, cur + d, c)); cur += d
        r = validate.speech_check(str(wav), text, lang); r.update(voice=voice, speed=round(speed, 2)); speech.append(r)
    narr = job_dir / "audio" / f"narration_{lang}.wav"
    sf.write(str(narr), track[: int(tl["total"] * sr)], sr)
    W, H = (int(x) for x in compose.probe_size(job_dir / "work" / "joined.mp4"))
    ass = job_dir / "work" / f"subs_{lang}.ass"
    title = s.get("title_" + lang, s["title"])
    compose.write_ass(cues, title, tl["total"], ass, size=(W, H), end_card=s.get("end_card_" + lang, s.get("end_card")))
    if lang == "ja":
        ass.write_text(ass.read_text().replace(",Inter,", f",{JA_FONT},"))
    mix = job_dir / "audio" / f"mix_{lang}.wav"
    compose.mix_audio(narr, job_dir / "audio" / "music.wav", mix, tl["total"], sfx=job_dir / "audio" / "sfx.wav", music_gain=0.5)
    out = job_dir / f"output_{lang}.mp4"
    compose.final_render(job_dir / "work" / "joined.mp4", mix, ass, out)
    final = validate.final_report(str(out), tl["total"])
    rep = {"lang": lang, "output": str(out), "final": final, "speech": speech,
           "intelligible_ratio": round(sum(x["intelligible"] for x in speech) / max(1, len(speech)), 2)}
    (job_dir / f"dub_{lang}_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    return rep
