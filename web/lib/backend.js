// Backend adapter. Two interchangeable engines, chosen by env vars:
//  1) ENGINE_URL + STUDIO_API_KEY  -> an always-on engine (engine/studio/server.py) reachable over HTTPS
//  2) GITHUB_TOKEN (+ GH_REPO)     -> GitHub Actions as a free on-demand worker (.github/workflows/generate.yml)
const GH = process.env.GH_REPO || 'Sthmpe/my-ai-video-studio';
const gh = (path, init = {}) => fetch(`https://api.github.com${path}`, {
  ...init, headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'my-ai-video-studio-web',
    Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, 'X-GitHub-Api-Version': '2022-11-28', ...(init.headers || {}) } });
const engine = (path, init = {}) => fetch(process.env.ENGINE_URL.replace(/\/$/, '') + path, {
  ...init, headers: { Authorization: `Bearer ${process.env.STUDIO_API_KEY}`, 'Content-Type': 'application/json', ...(init.headers || {}) } });

exports.mode = () => (process.env.ENGINE_URL ? 'engine' : process.env.GITHUB_TOKEN ? 'github' : 'none');

exports.submit = async ({ topic, script, orientation }) => {
  if (exports.mode() === 'engine') {
    const r = await engine('/jobs', { method: 'POST', body: JSON.stringify({ topic, script, orientation }) });
    if (!r.ok) throw new Error(`engine ${r.status}`);
    return (await r.json()).id;
  }
  const id = `web-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const r = await gh(`/repos/${GH}/actions/workflows/generate.yml/dispatches`, { method: 'POST',
    body: JSON.stringify({ ref: process.env.GH_REF || (await (await gh(`/repos/${GH}`)).json()).default_branch, inputs: { job_id: id, topic: topic || '',
      script_json: script ? JSON.stringify(script) : '', orientation: orientation || 'vertical' } }) });
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
  const runs = await (await gh(`/repos/${GH}/actions/workflows/generate.yml/runs?event=workflow_dispatch&per_page=30`)).json();
  const run = (runs.workflow_runs || []).find((x) => x.display_title === `studio ${id}`);
  if (!run) return { status: 'queued', message: 'waiting for a runner' };
  const rel = await gh(`/repos/${GH}/releases/tags/video-${encodeURIComponent(id)}`);
  if (rel.ok) {
    const a = (await rel.json()).assets.find((x) => x.name === 'output.mp4');
    if (a) return { status: 'done', videoUrl: a.browser_download_url, runUrl: run.html_url };
  }
  const map = { queued: 'queued', in_progress: 'running', completed: run.conclusion === 'success' ? 'done' : 'failed' };
  return { status: map[run.status] || run.status, message: `GitHub run ${run.status}`, runUrl: run.html_url };
};

exports.video = async (id) => engine(`/jobs/${encodeURIComponent(id)}/video`);
