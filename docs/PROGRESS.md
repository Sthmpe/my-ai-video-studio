# Progress (honest status) — updated 2026-11-18

Legend: ✅ done & verified · 🧪 works, limited testing · ⛔ blocked (owner action) · ⏳ remaining

## Benchmark: v2 anime engine vs v1 documentary engine (same machine, measured)
| Film | Engine | Native | Clip motion¹ | Clip contrast | s/shot | Identity² |
|---|---|---|---|---|---|---|
| Sloth (v1) | ToonYou t2v | 288×512 | 3.59 | 46.8 | ~45 | n/a |
| Cats (v1) | ToonYou t2v | 288×512 | 1.98 | 46.8 | ~45 | n/a |
| **Boy Who Stole Time Ep 1** | Counterfeit keyframe → i2v + camera LoRA + IP-Adapter-Face | **384×672** | **15.81** | **69.0** | 110 (+45 keyframe) | Kai 0.851 / Stranger 0.849 |
| **Ep 2 teaser** (continuation) | same, refs imported | 384×672 | 16.04 | 63.8 | 122 | Kai 0.850 / Stranger 0.856 / Seren 0.873 |
¹ mean abs gray frame diff at 8 fps (higher = more movement; visually confirmed as real motion, not noise). ² CLIP ViT-H cosine similarity of shots to their own character reference (other characters ≈ 0.72; v1-style baseline A = 0.61).

## Demonstrations
| Demo | Status | Evidence |
|---|---|---|
| A — "The Boy Who Stole Time — Ep 1" (38 s, 9:16, original anime, time-stop power, dialogue, SFX, music, subtitles, cliffhanger) | ✅ | `outputs/boy-who-stole-time-ep1-en-1080x1920.mp4`, bundle `outputs/bundles/boy-who-stole-time-ep1.studio.zip`, report `outputs/reports/btst-ep1-GENERATION_REPORT.md` |
| B — Ep 2 teaser from Ep 1's bundle | ✅ | `continuity_report.json`: refs byte-identical, voices/mode/aspect inherited; identity 0.850 vs 0.851 |
| C — documentary regression | ✅ | job `regression-doc`: valid 14 s video, speech error 0.0, now also gets report + bundle |
| D — English + Japanese | ✅ voices/subtitles · 🧪 dub timing | JA dub `outputs/boy-who-stole-time-ep1-ja-1080x1920.mp4`; Whisper: 7/8 lines intelligible; the line compressed to 1.35× is garbled |

## Features
| Area | Status | Notes |
|---|---|---|
| Modes: documentary, anime_action, superhuman, anime_edit, cinematic, story, explainer | ✅ router · 🧪 per-mode output | anime_action + documentary rendered end-to-end; others share the same code paths with different presets |
| Aspect 9:16 / 16:9 / 1:1 | ✅ code · 🧪 | 9:16 rendered; 16:9 tested in GH smoke (v1); 1:1 covered by router test only |
| Durations 15–180 s / custom | ✅ | pacing via `max_shot`; longest rendered: 126 s (v1) |
| Keyframe → image-to-video | ✅ | QUALITY_EXPERIMENTS exp 2 |
| Character memory (IDs, refs, voices, powers, continuity) | ✅ | `characters/<id>.json` + `ref_0.png` |
| `.studio.zip` export / verified import | ✅ | 18 unit tests incl. tamper + zip-slip |
| Episode continuation | ✅ | Demo B |
| Re-edit / regenerate specific shots | ✅ | delete a shot's keyframe/clip → re-run (OPERATIONS.md) |
| Import a previous *video* or images as character reference | 🧪 | `studio refs --video x.mp4 [--at 13] --image y.png --rights ...`; auto-pick crops title/subtitle bands; picks sharp frames, not guaranteed to be the character — use `--at` |
| Idea → story script (LLM APIs or local Qwen) | 🧪 | code path written; local Qwen tested for v1 scripts, v2 story prompt not yet run end-to-end |
| EN + JA TTS (Kokoro), per-character voices | ✅ | Whisper CER 0.00 on JA test line |
| Scene-timed SFX + ambience, SFX ducked under dialogue | ✅ | fix verified: masked line now recognised |
| Audio/subtitle sync verification | ✅ | median 0.19 s on Ep 1 final mix |
| Generation report MD + JSON in every job & bundle | ✅ | also for documentaries |
| Website v2 (modes, duration, aspect, language, continuation, downloads, history, report) | ✅ deployed · ⛔ submit | needs `GITHUB_TOKEN` + `SUBMIT_PASSCODE` in Vercel (DEPLOYMENT.md) |
| Reference image / video upload from the website | ⏳ | needs a storage target (Vercel Blob) — owner decision |
| GitHub Actions worker with modes + continuation | ✅ anime path · 🧪 continuation | v2 anime job verified live: release `claude-video-claude-gha-anime-1` (MP4 + .studio.zip + reports). fp32 runner: 50 min for 6 s / 2 shots (~10× slower than bf16 sandbox) — fine for teasers, too slow for 60 s+ episodes; continuation on Actions untested |
| Agent namespacing | ✅ | `claude-generate.yml`, `claude-video-*`, `claude-studio <id>` |
| GPU tier (Wan/LTX/CogVideoX) | ⏳ | researched only (no GPU) |

## Known quality limits (see each GENERATION_REPORT)
Upscaled ×2.86 (not native 1080p) · 2 s clips interpolated to 24 fps · hands/accessories warp in fast motion · one energy-blast shot renders a mecha-like figure · JA time-fitting above ~1.25× hurts intelligibility.
