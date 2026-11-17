const b = require('../lib/backend');
module.exports = (req, res) => res.status(200).json({ ok: true, backend: b.mode(), submitEnabled: !!process.env.SUBMIT_PASSCODE });
