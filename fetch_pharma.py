"""
制药行业阀门情报抓取管道
信号源：NMPA飞检 / CDE优先审评 / 巨潮募投公告 / 环评公示 / 招投标
输出：pharma_signals.json（对齐 PULSE data.js 结构）
"""

import json
import time
import hashlib
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PharmaIntelBot/1.0)"}
OUTPUT_FILE = Path("data/pharma_signals.json")
OUTPUT_FILE.parent.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def safe_get(url, timeout=15, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.encoding = r.apparent_encoding
            return r
        except Exception as e:
            if i == retries - 1:
                print(f"  [FAIL] {url} → {e}")
            time.sleep(2)
    return None

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

# ─────────────────────────────────────────────
# 信号源 1：NMPA 飞检通报
# 合规驱动型——被点名药厂 3-6 月内整改，换阀需求刚性
# ─────────────────────────────────────────────

def fetch_nmpa_alerts():
    print("→ 抓取 NMPA 飞检通报...")
    url = "https://www.nmpa.gov.cn/yaopin/ypjgdt/index.html"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("ul.list-content li, .news-list li")
    results = []

    for item in items[:20]:
        a = item.find("a")
        span = item.find("span")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.nmpa.gov.cn" + href
        date = span.get_text(strip=True) if span else today_str()

        # 飞检关键词过滤
        keywords = ["飞检", "GMP", "警告信", "整改", "不符合", "召回"]
        if not any(k in title for k in keywords):
            continue

        # 阀门相关度打分
        valve_score = score_for_valves(title, source="nmpa")

        results.append({
            "id": make_id(title),
            "source": "NMPA飞检",
            "source_type": "regulatory",
            "title": title,
            "url": href,
            "date": date,
            "valve_relevance": valve_score,
            "signal_type": "compliance",  # 合规驱动
            "lead_time_months": "1-6",
            "action": "销售跟进" if valve_score >= 6 else "持续观察"
        })

    print(f"   NMPA: {len(results)} 条有效信号")
    return results


# ─────────────────────────────────────────────
# 信号源 2：CDE 优先审评名单
# 产能扩张型——获批后 6-12 月开始建产线
# ─────────────────────────────────────────────

def fetch_cde_priority():
    print("→ 抓取 CDE 优先审评名单...")
    url = "https://www.cde.org.cn/main/news/listpage/316f488f23d3ef4b21a7fd7bae4b07ec"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select(".table-list tr, table tr")
    results = []

    for row in items[1:15]:  # 跳过表头
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        drug_name = cols[0].get_text(strip=True)
        category  = cols[1].get_text(strip=True) if len(cols) > 1 else ""
        company   = cols[2].get_text(strip=True) if len(cols) > 2 else ""
        date      = cols[-1].get_text(strip=True) if cols else today_str()

        # 生物制品和原料药对阀门需求最强
        bio_keywords = ["单抗", "疫苗", "细胞", "基因", "生物"]
        api_keywords = ["原料药", "注射", "无菌"]
        if any(k in drug_name + category for k in bio_keywords):
            valve_type = "卫生级隔膜阀/生物反应器配套"
            valve_score = 8
        elif any(k in drug_name + category for k in api_keywords):
            valve_type = "耐腐蚀阀/CIP配套"
            valve_score = 7
        else:
            valve_type = "通用卫生级阀门"
            valve_score = 5

        results.append({
            "id": make_id(drug_name + company),
            "source": "CDE优先审评",
            "source_type": "pipeline",
            "title": f"{drug_name}（{company}）",
            "drug_category": category,
            "valve_type_needed": valve_type,
            "date": date,
            "valve_relevance": valve_score,
            "signal_type": "expansion",  # 扩产驱动
            "lead_time_months": "6-12",
            "action": "建立客户档案，待获批后跟进"
        })

    print(f"   CDE: {len(results)} 条有效信号")
    return results


# ─────────────────────────────────────────────
# 信号源 3：巨潮资讯募投公告
# 最精准——直接写了建多少车间、投多少钱
# ─────────────────────────────────────────────

def fetch_cninfo_announcements():
    print("→ 抓取巨潮资讯制药募投公告...")
    # 巨潮API接口
    url = "http://www.cninfo.com.cn/new/hisAnnounce/query"
    keywords = ["GMP", "产能扩建", "新建车间", "募投项目", "生产基地"]
    pharma_industries = ["医药制造", "生物制品", "化学制药"]

    payload = {
        "pageNum": 1,
        "pageSize": 30,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": "新建 车间 GMP",
        "secid": "",
        "category": "category_ndbg_szsh",  # 可替换为其他公告类型
        "trade": "医药制造业",
        "seDate": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
        "eDate": today_str(),
        "isHLtitle": True
    }

    results = []
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        data = r.json()
        announcements = data.get("announcements", [])

        for ann in announcements[:20]:
            title = ann.get("announcementTitle", "")
            company = ann.get("secName", "")
            date = ann.get("announcementTime", "")[:10]
            ann_url = "http://www.cninfo.com.cn/new/announcement/detail?announceId=" + str(ann.get("announcementId", ""))

            # 过滤高价值公告
            high_value = ["新建", "扩建", "GMP", "车间", "产线", "募集资金"]
            if not any(k in title for k in high_value):
                continue

            valve_score = score_for_valves(title, source="cninfo")
            # 估算阀门预算（固定资产投资额 × 系数）
            capex_note = extract_capex_hint(title)

            results.append({
                "id": make_id(title + company),
                "source": "巨潮募投公告",
                "source_type": "capex",
                "title": f"{company}｜{title}",
                "url": ann_url,
                "date": date,
                "valve_relevance": valve_score,
                "capex_hint": capex_note,
                "signal_type": "expansion",
                "lead_time_months": "3-9",
                "action": "提取项目金额，估算阀门采购预算"
            })

    except Exception as e:
        print(f"   巨潮接口异常: {e}")

    print(f"   巨潮: {len(results)} 条有效信号")
    return results


# ─────────────────────────────────────────────
# 信号源 4：环评公示
# 提前量最长（12-18个月），覆盖非上市企业
# ─────────────────────────────────────────────

def fetch_eia_projects():
    print("→ 抓取环评公示（制药项目）...")
    # 生态环境部建设项目环评信息
    url = "https://eia.mee.gov.cn/db_pa_pub/getItemInfoList.vm"
    params = {
        "industryName": "医药制造业",
        "pageNum": 1,
        "pageSize": 20,
        "areaCode": "",
        "status": "受理"
    }

    results = []
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        items = r.json().get("data", {}).get("list", [])

        for item in items:
            name = item.get("projectName", "")
            company = item.get("constructionUnit", "")
            date = item.get("publishDate", today_str())
            province = item.get("province", "")

            # 高价值项目过滤
            high_value = ["原料药", "制剂", "生物", "疫苗", "注射", "无菌"]
            if not any(k in name for k in high_value):
                continue

            valve_score = score_for_valves(name, source="eia")

            results.append({
                "id": make_id(name + company),
                "source": "环评公示",
                "source_type": "project_filing",
                "title": f"【{province}】{name}",
                "company": company,
                "date": date,
                "valve_relevance": valve_score,
                "signal_type": "expansion",
                "lead_time_months": "12-18",
                "action": "建立项目追踪，12个月后主动联系"
            })

    except Exception as e:
        print(f"   环评接口异常（需登录或结构变化）: {e}")

    print(f"   环评: {len(results)} 条有效信号")
    return results


# ─────────────────────────────────────────────
# 信号源 5：招投标（阀门直接采购信号）
# ─────────────────────────────────────────────

def fetch_tender_signals():
    print("→ 抓取制药阀门招投标...")
    url = "https://www.ccgp.gov.cn/cggg/zygg/zbgg/index.shtml"
    r = safe_get(url)
    results = []

    if not r:
        return results

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select(".vT-srch-result-list-bid li, .list-content li")

    valve_keywords = ["隔膜阀", "卫生级阀", "蝶阀", "球阀", "调节阀", "阀门", "管件"]
    pharma_keywords = ["制药", "药业", "生物", "医药", "GMP", "疫苗"]

    for item in items[:30]:
        a = item.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")

        # 必须同时含阀门和制药关键词
        has_valve = any(k in title for k in valve_keywords)
        has_pharma = any(k in title for k in pharma_keywords)

        if not (has_valve or has_pharma):
            continue

        span = item.find("span")
        date = span.get_text(strip=True) if span else today_str()
        valve_score = 9 if (has_valve and has_pharma) else 6

        results.append({
            "id": make_id(title),
            "source": "政府采购招标",
            "source_type": "tender",
            "title": title,
            "url": href if href.startswith("http") else "https://www.ccgp.gov.cn" + href,
            "date": date,
            "valve_relevance": valve_score,
            "signal_type": "immediate",  # 即时需求
            "lead_time_months": "0-2",
            "action": "立即投标评估"
        })

    print(f"   招投标: {len(results)} 条有效信号")
    return results


# ─────────────────────────────────────────────
# DeepSeek 打分函数
# ─────────────────────────────────────────────

def score_for_valves(text, source="generic"):
    """
    基于关键词的快速打分（0-10）
    生产环境建议替换为 DeepSeek API 调用
    """
    score = 4  # 基准分

    high_value = ["无菌", "GMP", "生物反应器", "原料药", "注射剂", "隔膜阀",
                  "卫生级", "CIP", "SIP", "飞检", "警告信", "整改"]
    mid_value  = ["制剂", "疫苗", "发酵", "洁净", "新建", "扩建", "产线"]
    low_value  = ["仿制药", "普通片剂", "外包装"]

    for k in high_value:
        if k in text: score += 1.5
    for k in mid_value:
        if k in text: score += 0.8
    for k in low_value:
        if k in text: score -= 1

    # 来源权重调整
    source_boost = {"nmpa": 1.5, "tender": 2.0, "cninfo": 1.0, "eia": 0.5}
    score += source_boost.get(source, 0)

    return min(round(score, 1), 10)


def extract_capex_hint(title):
    """从公告标题提取募资金额线索"""
    import re
    # 匹配"X亿"或"X万"
    matches = re.findall(r'(\d+\.?\d*)\s*(亿|万)', title)
    if matches:
        amounts = []
        for val, unit in matches:
            v = float(val)
            if unit == "亿":
                amounts.append(f"{val}亿元（阀门预算约{round(v*0.1, 2)}-{round(v*0.15, 2)}亿）")
            else:
                amounts.append(f"{val}万元")
        return "；".join(amounts)
    return "金额待查"


# ─────────────────────────────────────────────
# 主函数：汇总 + 生成 PULSE 兼容 JSON
# ─────────────────────────────────────────────

def build_pulse_output(all_signals):
    """
    生成与 PULSE data.js 兼容的结构
    pharma 赛道 heat score = 各信号加权均值
    """
    if not all_signals:
        return {}

    # 按 signal_type 分组
    compliance = [s for s in all_signals if s["signal_type"] == "compliance"]
    expansion  = [s for s in all_signals if s["signal_type"] == "expansion"]
    immediate  = [s for s in all_signals if s["signal_type"] == "immediate"]

    # 热度计算（对齐 PULSE 公式）
    def avg_score(signals, weight):
        if not signals:
            return 0
        return round(sum(s["valve_relevance"] for s in signals) / len(signals) * weight, 1)

    D = avg_score(compliance, 1.0)   # 合规事件 → 破坏性/紧迫度
    C = avg_score(expansion,  1.0)   # 扩产信号 → 资本热度
    P = avg_score(immediate,  1.0)   # 招标 → 项目落地
    Pol = min(len(compliance) * 1.5, 10)  # 监管压力强度

    heat = round(D*0.35 + C*0.30 + P*0.20 + Pol*0.15, 1)

    # Top 10 最高优先级信号
    top_signals = sorted(all_signals, key=lambda x: x["valve_relevance"], reverse=True)[:10]

    return {
        "track": "pharma",
        "track_name": "制药·生物制品",
        "updated": today_str(),
        "heat_score": heat,
        "score_breakdown": {
            "D_compliance": D,
            "C_expansion": C,
            "P_tender": P,
            "Pol_regulatory": round(Pol, 1)
        },
        "signal_counts": {
            "compliance": len(compliance),
            "expansion": len(expansion),
            "immediate": len(immediate),
            "total": len(all_signals)
        },
        "top_signals": top_signals,
        "all_signals": all_signals
    }


def main():
    print(f"\n{'='*50}")
    print(f"制药情报管道启动  {today_str()}")
    print(f"{'='*50}\n")

    all_signals = []
    all_signals += fetch_nmpa_alerts()
    all_signals += fetch_cde_priority()
    all_signals += fetch_cninfo_announcements()
    all_signals += fetch_eia_projects()
    all_signals += fetch_tender_signals()

    print(f"\n→ 汇总信号数: {len(all_signals)}")

    output = build_pulse_output(all_signals)
    output["all_signals"] = all_signals

    # 写入 JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"→ 输出写入: {OUTPUT_FILE}")
    print(f"→ 制药赛道热度: {output.get('heat_score', 'N/A')}")
    print(f"\n{'='*50}\n")

    return output


if __name__ == "__main__":
    main()
