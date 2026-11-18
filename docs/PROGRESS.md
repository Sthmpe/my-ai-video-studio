# Progress (honest status)

Legend: ✅ done & verified · 🧪 experimental (works, limited testing) · ⛔ blocked · ⏳ remaining

| Area | Status | Evidence |
|---|---|---|
| Documentary pipeline (AnimateDiff-Lightning + ToonYou + Kokoro + FFmpeg) | ✅ | sloth 126 s / cat 68 s, reports in `outputs/` |
| Crash-safe queue + API + supervisor | ✅ | SIGKILL test (DEPLOYMENT.md) |
| GitHub Actions worker | ✅ | run 44186663971, release `video-gha-smoke-2` |
| Vercel site | ✅ | https://my-ai-video-studio-rho.vercel.app |
| Vercel → GitHub dispatch | ⛔ | needs owner-created `GITHUB_TOKEN` + `SUBMIT_PASSCODE` in Vercel |
| Local LLM scripts (Qwen2.5-3B) | ✅ | 126 s/script, no keys |
| Agent namespacing (workflow/release/run prefixes) | ✅ | `claude-generate.yml`, `claude-video-*` |
| Quality v2 / modes / bundles / continuation / JA | ⏳ | in progress — updated below as milestones land |
