# Environment audit (Claude Code cloud sandbox, 2026-11-17)

| Item | Result |
|---|---|
| CPU | Intel Xeon @ 2.1 GHz, **4 vCPU**, AVX2 + AVX-512 (BF16, FP16, VNNI) |
| GPU | **none** (`nvidia-smi` absent) |
| RAM | 15 GB |
| Disk | 252 GB volume, ~30 GB usable by the session |
| User | root, no systemd; Docker CLI present, daemon not usable |
| Python / Node / FFmpeg | 3.13 (venv uses 3.12 via `uv`) / 22 / 6.1 (libx264, libass, xfade, minterpolate) |
| Egress | HTTPS only, through a policy proxy; allow-list: PyPI, npm, GitHub, Hugging Face. Hugging Face's Xet host (`cas-server.xethub.hf.co`) is blocked, so `huggingface_hub` downloads hang at 0 B — `scripts/download_models.sh` uses plain `curl` against `resolve/` URLs instead (≈30 MB/s) |
| Ingress | **none** — no public listener, no tunnel (cloudflared/ngrok/localtunnel hosts are not allow-listed) |
| Lifetime | container is ephemeral and reclaimed after inactivity; only git-pushed state persists |

## What this means for "24/7"
See [DEPLOYMENT.md](DEPLOYMENT.md): the sandbox itself **cannot** be a permanent public worker. The verified 24/7 path is GitHub Actions (free for public repos) with Vercel as the control plane; the same engine also ships a supervisor + HTTP API for any always-on VM.
