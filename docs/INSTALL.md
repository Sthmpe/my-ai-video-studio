# Installation

Requirements: Linux x86-64, Python 3.12 (via `uv`), FFmpeg ≥ 6 with libx264/libass, ~8 GB free disk, ≥ 8 GB RAM. GPU optional (auto-detected, fp16).

```bash
git clone https://github.com/Sthmpe/my-ai-video-studio && cd my-ai-video-studio
sudo apt-get install -y ffmpeg fonts-inter      # fonts-inter: subtitle font
scripts/setup.sh                                # venv at /opt/studio/venv + ~3 GB of weights
/opt/studio/venv/bin/python -m pytest -q tests  # unit tests
```

Environment variables: `STUDIO_MODELS` (default `/opt/studio/models`), `STUDIO_DATA` (default `./data`), `STUDIO_API_KEY` (API mode), optional LLM keys `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`.

## Generate from the command line
```bash
cd engine
# 1) with a script (Claude Code / you wrote it):
/opt/studio/venv/bin/python -m studio generate --script ../examples/sloth.json --job sloth
# 2) topic only (needs an LLM key or uses the local Qwen fallback):
/opt/studio/venv/bin/python -m studio generate --topic "The secret life of the octopus" --job octopus
```
Output: `data/jobs/<job>/output.mp4` plus `report.json`, `script.json`, `storyboard.json`, per-shot clips. Re-running the same `--job` resumes.

## From Claude Code
Say *"Generate a documentary about the octopus"* (or run `/generate-documentary the octopus`). Claude researches, writes `examples/<slug>.json`, runs the engine in the background, inspects frames, validates and commits the MP4. See `.claude/commands/`.

## Always-on API + worker
```bash
export STUDIO_API_KEY=$(openssl rand -hex 24)
cd engine && /opt/studio/venv/bin/python -m studio.supervisor   # API :8787 + worker, auto-restart
curl -s localhost:8787/health
curl -s -XPOST localhost:8787/jobs -H "Authorization: Bearer $STUDIO_API_KEY" -H 'content-type: application/json' -d '{"topic":"octopus"}'
```
A systemd unit is in `deploy/studio.service`; a Dockerfile is in `deploy/Dockerfile`.
