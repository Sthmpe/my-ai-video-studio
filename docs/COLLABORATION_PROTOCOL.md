# Collaboration protocol — Claude ⟷ Astra

| | Claude (this agent) | Astra / Codex |
|---|---|---|
| Branch | `ccr-931534f5-lqm602` | `astra/independent` |
| Vercel project | `my-ai-video-studio` (https://my-ai-video-studio-rho.vercel.app) | its own project |
| Workflow file | `.github/workflows/claude-generate.yml` (name `claude-generate-video`) | its own file name, e.g. `astra-generate.yml` |
| Run title | `claude-studio <job_id>` | suggested `astra-studio <job_id>` |
| Release tags | `claude-video-<job_id>` | suggested `astra-video-<job_id>` |
| Job ids from web | `claude-web-*` | suggested `astra-web-*` |
| Artifacts | `claude-studio-<job_id>` | suggested `astra-studio-<job_id>` |
| Concurrency group | `claude-gen-<job_id>` | suggested `astra-gen-<job_id>` |

Rules (from the owner)
1. Each agent pushes only to its own branch and deploys only its own Vercel project.
2. No merge / rebase / cherry-pick / direct edit of the other branch without the owner's approval.
3. No automatic cross-branch integration (no workflow listens to the other branch).
4. Reading the other branch and adapting ideas independently is allowed — credit the source in commit messages / `docs/PROGRESS.md`.
5. Suggestions go through GitHub issues (label `agent-proposal`) or `docs/proposals/*.md` on one's own branch.
6. Only the owner authorises integration. Each agent owns its own tests and deployment.
7. Secrets are never committed; each agent's Vercel env is configured separately by the owner.

Collision checks: release tags, run titles and artifact names are prefixed; workflow files have different paths, so `workflow_dispatch` by file name never triggers the other agent's pipeline. Both workflows use the default `GITHUB_TOKEN`, scoped to the run.

Note: the release tag `video-gha-smoke-2` predates namespacing and belongs to Claude (smoke test). All newer Claude tags use `claude-video-*`.
