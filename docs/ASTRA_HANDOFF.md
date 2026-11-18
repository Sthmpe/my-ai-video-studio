# Handoff for Astra

**Reproducible baseline commit:** `c5e9b12` on `ccr-931534f5-lqm602` (everything below was verified at that commit). Branch from it: `git fetch origin ccr-931534f5-lqm602 && git checkout -b astra/independent c5e9b12`.

## What works at the baseline (verified)
* `engine/studio` pipeline: script → Kokoro TTS timeline → storyboard → AnimateDiff-Lightning (4-step) on ToonYou β6 → clip quality gate with re-seed → FFmpeg edit (interpolation, xfade, ASS subtitles, ducked procedural music) → validator.
* Demos: `outputs/sloth-documentary-1080x1920.mp4` (126 s, 30 shots), `outputs/cat-knocks-things-over-1080x1920.mp4` (68 s, 17 shots).
* Queue/API/supervisor with crash recovery (tested by SIGKILL), GitHub Actions worker (tested: run 44186663971), Vercel front end.
* Local keyless script writing with Qwen2.5-3B (tested, 126 s per script).

## Setup
```
scripts/setup.sh                 # venv /opt/studio/venv + weights (curl; HF Xet host is blocked in Claude's sandbox)
cd engine && python -m studio generate --script ../examples/sloth.json --job test
pytest -q tests
```

## Known limits at the baseline
1. Native 288×512, upscaled 3.75× (soft). 2. Weak motion (2 s, 8 fps, mean frame diff ≈ 2–3.6). 3. No character identity conditioning.
4. No SFX/ambience, single narrator, no dialogue. 5. Uniform pacing, no hook structure.
6. Vercel→GitHub dispatch untested end-to-end (needs owner-created `GITHUB_TOKEN`).

## Gotchas
* bf16 only on CPUs with `avx512_bf16`/`amx` (else fp32) — GitHub runners stall otherwise.
* `minterpolate` drops the clip tail; shots are padded with `tpad` and cut to exact frame counts.
* Lightning weights need `MotionAdapter()` default config (mid-block motion modules).
* Use your own workflow file name, release prefix and run-title prefix (see COLLABORATION_PROTOCOL.md).

Claude continues on its own branch; this handoff does not freeze Claude's work.

---
## Update — v2 baseline `30c1ae5` (2026-11-18)
New since `c5e9b12` (all verified, see PROGRESS.md / QUALITY_EXPERIMENTS.md):
* `studio story` (script v2), `continue`, `dub`, `export`, `import`, `report` CLI commands.
* Keyframe → image-to-video with Counterfeit-V2.5 + AnimateDiff-Lightning v2v + camera LoRAs + IP-Adapter-Plus-Face.
* Kokoro Japanese via misaki G2P (+ unidic-lite, offline); Whisper-base speech + sync checks; procedural SFX/ambience.
* `.studio.zip` schema v1 (checksums, zip-slip safe), generation reports (MD + JSON).
Reusable findings (free to adapt independently):
1. `AnimateDiffVideoToVideoPipeline.from_pipe()` casts the shared UNet to fp32 unless `torch_dtype` is passed (5× slower on CPU).
2. SD VAEs have `force_upcast=True` → fp32 decode; disable it when running bf16.
3. Building UNetMotionModel leaves ~5 GB of freed fp32 heap resident → `malloc_trim(0)`.
4. IP-Adapter-Plus copies the reference composition; Plus-Face at 0.5 keeps identity *and* the scene.
5. CLIP truncates at 77 tokens — put the scene before the character descriptor.
6. Duck SFX under dialogue as well as music (Whisper caught a masked line).
