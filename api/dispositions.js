import { kv } from '@vercel/kv';

const STATES = ['跟进中', '赢', '输', '忽略', '无效'];
const NEED_REASON = new Set(['输', '无效']);

export default async function handler(req, res) {
  try {
    if (req.method === 'GET') {
      const keys = await kv.keys('disp:*');
      if (!keys.length) return res.status(200).json({});
      const vals = await kv.mget(...keys);
      const out = {};
      keys.forEach((k, i) => { if (vals[i]) out[k.slice(5)] = vals[i]; });
      return res.status(200).json(out);
    }

    if (req.method === 'POST') {
      const b = req.body || {};
      const event_id = (b.event_id || '').toString().trim();
      const status = (b.status || '').toString().trim();
      const reason = (b.reason || '').toString().trim();
      if (!event_id || !status) return res.status(400).json({ error: 'event_id 和 status 必填' });
      if (!STATES.includes(status)) return res.status(400).json({ error: '非法 status' });
      if (NEED_REASON.has(status) && !reason) return res.status(400).json({ error: '输/无效 必填原因' });

      const rec = {
        event_id,
        date: (b.date || '').toString(),
        headline: (b.headline || '').toString(),
        status,
        reason,
        owner: (b.owner || '').toString().trim(),
        updated_at: new Date().toISOString(),
      };
      await kv.set('disp:' + event_id, rec);
      return res.status(200).json(rec);
    }

    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'method not allowed' });
  } catch (e) {
    return res.status(500).json({ error: String((e && e.message) || e) });
  }
}
