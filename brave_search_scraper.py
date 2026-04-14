#!/usr/bin/env python3
"""
Brave Search Scraper for Nicole Intelligence (PULSE 2026) Industry Monitoring Dashboard.
Fetches industry news for 7 verticals using the Brave Search REST API.
"""

import json
import hashlib
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Any

# ── Configuration ────────────────────────────────────────────────────────────
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_API_KEY = "BSAGPv8XrTAHa4WKCRAqvt_ClLagPPi"
PROXY = "http://127.0.0.1:1087"
MAX_ITEMS_PER_VERTICAL = 20
MAX_RESULTS_PER_QUERY   = 10   # Brave returns ≤ 20; request 10 per query
MAX_QUERIES_PER_VERTICAL = 10  # cap queries per vertical

OUTPUT_DIR = "/tmp/nicole-intelligence/data/rss"

HEADERS = {
    "Accept": "application/json",
    "X-Subscription-Token": BRAVE_API_KEY,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# ── Vertical Definitions ──────────────────────────────────────────────────────
VERTICALS = {
    "macro": {
        "vertical_id":   "macro",
        "vertical_name": "宏观经济",
        "vertical_en":   "Macro",
        "color":         "#00d4ff",
        "queries": [
            "中国GDP 2026 经济增长",
            "中国制造业PMI 最新数据",
            "工业增加值 中国 2026",
            "制造业固定资产投资 中国 2026",
            "中国出口增速 2026",
            "PPI指数 中国工业品价格",
            "宏观经济政策 两会 财政刺激",
            "China GDP growth Q1 2026",
            "manufacturing PMI China April 2026",
        ],
    },
    "semiconductor": {
        "vertical_id":   "semiconductor",
        "vertical_name": "半导体",
        "vertical_en":   "Semiconductor",
        "color":         "#ff6b9d",
        "queries": [
            "半导体设备 国产替代 2026",
            "晶圆厂 扩产 中国 2026",
            "光刻机 ASML 中国 进展",
            "芯片制造 先进制程 2026",
            "超纯水 半导体 供应",
            "半导体材料 国产化 最新",
            "semiconductor equipment China 2026",
            "wafer fab expansion China 2026",
            "chip manufacturing breakthrough 2026",
        ],
    },
    "ai_liquid_cooling": {
        "vertical_id":   "ai_liquid_cooling",
        "vertical_name": "AI液冷",
        "vertical_en":   "AI Liquid Cooling",
        "color":         "#7b68ee",
        "queries": [
            "AI液冷 数据中心 散热 2026",
            "CDU 液冷分配单元 智算中心",
            "智算中心 建设 2026 中国",
            "算力基础设施 数据中心 投资",
            "浸没式冷却 液冷技术 进展",
            "AI data center liquid cooling 2026",
            "immersion cooling AI servers 2026",
            "liquid cooling CDU 智算 2026",
        ],
    },
    "hydrogen": {
        "vertical_id":   "hydrogen",
        "vertical_name": "氢能",
        "vertical_en":   "Hydrogen Energy",
        "color":         "#50fa7b",
        "queries": [
            "氢能产业 中国 2026 最新进展",
            "电解槽 绿氢 设备 国产",
            "燃料电池 氢燃料电池汽车 2026",
            "绿氢项目 中国 2026",
            "氢能装备 氢气压缩机 储运",
            "hydrogen energy China 2026",
            "green hydrogen electrolysis 2026",
            "fuel cell hydrogen vehicle 2026",
        ],
    },
    "pharma_equipment": {
        "vertical_id":   "pharma_equipment",
        "vertical_name": "医药设备",
        "vertical_en":   "Pharma Equipment",
        "color":         "#ff8c42",
        "queries": [
            "制药装备 国产替代 2026",
            "生物反应器 制药 设备 2026",
            "冻干机 制药冻干 最新",
            "灌装线 制药 自动化",
            "东富龙 楚天科技 最新动态",
            "pharmaceutical equipment China 2026",
            "bioreactor pharmaceutical manufacturing 2026",
            "pharma machinery lyophilizer 2026",
        ],
    },
    "food_beverage": {
        "vertical_id":   "food_beverage",
        "vertical_name": "食品饮料",
        "vertical_en":   "Food & Beverage",
        "color":         "#ffd166",
        "queries": [
            "食品饮料行业 2026 中国市场",
            "食品安全 检测 技术 2026",
            "食品机械 自动化 设备",
            "饮料生产线 灌装 设备 2026",
            "food beverage industry China 2026",
            "food safety technology 2026",
            "beverage manufacturing automation 2026",
        ],
    },
    "mass_spec": {
        "vertical_id":   "mass_spec",
        "vertical_name": "质谱色谱",
        "vertical_en":   "Mass Spectrometry & Chromatography",
        "color":         "#06d6a0",
        "queries": [
            "质谱仪 国产 进展 2026",
            "色谱仪 分析仪器 设备",
            "质谱色谱 联用技术 进展",
            "分析仪器 行业 市场 2026",
            "mass spectrometry instrument China 2026",
            "chromatography analytical instrument 2026",
            "mass spec chromatography analysis 2026",
        ],
    },
}

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("brave_search_scraper")


# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(text: str) -> str:
    """10-char deterministic hash from a string."""
    return hashlib.md5(text.encode()).hexdigest()[:10]


def parse_relative_date(page_age: str | None) -> tuple[str, int]:
    """
    Convert Brave's page_age string (e.g. '3 days ago', '2 weeks ago')
    to ISO datetime and Unix timestamp.
    Falls back to now() if unparseable.
    """
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp())
    iso = now.isoformat()

    if not page_age:
        return iso, ts

    page_age_lower = page_age.lower().strip()

    # Try "N <unit> ago"
    import re
    m = re.match(r"(\d+)\s*(hour|day|week|month|year)s?\s+ago", page_age_lower)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta_kwargs = {"hours": n} if unit == "hour" else {
            "days": n} if unit == "day" else {
            "weeks": n} if unit == "week" else {
            "days": n * 30} if unit == "month" else {"days": n * 365}
        then = now.replace(microsecond=0) - __import__("datetime").timedelta(**delta_kwargs)
        return then.isoformat(), int(then.timestamp())

    return iso, ts


