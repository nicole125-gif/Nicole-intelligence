"""
update_news.py  —  PULSE 2026 每周自动更新脚本
功能：
  1. 抓取 Google News RSS → 对 20 个子赛道打分（D/C/P/Pol + heat）
  2. 计算 6 个板块综合分
  3. 保存历史到 data/history.json
  4. 注入 index.html（调用 inject_scores.py）
  5. 抓取制药装备行业动态 → 注入 pharma.html
"""

import os
import re
import json
import hashlib
import datetime
import argparse
import urllib.parse
from collections import defaultdict
from pathlib import Path
import anthropic

# ── 打分缓存 ──────────────────────────────────────────────────
SCORE_CACHE_FILE = "data/score_cache.json"
WEEKLY_DIR = Path("data/weekly")
WATCHLIST_PATH = Path("data/watchlist.json")
RSS_DIR = Path("data/rss")

MACRO_TRACK_IDS = {"m1", "m2", "m3"}
OFFICIAL_DOMAINS = (
    "stats.gov.cn", "pbc.gov.cn", "sse.com.cn", "szse.cn",
    "hkexnews.hk", "gov.cn", "ndrc.gov.cn", "miit.gov.cn",
)
STRONG_EVIDENCE_KEYWORDS = (
    "公告", "财报", "年报", "季报", "业绩", "招标", "中标", "订单",
    "扩产", "产能", "投资", "融资", "募资", "立项", "开工", "获批",
    "PMI", "M2", "社融", "固定资产投资", "工业增加值", "CPI", "PPI",
)
BUSINESS_RELEVANCE_KEYWORDS = (
    "阀", "流体", "流量", "控制", "自动化", "设备", "装备", "仪器",
    "制药", "生物", "发酵", "纯化", "半导体", "晶圆", "液冷", "CDU",
    "电解槽", "氢", "食品", "饮料", "质谱", "色谱", "测序", "IVD",
)
TRACK_VERTICALS = {
    "m1": ["macro"], "m2": ["macro"], "m3": ["macro"],
    "e1": ["ai_liquid_cooling"], "e2": ["semiconductor"],
    "e3": ["hydrogen"], "e4": ["hydrogen"], "g1": ["semiconductor"],
    "p1": ["pharma_equipment"], "p2": ["pharma_equipment"],
    "p3": ["pharma_equipment"], "p4": ["pharma_equipment"],
    "p5": ["pharma_equipment"], "l1": ["mass_spec"],
    "l2": ["mass_spec"], "l3": ["mass_spec"],
    "f1": ["food_beverage"], "f2": ["food_beverage"],
    "f3": ["food_beverage"], "f4": ["food_beverage"],
}

