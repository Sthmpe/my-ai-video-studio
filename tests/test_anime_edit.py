import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from studio.story import StoryPipeline


def test_original_edit_uses_40_distinct_shots_on_60_second_beat_grid(tmp_path):
    script = json.loads((ROOT / "examples/vale_storm_engine_edit.json").read_text())
    pipeline = StoryPipeline(tmp_path, script)
    timeline = pipeline.stage_voice({})
    shots = pipeline.stage_storyboard(timeline)

    assert timeline["music_bpm"] == 120
    assert timeline["total"] == 60
    assert len(shots) == len({shot["prompt"] for shot in shots}) == 40
    assert [shot["slot"] for shot in shots] == [1.5] * 40
    assert timeline["scenes"][-1]["end"] == 60
    assert all(not scene["lines"] for scene in timeline["scenes"])


def test_edit_rejects_reused_coverage(tmp_path):
    shot = {"prompt": "Warrior in the rain"}
    script = {"mode": "anime_edit", "target_seconds": 3, "scenes": [{"shots": [shot, shot]}]}
    with pytest.raises(ValueError, match="distinct shot prompts"):
        StoryPipeline(tmp_path, script).stage_voice({})
