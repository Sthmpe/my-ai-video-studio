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
