# Operations runbook

| Task | Command |
|---|---|
| Health | `curl localhost:8787/health` → `worker_alive`, `queued` |
| Start everything | `cd engine && python -m studio.supervisor` (logs in `data/logs/`) |
| Submit | `POST /jobs {"topic":…}` or `{"script":{…}}` with `Authorization: Bearer $STUDIO_API_KEY` |
| Resume a CLI job | re-run the same `studio generate … --job <id>` — cached stages are skipped |
| Redo only the edit | delete `data/jobs/<id>/work` and `output.mp4`, re-run |
| Re-roll one bad shot | delete `clips/shot_NNN.mp4` (and its entry in `clip_reports.json`), re-run |
| Tests | `pytest -q tests` |

## Failure modes seen while building (and fixes)
* **`huggingface_hub` downloads stall at 0 B** — Hugging Face's Xet CAS host is blocked by the sandbox proxy. `scripts/download_models.sh` uses plain `curl`.
* **Final video 14 s instead of 126 s** — caught by `validate.final_report`. `minterpolate` drops the last ~0.4 s of every clip, so cross-fade offsets overran. Fix: pad each shot with `tpad`, cut to an exact whole number of frames.
* **MotionAdapter state-dict mismatch** — Lightning weights include mid-block motion modules; build `MotionAdapter()` with default config.
* **Clip quality gate** — all-black, flat or frozen clips are re-seeded (up to 3×) and the best attempt kept.

## Performance (4 vCPU, no GPU)
~42 s per 16-frame 288×512 shot · 30 shots ≈ 22 min · edit/render ≈ 5 min · narration (Kokoro) ≈ 1.3× real time. A 2-minute film ≈ 30 min end-to-end.

## bf16 vs float32 (learned the hard way)
The first GitHub Actions smoke job sat at `0/4` denoising steps for 21 minutes: hosted runners have no native bf16, so PyTorch emulates it. `videogen.device_and_dtype()` now enables bf16 only when `avx512_bf16`/`amx_bf16` is present and uses float32 otherwise. (This sandbox's Xeon has native bf16, hence ~6 s/step here.)

## Story / anime jobs (v2)
| Task | Command |
|---|---|
| Story from a script | `python -m studio story --script ../examples/boy_who_stole_time_ep1.json --job ep1` |
| Story from an idea | `python -m studio story --idea "..." --mode superhuman --seconds 30 --aspect 9:16 --job x` |
| Export / import bundle | `python -m studio export --job ep1` · `python -m studio import --bundle x.studio.zip --job y` |
| Next episode | `python -m studio continue --bundle ep1.studio.zip --script ep2.json --job ep2` (or `--idea "..."`) |
| Japanese dub | `python -m studio dub --job ep1 --lang ja` → `output_ja.mp4`, `dub_ja_report.json` |
| Re-roll one shot | delete `keyframes/shot_NNN.png` and/or `clips/shot_NNN.mp4`, re-run the same command |
| Re-edit only | delete `output.mp4`, re-run (keyframes/clips/voice are cached) |

Memory: peak ≈ 10 GB for 384×672 image-to-video. Do not run two generation jobs at once on a 15 GB machine.
