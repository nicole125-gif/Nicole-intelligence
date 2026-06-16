"""政府采购招标（L0, 0-2月，即时最强信号）。骨架移植自 fetch_pharma.py L278-325。

泛化点：制药关键词 → 全工况关键词；保留"阀门词 OR 工况词"双命中逻辑。
"""

from __future__ import annotations

from engine.sources.base import keyword_pool, make_id, safe_get, today_str, valve_pool

URL = "https://www.ccgp.gov.cn/cggg/zygg/zbgg/index.shtml"


def fetch(cfg: dict, limit: int = 40) -> list[dict]:
    from bs4 import BeautifulSoup  # 惰性导入
    print("→ 抓取政府采购招标...")
    r = safe_get(URL)
    results = []
    if not r:
        print("   招标: 0 条（抓取失败）")
        return results

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select(".vT-srch-result-list-bid li, .list-content li")
    valves = valve_pool(cfg)
    conditions = keyword_pool(cfg)

    for item in items:
        a = item.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        has_valve = any(k in title for k in valves)
        has_condition = any(k in title for k in conditions)
        if not (has_valve or has_condition):
            continue
        span = item.find("span")
        date = span.get_text(strip=True) if span else today_str()
        results.append({
            "id": make_id(title),
            "source": "政府采购招标",
            "source_type": "tender",
            "title": title,
            "url": href if href.startswith("http") else "https://www.ccgp.gov.cn" + href,
            "date": date,
            "signal_type": "immediate",
            "lead_time_months": "0-2",
            # 同时命中阀门词+工况词 → 极强信号，提示 build 给满分倾向
            "_valve_and_condition": has_valve and has_condition,
        })
        if len(results) >= limit:
            break

    print(f"   招标: {len(results)} 条")
    return results