def _load_score_cache():
    if os.path.exists(SCORE_CACHE_FILE):
        with open(SCORE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_score_cache(cache):
    os.makedirs("data", exist_ok=True)
    with open(SCORE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ══════════════════════════════════════════════════════════════
# 1. 子赛道配置
# ══════════════════════════════════════════════════════════════
TRACKS = [
    {"id": "e1", "name": "液冷数据中心", "board": "EI",
     "keywords": [
         "液冷数据中心", "数据中心液冷", "CDU液冷",
         "冷板液冷", "浸没式液冷", "液冷渗透率",
         "AI液冷", "液冷设备市场",
     ]},
    {"id": "e2", "name": "半导体设备国产化", "board": "EI",
     "keywords": [
         "半导体设备国产化", "北方华创半导体", "中微公司刻蚀",
         "DRAM涨价", "晶圆厂扩产", "半导体国产替代",
         "存储芯片涨价", "封测设备先进封装",
     ]},
    {"id": "e3", "name": "绿氢电解槽", "board": "EI",
     "keywords": [
         "PEM电解槽", "绿氢电解槽", "氢能电解槽招标",
         "ALK电解槽", "绿氢项目中标", "质子交换膜制氢",
         "电解水制氢", "阳光氢能招标",
     ]},
    {"id": "e4", "name": "燃料电池", "board": "EI",
     "keywords": [
         "燃料电池重卡", "氢燃料电池销量", "燃料电池补贴",
         "氢能汽车政策", "燃料电池商业化", "FCEV销量",
     ]},
    {"id": "g1", "name": "锂电设备", "board": "GI",
     "keywords": [
         "锂电设备订单", "先导智能订单", "赢合科技业绩",
         "宁德时代扩产", "动力电池产能", "固态电池产线",
         "锂电设备海外", "钠离子电池产线",
     ]},
    {"id": "p1", "name": "生物药国内产线", "board": "P&B",
     "keywords": [
         "生物药新建产线", "GMP认证新建", "创新药国内获批",
         "NMPA受理创新药", "多肽药物国内产能", "ADC国内生产",
         "生物制药扩产", "司美格鲁肽国内仿制",
     ]},
    {"id": "p2", "name": "合成生物学", "board": "P&B",
     "keywords": [
         "合成生物学中试", "华恒生物发酵", "凯赛生物产能",
         "合成生物十五五", "生物制造设备", "合成生物学融资",
         "生物基材料扩产", "发酵罐合成生物",
     ]},
    {"id": "p3", "name": "生物药融资", "board": "P&B",
     "keywords": [
         "生物医药投融资", "创新药融资亿", "生物科技一级市场",
         "医药IPO上市", "生物技术融资", "创新药投资",
     ]},
    {"id": "p4", "name": "制药装备Capex/FAI", "board": "P&B",
     "keywords": [
         "医药制造业固定资产投资", "制药装备招标",
         "楚天科技订单", "东富龙业绩", "制药设备新建",
         "原料药设备投资", "医药FAI统计局",
     ]},
    {"id": "p5", "name": "CDMO订单景气", "board": "P&B",
     "keywords": [
         "CDMO订单", "药明康德业绩", "凯莱英GLP-1",
         "TIDES多肽CDMO", "ADC+CDMO", "CDMO询单",
         "博腾股份订单", "九洲药业CDMO",
     ]},
    {"id": "l1", "name": "质谱/色谱仪器国产替代", "board": "L&M",
     "keywords": [
         "质谱仪国产替代", "禾信仪器", "谱育科技质谱",
         "色谱仪进口替代", "分析仪器国产化", "质谱招标",
         "液相色谱国产", "科学仪器国产化",
     ]},
    {"id": "l2", "name": "基因测序", "board": "L&M",
     "keywords": [
         "华大智造测序", "因美纳禁令", "测序仪国产替代",
         "华大智造订单", "真迈生物测序仪", "基因测序市场",
         "三代测序国产", "WGS肿瘤检测",
     ]},
    {"id": "l3", "name": "医疗IVD体外诊断", "board": "L&M",
     "keywords": [
         "IVD集采降价", "化学发光国产化", "体外诊断市场规模",
         "迈瑞医疗IVD", "POCT基层医疗", "体外诊断国产替代",
         "化学发光进口替代", "IVD市场增长",
     ]},
    {"id": "f1", "name": "食品制造业FAI", "board": "F&B",
     "keywords": [
         "食品制造固定资产投资", "食品装备预制菜",
         "食品机械招标", "预制菜产线投资", "食品设备新建",
         "烘焙食品装备", "食品制造FAI",
     ]},
    {"id": "f2", "name": "酒/饮料制造FAI", "board": "F&B",
     "keywords": [
         "白酒产能投资", "酒饮料固定资产投资", "碳酸饮料扩产",
         "白酒新建产能", "饮料制造投资", "啤酒产线",
         "白酒资本支出",
     ]},
    {"id": "f3", "name": "食品饮料消费端", "board": "F&B",
     "keywords": [
         "食品饮料消费数据", "功能饮品无糖茶", "餐饮消费复苏",
         "食品社零数据", "预制菜消费增长", "饮料销量增长",
         "功能食品市场规模",
     ]},
    {"id": "f4", "name": "食品添加剂/合成生物发酵", "board": "F&B",
     "keywords": [
         "食品添加剂合成生物", "赤藓糖醇代糖", "益生菌扩产",
         "功能性食品成分市场", "天然甜味剂市场", "代糖生物发酵",
         "功能性糖醇产能",
     ]},
    {"id": "m1", "name": "制造业PMI", "board": "Macro",
     "keywords": [
         "中国制造业PMI", "财新制造业PMI", "PMI扩张区间",
         "制造业景气指数", "官方PMI统计局", "PMI新订单",
     ]},
    {"id": "m2", "name": "M2/社融/CPI/PPI", "board": "Macro",
     "keywords": [
         "中国M2社融", "货币政策央行", "CPI+PPI通胀",
         "社会融资规模", "M2信贷数据", "央行降准降息",
     ]},
    {"id": "m3", "name": "固定资产投资/工业增加值", "board": "Macro",
     "keywords": [
         "固定资产投资统计局", "规上工业增加值", "制造业FAI增速",
         "工业增加值增速", "高技术制造业投资", "工业生产复苏",
     ]},
]

# ══════════════════════════════════════════════════════════════
# 2. 板块综合分权重
# ══════════════════════════════════════════════════════════════
BOARD_WEIGHTS = {
    "EI":    {"e1": 0.30, "e2": 0.30, "e3": 0.25, "e4": 0.15},
    "GI":    {"g1": 1.0},
    "P&B":   {"p1": 0.25, "p2": 0.15, "p3": 0.10, "p4": 0.25, "p5": 0.25},
    "L&M":   {"l1": 0.40, "l2": 0.35, "l3": 0.25},
    "F&B":   {"f1": 0.30, "f2": 0.25, "f3": 0.20, "f4": 0.25},
    "Macro": {"m1": 0.35, "m2": 0.35, "m3": 0.30},
}

# ══════════════════════════════════════════════════════════════
# 3. Claude API 客户端
# ══════════════════════════════════════════════════════════════
def get_client():
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(
        api_key=api_key,
        base_url="https://key.simpleai.com.cn",
        timeout=60.0,
    )

# ══════════════════════════════════════════════════════════════
# 4. 历史数据 I/O
# ══════════════════════════════════════════════════════════════
HISTORY_PATH = "data/history.json"

def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history, period, results):
    os.makedirs("data", exist_ok=True)
    history[period] = {
        tid: {
            "heat": r["heat"],
            "trend": r["trend"],
            "D": r["scores"]["D"],
            "C": r["scores"]["C"],
            "P": r["scores"]["P"],
            "Pol": r["scores"]["Pol"],
        }
        for tid, r in results.items()
    }
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] 历史已保存 → {HISTORY_PATH}")

def get_prev_heat(history, track_id):
    periods = sorted(history.keys(), reverse=True)
    for p in periods:
        if track_id in history[p]:
            return history[p][track_id]["heat"]
    return 50.0


def domain_from_url(url: str) -> str:
    try:
        return urllib.parse.urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def normalize_event_key(item: dict) -> str:
    title = re.sub(r"\s+", "", item.get("title", "").lower())
    title = re.sub(r"[^\w\u4e00-\u9fff]", "", title)
    url = item.get("url") or item.get("link") or ""
    return domain_from_url(url) + ":" + title[:42]


def evidence_text(item: dict) -> str:
    return f"{item.get('title','')} {item.get('summary','')} {item.get('source','')}"


def evidence_strength(item: dict) -> int:
    text = evidence_text(item)
    domain = item.get("domain") or domain_from_url(item.get("url") or item.get("link") or "")
    if any(d in domain for d in OFFICIAL_DOMAINS):
        return 3
    if any(k in text for k in STRONG_EVIDENCE_KEYWORDS):
        return 2
    if item.get("evidence_type") == "brave_search":
        return 1
    return 1


