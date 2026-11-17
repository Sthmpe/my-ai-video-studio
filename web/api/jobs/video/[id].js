const b = require('../../../lib/backend');
// Proxies the MP4 from an always-on engine (the API key never reaches the browser).
module.exports = async (req, res) => {
  const r = await b.video(req.query.id);
  if (!r.ok) return res.status(r.status).json({ error: 'video not ready' });
  res.setHeader('Content-Type', 'video/mp4');
  res.send(Buffer.from(await r.arrayBuffer()));
};
