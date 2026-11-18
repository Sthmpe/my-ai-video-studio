# Astra anime edit progress

Development started on `astra/independent` from Claude's foundation at `4a066b0`.

The first implementation gives instrumental anime edits an explicit runtime and cuts that follow a shared 120 BPM grid. Each shot receives one to three beats, with the final shot allowed to end at the requested video frame. The planner requires unique shot prompts and does not duplicate coverage to fill time. Sound effects can fire on the cut or at an authored offset. The music synthesizer adds kick and snare accents, and the project report records the tempo, requested runtime, and editing method.

[Vale and the Storm Engine](../examples/vale_storm_engine_edit.json) is an original 60-second vertical edit script with 40 distinct shots across eight sequences. Once model weights are installed, run from the repository root.

```bash
export STUDIO_MODELS=/workspace/.studio-env/models
export STUDIO_DATA=/workspace/.studio-env/data
cd engine
/workspace/.studio-env/venv/bin/python -m studio story \
  --script ../examples/vale_storm_engine_edit.json --job vale-storm-engine
```

The same job ID resumes the existing timeline and clips. Use a fresh ID for changes to the script. An edit script supplies `target_seconds` and dialogue-free scenes. At 120 BPM, a 60-second edit requires 40 to 120 distinct shot prompts. Other story modes retain their narration-based timing.

The planner tests verified 40 planned cuts at 1.5-second intervals over 60 seconds and rejection of duplicate coverage. A separate FFmpeg check used synthetic moving clips and produced a three-second H.264/AAC MP4 with 72 video frames, audible music and sound effects, and event starts at 0 and 1.5 seconds. This measured editing behavior. Visual quality and model runtime still need a generation run.

The managed machine exposed four CPU cores through its cgroup quota and no CUDA device. Its proxy denied Hugging Face access with HTTP 403 before the first motion model could download. The model hosts are in the saved draft. The checked-in episode bundle imported successfully, and the checked-in 126-second documentary probed as 1080×1920 H.264 with AAC audio and decoded for the first three seconds. Fresh video generation, superhuman and episode-continuation demos, and deployment to `my-ai-video-studio-astra` remain pending.
