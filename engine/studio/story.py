"""Story / anime production pipeline (script v2): characters with reference sheets, multi-voice EN/JA dialogue,
per-shot keyframes -> image-to-video, scene-aware SFX + ambience, mode-aware pacing, reports, `.studio.zip`.

Script v2 (see docs/ANIME_SERIES_SPEC.md):
  {title, mode, aspect, language, subtitle_language, project_id, series:{id, episode, previously},
   characters:[{id, name, prompt, ref_prompt, negative, voice:{en, ja}, seed}],
   narrator:{voice:{en, ja}},
   scenes:[{lines:[{speaker, text, ja}], ambience, shots:[{prompt, characters, camera, sfx, strength}]}],
   end_card, social:{titles, description, hashtags, thumbnail, hooks}}
"""
from __future__ import annotations
import json, math, shutil, time
from pathlib import Path
from typing import Callable
import numpy as np
import soundfile as sf
from PIL import Image

from . import tts, music, videogen, compose, validate, sfx, modes, report, bundle

LINE_GAP = 0.25
SCENE_GAP = 0.35
LEAD = 0.6
TAIL = 2.8


def _w(p: Path, o): p.write_text(json.dumps(o, indent=2, ensure_ascii=False))


class StoryPipeline:
    def __init__(self, job_dir: Path, script: dict, progress: Callable | None = None, quality: str = "balanced"):
        self.dir = Path(job_dir); self.dir.mkdir(parents=True, exist_ok=True)
        for d in ("audio", "clips", "keyframes", "characters", "work"):
            (self.dir / d).mkdir(exist_ok=True)
        self.s = script
        self.cb = progress or (lambda *a: None)
        self.sel = modes.select(script.get("mode", "anime_action"), script.get("aspect", "9:16"), quality)
        self.lang = script.get("language", "en")
        self.sub_lang = script.get("subtitle_language", self.lang)
        self.timings: dict = {}
        self.log: list[str] = []

    def note(self, m):
        self.log.append(m); print(m, flush=True)

    # ---------------------------------------------------------------- characters
    def stage_characters(self):
        t0 = time.time()
        chars = {c["id"]: c for c in self.s.get("characters", [])}
        for cid, c in chars.items():
            cdir = self.dir / "characters" / cid; cdir.mkdir(parents=True, exist_ok=True)
            ref = cdir / "ref_0.png"
            if not ref.exists():
                self.cb("characters", 0, len(chars), f"designing character {c['name']}")
                prompt = c.get("ref_prompt") or f"{c['prompt']}, upper body portrait, looking at viewer, simple background"
                img = videogen.generate_keyframe(f"{prompt}, {self.sel['style']}", c.get("seed", 777), 512, 768,
                                                 steps=22, base=self.sel["base"])
                img.save(ref)
                self.note(f"character {cid}: generated reference sheet")
            else:
                self.note(f"character {cid}: reusing existing reference {ref.name}")
            rec = dict(c); rec["references"] = [f"characters/{cid}/ref_0.png"]
            rec.setdefault("episodes", [])
            ep = (self.s.get("series") or {}).get("episode")
            if ep and ep not in rec["episodes"]:
                rec["episodes"].append(ep)
            rec["generation"] = {"model": self.sel["base"], "seed": c.get("seed", 777), "ip_adapter_scale": 0.5, "ip_adapter_variant": "plus-face"}
            _w(self.dir / "characters" / f"{cid}.json", rec)
        self.timings["characters"] = round(time.time() - t0, 1)
        return chars

    # ---------------------------------------------------------------- voice / dialogue
    def _voice_for(self, speaker: str, chars: dict) -> str:
        lang = self.lang
        if speaker in chars:
            return chars[speaker].get("voice", {}).get(lang) or tts.LANG_VOICES[lang][0]
        return (self.s.get("narrator", {}).get("voice", {}) or {}).get(lang) or tts.LANG_VOICES[lang][-1]

    def stage_voice(self, chars: dict) -> dict:
        f = self.dir / "timeline.json"
        if f.exists():
            return json.loads(f.read_text())
        t0 = time.time()
        sr = tts.SR
        pieces = [np.zeros(int(LEAD * sr), np.float32)]
        t, scenes, speech = LEAD, [], []
        for i, sc in enumerate(self.s["scenes"]):
            self.cb("voice", i, len(self.s["scenes"]), f"voicing scene {i+1}")
            start, lines = t, []
            for j, ln in enumerate(sc.get("lines", [])):
                text = ln.get("ja") if self.lang == "ja" and ln.get("ja") else ln["text"]
                sub = ln.get("ja") if self.sub_lang == "ja" and ln.get("ja") else ln["text"]
                voice = self._voice_for(ln["speaker"], chars)
                wav = self.dir / "audio" / f"s{i:02d}_l{j:02d}.wav"
                dur = tts.synth(text, wav, voice=voice, speed=ln.get("speed", 1.0))
                a, _ = sf.read(str(wav), dtype="float32")
                pieces += [a, np.zeros(int(LINE_GAP * sr), np.float32)]
                name = chars.get(ln["speaker"], {}).get("name", "")
                lines.append({"speaker": ln["speaker"], "name": name, "voice": voice, "start": round(t, 3),
                              "dur": round(dur, 3), "text": text, "sub": sub, "wav": wav.name})
                ln["voice"] = voice
                t += dur + LINE_GAP
            if not lines:   # silent scene (pure action / dramatic silence)
                hold = float(sc.get("hold", 2.0))
                pieces.append(np.zeros(int(hold * sr), np.float32)); t += hold
            pieces.append(np.zeros(int(SCENE_GAP * sr), np.float32)); t += SCENE_GAP
            scenes.append({"scene": i, "start": round(start, 3), "end": round(t, 3), "lines": lines})
        pieces.append(np.zeros(int(TAIL * sr), np.float32)); t += TAIL
        sf.write(str(self.dir / "audio" / "narration.wav"), np.concatenate(pieces), sr)
        tl = {"scenes": scenes, "total": round(t, 3), "language": self.lang, "subtitle_language": self.sub_lang}
        _w(f, tl)
        self.timings["voice"] = round(time.time() - t0, 1)
        return tl

    def stage_speech_check(self, tl: dict) -> list[dict]:
        f = self.dir / "speech_report.json"
        if f.exists():
            return json.loads(f.read_text())
        out = []
        for sc in tl["scenes"]:
            for ln in sc["lines"]:
                try:
                    r = validate.speech_check(str(self.dir / "audio" / ln["wav"]), ln["text"], self.lang)
                    r["voice"] = ln["voice"]; out.append(r)
                except Exception as e:  # noqa: BLE001
                    out.append({"expected": ln["text"], "heard": f"(check failed: {e})", "error_rate": 1.0,
                                "intelligible": False, "lang": self.lang})
        _w(f, out)
        return out

    # ---------------------------------------------------------------- storyboard
    def stage_storyboard(self, tl: dict) -> list[dict]:
        f = self.dir / "storyboard.json"
        if f.exists():
            return json.loads(f.read_text())
        shots, base_seed = [], int(self.s.get("seed", 2024))
        for i, sc in enumerate(self.s["scenes"]):
            span = tl["scenes"][i]["end"] - tl["scenes"][i]["start"]
            if i == 0:
                span += tl["scenes"][0]["start"]
            if i == len(self.s["scenes"]) - 1:
                span = tl["total"] - tl["scenes"][i]["start"]
            k = max(len(sc["shots"]), math.ceil(span / self.sel["max_shot"]))
            for j in range(k):
                sh = dict(sc["shots"][j % len(sc["shots"])])
                sh.update(scene=i, slot=span / k, method=sh.get("method", self.sel["method"]),
                          camera=sh.get("camera", self.sel["camera"]))
                if j >= len(sc["shots"]):      # extra coverage of the same beat: vary camera, drop one-shot sfx
                    sh["camera"] = ["zoom-out", "pan-left", "pan-right", "tilt-up"][j % 4]; sh["sfx"] = []
                shots.append(sh)
        chars = {c["id"]: c for c in self.s.get("characters", [])}
        for n, sh in enumerate(shots):
            sh["id"] = n
            sh["seed"] = base_seed + n * 31
            desc = ", ".join(chars[c]["prompt"] for c in sh.get("characters", []) if c in chars)
            # anime checkpoints insert people into empty scenes; keep character-less shots character-less
            import re as _re
            if not sh.get("characters") and not _re.search(r"people|person|crowd|man\b|woman|boy|girl|pedestrian|humans",
                                                           sh["prompt"]):
                sh["prompt"] += ", no humans, scenery"
            # CLIP truncates at 77 tokens: scene first (what must happen), then identity, then style tags.
            sh["full_prompt"] = ", ".join(x for x in (sh["prompt"], desc, self.sel["style"]) if x)
        _w(f, shots)
        return shots

    # ---------------------------------------------------------------- visuals
    def stage_keyframes(self, shots: list[dict]):
        t0 = time.time()
        w, h = self.sel["native"]
        for sh in shots:
            if sh["method"] != "i2v":
                continue
            kf = self.dir / "keyframes" / f"shot_{sh['id']:03d}.png"
            if kf.exists() or (self.dir / "clips" / f"shot_{sh['id']:03d}.mp4").exists():
                continue
            self.cb("keyframes", sh["id"], len(shots), f"keyframe {sh['id']+1}/{len(shots)}")
            ref = None
            if sh.get("characters") and self.sel["ip_adapter"]:
                rp = self.dir / "characters" / sh["characters"][0] / "ref_0.png"
                ref = Image.open(rp).convert("RGB") if rp.exists() else None
            img = videogen.generate_keyframe(sh["full_prompt"], sh["seed"], w, h, steps=18, base=self.sel["base"],
                                             ip_image=ref, ip_scale=float(sh.get("ip_scale", 0.5)), ip_variant="face")
            img.save(kf)
        self.timings["keyframes"] = round(time.time() - t0, 1)

    def stage_clips(self, shots: list[dict]) -> dict:
        t0 = time.time()
        rf = self.dir / "clip_reports.json"
        reps = json.loads(rf.read_text()) if rf.exists() else {}
        w, h = self.sel["native"]
        for sh in shots:
            out = self.dir / "clips" / f"shot_{sh['id']:03d}.mp4"
            if out.exists():
                continue
            self.cb("video", sh["id"], len(shots), f"animating shot {sh['id']+1}/{len(shots)}")
            best = None
            for attempt in range(3):
                seed = sh["seed"] + attempt * 101
                t1 = time.time()
                if sh["method"] == "i2v":
                    key = Image.open(self.dir / "keyframes" / f"shot_{sh['id']:03d}.png").convert("RGB")
                    fr = videogen.animate_keyframe(key, sh["full_prompt"], seed, strength=float(sh.get("strength", 0.65)),
                                                   base=self.sel["base"], camera=sh.get("camera"),
                                                   camera_strength=0.5, steps=6)
                else:
                    fr = videogen.generate_clip(sh["full_prompt"], seed, w, h, base=self.sel["base"],
                                                camera=sh.get("camera"), camera_strength=0.6)
                r = validate.clip_report(fr); r.update(seed=seed, attempt=attempt, secs=round(time.time() - t1, 1),
                                                       method=sh["method"], camera=sh.get("camera"))
                self.note(f"shot {sh['id']} {r}")
                if best is None or r["ok"]:
                    best = (fr, r)
                if r["ok"]:
                    break
            videogen.save_frames_mp4(best[0], out)
            reps[str(sh["id"])] = best[1]; _w(rf, reps)
        self.timings["clips"] = round(time.time() - t0, 1)
        return reps

    # ---------------------------------------------------------------- sound + edit
    def stage_edit(self, tl: dict, shots: list[dict]) -> Path:
        t0 = time.time()
        W, H = self.sel["export"]
        fps = compose.FPS
        xf = 0.25 if self.sel["max_shot"] < 3 else 0.5
        rendered, lengths, starts, acc = [], [], [], 0.0
        for sh in shots:
            self.cb("edit", sh["id"], len(shots), f"rendering shot {sh['id']+1}")
            last = sh["id"] == len(shots) - 1
            length = round((sh["slot"] + (0 if last else xf)) * fps) / fps
            o = self.dir / "work" / f"r_{sh['id']:03d}.mp4"
            compose.render_shot(self.dir / "clips" / f"shot_{sh['id']:03d}.mp4", o, length, W, H)
            rendered.append(o); lengths.append(length); starts.append(acc); acc += length - (0 if last else xf)
        joined = self.dir / "work" / "joined.mp4"
        compose.join_with_transitions(rendered, lengths, joined, seed=int(self.s.get("seed", 3)), xf=xf,
                                      transitions=["fade", "fadeblack", "smoothleft", "zoomin", "dissolve"])
        # subtitles from measured line timing
        cues = []
        for sc in tl["scenes"]:
            for ln in sc["lines"]:
                chunks = compose.chunk_words(ln["sub"], 4) if self.sub_lang != "ja" else _ja_chunks(ln["sub"])
                wts = [max(1, len(c)) for c in chunks]; cur = ln["start"]
                for c, wt in zip(chunks, wts):
                    d = ln["dur"] * wt / sum(wts); cues.append((cur, cur + d, c)); cur += d
        ass = self.dir / "work" / "subs.ass"
        compose.write_ass(cues, self.s["title"], tl["total"], ass, size=(W, H), end_card=self.s.get("end_card"))
        if self.sub_lang == "ja":
            txt = ass.read_text().replace(",Inter,", f",{JA_FONT},"); ass.write_text(txt)
        # scene-aware SFX: tags fire at the start of their shot (+ optional offset); ambience per scene
        events = []
        for sh, st in zip(shots, starts):
            for tag in sh.get("sfx", []):
                name, off = (tag["name"], tag.get("at", 0.0)) if isinstance(tag, dict) else (tag, 0.0)
                events.append({"t": st + off + (0.05 if name != "riser" else -0.4), "name": name})
        amb = []
        for i, sc in enumerate(self.s["scenes"]):
            a = sc.get("ambience", self.sel["ambience"])
            if a:
                amb.append({"start": tl["scenes"][i]["start"], "end": tl["scenes"][i]["end"], "name": a})
        fx = sfx.render_track(events, amb, tl["total"], self.dir / "audio" / "sfx.wav", seed=int(self.s.get("seed", 11)))
        _w(self.dir / "sfx_events.json", {"events": events, "ambience": amb})
        mus = music.compose(tl["total"] + 1, self.dir / "audio" / "music.wav", self.s.get("music_mood", self.sel["music"]),
                            int(self.s.get("seed", 7)))
        mix = self.dir / "audio" / "mix.wav"
        compose.mix_audio(self.dir / "audio" / "narration.wav", mus, mix, tl["total"], sfx=fx, music_gain=0.5)
        out = self.dir / "output.mp4"
        compose.final_render(joined, mix, ass, out)
        self.timings["edit"] = round(time.time() - t0, 1)
        return out

    def stage_extras(self):
        soc = self.s.get("social")
        if soc:
            _w(self.dir / "social.json", soc)

    def rebuild_report(self) -> dict:
        """Regenerate GENERATION_REPORT + bundle from a finished job (after extra checks like sync/dub)."""
        shots = json.loads((self.dir / "storyboard.json").read_text())
        reps = json.loads((self.dir / "clip_reports.json").read_text())
        speech = json.loads((self.dir / "speech_report.json").read_text())
        final = json.loads((self.dir / "report.json").read_text())
        rep = report.build(self.dir, self.s, self.sel, shots, reps, final, speech, {})
        return {"report": rep["title"], "bundle": str(bundle.export_bundle(self.dir))}

    # ---------------------------------------------------------------- run
    def run(self) -> dict:
        t0 = time.time()
        _w(self.dir / "script.json", self.s)
        if self.s.get("series"):
            _w(self.dir / "series.json", self.s["series"])
        chars = self.stage_characters()
        tl = self.stage_voice(chars)
        speech = self.stage_speech_check(tl)
        shots = self.stage_storyboard(tl)
        self.note(f"{len(self.s['scenes'])} scenes, {len(shots)} shots, {tl['total']}s, selection: {self.sel['reasons']}")
        self.stage_keyframes(shots)
        videogen.unload()
        reps = self.stage_clips(shots)
        videogen.unload()
        out = self.stage_edit(tl, shots)
        self.stage_extras()
        final = validate.final_report(str(out), tl["total"])
        final["speech_intelligible_ratio"] = round(sum(1 for x in speech if x["intelligible"]) / max(1, len(speech)), 2)
        self.timings["total"] = round(time.time() - t0, 1)
        _w(self.dir / "report.json", final)
        report.build(self.dir, self.s, self.sel, shots, reps, final, speech, self.timings)
        z = bundle.export_bundle(self.dir)
        self.cb("done", 1, 1, "complete")
        return {"final": final, "bundle": str(z), "output": str(out), "timings": self.timings}


JA_FONT = "IPAGothic"


def _ja_chunks(text: str, n: int = 14) -> list[str]:
    import re
    parts = [p for p in re.split(r"(?<=[。！？、…])", text) if p.strip()]
    out, cur = [], ""
    for p in parts:
        if len(cur) + len(p) > n and cur:
            out.append(cur); cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    return out