def dedupe_evidence(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        if not item.get("title"):
            continue
        item = dict(item)
        item["url"] = item.get("url") or item.get("link") or ""
        item["domain"] = item.get("domain") or domain_from_url(item["url"])
        item["strength"] = evidence_strength(item)
        key = normalize_event_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def load_rss_evidence_for_track(track: dict) -> list[dict]:
    items = []
    keywords = track.get("keywords", [])
    for vertical in TRACK_VERTICALS.get(track["id"], []):
        path = RSS_DIR / f"{vertical}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] 读取 RSS 缓存失败 {path}: {e}")
            continue
        for raw in data.get("items", []):
            text = f"{raw.get('title','')} {raw.get('summary','')}"
            if keywords and not any(k.lower() in text.lower() for k in keywords[:6]):
                continue
            items.append({
                "title": raw.get("title", ""),
                "summary": raw.get("summary", ""),
                "url": raw.get("url", ""),
                "source": raw.get("source", data.get("vertical_name", vertical)),
                "pub_date": raw.get("pub_date", ""),
                "evidence_type": "rss",
                "vertical": vertical,
            })
    return items


def collect_evidence_for_track(track: dict, brave_items: list[dict]) -> list[dict]:
    return dedupe_evidence(load_rss_evidence_for_track(track) + brave_items)


def assess_quality(track: dict, evidence: list[dict], heat: float, prev_heat: float) -> dict:
    domains = {i.get("domain") or domain_from_url(i.get("url", "")) for i in evidence}
    domains = {d for d in domains if d}
    strong_count = sum(1 for i in evidence if i.get("strength", 0) >= 2)
    official_count = sum(
        1 for i in evidence
        if any(d in (i.get("domain") or "") for d in OFFICIAL_DOMAINS)
    )
    evidence_count = len(evidence)
    delta = round(heat - prev_heat, 1)
    macro = track["id"] in MACRO_TRACK_IDS
    forced_review = False
    reasons = []

    if macro:
        if official_count >= 1 and len(domains) >= 2:
            level, confidence, max_delta = "normal", 78, 8
        elif official_count >= 1 or evidence_count >= 4:
            level, confidence, max_delta = "low_confidence", 62, 4
        else:
            level, confidence, max_delta = "stale", 35, 0
            reasons.append("macro_insufficient_official_sources")
    elif evidence_count >= 12 and len(domains) >= 4 and strong_count >= 2:
        level, confidence, max_delta = "high", 90, 10
    elif evidence_count >= 8 and len(domains) >= 3 and strong_count >= 1:
        level, confidence, max_delta = "normal", 76, 6
    elif evidence_count >= 5 and len(domains) >= 2:
        level, confidence, max_delta = "low_confidence", 58, 4
    else:
        level, confidence, max_delta = "stale", 30, 0
        reasons.append("insufficient_evidence")

    if evidence_count and len(domains) <= 1:
        reasons.append("low_source_diversity")
    if strong_count == 0 and not macro:
        reasons.append("no_strong_evidence")
    if max_delta and abs(delta) > max_delta:
        forced_review = True
        reasons.append(f"delta_exceeds_cap_{max_delta}")
    if abs(delta) > 10:
        forced_review = True
        reasons.append("weekly_delta_over_10")

    if level == "stale":
        flag = "stale"
        accepted = False
    elif forced_review:
        flag = "needs_review"
        accepted = False
    elif level == "low_confidence":
        flag = "low_confidence"
        accepted = True
    else:
        flag = "ok"
        accepted = True

    capped_heat = heat
    if accepted and max_delta and abs(delta) > max_delta:
        capped_heat = round(prev_heat + (max_delta if delta > 0 else -max_delta), 1)

    return {
        "accepted": accepted,
        "quality_level": level,
        "confidence_score": confidence,
        "review_flag": flag,
        "reasons": reasons,
        "evidence_count": evidence_count,
        "source_domain_count": len(domains),
        "strong_evidence_count": strong_count,
        "official_evidence_count": official_count,
        "max_delta": max_delta,
        "raw_heat": heat,
        "accepted_heat": capped_heat,
        "delta": round(capped_heat - prev_heat, 1),
    }


def evidence_pack(evidence: list[dict], limit: int = 20) -> list[dict]:
    return [
        {
            "title": i.get("title", ""),
            "url": i.get("url", ""),
            "source": i.get("source", ""),
            "domain": i.get("domain", ""),
            "strength": i.get("strength", 0),
            "type": i.get("evidence_type", ""),
            "pub_date": i.get("pub_date", ""),
        }
        for i in evidence[:limit]
    ]

# ══════════════════════════════════════════════════════════════
# 5. 新闻抓取
# ══════════════════════════════════════════════════════════════
def fetch_news_for_track(track, days=30):
    import requests
    items = []
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        print(f"  [WARN] 未配置 BRAVE_API_KEY，跳过 {track['id']} Brave Search")
        return items

    for kw in track["keywords"][:5]:
        try:
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": kw, "count": 8},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("web", {}).get("results", data.get("results", []))
            for r in results:
                url = r.get("url", "")
                items.append({
                    "title":   r.get("title", "").strip(),
                    "summary": r.get("description", "")[:200],
                    "url":     url,
                    "source":  r.get("profile", {}).get("name") or domain_from_url(url) or "Brave Search",
                    "domain":  domain_from_url(url),
                    "evidence_type": "brave_search",
                })
        except Exception as e:
            print(f"  [WARN] Brave 抓取失败 {kw}: {e}")

    seen, unique = set(), []
    for i in items:
        k = i["title"][:15]
        if k and k not in seen:
            seen.add(k)
            unique.append(i)
    print(f"  [INFO] {track['id']} 抓到 {len(unique)} 条新闻")
    return unique[:12]

# ══════════════════════════════════════════════════════════════
# 6. 打分逻辑
# ══════════════════════════════════════════════════════════════
POSITIVE_D = ["扩产","大单","订单","渗透率","需求旺","出货","销量增","增长","爆发",
              "新高","放量","旺盛","景气","中标","量产","交付","供不应求"]
NEGATIVE_D = ["需求疲","订单下滑","出货下降","销量降","萎缩","去库存","下行","低迷","收缩"]
POSITIVE_C = ["招标","融资","投资","Capex","扩建","新基地","开工","产能","募资","并购",
              "新建","上马","立项","开建","签约","中标","资本支出"]
