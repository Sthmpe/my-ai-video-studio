const b = require('../lib/backend');
module.exports = async (req, res) => {
  try { res.setHeader('Cache-Control', 's-maxage=60'); res.status(200).json(await b.history()); }
  catch (e) { res.status(502).json({ error: String(e.message || e) }); }
};
