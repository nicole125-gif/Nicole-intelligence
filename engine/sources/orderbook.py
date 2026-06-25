"""装备商订单簿监测（P1#4，L1 3-9月）。

盯战略 OEM（楚天/东富龙/森松/奥星/正帆）的 新签/在手/中标/海外/扩产 披露——
OEM 自身有单 = ESG 顺风（尤其东富龙已 spec 进 BOM）。复用巨潮 fulltext，按 OEM 名检索，
过滤订单簿意图词；OEM 名单从 entities.yml（type=oem）取，单一来源。

build_event 对「业主即在册 OEM」放行无工况信号，并用 OEM 的 O4 档案兜底阀型/行业。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from engine import entities
from engine.sources.base import make_id, today_str

API = "http://www.cninfo.com.cn/new/fulltextSearch/full"
_EM = re.compile(r"</?em>")

# 订单簿意图：标题须含其一，否则是例行公告（人事/分红/股东会）→ 丢弃。
ORDERBOOK_INTENT = [
    "新签", "在手订单", "中标", "签订", "订单", "海外", "出口", "出海",
    "扩产", "扩建", "投资", "产能", "生产基地", "新建", "产线", "大额",
]


def _clean(text: str) -> str:
    return _EM.sub("", text or "").strip()


def fetch(cfg: dict, registry: dict | None = None, days: int = 180, per_oem: int = 8) -> list[dict]:
    import requests  # 惰性导入
    reg = registry or entities.load_registry()
    oems = [(e["name"], e.get("aliases", []))
            for e in reg["by_id"].values() if e.get("type") == "oem"]
    print(f"→ 抓取装备商订单簿（{len(oems)} 家 OEM）...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://www.cninfo.com.cn/",
    }
    sdate = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    edate = today_str()

    seen: set[str] = set()
    results = []
    for name, aliases in oems:
        try:
            r = requests.get(
                API,
                params={"searchkey": name, "sdate": sdate, "edate": edate, "pageNum": 1},
                headers=headers, timeout=15)
            anns = r.json().get("announcements") or []
        except Exception as e:
            print(f"   [{name}] 异常: {e}")
            continue
        for ann in anns[:per_oem]:
            ann_id = str(ann.get("announcementId", ""))
            if ann_id in seen:
                continue
            title = _clean(ann.get("announcementTitle", ""))
            company = _clean(ann.get("secName", ""))
            if not any(k in title for k in ORDERBOOK_INTENT):
                continue
            # 确认确是该 OEM（secName 命中名/别名），避免同名/模糊召回
            if not any(a in company for a in [name, *aliases]):
                continue
            seen.add(ann_id)
            ts = ann.get("announcementTime")
            if isinstance(ts, (int, float)):
                date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            else:
                date = str(ts)[:10]
            adjunct = ann.get("adjunctUrl", "")
            url = ("http://static.cninfo.com.cn/" + adjunct) if adjunct else (
                "http://www.cninfo.com.cn/new/announcement/detail?announceId=" + ann_id)
            results.append({
                "id": make_id(title + company),
                "source": "装备商订单簿",
                "source_type": "capex",
                "title": f"{company}：{title}",
                "company": company,
                "url": url,
                "date": date,
                "signal_type": "expansion",
                "lead_time_months": "3-9",
            })

    print(f"   订单簿: {len(results)} 条")
    return results
