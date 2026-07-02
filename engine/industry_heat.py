"""L2 派生行业热度信号（ROADMAP A1 的地基）。

把引擎事件（data/events）按 industry_tag 聚合成"自下而上、来自真实事件"的热度信号，
为热力图 heat 提供可自动刷新的源——**终局是 heat 从这里长出来，不再靠人工重抓**。

⚠ 现状纪律：源稀疏，多数行业 0 事件 → L2 信号目前是 rubric heat 的**并行印证层**
（不替换）。覆盖成熟后再按 blend 权重逐步接管（见 docs/heat-scoring-rubric.md §7）。

纯函数 `build_industry_heat(pack, pack_date)` 便于单测；IO（找最新 pack、写文件）在
scripts/build_industry_heat.py。
"""

from __future__ import annotations

import datetime as dt

# 价值档 → 单事件基础分（与 valuation.value_band 的档对齐；大项目=更强 capex 信号）
BAND_PTS = {"大": 10, "中": 6, "小": 3, "未知": 2}


def recency_mult(ev_date: str | None, pack_date: dt.date) -> float:
    """新鲜度衰减：越近的事件对"当前热度"贡献越大（heat 是趋势不是存量）。"""
    try:
        d = dt.date.fromisoformat((ev_date or "")[:10])
    except (ValueError, TypeError):
        return 0.6
    days = (pack_date - d).days
    if days <= 30:
        return 1.0
    if days <= 90:
        return 0.6
    return 0.3


def build_industry_heat(pack: dict, pack_date: dt.date) -> dict:
    """把一份 events pack 聚合成 {industry_tag: 指标}。

    l2_signal = Σ(价值档基础分 × 新鲜度)，封顶 100——可读为"近期加权 capex 事件强度"。
    稀疏时自然偏低（=诚实：该行业 L2 证据还少），不与 rubric heat 强行等价。
    """
    agg: dict[str, dict] = {}
    for e in pack.get("events", []):
        tag = e.get("industry_tag") or "其他"
        g = agg.setdefault(tag, {
            "industry_tag": tag, "event_count": 0, "_owners": set(),
            "_raw": 0.0, "band_dist": {}, "lead_dist": {},
            "freshest": None, "event_ids": [],
        })
        g["event_count"] += 1
        oid = (e.get("owner") or {}).get("id")
        if oid:
            g["_owners"].add(oid)
        band = (e.get("value_band") or {}).get("band", "未知")
        g["band_dist"][band] = g["band_dist"].get(band, 0) + 1
        lv = (e.get("lead_time") or {}).get("level", "L1")
        g["lead_dist"][lv] = g["lead_dist"].get(lv, 0) + 1
        ev_date = (e.get("source") or {}).get("published_at") or pack.get("date")
        g["_raw"] += BAND_PTS.get(band, 2) * recency_mult(ev_date, pack_date)
        dd = (ev_date or "")[:10]
        if dd and (g["freshest"] is None or dd > g["freshest"]):
            g["freshest"] = dd
        g["event_ids"].append(e.get("id"))

    out: dict[str, dict] = {}
    for tag, g in agg.items():
        out[tag] = {
            "industry_tag": tag,
            "event_count": g["event_count"],
            "account_count": len(g["_owners"]),
            "l2_signal": min(100, round(g["_raw"])),
            "band_dist": g["band_dist"],
            "lead_dist": g["lead_dist"],
            "freshest": g["freshest"],
            "event_ids": g["event_ids"][:20],
        }
    return out
