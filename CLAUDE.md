# My AI Video Studio — instructions for Claude Code
Engine: `engine/studio` (Python). Models in `/opt/studio/models` (`scripts/setup.sh` installs everything).
- "Generate a documentary/video about X" → follow `.claude/commands/generate-documentary.md`.
- Run tests: `/opt/studio/venv/bin/python -m pytest -q tests`
- The visuals MUST come from the AI model (AnimateDiff-Lightning). Never replace with stock footage or slides.
- No GPU here: ~45 s per 2-second 288x512 clip on 4 vCPU. Plan runs in background and resume (stages are cached per job dir).
- Never commit weights, `data/`, or API keys.
