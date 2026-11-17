# Deployment & 24/7 operation — what was tested, what was not

## Findings (Claude Code cloud sandbox)
| Question | Result | Evidence |
|---|---|---|
| Can the sandbox host a public always-on worker? | **No.** Container is ephemeral (reclaimed after inactivity); there is **no inbound networking** and no tunnel host (cloudflared/ngrok/localtunnel) is allow-listed. A Vercel function cannot reach a process in it. | egress-only policy proxy, `docs/ENVIRONMENT.md` |
| Does process supervision / crash recovery work? | **Yes — tested.** `studio.supervisor` + SQLite queue: a worker `kill -9`'d mid-job was restarted within ~1 s, the interrupted job was re-queued (`attempts=2`), finished, passed validation, and the MP4 was downloaded through the HTTP API. | run on 2026-11-17, `/tmp/persist/logs/worker.log`: "re-queued 1 interrupted jobs" |
| Can it survive the end of the interactive session? | **Not as a service.** Only git-pushed state survives. | — |
| Free 24/7-ish alternative with outside verification? | **GitHub Actions** (free for public repos; 4 vCPU/16 GB Linux runner, 6 h job limit) used as an on-demand worker, triggered externally. | `generate.yml`, run `gha-smoke-1` (see below) |

So the honest architecture is: **Vercel = control plane, GitHub Actions = elastic worker, Release assets = storage.** The always-on API/worker pair is shipped for anyone with a VM (Oracle Always-Free ARM, a home server, Fly/Railway free tiers) and is the right choice once a GPU is available.

## Verified from outside the sandbox
`generate.yml` was dispatched via the GitHub API (job `gha-smoke-2`, run 44186663971): a fresh GitHub-hosted runner installed the stack, downloaded the weights, **generated 2 AI shots + narration + music, rendered and validated the video in 6 min 1 s**, and published it as a Release. Downloaded back over plain HTTPS from the sandbox: https://github.com/Sthmpe/my-ai-video-studio/releases/tag/video-gha-smoke-2 (1920×1080 h264+aac, `report.json` `"ok": true`). The first attempt (`gha-smoke-1`) was cancelled after 48 min because bf16 is emulated on those CPUs — fixed (see OPERATIONS.md).
Not yet tested end-to-end: the Vercel → GitHub dispatch hop, because it needs a `GITHUB_TOKEN` secret that only the repo owner can create (step 2 below).

## Path A — GitHub Actions worker (works today, no server)
1. Make sure `.github/workflows/generate.yml` is on the default branch.
2. Create a fine-grained PAT for this repo: *Actions: read & write*, *Contents: read*. Add it to Vercel as `GITHUB_TOKEN`.
3. Vercel env: `SUBMIT_PASSCODE` (anything secret), optional `GH_REPO`, `GH_REF`.
4. Optional repo secrets for keyed topic→script: `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`. Without them, topic-only jobs use the local Qwen model; jobs with `script_json` never need an LLM.
5. `POST /api/jobs` → `workflow_dispatch(job_id, topic|script_json, orientation)`. `GET /api/jobs/<id>` finds the run by its title `studio <id>` and the release `video-<id>`; `done` returns the asset URL.

## Path B — always-on engine
`scripts/setup.sh`, then `systemctl enable --now studio` (`deploy/studio.service`) or `docker run` (`deploy/Dockerfile`). Put it behind HTTPS (Caddy/Cloudflare Tunnel), set `STUDIO_API_KEY`, and in Vercel set `ENGINE_URL` + `STUDIO_API_KEY`. The web layer switches to Path B automatically when `ENGINE_URL` is set.

## Vercel
Project `my-ai-video-studio` (team `sthmpe's projects`), root directory `web/`, Git-connected: every push redeploys. Public (Vercel Authentication disabled) so it can be a portfolio piece. Live: https://my-ai-video-studio-rho.vercel.app
`/api/health` reports the configured backend; `/api/jobs` refuses submissions without the passcode so strangers cannot burn compute.
