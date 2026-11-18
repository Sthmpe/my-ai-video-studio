// Backend adapter. Two interchangeable engines, chosen by env vars:
//  1) ENGINE_URL + STUDIO_API_KEY  -> an always-on engine (engine/studio/server.py) reachable over HTTPS
//  2) GITHUB_TOKEN (+ GH_REPO)     -> GitHub Actions as a free on-demand worker (.github/workflows/claude-generate.yml)
const GH = process.env.GH_REPO || 'Sthmpe/my-ai-video-studio';
const gh = (path, init = {}) => fetch(`https://api.github.com${path}`, {
  ...init, headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'my-ai-video-studio-web',
    Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, 'X-GitHub-Api-Version': '2022-11-28', ...(init.headers || {}) } });
const engine = (path, init = {}) => fetch(process.env.ENGINE_URL.replace(/\/$/, '') + path, {
  ...init, headers: { Authorization: `Bearer ${process.env.STUDIO_API_KEY}`, 'Content-Type': 'application/json', ...(init.headers || {}) } });

exports.mode = () => (process.env.ENGINE_URL ? 'engine' : process.env.GITHUB_TOKEN ? 'github' : 'none');

exports.submit = async ({ topic, script, mode, aspect, seconds, language, continueFrom }) => {
  if (exports.mode() === 'engine') {
    const r = await engine('/jobs', { method: 'POST', body: JSON.stringify({ topic, script, mode, aspect, seconds, language, continue_from: continueFrom }) });
    if (!r.ok) throw new Error(`engine ${r.status}`);
    return (await r.json()).id;
  }
  const id = `claude-web-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const r = await gh(`/repos/${GH}/actions/workflows/claude-generate.yml/dispatches`, { method: 'POST',
    body: JSON.stringify({ ref: process.env.GH_REF || (await (await gh(`/repos/${GH}`)).json()).default_branch, inputs: { job_id: id, topic: topic || '',
      script_json: script ? JSON.stringify(script) : '', mode: mode || 'documentary', aspect: aspect || '9:16',
      seconds: String(seconds || 45), language: language || 'en', continue_from: continueFrom || '' } }) });
  if (r.status !== 204) throw new Error(`github dispatch ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return id;
};

exports.status = async (id) => {
  if (exports.mode() === 'engine') {
    const r = await engine(`/jobs/${encodeURIComponent(id)}`);
    if (r.status === 404) return { status: 'unknown' };
    const j = await r.json();
    return { status: j.status, stage: j.stage, done: j.done, total: j.total, message: j.message,
      videoUrl: j.video_ready ? `/api/jobs/video/${id}` : null, error: j.error };
  }
  const runs = await (await gh(`/repos/${GH}/actions/workflows/claude-generate.yml/runs?event=workflow_dispatch&per_page=30`)).json();
  const run = (runs.workflow_runs || []).find((x) => x.display_title === `claude-studio ${id}`);
  if (!run) return { status: 'queued', message: 'waiting for a runner' };
  const rel = await gh(`/repos/${GH}/releases/tags/claude-video-${encodeURIComponent(id)}`);
  if (rel.ok) {
    const assets = (await rel.json()).assets;
    const url = (pred) => (assets.find(pred) || {}).browser_download_url || null;
    const v = url((x) => x.name === 'output.mp4');
    if (v) return { status: 'done', videoUrl: v, runUrl: run.html_url,
      bundleUrl: url((x) => x.name.endsWith('.studio.zip')), reportUrl: url((x) => x.name === 'GENERATION_REPORT.md'),
      reportJsonUrl: url((x) => x.name === 'generation_report.json'), metadataUrl: url((x) => x.name === 'script.json'),
      jaUrl: url((x) => x.name === 'output_ja.mp4') };
  }
  const map = { queued: 'queued', in_progress: 'running', completed: run.conclusion === 'success' ? 'done' : 'failed' };
  return { status: map[run.status] || run.status, message: `GitHub run ${run.status}`, runUrl: run.html_url };
};

exports.video = async (id) => engine(`/jobs/${encodeURIComponent(id)}/video`);

// Recent finished jobs (GitHub mode): releases tagged claude-video-*
exports.history = async () => {
  if (exports.mode() !== 'github' && !process.env.GH_PUBLIC_READ) return [];
  const r = await fetch(`https://api.github.com/repos/${GH}/releases?per_page=20`, { headers: { Accept: 'application/vnd.github+json',
    'User-Agent': 'my-ai-video-studio-web', ...(process.env.GITHUB_TOKEN ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}) } });
  if (!r.ok) return [];
  return (await r.json()).filter((x) => x.tag_name.startsWith('claude-video-')).map((x) => ({
    id: x.tag_name.replace('claude-video-', ''), created: x.published_at,
    video: (x.assets.find((a) => a.name === 'output.mp4') || {}).browser_download_url,
    bundle: (x.assets.find((a) => a.name.endsWith('.studio.zip')) || {}).browser_download_url,
    report: (x.assets.find((a) => a.name === 'GENERATION_REPORT.md') || {}).browser_download_url }));
};

// Simplified generation report (server-side fetch avoids browser CORS on release assets)
exports.reportSummary = async (url) => {
  const r = await fetch(url, { redirect: 'follow' });
  if (!r.ok) throw new Error(`report ${r.status}`);
  const g = await r.json();
  return { title: g.title, mode: g.mode, models: { video: g.models.video_motion.id, image: g.models.image_base.id,
    voice: g.models.voice.id, characterConditioning: g.models.character_conditioning && g.models.character_conditioning.id },
    method: g.generation_method, native: g.specs.native_resolution, export: g.specs.export_resolution,
    shots: g.specs.shots, secondsPerShot: g.specs.seconds_per_shot_mean, cost: g.cost.usd,
    reasons: g.selection_reasons, limitations: g.limitations };
};
