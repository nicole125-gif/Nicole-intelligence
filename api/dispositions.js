import { Redis } from '@upstash/redis';

// @vercel/kv 已废弃，改用 @upstash/redis；两套变量名都读（Vercel 控制台建 Redis/KV
// 注入的可能是 KV_REST_API_* 或 UPSTASH_REDIS_REST_*），上线不必猜控制台给哪套。
const kv = new Redis({
  url: process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL,
  token: process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN,
});

const STATES = ['跟进中', '赢', '输', '忽略', '无效'];
const NEED_REASON = new Set(['输', '无效']);

export default async function handler(req, res) {
  try {
    if (!process.env.KV_REST_API_URL && !process.env.UPSTASH_REDIS_REST_URL) {
      return res.status(500).json({ error: 'KV 未配置：缺 KV_REST_API_URL/UPSTASH_REDIS_REST_URL（去 Vercel 建 Redis store 并连到项目）' });
    }
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
