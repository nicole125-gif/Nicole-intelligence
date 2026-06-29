"""产业新闻流（news, L1 默认）。读已抓好的 RSS 产出，转成事件信号。

与其它源不同：不自己打网络，而是吃 legacy `fetch_rss.py` 已落盘的 `data/rss/<vertical>.json`
（feedparser 抓的 28 个行业垂直源，**条目本身多为微信公众号文章**——url 即 mp.weixin.qq.com）。
这样零重复抓取、离线可跑，且微信只是 RSS 清单里的几条 feed——要加号改 `rss_sources.json` 即可，
引擎侧零改动。源结构对任意 RSS 通吃（含微信中转 feed），不写死行业。

新闻是软信号：按 阀型 OR 工况词 粗过滤（同 tender），其余精分类/丢弃交给 build。
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.sources.base import keyword_pool, make_id, valve_pool

ROOT = Path(__file__).resolve().parents[2]
RSS_DIR = ROOT / "data" / "rss"


def _load_items(rss_dir: Path) -> list[dict]:
    items: list[dict] = []
    if not rss_dir.is_dir():
        return items
    for f in sorted(rss_dir.glob("*.json")):
        if f.stem == "index":
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   RSS[{f.name}] 解析异常: {e}")
            continue
        batch = doc if isinstance(doc, list) else (doc.get("items") or [])
        for it in batch:
            if isinstance(it, dict):
                it["_vertical"] = doc.get("vertical_id") if isinstance(doc, dict) else None
                items.append(it)
    return items


def fetch(cfg: dict, rss_dir: Path = RSS_DIR) -> list[dict]:
    print("→ 读取产业新闻流（RSS / 微信公众号）...")
    pool = keyword_pool(cfg)
    valves = valve_pool(cfg)

    seen: set[str] = set()
    results = []
    for it in _load_items(rss_dir):
        title = (it.get("title") or "").strip()
        if not title:
            continue
        blob = f"{title} {it.get('summary', '')}"
        if not (any(k in blob for k in valves) or any(k in blob for k in pool)):
            continue
        url = it.get("url", "")
        key = it.get("id") or url or title
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "id": make_id(title + (it.get("source") or "")),
            "source": it.get("source") or "产业新闻",  # 微信公众号名 / 媒体名
            "source_type": "news",
            "title": title,
            "summary": it.get("summary", ""),
            "company": "",  # 新闻多不点名业主，交 build 标 unresolved，不臆造
            "url": url,
            "date": (it.get("pub_date") or "")[:10],
            "signal_type": "expansion",
            "lead_time_months": "",  # 留空 → classify 按文本推断（默认 L1）
            "industry_pull": it.get("_vertical"),
        })

    print(f"   产业新闻: {len(results)} 条")
    return results