def fetch_brave_search(query: str, count: int = MAX_RESULTS_PER_QUERY,
                        freshness: str | None = None) -> list[dict]:
    """
    Call Brave Search REST API and return list of web results.
    Returns empty list on failure.
    """
    params: dict[str, Any] = {
        "q": query,
        "count": count,
    }
    if freshness:
        params["freshness"] = freshness

    try:
        resp = requests.get(
            BRAVE_API_URL,
            headers=HEADERS,
            params=params,
            proxies={"http": PROXY, "https": PROXY},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("  ✗ API error for query %r: %s", query, exc)
        return []

    try:
        data = resp.json()
    except ValueError as exc:
        log.warning("  ✗ JSON parse error for query %r: %s", query, exc)
        return []

    results = data.get("web", {}).get("results", [])
    return results


def extract_source(meta_url: dict | None) -> str:
    """Extract a readable source/domain name from Brave's meta_url field."""
    if not meta_url:
        return "Unknown"
    site = meta_url.get("netloc") or meta_url.get("hostname") or ""
    # Strip leading www.
    return site.lstrip("www.").split("/")[0] or "Unknown"


def brave_result_to_item(result: dict) -> dict:
    """Convert a single Brave search result dict to a dashboard item."""
    url = result.get("url", "")
    title = result.get("title", "")
    description = result.get("description", "")
    page_age = result.get("page_age")
    lang = result.get("language", "zh") or "zh"
    source = extract_source(result.get("meta_url"))

    # Truncate summary to 300 chars
    summary = (description or title)[:300].strip()

    iso_date, ts = parse_relative_date(page_age)

    return {
        "id": make_id(url or title),
        "title": title,
        "url": url,
        "summary": summary,
        "source": source,
        "lang": lang[:2].lower(),
        "pub_date": iso_date,
        "pub_ts": ts,
    }


def process_vertical(vid: str, vcfg: dict) -> dict:
    """Run all queries for one vertical and return the output dict."""
    log.info("─── Vertical: %s (%s) ───", vid, vcfg["vertical_en"])

    queries = vcfg["queries"][:MAX_QUERIES_PER_VERTICAL]
    seen_urls: set[str] = set()
    all_items: list[dict] = []

    for i, query in enumerate(queries, 1):
        log.info("  [%d/%d] Query: %r", i, len(queries), query)
        results = fetch_brave_search(query, count=MAX_RESULTS_PER_QUERY,
                                      freshness="pm")   # past month
        if not results:
            time.sleep(0.5)
            # Try without freshness filter as fallback
            results = fetch_brave_search(query, count=MAX_RESULTS_PER_QUERY)
            if not results:
                log.warning("    No results for: %s", query)
                time.sleep(1)
                continue

        for result in results:
            url = result.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            item = brave_result_to_item(result)
            all_items.append(item)
            log.info("    + %s  [%s]", item["title"][:60], item["source"])

        time.sleep(0.8)   # polite rate-limiting

    # Sort by pub_ts descending, keep top MAX_ITEMS_PER_VERTICAL
    all_items.sort(key=lambda x: x["pub_ts"], reverse=True)
    all_items = all_items[:MAX_ITEMS_PER_VERTICAL]

    log.info("  → %d unique items collected (max %d)", len(all_items), MAX_ITEMS_PER_VERTICAL)

    return {
        "vertical_id":   vid,
        "vertical_name": vcfg["vertical_name"],
        "vertical_en":   vcfg["vertical_en"],
        "color":         vcfg["color"],
        "updated_at":    safe_now_iso(),
        "item_count":    len(all_items),
        "items":         all_items,
    }


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_index(verticals_output: dict[str, dict]) -> dict:
    """Build the index.json structure from per-vertical output dicts."""
    verticals_meta = {}
    for vid, vdata in verticals_output.items():
        verticals_meta[vid] = {
            "name":       vdata["vertical_name"],
            "item_count": vdata["item_count"],
            "updated_at": vdata["updated_at"],
        }
    return {
        "generated_at": safe_now_iso(),
        "verticals":    verticals_meta,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=" * 60)
    log.info("Nicole Intelligence – Brave Search Scraper (PULSE 2026)")
    log.info("=" * 60)

    verticals_output: dict[str, dict] = {}

    for vid, vcfg in VERTICALS.items():
        try:
            vdata = process_vertical(vid, vcfg)
            verticals_output[vid] = vdata

            # Write individual vertical JSON
            out_path = f"{OUTPUT_DIR}/{vid}.json"
            write_json(out_path, vdata)
            log.info("  ✓ Written: %s", out_path)

        except Exception as exc:
            log.error("  ✗ Fatal error for vertical %s: %s", vid, exc, exc_info=True)
            # Write an empty valid file so dashboard doesn't break
            empty = {
                "vertical_id":   vid,
                "vertical_name": vcfg["vertical_name"],
                "vertical_en":   vcfg["vertical_en"],
                "color":         vcfg["color"],
                "updated_at":    safe_now_iso(),
                "item_count":    0,
                "items":         [],
            }
            write_json(f"{OUTPUT_DIR}/{vid}.json", empty)
            verticals_output[vid] = empty

        time.sleep(2)   # pause between verticals

    # Write index.json
    index = build_index(verticals_output)
    write_json(f"{OUTPUT_DIR}/index.json", index)
    log.info("✓ Written: %s/index.json", OUTPUT_DIR)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FETCH SUMMARY")
    print("=" * 60)
    total = 0
    for vid, vdata in verticals_output.items():
        count = vdata["item_count"]
        total += count
        bar = "█" * min(count, 20)
        print(f"  {vid:<22} {count:>3} items  {bar}")
    print("-" * 60)
    print(f"  {'TOTAL':<22} {total:>3} items")
    print("=" * 60)

    issues = []
    for vid, vdata in verticals_output.items():
        if vdata["item_count"] == 0:
            issues.append(f"  ⚠  {vid}: 0 items (check API key / proxy)")
    if issues:
        print("\nISSUES:")
        print("\n".join(issues))
    else:
        print("\n✓ All verticals returned data successfully.")

    log.info("Done. Output in %s/", OUTPUT_DIR)


if __name__ == "__main__":
    main()
