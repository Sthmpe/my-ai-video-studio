"""End-to-end documentary pipeline with resumable stages, quality gates and scene retries."""
from __future__ import annotations
import json, math, shutil, time, traceback
from pathlib import Path
from typing import Callable
import numpy as np
import soundfile as sf

from . import research as research_mod, scriptwriter, tts, music, videogen, compose, validate

GAP = 0.45      # silence between scenes
LEAD = 1.0      # lead-in before first word
TAIL = 2.2      # outro after last word
MAX_SHOT = 5.0  # longest slot we assign to one 2-second AI clip


def _write(p: Path, obj): p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


class Pipeline:
    def __init__(self, job_dir: Path, spec: dict, progress: Callable[[str, int, int, str], None] | None = None):
        self.dir, self.spec = Path(job_dir), spec
        self.dir.mkdir(parents=True, exist_ok=True)
        for sub in ("audio", "clips", "work"):
            (self.dir / sub).mkdir(exist_ok=True)
        self.cb = progress or (lambda *a: None)
        self.vertical = spec.get("orientation", "vertical") == "vertical"
        self.dims = (288, 512) if self.vertical else (512, 288)
        self.log: list[str] = []

    def note(self, msg):
        self.log.append(msg); print(msg, flush=True)

    # ---- stages -------------------------------------------------------------------------------
    def stage_script(self) -> dict:
        f = self.dir / "script.json"
        if f.exists():
            return json.loads(f.read_text())
        self.cb("script", 0, 1, "writing script")
        if self.spec.get("script"):
            s = self.spec["script"]
        else:
            res = research_mod.research(self.spec["topic"])
            _write(self.dir / "research.json", res)
            text = "\n\n".join(x["text"] for x in res["sources"])
            s = scriptwriter.write_with_llm(self.spec["topic"], text, self.spec.get("target_seconds", 150))
            s["credits"] = [x["url"] for x in res["sources"]]
        s = scriptwriter.finalize(s, self.spec.get("topic", ""))
        _write(f, s)
        return s

    def stage_voice(self, s: dict) -> dict:
        f = self.dir / "timeline.json"
        if f.exists():
            return json.loads(f.read_text())
        n = len(s["scenes"])
        t, tl = LEAD, []
        pieces = [np.zeros(int(LEAD * tts.SR), dtype=np.float32)]
        for i, sc in enumerate(s["scenes"]):
            self.cb("voice", i, n, f"narrating scene {i+1}/{n}")
            wav = self.dir / "audio" / f"scene_{i:02d}.wav"
            dur = tts.synth(sc["narration"], wav, voice=s["voice"], speed=self.spec.get("speed", 1.0))
            audio, _ = sf.read(str(wav), dtype="float32")
            pieces += [audio, np.zeros(int(GAP * tts.SR), dtype=np.float32)]
            tl.append({"scene": i, "start": round(t, 3), "dur": round(dur, 3), "text": sc["narration"]})
            t += dur + GAP
        total = t - GAP + TAIL
        pieces.append(np.zeros(int(TAIL * tts.SR), dtype=np.float32))
        sf.write(str(self.dir / "audio" / "narration.wav"), np.concatenate(pieces), tts.SR)
        out = {"scenes": tl, "total": round(total, 3)}
        _write(f, out)
        return out

    def stage_storyboard(self, s: dict, tl: dict) -> list[dict]:
        f = self.dir / "storyboard.json"
        if f.exists():
            return json.loads(f.read_text())
        shots = []
        for i, sc in enumerate(s["scenes"]):
            # scene "owns" time from its start to the next scene's start (first scene also owns the lead-in)
            a = 0.0 if i == 0 else tl["scenes"][i]["start"] - GAP / 2
            b = tl["total"] if i == len(s["scenes"]) - 1 else tl["scenes"][i + 1]["start"] - GAP / 2
            span = b - a
            k = max(len(sc["shots"]), math.ceil(span / MAX_SHOT))
            prompts = [sc["shots"][j % len(sc["shots"])]["prompt"] for j in range(k)]
            for j in range(k):
                shots.append({"scene": i, "prompt": prompts[j], "slot": span / k})
        for n, sh in enumerate(shots):
            sh["id"] = n
        _write(f, shots)
        return shots

    def stage_clips(self, s: dict, shots: list[dict]):
        base = self.spec.get("seed", 1000)
        w, h = self.dims
        reports = {}
        rf = self.dir / "clip_reports.json"
        if rf.exists():
            reports = json.loads(rf.read_text())
        for sh in shots:
            out = self.dir / "clips" / f"shot_{sh['id']:03d}.mp4"
            if out.exists():
                continue
            self.cb("video", sh["id"], len(shots), f"generating AI shot {sh['id']+1}/{len(shots)}")
            prompt = f"{sh['prompt']}, {s['style_suffix']}"
            best = None
            for attempt in range(self.spec.get("max_retries", 3)):
                seed = base + sh["id"] * 17 + attempt * 101
                t0 = time.time()
                try:
                    frames = videogen.generate_clip(prompt, seed, w, h, frames=16)
                    rep = validate.clip_report(frames)
                except Exception as e:  # noqa: BLE001
                    self.note(f"shot {sh['id']} attempt {attempt} crashed: {e}")
                    continue
                rep.update(seed=seed, attempt=attempt, secs=round(time.time() - t0, 1))
                self.note(f"shot {sh['id']} attempt {attempt}: {rep}")
                if best is None or rep["ok"]:
                    best = (frames, rep)
                if rep["ok"]:
                    break
            if best is None:
                raise RuntimeError(f"shot {sh['id']} failed all attempts")
            videogen.save_frames_mp4(best[0], out)
            reports[str(sh["id"])] = best[1]
            _write(rf, reports)

    def stage_edit(self, s: dict, tl: dict, shots: list[dict]) -> Path:
        W, H = (compose.W, compose.H) if self.vertical else (compose.H, compose.W)
        rendered, lengths = [], []
        for sh in shots:
            self.cb("edit", sh["id"], len(shots), f"rendering shot {sh['id']+1}/{len(shots)}")
            last = sh["id"] == len(shots) - 1
            length = sh["slot"] + (0 if last else compose.XF)
            out = self.dir / "work" / f"r_{sh['id']:03d}.mp4"
            compose.render_shot(self.dir / "clips" / f"shot_{sh['id']:03d}.mp4", out, length, W, H)
            rendered.append(out); lengths.append(length)
        self.cb("edit", len(shots), len(shots), "joining with transitions")
        joined = self.dir / "work" / "joined.mp4"
        compose.join_with_transitions(rendered, lengths, joined, seed=self.spec.get("seed", 3))
        # subtitles
        cues = []
        for e in tl["scenes"]:
            chunks = compose.chunk_words(e["text"], 4)
            weights = [max(1, len(c)) for c in chunks]
            tot, cur = sum(weights), e["start"]
            for c, wgt in zip(chunks, weights):
                d = e["dur"] * wgt / tot
                cues.append((cur, cur + d, c)); cur += d
        ass = self.dir / "work" / "subs.ass"
        compose.write_ass(cues, s["title"], tl["total"], ass, vertical=self.vertical)
        # music + mix
        mus = music.compose(tl["total"] + 1, self.dir / "audio" / "music.wav", s["mood"], self.spec.get("seed", 7))
        mix = self.dir / "audio" / "mix.wav"
        compose.mix_audio(self.dir / "audio" / "narration.wav", mus, mix, tl["total"])
        self.cb("edit", len(shots), len(shots), "final render")
        out = self.dir / "output.mp4"
        compose.final_render(joined, mix, ass, out)
        return out

    # ---- orchestration -----------------------------------------------------------------------------
    def run(self) -> dict:
        t0 = time.time()
        s = self.stage_script()
        tl = self.stage_voice(s)
        shots = self.stage_storyboard(s, tl)
        self.note(f"{len(s['scenes'])} scenes, {len(shots)} AI shots, narration {tl['total']}s")
        self.stage_clips(s, shots)
        out = self.stage_edit(s, tl, shots)
        rep = validate.final_report(str(out), tl["total"])
        rep.update(title=s["title"], shots=len(shots), wall_seconds=round(time.time() - t0, 1), log=self.log[-40:])
        _write(self.dir / "report.json", rep)
        self.cb("done", 1, 1, "complete" if rep["ok"] else "finished with validation warnings")
        return rep
