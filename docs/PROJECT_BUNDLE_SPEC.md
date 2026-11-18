# `.studio.zip` project bundle — schema v1

A portable, versioned archive of one production. Created by `studio.bundle.export_bundle(job_dir)`; imported by `studio.bundle.import_bundle(zip)`.

```
manifest.json            schema "studio-bundle/1", project id, title, created, engine commit, file list + sha256 + sizes + roles
story/script.json        title, logline, mode, scenes[narration|dialogue lines, shots[prompt, camera, sfx]]
story/timeline.json      measured speech timing per scene
story/storyboard.json    shot list with slots, prompts, camera motion, seeds
characters/<id>.json     character record (see ANIME_SERIES_SPEC.md) + characters/<id>/ref_*.png
series/series.json       series id, episode number, previous episodes, continuity notes (optional)
clips/shot_NNN.mp4       raw generated clips (native resolution)   keyframes/shot_NNN.png  first frame of each shot
audio/*.wav              narration/dialogue, music, sfx, mix
subtitles/subs.ass, subtitles/subs.srt
reports/report.json      validation;  reports/clip_reports.json  per-shot gates
GENERATION_REPORT.md, generation_report.json   model transparency report
final/output.mp4         the rendered video
LICENSES.md              asset licences & attribution
```

Integrity & safety
* Every file listed in `manifest.files` with `sha256`; import verifies all hashes and refuses mismatches.
* Import rejects absolute paths, `..` components, symlinks and entries outside the manifest; total size and file count are capped.
* Schema version is checked; unknown major versions are refused.

Reproducibility limits: same weights + seeds + settings reproduce clips closely on the same backend, but bf16 vs fp32, CPU vs GPU and library versions change pixels. The bundle stores model ids, file hashes of weights where known, dtype and library versions to make this auditable.
