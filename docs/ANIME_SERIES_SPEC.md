# Anime series & character memory

## Character record (`characters/<id>.json`)
```json
{ "id": "kai-arata", "name": "Kai Arata", "role": "protagonist",
  "visual": {"summary": "...", "face": "...", "hair": "...", "body": "...", "outfit": "...", "palette": ["#..."]},
  "prompt": "the exact descriptor inserted into every shot prompt",
  "negative": "things that must never appear on this character",
  "references": ["characters/kai-arata/ref_0.png"],
  "voice": {"en": {"engine": "kokoro", "voice": "am_puck", "speed": 1.0}, "ja": {"engine": "kokoro", "voice": "jm_kumo", "speed": 1.0}},
  "personality": "...", "powers": ["time stop"], "relationships": {"stranger": "unknown pursuer"},
  "continuity": ["scar on left hand appears from Ep1 onward"], "episodes": ["ep1"],
  "generation": {"model": "counterfeit-v2.5", "seed": 1234, "ip_adapter_scale": 0.6} }
```

## How consistency is enforced
1. A **character sheet keyframe** is generated once (SD1.5 anime checkpoint, fixed seed) and stored as `ref_0.png`.
2. Every shot featuring the character: descriptor injected in the prompt + **IP-Adapter-Plus** conditioned on the reference image.
3. Voices are fixed per character per language.
4. On continuation, references and records are loaded from the imported bundle — never regenerated.

Limits: IP-Adapter preserves palette, outfit and overall look well; fine facial identity and small accessories can still drift, especially in fast action at 4 denoising steps.

## Third-party IP
Original characters are the default. Existing anime characters or user references are only used when the user states they have rights; the generation report records that the content contains user-supplied references, and publishing permission remains the user's responsibility.
