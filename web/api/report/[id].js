const b = require('../../lib/backend');
// GET /api/report/<job id>  -> simplified generation report for a finished job
module.exports = async (req, res) => {
  try {
    const id = String(req.query.id || '');
    if (!/^[a-z0-9-]{3,80}$/.test(id)) return res.status(422).json({ error: 'bad id' });
    const url = req.query.src && /^https:\/\/(github\.com|raw\.githubusercontent\.com)\//.test(req.query.src)
      ? req.query.src : `https://github.com/${process.env.GH_REPO || 'Sthmpe/my-ai-video-studio'}/releases/download/claude-video-${id}/generation_report.json`;
    res.status(200).json(await b.reportSummary(url));
  } catch (e) { res.status(404).json({ error: String(e.message || e) }); }
};
