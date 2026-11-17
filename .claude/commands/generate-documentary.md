---
description: Generate a documentary / cartoon video end-to-end with the local AI engine
argument-hint: <topic or story idea> [vertical|landscape]
---
Produce a complete AI-generated video about: $ARGUMENTS

You ARE the script writer (no paid LLM needed). Steps:
1. Research the topic (WebSearch/WebFetch if allowed, else your own verified knowledge). Only state true facts.
2. Write `examples/<slug>.json` following the schema in `docs/ARCHITECTURE.md` (title, mood, voice,
   scenes[{narration (<=32 words), shots[{prompt}]}]). Funny, warm, story-driven; ~13-16 scenes for 2-3 min.
   Keep ONE consistent character descriptor in every shot prompt. Describe action + camera, no text in image.
3. Make sure the environment exists (`scripts/setup.sh` if /opt/studio is missing).
4. Run in the background: `cd engine && /opt/studio/venv/bin/python -m studio generate --script ../examples/<slug>.json --job <slug>`
   (resumable: re-run the same command after any interruption). Poll the log; inspect early clips visually.
5. Validate: `data/jobs/<slug>/report.json` must have `"ok": true`. Look at frames before delivering.
6. Copy the MP4 to `outputs/<slug>.mp4`, commit, push, and report the path.
