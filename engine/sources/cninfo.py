"""巨潮资讯募投公告（L1, 3-9月）。

现行 API：GET /new/fulltextSearch/full（旧 hisAnnounce/query 已 404）。
按工况关键词多次检索，覆盖食品/锂电/橡塑/化工/制药，再由 build 做精细工况分类。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from engine.sources.base import keyword_pool, make_id, today_str

API = "http://www.cninfo.com.cn/new/fulltextSearch/full"

# 建设意图检索词：直接让 API 返回产线/扩产公告（而非靠公司名召回例行公告）。
# 实测 "年产"/"扩建项目" 召回的几乎全是真·Capex 公告，跨行业覆盖各工况。
SEARCH_KEYS = [
    "年产", "扩建项目", "新建生产线", "投资建设",
    "募投项目", "生产基地", "技改项目", "扩产",
    "电池项目", "正极材料", "储能",  # 锂电工况专项
]
PAGES = 2  # 每个检索词翻 2 页（每页约 10 条）

_EM = re.compile(r"</?em>")

# Capex 意图闸：标题须含建设/扩产意图词，否则是例行公告（股东会/决议/获批通知）→ 丢弃。
# 复活制药链 fetch_pharma.py L190 的标题过滤思路，避免靠公司名命中工况造成误报。
CAPEX_INTENT = [
    "新建", "扩建", "扩产", "拟建", "募投", "投资项目", "产线", "生产线",
    "车间", "技改", "产能", "生产基地", "开工", "投产", "建设项目", "智能工厂",
]


def _clean(text: str) -> str:
    return _EM.sub("", text or "").strip()


def _is_capex_signal(title: str) -> bool:
    return any(k in title for k in CAPEX_INTENT)


def fetch(cfg: dict, days: int = 150, per_key: int = 20) -> list[dict]:
    import requests  # 惰性导入
    print("→ 抓取巨潮募投公告（fulltextSearch，多工况）...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://www.cninfo.com.cn/",
    }
    sdate = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    edate = today_str()
    pool = keyword_pool(cfg)

    seen: set[str] = set()
    results = []
    for key in SEARCH_KEYS:
        anns = []
        for page in range(1, PAGES + 1):
            try:
                r = requests.get(
                    API,
                    params={"searchkey": key, "sdate": sdate, "edate": edate, "pageNum": page},
                    headers=headers, timeout=15)
                batch = r.json().get("announcements") or []
            except Exception as e:
                print(f"   [{key} p{page}] 异常: {e}")
                break
            if not batch:
                break
            anns += batch
        for ann in anns[:per_key]:
            ann_id = str(ann.get("announcementId", ""))
            if ann_id in seen:
                continue
            title = _clean(ann.get("announcementTitle", ""))
            company = _clean(ann.get("secName", ""))
            if not _is_capex_signal(title):  # Capex 意图闸：滤掉例行公告
                continue
            blob = f"{company} {title}"
            if not any(k in blob for k in pool):
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
                "source": "巨潮募投公告",
                "source_type": "capex",
                "title": title,  # cninfo 标题已含"公司：..."，不再重复前缀
                "company": company,
                "url": url,
                "date": date,
                "signal_type": "expansion",
                "lead_time_months": "3-9",
            })

    print(f"   巨潮: {len(results)} 条")
    return results
