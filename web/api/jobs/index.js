const b = require('../../lib/backend');
// POST /api/jobs {topic|script, orientation}  header: x-passcode (== SUBMIT_PASSCODE)
module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  if (b.mode() === 'none') return res.status(503).json({ error: 'No generation backend configured (set ENGINE_URL or GITHUB_TOKEN).' });
  if (!process.env.SUBMIT_PASSCODE || req.headers['x-passcode'] !== process.env.SUBMIT_PASSCODE)
    return res.status(401).json({ error: 'Submitting jobs needs the owner passcode (compute is not free to abuse).' });
  const { topic = '', script = null, orientation = 'vertical' } = req.body || {};
  if (!topic && !script) return res.status(422).json({ error: 'topic or script required' });
  if (String(topic).length > 300) return res.status(422).json({ error: 'topic too long' });
  try { res.status(202).json({ id: await b.submit({ topic, script, orientation }), backend: b.mode() }); }
  catch (e) { res.status(502).json({ error: String(e.message || e) }); }
};
