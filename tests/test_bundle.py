import json, sys, zipfile
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from studio import bundle, sfx, modes


def make_job(tmp):
    j = tmp / "job"; (j / "characters" / "kai").mkdir(parents=True); (j / "clips").mkdir()
    (j / "script.json").write_text(json.dumps({"title": "Test Ep", "project_id": "p1", "scenes": []}))
    (j / "characters" / "kai.json").write_text(json.dumps({"id": "kai"}))
    (j / "characters" / "kai" / "ref_0.png").write_bytes(b"\x89PNGfake")
    (j / "clips" / "shot_000.mp4").write_bytes(b"mp4data")
    (j / "output.mp4").write_bytes(b"final")
    return j


def test_roundtrip_and_checksums(tmp_path):
    z = bundle.export_bundle(make_job(tmp_path))
    m = bundle.import_bundle(z, tmp_path / "imp")
    assert m["schema"] == bundle.SCHEMA and m["title"] == "Test Ep"
    assert (tmp_path / "imp" / "characters" / "kai" / "ref_0.png").read_bytes() == b"\x89PNGfake"
    assert (tmp_path / "imp" / "output.mp4").read_bytes() == b"final"
    assert all(len(f["sha256"]) == 64 for f in m["files"])


def test_tampered_file_rejected(tmp_path):
    z = bundle.export_bundle(make_job(tmp_path))
    bad = tmp_path / "bad.studio.zip"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(bad, "w") as dst:
        for i in src.infolist():
            data = src.read(i.filename)
            dst.writestr(i, b"evil" if i.filename == "final/output.mp4" else data)
    with pytest.raises(bundle.BundleError, match="checksum"):
        bundle.import_bundle(bad, tmp_path / "x")


@pytest.mark.parametrize("name", ["../escape.txt", "/abs.txt", "a/../../b.txt", "C:/win.txt", "a\\..\\b"])
def test_zip_slip_rejected(tmp_path, name):
    bad = tmp_path / "slip.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("manifest.json", json.dumps({"schema": bundle.SCHEMA, "files": []}))
        z.writestr(name, "x")
    with pytest.raises(bundle.BundleError):
        bundle.import_bundle(bad, tmp_path / "y")


def test_unknown_schema_and_unlisted_files_rejected(tmp_path):
    bad = tmp_path / "s.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("manifest.json", json.dumps({"schema": "studio-bundle/9", "files": []}))
    with pytest.raises(bundle.BundleError, match="schema"):
        bundle.import_bundle(bad, tmp_path / "a")
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("manifest.json", json.dumps({"schema": bundle.SCHEMA, "files": []}))
        z.writestr("story/script.json", "{}")
    with pytest.raises(bundle.BundleError, match="not in manifest"):
        bundle.import_bundle(bad, tmp_path / "b")


def test_sfx_track_places_events(tmp_path):
    import soundfile as sf, numpy as np
    out = sfx.render_track([{"t": 1.0, "name": "impact"}], [{"start": 0, "end": 3, "name": "rain"}], 3.0, tmp_path / "f.wav")
    a, sr = sf.read(str(out))
    assert abs(len(a) / sr - 3.0) < 0.01
    assert np.abs(a[int(1.0 * sr):int(1.3 * sr)]).max() > 5 * np.abs(a[int(0.3 * sr):int(0.6 * sr)]).max()


def test_mode_router_explains_choice():
    sel = modes.select("anime_action", "1:1")
    assert sel["export"] == (1080, 1080) and sel["method"] == "i2v" and len(sel["reasons"]) >= 3
    assert modes.select("documentary")["method"] == "t2v"
