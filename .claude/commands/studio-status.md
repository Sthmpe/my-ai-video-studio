---
description: Show worker/queue health and recent jobs
---
Run `curl -s localhost:8787/health` and `curl -s -H "Authorization: Bearer $STUDIO_API_KEY" localhost:8787/jobs`;
if the API is down, start it with `cd engine && /opt/studio/venv/bin/python -m studio.supervisor` (background) and re-check.