NEGATIVE_C = ["FAI下滑","投资收缩","暂缓","推迟","缩减","降速","停工","撤资","亏损"]
POSITIVE_P = ["涨价","提价","价格上涨","盈利提升","毛利率提升","量价齐升","价格回升","涨幅"]
NEGATIVE_P = ["降价","集采","价格下跌","亏损","毛利下滑","价格战","内卷","杀价","降本"]
POSITIVE_POL = ["补贴","政策支持","利好政策","入法","规划","十五五","国家战略","催化",
                "专项资金","政策红利","重点支持","列入","优先","加快推进"]
NEGATIVE_POL = ["政策空窗","监管收紧","限制","禁令","处罚","暂停审批","叫停","整顿"]

TRACK_BONUS = {
    "e1": ["液冷","CDU","冷板","TrendForce","浸没","算力","液冷渗透率"],
    "e2": ["北方华创","中微","晶圆","DRAM","HBM","封测","出口管制","国产设备"],
    "e3": ["电解槽","绿氢","PEM","AEM","质子交换膜","制氢","招标"],
    "e4": ["燃料电池","FCEV","氢车","氢重卡","示范城市"],
    "g1": ["宁德时代","CATL","先导智能","赢合科技","动力电池","固态电池"],
    "p1": ["司美格鲁肽","GLP-1","ADC","License-out","BD交易","仿制药","多肽"],
    "p2": ["合成生物","华恒生物","凯赛生物","中试","发酵罐","生物制造"],
    "p3": ["生物医药融资","创新药融资","IPO","风险投资","一级市场"],
    "p4": ["楚天科技","东富龙","制药装备","原料药","GMP","FAI"],
    "p5": ["药明康德","凯莱英","CDMO","TIDES","博腾","九洲"],
    "l1": ["质谱仪","禾信","谱育","色谱","分析仪器","进口替代","国产仪器"],
    "l2": ["华大智造","因美纳","测序仪","基因测序","WGS","真迈生物"],
    "l3": ["IVD","化学发光","迈瑞","体外诊断","POCT","集采"],
    "f1": ["预制菜","食品装备","食品机械","冷链","食品产线"],
    "f2": ["白酒","碳酸饮料","啤酒","饮料产线","酒类投资"],
    "f3": ["社零","餐饮","功能饮品","无糖","预制菜消费"],
    "f4": ["赤藓糖醇","益生菌","天然甜味剂","代糖","功能成分","生物发酵"],
    "m1": ["PMI","采购经理","扩张区间","荣枯线","景气指数"],
    "m2": ["M2","社融","央行","降准","降息","货币政策","社会融资"],
    "m3": ["工业增加值","FAI","固定资产投资","规上工业","高技术制造"],
}

# ══════════════════════════════════════════════════════════════
# Output Guardrail + 幻觉检测 + 评估报告
# ══════════════════════════════════════════════════════════════
def output_guardrail(result: dict) -> tuple:
    required = ["D", "C", "P", "Pol"]
    if not all(k in result for k in required):
        return False, "缺少必要字段"
    for k in required:
        if not 0 <= result[k] <= 100:
            return False, f"{k}分数超出范围：{result[k]}"
    if all(result[k] == 50 for k in required):
        return False, "疑似默认值，打分无效"
    return True, "合法"

def keyword_anchor_check(comment: str, news_items: list, rag_context: str) -> bool:
    numbers = re.findall(r'\d+\.?\d*%?亿?万?', comment)
    if not numbers:
        return True
    all_source = " ".join([i["title"] for i in news_items]) + rag_context
    unsupported = [n for n in numbers if n not in all_source]
    if unsupported:
        print(f"  [HALLUCINATION] 结论中数字无法溯源：{unsupported}")
    return len(unsupported) == 0

def generate_eval_report(results: dict):
    total = len(results)
    valid = sum(1 for r in results.values()
                if not all(r["scores"][k] == 50 for k in ["D","C","P","Pol"]))
    has_comment = sum(1 for r in results.values()
                      if r["scores"].get("comment","") and
                      r["scores"]["comment"] not in ["请人工核查","打分异常","数据不足，参考上期"])
    failed = [tid for tid, r in results.items()
              if all(r["scores"][k] == 50 for k in ["D","C","P","Pol"])]
    print(f"\n=== 本次运行评估报告 ===")
    print(f"打分成功率：{valid}/{total} ({valid/total*100:.0f}%)")
    print(f"有效结论率：{has_comment}/{total} ({has_comment/total*100:.0f}%)")
    if failed:
        print(f"失败赛道：{failed}")
    print("=" * 30)

