# Free providers, limits and rotation

Rules the code follows (`engine/studio/providers.py`):
1. A provider is **eligible only if its key env-var is set** (keyless providers excepted). No key is ever assumed.
2. On **HTTP 429 / quota error** the provider goes on **cooldown** (`Retry-After` honoured) and the next one is tried.
3. We **never rotate multiple accounts/keys of one provider** to bypass its quota.
4. Everything has a local fallback, so quotas can slow the system but never stop it.

Published free-tier limits change often — treat numbers below as orientation and check the provider's page before relying on them.

## Text / script (LLM)
| Provider | Key env | Free tier (orientation) | Notes |
|---|---|---|---|
| Groq | `GROQ_API_KEY` | per-model RPM + daily token caps | OpenAI-compatible, very fast |
| Google Gemini | `GEMINI_API_KEY` | per-model RPM/RPD caps (AI Studio) | OpenAI-compat endpoint used |
| OpenRouter `:free` models | `OPENROUTER_API_KEY` | ~20 req/min, daily cap on `:free` models | many open models |
| Mistral (La Plateforme, free tier) | `MISTRAL_API_KEY` | strict RPM, monthly token cap | |
| **Local Qwen2.5-3B** | none | unlimited | automatic fallback; **tested**: topic → valid 9-scene script in 126 s on 4 vCPU, no keys (fact quality is only as good as a 3B model — review before publishing) |
| **Claude Code session** | none | — | the interactive agent writes `script.json` itself |

## Research
| Provider | Key | Limits | Use |
|---|---|---|---|
| Wikipedia / MediaWiki API | none | polite use; descriptive `User-Agent` required | primary factual source (CC BY-SA, credited in the script) |
| Wikidata / Open Library / arXiv | none | polite use | planned secondary sources |

## Voice, music, imagery
| Need | Primary (default) | Optional free API fallbacks |
|---|---|---|
| Narration | Kokoro-82M local | Hugging Face Inference free credits; Pollinations text/audio (keyless, rate-limited) |
| Music | procedural synth, original | Freesound (CC0 filter, free key), Free Music Archive, Incompetech (CC-BY, credit required) |
| Video | AnimateDiff-Lightning local | none — **intentionally no stock-footage APIs** (Pexels/Pixabay are not used; the goal is generated video) |

## Reachability in the build sandbox (measured 2026-11-17)
The Claude Code cloud sandbox only allows egress to PyPI, npm, GitHub and Hugging Face. **Blocked (HTTP 403 from the egress proxy):** wikipedia.org, pollinations.ai, pexels.com, archive.org, download.pytorch.org, bing speech. Consequences:
* Wikipedia research and every keyed LLM API are implemented and unit-tested for rotation logic but **could not be exercised live from this sandbox**; they work from a normal runner (e.g. GitHub Actions) or after the environment's allow-list is extended.
* The demo video's script was therefore written by Claude Code from verified zoology knowledge — exactly the "Claude Code mode" in the architecture.
