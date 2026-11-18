# Quality improvement plan

## Audit of the existing films (measured 2026-11-18)
| # | Problem | Evidence | Planned fix (feasible on 4 vCPU) |
|---|---|---|---|
| 1 | **Weak motion** — clips mostly "breathe" | mean abs frame diff: cat 1.98, sloth 3.59 (gray, 144×256, 8 fps); 2 s clips stretched 2× | camera-motion LoRAs (zoom/pan/tilt/roll) chosen per shot; action-verb prompting; shot-type aware pacing |
| 2 | **Character drift** between shots | sloth/cat design changes per shot (frame review) | character sheet keyframe → **IP-Adapter-Plus** conditioning on every shot; fixed descriptor; seeds per character |
| 3 | **Low native resolution** (288×512 → 1080×1920) | soft detail | raise native to 384×672 where time allows; optional Real-ESRGAN ×2 enhancement (reported as enhancement, not native) |
| 4 | **Sound** — narrator + generic loop only | no SFX/ambience/dialogue | scene-aware SFX synthesis (whoosh, impact, electricity, wind, clock, time-freeze), ambience beds, multi-voice dialogue, EN + JA |
| 5 | **Storytelling/editing** — uniform ~4.5 s shots, no hook | storyboard slots all equal | hook-first story template, shot types (wide/close/action/reveal), variable pacing, cliffhanger, title/hashtag kit |

Out of reach on this hardware (documented in MODELS.md): Wan 2.1/2.2, LTX-Video, CogVideoX, HunyuanVideo — need a GPU and/or >20 GB text encoders.