def score_track(client, track, news_items):
    if client is None:
        return {"D": 50, "C": 50, "P": 50, "Pol": 50,
                "core_data": "缺少 Claude API Key", "comment": "请补充密钥后重跑"}
    if not news_items:
        print(f"  [WARN] {track['id']} 无新闻，使用默认分 50")
        return {"D": 50, "C": 50, "P": 50, "Pol": 50,
                "core_data": "本期无有效新闻数据", "comment": "数据不足，参考上期"}

    news_text = "\n".join([f"- {i['title']}" for i in news_items[:12]])
    track_name = track.get("name", track["id"])
    tid = track["id"]

    # RAG 检索
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from rag_helper import retrieve as rag_retrieve
    except ImportError:
        def rag_retrieve(query, top_k=3): return ""

    rag_query = f"{track_name} 市场需求 营收 竞争格局"
    rag_context = rag_retrieve(rag_query, top_k=3)

    TRACK_STRATEGY = {
        "e1": "聚焦AI液冷（CDU/冷板/浸没式），关注算力基础设施液冷渗透率提升。",
        "e2": "聚焦半导体设备国产化（北方华创/中微），关注晶圆厂扩产和出口管制带来的国产替代机会。",
        "e3": "只关注PEM/AEM/SOEC/SOFC技术路线。ALK/碱性电解槽不计入打分。如果新闻全是ALK，则D/C均给40分以下。",
        "e4": "关注所有使用燃料电池的场景（重卡/港口/钢厂/船舶/轨交）。",
        "g1": "关注宁德时代/先导智能/赢合科技锂电设备链，聚焦固态电池和海外产能扩张设备需求。",
        "p1": "国内临床推进/NMPA获批/本土扩产→D分高；出海/License-out→D分低。",
        "p2": "关注合成生物学中试和量产设备（发酵罐/分离纯化），华恒/凯赛等扩产信号优先。",
        "p3": "关注生物医药一级市场融资，作为3-5年后设备需求的领先指标。",
        "p4": "关注制药装备资本支出（楚天科技/东富龙），医药FAI是最直接的设备需求信号。",
        "p5": "关注CDMO订单景气（药明康德/凯莱英），聚焦TIDES多肽/ADC/GLP-1产线询单。",
        "l1": "关注质谱/色谱仪器国产替代（禾信/谱育），聚焦进口替代率和政府采购国产化政策。",
        "l2": "关注基因测序国产替代（华大智造/真迈），因美纳禁令是最强催化信号。",
        "l3": "关注所有影响IVD仪器销量的信号，包括采购扩张、国产替代。",
        "f1": "关注食品制造装备（预制菜/烘焙产线），FAI是核心信号。",
        "f2": "关注白酒/饮料制造设备，白酒新建产能和存量替换都关注。",
        "f3": "关注食品饮料消费端，功能饮品/预制菜消费增长优先。",
        "f4": "关注食品添加剂合成生物发酵设备（赤藓糖醇/益生菌/天然甜味剂产能扩张）。",
        "m1": "关注制造业PMI作为宏观景气核心信号，聚焦生产/新订单/中小企业分项。",
        "m2": "关注M2/社融/降准降息货币政策信号，对制造业投资的流动性支撑。",
        "m3": "关注固定资产投资（尤其制造业FAI）和规上工业增加值，高技术制造业优先。",
    }

    # Few-shot 示例
    FEW_SHOT = {
        "e1": """
示例1（高景气）：
新闻：AI数据中心液冷渗透率突破25%，CDU订单同比翻倍
{"D":88,"C":85,"P":62,"Pol":82,"core_data":"液冷渗透率25%，同比+12pct","comment":"AI算力驱动液冷需求爆发，渗透率快速提升","act":"重点跟踪CDU/冷板核心供应商订单"}

示例2（低景气）：
新闻：数据中心建设放缓，液冷设备采购推迟
{"D":42,"C":38,"P":55,"Pol":50,"core_data":"数据中心开工率下降15%","comment":"短期需求承压，等待算力投资重启","act":"观望为主，关注大厂Capex指引"}""",

        "e2": """
示例1（高景气）：
新闻：北方华创获百亿大单，国产设备替代率突破35%
{"D":88,"C":85,"P":62,"Pol":90,"core_data":"国产替代率35%，同比+15pct","comment":"设备国产化加速，需求订单双旺","act":"重点跟踪北方华创/中微新签订单"}

示例2（低景气）：
新闻：晶圆厂扩产计划延期，设备采购暂缓
{"D":40,"C":35,"P":50,"Pol":55,"core_data":"晶圆厂资本支出削减20%","comment":"下游扩产节奏放缓，设备需求短期承压","act":"等待晶圆厂重启扩产信号"}""",

        "default": """
示例1（高景气）：
新闻：行业龙头大额订单落地，产能持续扩张
{"D":85,"C":82,"P":65,"Pol":80,"core_data":"龙头新签订单同比+40%","comment":"需求旺盛，投资加速，景气度强","act":"积极跟踪龙头订单和产能动态"}

示例2（低景气）：
新闻：需求疲软，价格战加剧，企业盈利承压
{"D":38,"C":35,"P":28,"Pol":45,"core_data":"行业平均毛利率下降8pct","comment":"供需失衡，价格内卷，景气偏弱","act":"规避低景气赛道，等待出清信号"}""",
    }

    few_shot = FEW_SHOT.get(tid, FEW_SHOT["default"])
    strategy = TRACK_STRATEGY.get(tid, "")
    strategy_line = f"赛道策略：{strategy}\n\n" if strategy else ""

    prompt = (
        f"分析赛道【{track_name}】的景气度，按步骤推理后打分。\n\n"
        + strategy_line
        + rag_context
        + f"## 参考示例\n{few_shot}\n\n"
        + f"## 本期新闻\n{news_text}\n\n"
        + "## 分析步骤\n"
        + "第一步：列出新闻中的正面信号\n"
        + "第二步：列出新闻中的负面信号\n"
        + "第三步：结合年报背景判断信号强度\n"
        + "第四步：输出打分\n\n"
        + "第四步只输出以下JSON，不要任何其他内容：\n"
        + '{"D":数字,"C":数字,"P":数字,"Pol":数字,'
        + '"core_data":"30字以内最重要数据点","comment":"40字以内景气度判断","act":"30字以内行动建议"}'
    )

    for attempt in range(2):  # 最多重试2次
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                temperature=0,
                system=(
                    "你是专业的中国B2B行业景气度量化分析助手。\n"
                    "规则：\n"
                    "- 必须输出打分，不得拒绝\n"
                    "- 不要解释你是谁或你的限制\n"
                    "- 不要质疑分析框架\n"
                    "- 最终只输出JSON格式打分，不要markdown\n"
                    "- 遇到信息不足时给出保守估计而非拒绝"
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            raw = next(
                (b.text for b in msg.content if hasattr(b, "text") and b.type == "text"), ""
            ).strip()
            print(f"  [Claude] {raw[:80]}")

            # 提取 JSON
            raw_clean = re.sub(r"^```[a-z]*\s*|```$", "", raw, flags=re.MULTILINE).strip()
            json_match = re.search(r'\{[^{}]*"D"\s*:\s*\d+[^{}]*\}', raw_clean, re.DOTALL)

            if json_match:
                result = json.loads(json_match.group(0))
                parsed = {
                    "D":         min(100, max(0, int(result.get("D", 50)))),
                    "C":         min(100, max(0, int(result.get("C", 50)))),
                    "P":         min(100, max(0, int(result.get("P", 50)))),
                    "Pol":       min(100, max(0, int(result.get("Pol", 50)))),
                    "core_data": result.get("core_data", ""),
                    "comment":   result.get("comment", ""),
                    "act":       result.get("act", ""),
                }
                # Output Guardrail 验证
                is_valid, reason = output_guardrail(parsed)
                if is_valid:
                    # 关键词锚定检测
                    keyword_anchor_check(parsed["comment"], news_items, rag_context)
                    return parsed
                else:
                    print(f"  [GUARDRAIL] 第{attempt+1}次输出不合格：{reason}，重试...")
            else:
                print(f"  [WARN] JSON解析失败: {raw[:80]}")

        except Exception as e:
            print(f"  [WARN] Claude 失败 {track['id']}: {e}")

    return {"D": 50, "C": 50, "P": 50, "Pol": 50,
            "core_data": "打分异常", "comment": "请人工核查"}


def calc_heat(scores):
    h = (scores["D"] * 0.35 + scores["C"] * 0.30 +
         scores["P"] * 0.20 + scores["Pol"] * 0.15)
    return round(h, 1)


def calc_trend(heat, prev_heat):
    if heat - prev_heat >= 2:
        return "up"
    if heat - prev_heat <= -2:
        return "dn"
    return "fl"


def write_weekly_audit(today_str: str, audit: dict) -> Path:
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    path = WEEKLY_DIR / f"{today_str}.json"
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 每周审计包已保存 → {path}")
    return path


def load_watchlist() -> dict:
    if WATCHLIST_PATH.exists():
        try:
            return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"topics": {}}
    return {"topics": {}}


