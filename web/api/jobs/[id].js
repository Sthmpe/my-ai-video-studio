const b = require('../../lib/backend');
module.exports = async (req, res) => {
  try { res.status(200).json(await b.status(req.query.id)); }
  catch (e) { res.status(502).json({ error: String(e.message || e) }); }
};
