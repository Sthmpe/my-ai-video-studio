#!/usr/bin/env bash
# One-shot install: venv + deps + models.  Usage: scripts/setup.sh
set -euo pipefail
command -v uv >/dev/null || pip install uv
uv venv -p 3.12 "${STUDIO_VENV:-/opt/studio/venv}"
. "${STUDIO_VENV:-/opt/studio/venv}/bin/activate"
uv pip install -r "$(dirname "$0")/../engine/requirements.txt"
python - <<'PY'
from pathlib import Path
import unidic, unidic_lite
# fugashi prefers unidic if installed. Its PyPI package omits the dictionary.
target = Path(unidic.DICDIR)
if not target.exists():
    target.symlink_to(unidic_lite.DICDIR, target_is_directory=True)
PY
"$(dirname "$0")/download_models.sh"