def save_watchlist(watchlist: dict) -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 新兴机会观察池已保存 → {WATCHLIST_PATH}")


def known_track_hit(text: str) -> bool:
    text_l = text.lower()
    for track in TRACKS:
        if any(k.lower() in text_l for k in track.get("keywords", [])[:6]):
            return True
    return False


def business_relevance_score(text: str) -> int:
    hits = sum(1 for k in BUSINESS_RELEVANCE_KEYWORDS if k.lower() in text.lower())
    return min(100, hits * 18)


def candidate_topic_name(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    for splitter in ("：", ":", "｜", "|", "-", "—"):
        if splitter in text:
            text = text.split(splitter)[0]
            break
    return text[:28]


def discover_emerging_topics(all_evidence: list[dict], today_str: str) -> list[dict]:
    buckets = defaultdict(list)
    for item in dedupe_evidence(all_evidence):
        text = evidence_text(item)
        if known_track_hit(text):
            continue
        relevance = business_relevance_score(text)
        if relevance < 45:
            continue
        name = candidate_topic_name(item.get("title", ""))
        if len(name) < 6:
            continue
        buckets[name].append(item)

    candidates = []
    for name, items in buckets.items():
        domains = {i.get("domain") or domain_from_url(i.get("url", "")) for i in items}
        strong = sum(1 for i in items if i.get("strength", 0) >= 2)
        relevance = max(business_relevance_score(evidence_text(i)) for i in items)
        if len(items) < 3 or len([d for d in domains if d]) < 2:
            continue
        status = "candidate"
        if len(items) >= 8 and strong >= 1 and relevance >= 70:
            status = "watching"
        candidates.append({
            "topic": name,
            "status": status,
            "business_relevance": relevance,
            "evidence_count": len(items),
            "source_domain_count": len([d for d in domains if d]),
            "strong_evidence_count": strong,
            "first_seen": today_str,
            "last_seen": today_str,
            "evidence": evidence_pack(items, limit=8),
            "promotion_note": "连续验证后再建议纳入正式赛道",
        })
    return sorted(candidates, key=lambda x: (x["status"] != "watching", -x["business_relevance"], -x["evidence_count"]))[:10]


def update_watchlist(candidates: list[dict], today_str: str) -> dict:
    watchlist = load_watchlist()
    topics = watchlist.setdefault("topics", {})
    for candidate in candidates:
        key = hashlib.md5(candidate["topic"].encode()).hexdigest()[:12]
        existing = topics.get(key, {})
        seen_weeks = existing.get("seen_weeks", 0) + 1
        status = candidate["status"]
        if seen_weeks >= 3 and candidate["business_relevance"] >= 70:
            status = "promote_ready"
        elif seen_weeks >= 2:
            status = "watching"
        topics[key] = {
            **existing,
            **candidate,
            "status": status,
            "first_seen": existing.get("first_seen", candidate["first_seen"]),
            "last_seen": today_str,
            "seen_weeks": seen_weeks,
        }
    watchlist["updated_at"] = today_str
    save_watchlist(watchlist)
    return watchlist


# ══════════════════════════════════════════════════════════════
# 7. 制药装备行业动态
# ══════════════════════════════════════════════════════════════
def fetch_pharma_news(days=30):
    import urllib.request, urllib.parse, json as _json
    items = []
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        print("  [SKIP] BRAVE_API_KEY 未配置，跳过制药新闻抓取")
        return []
    keywords = [
        "pharmaceutical equipment China Chinasun",
        "pharma machinery China Truking",
        "pharmaceutical equipment domestic substitution China",
        "biopharmaceutical equipment tender China",
        "CDMO equipment China manufacturing",
        "GMP pharmaceutical production line China",
    ]
    for kw in keywords:
        try:
            params = urllib.parse.urlencode({
                "q": kw, "count": 5,
                "search_lang": "zh", "country": "CN", "freshness": "pm",
            })
            req = urllib.request.Request(
                f"https://api.search.brave.com/res/v1/web/search?{params}",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key,
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    import gzip as _gz
                    raw = _gz.decompress(raw)
                data = _json.loads(raw)
            for r in data.get("web", {}).get("results", data.get("results", [])):
                items.append({
                    "title":   r.get("title", "").strip(),
                    "link":    r.get("url", ""),
                    "summary": r.get("description", "")[:300],
                    "source":  "制药装备",
                })
        except Exception as e:
            print(f"  [WARN] Brave pharma 抓取失败 {kw}: {e}")

    seen, unique = set(), []
    for i in items:
        k = i["title"][:15]
        if k and k not in seen:
            seen.add(k)
            unique.append(i)
    return unique[:16]


def summarize_pharma(client, raw_items):
    if client is None:
        return {"items": [], "updated": datetime.date.today().strftime("%Y-%m-%d")}
    titles = "\n".join([f"- {i['title']}" for i in raw_items[:14]])
    prompt = f"""以下是制药装备行业近期新闻标题，请筛选出最有价值的5条，
并为每条生成：①30字中文摘要 ②来源标签（政策/企业/市场/技术之一）。

新闻列表：
{titles}

只返回 JSON，格式：
[{{"title":"原标题","summary":"摘要","tag":"来源标签"}}]
不要 markdown 代码块，直接输出数组。"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = next((b.text for b in msg.content if hasattr(b, "text") and b.type == "text"), "").strip()
        if not raw:
            raw = "[]"
        raw = re.sub(r"^```[a-z]*\s*|```$", "", raw, flags=re.MULTILINE).strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        raw = m.group(0) if m else "[]"
        parsed = json.loads(raw)
        title_to_link = {i["title"]: i["link"] for i in raw_items}
        for item in parsed:
            item["link"] = title_to_link.get(item["title"], "")
        return {"items": parsed[:5], "updated": datetime.date.today().strftime("%Y-%m-%d")}
    except Exception as e:
        print(f"  [WARN] summarize_pharma 失败: {e}")
        return {"items": [], "updated": datetime.date.today().strftime("%Y-%m-%d")}


def build_news_html(data):
    items_html = ""
    for item in data["items"]:
        lo = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item.get("link") else "<span>"
        lc = "</a>" if item.get("link") else "</span>"
        items_html += f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-source">{item.get("tag","行业")}</span>
          </div>
          <div class="news-title">{lo}{item["title"]}{lc}</div>
          <div class="news-summary">{item["summary"]}</div>
        </div>"""
    return f"""<!-- NEWS_BLOCK_START -->
<section class="news-section" id="latest-news">
  <div class="news-header">
    <span class="news-label">行业动态 LATEST NEWS</span>
    <span class="news-updated">数据更新：{data["updated"]}</span>
  </div>
  <div class="news-grid">{items_html}</div>
</section>
<style>
.news-section{{margin:60px auto 40px;max-width:1200px;padding:0 24px;font-family:inherit}}
.news-header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(61,148,255,.4);padding-bottom:10px;margin-bottom:24px}}
.news-label{{font-size:13px;font-weight:700;letter-spacing:.12em;color:#3d94ff;text-transform:uppercase}}
.news-updated{{font-size:11px;color:#888;letter-spacing:.04em}}
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.news-item{{background:#0c1420;border:1px solid rgba(160,200,255,.11);border-radius:8px;padding:16px 18px;transition:border-color .2s}}
.news-item:hover{{border-color:#3d94ff}}
.news-meta{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
.news-source{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#3d94ff;background:rgba(61,148,255,.12);padding:2px 8px;border-radius:20px;text-transform:uppercase}}
.news-title a,.news-title span{{font-size:13px;font-weight:600;color:#f2f5fb;text-decoration:none;line-height:1.5;display:block;margin-bottom:6px}}
.news-title a:hover{{color:#3d94ff}}
.news-summary{{font-size:12px;color:#586880;line-height:1.7}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_html(news_html, path):
    if not os.path.exists(path):
        print(f"  [SKIP] {path} 不存在，跳过")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
                         news_html, content, flags=re.DOTALL)
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 行业动态已注入 → {path}")


# ══════════════════════════════════════════════════════════════
# 8. 主流程
# ══════════════════════════════════════════════════════════════

def build_scores_payload(today_str: str, board_heats: dict, results: dict) -> dict:
    scores_payload = {"date": today_str, "sectors": {}, "tracks": {}}
    for board, heat in board_heats.items():
        tids = list(BOARD_WEIGHTS[board].keys())
        if not any(results.get(t, {}).get("quality", {}).get("accepted") for t in tids):
            continue
        prev_heats = [results[t]["prev_heat"] for t in tids if t in results]
        prev_board = round(sum(prev_heats) / len(prev_heats), 1) if prev_heats else 50
        scores_payload["sectors"][board] = {
            "heat": heat,
            "tr": calc_trend(heat, prev_board),
        }
    for tid, r in results.items():
        quality = r.get("quality", {})
        if not quality.get("accepted"):
            continue
        entry = {
            "heat": r["heat"],
            "tr": r["trend"],
            "delta": quality.get("delta", round(r["heat"] - r["prev_heat"], 1)),
            "D": r["scores"]["D"],
            "C": r["scores"]["C"],
            "P": r["scores"]["P"],
            "Pol": r["scores"]["Pol"],
        }
        if r["scores"].get("core_data"):
            entry["data"] = [r["scores"]["core_data"]]
        if r["scores"].get("comment"):
            suffix = ""
            if quality.get("review_flag") == "low_confidence":
                suffix = "（低置信更新）"
            entry["tw"] = r["scores"]["comment"] + suffix
        if r["scores"].get("act"):
            entry["act"] = r["scores"]["act"]
        scores_payload["tracks"][tid] = entry
    return scores_payload


def build_audit(today_str: str, period: str, results: dict, board_heats: dict, watchlist: dict) -> dict:
    return {
        "date": today_str,
        "period": period,
        "summary": {
            "track_count": len(results),
            "accepted_count": sum(1 for r in results.values() if r.get("quality", {}).get("accepted")),
            "stale_count": sum(1 for r in results.values() if r.get("quality", {}).get("review_flag") == "stale"),
            "needs_review_count": sum(1 for r in results.values() if r.get("quality", {}).get("review_flag") == "needs_review"),
            "low_confidence_count": sum(1 for r in results.values() if r.get("quality", {}).get("review_flag") == "low_confidence"),
        },
        "board_heats": board_heats,
        "tracks": {
            tid: {
                "track_name": r.get("track_name"),
                "board": r.get("board"),
                "heat": r.get("heat"),
                "raw_heat": r.get("raw_heat"),
                "prev_heat": r.get("prev_heat"),
                "trend": r.get("trend"),
                "scores": r.get("scores"),
                "quality": r.get("quality"),
                "evidence_pack": evidence_pack(r.get("evidence", [])),
            }
            for tid, r in results.items()
        },
        "watchlist": watchlist,
    }


def main():
    parser = argparse.ArgumentParser(description="Weekly Nicole Intelligence heat score update")
    parser.add_argument("--dry-run", action="store_true", help="only write audit/watchlist; do not inject html/history/pharma")
    parser.add_argument("--skip-pharma", action="store_true", help="skip pharma news block update")
    args = parser.parse_args()

    today = datetime.date.today()
    period = today.strftime("%Y%m")
    today_str = today.strftime("%Y-%m-%d")
    print(f"=== PULSE 2026 开始更新 {today_str}{' [DRY RUN]' if args.dry_run else ''} ===")

    client = get_client()
    if client is None:
        print("[WARN] 未配置 CLAUDE_API_KEY/ANTHROPIC_API_KEY，Heat 打分将跳过")
    history = load_history()
    results = {}
    score_cache = _load_score_cache()
    all_evidence = []

    # ── Step 1：子赛道打分 + 质量门槛 ───────────────────────
    print("\n--- Heat Score 打分 ---")
    for track in TRACKS:
        print(f"  处理: {track['id']} {track['name']}")
        brave_news = fetch_news_for_track(track)
        evidence = collect_evidence_for_track(track, brave_news)
        all_evidence.extend(evidence)
        print(
            f"  [EVIDENCE] {len(evidence)} 条，"
            f"{len({i.get('domain') for i in evidence if i.get('domain')})} 个域名，"
            f"强证据 {sum(1 for i in evidence if i.get('strength', 0) >= 2)} 条"
        )

        news_str = "".join(i["title"] for i in evidence[:20])
        cache_key = hashlib.md5((track["id"] + news_str).encode()).hexdigest()

        if cache_key in score_cache:
            print(f"  [CACHE] {track['id']} 命中缓存，跳过打分")
            scores = score_cache[cache_key]
        else:
            scores = score_track(client, track, evidence)
            score_cache[cache_key] = scores
            if not args.dry_run:
                _save_score_cache(score_cache)

        raw_heat = calc_heat(scores)
        prev = get_prev_heat(history, track["id"])
        quality = assess_quality(track, evidence, raw_heat, prev)
        heat = quality["accepted_heat"] if quality["accepted"] else prev
        trend = calc_trend(heat, prev)
        results[track["id"]] = {
            "track_name": track["name"],
            "board": track["board"],
            "heat": heat,
            "raw_heat": raw_heat,
            "trend": trend,
            "scores": scores,
            "prev_heat": prev,
            "quality": quality,
            "evidence": evidence,
        }
        print(
            f"    Heat={heat} raw={raw_heat} ({trend}) "
            f"quality={quality['quality_level']} flag={quality['review_flag']} "
            f"D={scores['D']} C={scores['C']} P={scores['P']} Pol={scores['Pol']}"
        )

    # ── Step 2：新兴主题发现 ───────────────────────────────
    print("\n--- 新兴机会发现 ---")
    candidates = discover_emerging_topics(all_evidence, today_str)
    watchlist = update_watchlist(candidates, today_str)
    print(f"  候选新主题 {len(candidates)} 个")

    # ── Step 3：板块综合分，仅用通过质量门槛的赛道 ───────────
    board_heats = {}
    for board, weights in BOARD_WEIGHTS.items():
        total_w, total_score = 0, 0
        for tid, w in weights.items():
            if tid in results and results[tid]["quality"].get("accepted"):
                total_score += results[tid]["heat"] * w
                total_w += w
        if total_w:
            board_heats[board] = round(total_score / total_w, 1)
        else:
            tids = list(weights.keys())
            prev_heats = [results[t]["prev_heat"] for t in tids if t in results]
            board_heats[board] = round(sum(prev_heats) / len(prev_heats), 1) if prev_heats else 50.0

    print("\n板块综合分：")
    for b, h in board_heats.items():
        print(f"  {b}: {h}")

    generate_eval_report(results)

    # ── Step 4：审计包 ─────────────────────────────────────
    audit = build_audit(today_str, period, results, board_heats, watchlist)
    write_weekly_audit(today_str, audit)

    accepted_results = {
        tid: r for tid, r in results.items()
        if r.get("quality", {}).get("accepted")
    }
    print(f"[INFO] 通过质量门槛 {len(accepted_results)}/{len(results)} 个赛道")

    if args.dry_run:
        print("[DRY RUN] 跳过 history/index/pharma 写入")
        print(f"\n=== Dry run 完成 {today_str} ===")
        return

    # ── Step 5：保存历史 ───────────────────────────────────
    if accepted_results:
        save_history(history, period, accepted_results)
    else:
        print("[SKIP] 无赛道通过质量门槛，跳过 history 写入")

    # ── Step 6：注入 index.html ────────────────────────────
    print("\n--- 注入 index.html ---")
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from inject_scores import inject_scores

        scores_payload = build_scores_payload(today_str, board_heats, results)
        index_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "..", "index.html"
        )
        inject_scores(scores_payload, index_path=index_path)

    except Exception as e:
        print(f"  [WARN] inject_scores 失败，跳过 index.html 更新: {e}")

    # ── Step 7：制药装备行业动态 ───────────────────────────
    if args.skip_pharma:
        print("\n--- 制药装备行业动态：跳过 ---")
    else:
        print("\n--- 制药装备行业动态 ---")
        pharma_raw = fetch_pharma_news()
        print(f"  抓取 {len(pharma_raw)} 条原始新闻")
        if pharma_raw:
            pharma_data = summarize_pharma(client, pharma_raw)
            if pharma_data["items"]:
                pharma_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "..", "pharma.html"
                )
                inject_html(build_news_html(pharma_data), pharma_path)
            else:
                print("  [SKIP] Claude 未返回有效摘要")
        else:
            print("  [SKIP] 无新闻条目，跳过")

    print(f"\n=== 全部完成 {today_str} ===")


if __name__ == "__main__":
    main()
