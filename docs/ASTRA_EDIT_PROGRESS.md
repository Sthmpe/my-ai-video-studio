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

The initial model request returned HTTP 403. On the following cloud session, the host returned HTTP 200. The download and CPU build then completed.

## Verified opening cut

The three-second opening cut uses two newly generated shots. Each uses a six-step LCM keyframe and the four-step AnimateDiff-Lightning checkpoint for image-to-video. The motion source is 288×512 at 8 fps and the H.264/AAC export is 1080×1920 at 24 fps. The resumed animation and edit pass took 469.7 seconds. Reference and keyframe creation happened in an earlier session. The local clip validator accepted both shots on their first attempts. Mean output audio volume was −17.1 dB.

Inspection of the reference, both keyframes and twelve decoded final frames found consistent hair and collar design. The model changed eye colour, softened the face at export size and maintained a similar pose across most of the running shot. The full edit is a separate production. Its target duration is 60 seconds.

The deployed MP4, project ZIP and JSON generation report returned HTTP 200. The downloaded bytes matched the local artifacts by SHA-256. [Opening MP4](https://my-ai-video-studio-astra.vercel.app/demo/astra/vale-opening.mp4) · [Project archive](https://my-ai-video-studio-astra.vercel.app/demo/astra/vale-opening.studio.zip) · [Generation report](https://my-ai-video-studio-astra.vercel.app/demo/astra/vale-opening.report.json)

## Local speech and script writing

Kokoro generated a 3.05-second English sample and a 4.20-second Japanese sample at 24 kHz. Whisper transcribed both with zero normalized error for the tested lines. Japanese synthesis initially failed because fugashi selected an empty UniDic path. The installer now links the bundled lightweight dictionary when that path is absent.

llama.cpp at `2cbfc3cf` loaded the official Qwen2.5-3B-Instruct Q4_K_M GGUF after SHA-256 verification. On the first CPU machine the four-thread benchmark averaged 26.70 tokens/s for prompt processing (128 tokens) and 2.68 tokens/s for generation (32 tokens), each over three repetitions. The application received valid title and action fields from the local model through its chat endpoint.

## Alternative video models

The Wan2.2-TI2V-5B repository lists an 11.36 GB text encoder, with the first two diffusion shards alone totalling over 19 GB. This environment has a four-core CPU quota, 32 GiB memory limit and no CUDA device. The LTX-Video repository's 13B distilled checkpoint is 28.58 GB. These were model-card and file-size comparisons. Neither model was benchmarked on the machine.
