"""环评公示（L2, 12-18月，覆盖非上市企业）。骨架移植自 fetch_pharma.py L224-271。

泛化点：industryName 从单一"医药制造业"改为遍历多个 ESG 相关行业。
"""

from __future__ import annotations

from engine.sources.base import keyword_pool, make_id, safe_get, today_str

API = "https://eia.mee.gov.cn/db_pa_pub/getItemInfoList.vm"

# 遍历 ESG 工况覆盖的环评行业分类
INDUSTRIES = [
    "食品制造业",
    "酒、饮料和精制茶制造业",
    "橡胶和塑料制品业",
    "电池制造",
    "医药制造业",
    "化学原料和化学制品制造业",
]


def fetch(cfg: dict, page_size: int = 20, limit_per_industry: int = 15) -> list[dict]:
    print("→ 抓取环评公示（多行业）...")
    pool = keyword_pool(cfg)
    results = []
    for industry in INDUSTRIES:
        params = {
            "industryName": industry,
            "pageNum": 1,
            "pageSize": page_size,
            "areaCode": "",
            "status": "受理",
        }
        r = safe_get(API, params=params)
        if not r:
            continue
        try:
            items = r.json().get("data", {}).get("list", []) or []
        except Exception as e:
            print(f"   环评[{industry}]解析异常: {e}")
            continue
        kept = 0
        for item in items:
            name = item.get("projectName", "")
            company = item.get("constructionUnit", "")
            blob = f"{name} {company}"
            if not any(k in blob for k in pool):
                continue
            province = item.get("province", "")
            results.append({
                "id": make_id(name + company),
                "source": "环评公示",
                "source_type": "project_filing",
                "title": f"【{province}】{name}" if province else name,
                "company": company,
                "url": item.get("url", "") or "https://eia.mee.gov.cn/",
                "date": item.get("publishDate", today_str()),
                "signal_type": "expansion",
                "lead_time_months": "12-18",
                "industry_pull": industry,
            })
            kept += 1
            if kept >= limit_per_industry:
                break
    print(f"   环评: {len(results)} 条")
    return results
