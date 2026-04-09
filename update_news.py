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
import datetime
import feedparser
import anthropic

# ══════════════════════════════════════════════════════════════
# 1. 子赛道配置（id 必须和 index.html 里的 T 对象 key 对应）
# ══════════════════════════════════════════════════════════════
TRACKS = [
    {"id": "e1", "name": "液冷数据中心", "board": "EI",
     "keywords": [
         "AI液冷数据中心", "液冷渗透率+数据中心", "AI基础设施+液冷",
         "CDU冷板+液冷", "TrendForce+液冷", "数据中心液冷+算力",
         "液冷设备+市场规模", "浸没式液冷+冷板液冷",
     ]},
    {"id": "e2", "name": "半导体设备国产化", "board": "EI",
     "keywords": [
         "半导体设备国产化", "北方华创+中微公司", "晶圆厂扩产+设备",
         "DRAM涨价+半导体", "半导体设备+出口管制", "封测设备+先进封装",
         "半导体+国产替代", "存储芯片+涨价",
     ]},
    {"id": "e3", "name": "绿氢电解槽", "board": "EI",
     "keywords": [
         "PEM电解槽+绿氢", "氢能+电解槽招标", "质子交换膜+氢能",
         "ALK电解槽+招标", "绿氢+项目中标", "氢能+十五五",
         "电解水制氢+设备", "氢辉+阳光氢能+电解槽",
     ]},
    {"id": "e4", "name": "燃料电池", "board": "EI",
     "keywords": [
         "燃料电池+重卡", "氢燃料电池+销量", "燃料电池+补贴",
         "FCEV+氢车", "燃料电池+商业化", "氢能汽车+政策",
     ]},
    {"id": "g1", "name": "锂电设备", "board": "GI",
     "keywords": [
         "锂电设备+宁德时代", "先导智能+赢合科技", "锂电池+产能扩张",
         "动力电池+设备订单", "CATL+扩产", "锂电+固态电池+设备",
         "锂电设备+海外订单", "钠离子电池+产线",
     ]},
    {"id": "p1", "name": "生物药出海/CDMO", "board": "P&B",
     "keywords": [
         "创新药+License-out", "司美格鲁肽+仿制药", "生物药+BD交易",
         "ADC+出海", "GLP-1+CDMO", "创新药+NDA申报",
         "生物类似药+上市", "多肽药物+CDMO",
     ]},
    {"id": "p2", "name": "合成生物学", "board": "P&B",
     "keywords": [
         "合成生物学+中试", "华恒生物+发酵", "凯赛生物+产能",
         "合成生物+十五五", "生物制造+设备", "发酵罐+合成生物",
         "合成生物学+融资", "生物基材料+扩产",
     ]},
    {"id": "p3", "name": "生物药融资", "board": "P&B",
     "keywords": [
         "生物医药+投融资", "创新药+融资", "生物科技+一级市场",
         "医药+IPO", "生物技术+风险投资", "创新药+pre-IPO",
     ]},
    {"id": "p4", "name": "制药装备Capex/FAI", "board": "P&B",
     "keywords": [
         "医药制造业+固定资产投资", "制药装备+资本支出",
         "医药FAI+统计局", "制药设备+招标", "楚天科技+东富龙",
         "制药装备+新建产线", "原料药+设备投资",
     ]},
    {"id": "p5", "name": "CDMO订单景气", "board": "P&B",
     "keywords": [
         "CDMO+订单", "药明康德+凯莱英", "TIDES+多肽CDMO",
         "ADC+CDMO", "凯莱英+GLP-1", "CDMO+询单",
         "博腾股份+九洲药业", "小分子CDMO+产能",
     ]},
    {"id": "l1", "name": "质谱/色谱仪器国产替代", "board": "L&M",
     "keywords": [
         "质谱仪+国产替代", "禾信仪器+谱育科技", "色谱仪+进口替代",
         "分析仪器+国产化", "质谱+招标", "液相色谱+国产",
         "科学仪器+国产化率", "高端仪器+进口替代",
     ]},
    {"id": "l2", "name": "基因测序", "board": "L&M",
     "keywords": [
         "基因测序+华大智造", "因美纳+禁令", "测序仪+国产替代",
         "华大智造+订单", "真迈生物+测序", "WGS+肿瘤检测",
         "基因组学+测序", "三代测序+国产",
     ]},
    {"id": "l3", "name": "医疗IVD体外诊断", "board": "L&M",
     "keywords": [
         "IVD+集采", "化学发光+国产化", "体外诊断+市场规模",
         "迈瑞医疗+IVD", "POCT+基层医疗", "IVD+降价",
         "体外诊断+国产替代", "化学发光+进口替代",
     ]},
    {"id": "f1", "name": "食品制造业FAI", "board": "F&B",
     "keywords": [
         "食品制造业+固定资产投资", "食品装备+预制菜", "食品设备+新建产线",
         "食品机械+招标", "预制菜+产线投资", "烘焙+食品装备",
         "食品制造+FAI",
     ]},
    {"id": "f2", "name": "酒/饮料制造FAI", "board": "F&B",
     "keywords": [
         "白酒+产能投资", "酒饮料+固定资产投资", "碳酸饮料+扩产",
         "白酒+新建产能", "饮料制造+FAI", "啤酒+产线投资",
         "白酒+资本支出",
     ]},
    {"id": "f3", "name": "食品饮料消费端", "board": "F&B",
     "keywords": [
         "食品饮料+消费数据", "功能饮品+无糖茶", "餐饮+复苏",
         "食品+社零数据", "预制菜+消费增长", "饮料+销量增长",
         "功能食品+市场规模",
     ]},
    {"id": "f4", "name": "食品添加剂/合成生物发酵", "board": "F&B",
     "keywords": [
         "食品添加剂+合成生物", "天然甜味剂+赤藓糖醇", "益生菌+扩产",
         "功能性食品成分+市场", "发酵设备+食品添加剂", "代糖+生物发酵",
         "功能性糖醇+产能",
     ]},
    {"id": "m1", "name": "制造业PMI", "board": "Macro",
     "keywords": [
         "中国制造业PMI", "财新PMI+制造业", "PMI+扩张区间",
         "制造业景气指数", "PMI+新订单", "官方PMI+统计局",
     ]},
    {"id": "m2", "name": "M2/社融/CPI/PPI", "board": "Macro",
     "keywords": [
         "中国M2+社融", "货币政策+央行", "CPI+PPI+通胀",
         "社会融资规模", "M2+信贷数据", "降准+降息",
         "PPI+工业品价格",
     ]},
    {"id": "m3", "name": "固定资产投资/工业增加值", "board": "Macro",
     "keywords": [
         "固定资产投资+统计局", "规上工业增加值", "制造业FAI",
         "工业增加值+增速", "高技术制造业+投资", "工业生产+复苏",
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
    return anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
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
    """返回上一期的 heat，找不到返回 50。"""
    periods = sorted(history.keys(), reverse=True)
    for p in periods:
        if track_id in history[p]:
            return history[p][track_id]["heat"]
    return 50.0

# ══════════════════════════════════════════════════════════════
# 5. 新闻抓取
# ══════════════════════════════════════════════════════════════
def fetch_news_for_track(track, days=35):
    items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for kw in track["keywords"]:
        url = f"https://news.google.com/rss/search?q={kw}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                items.append({
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:200],
                })
        except Exception as e:
            print(f"  [WARN] 抓取失败 {kw}: {e}")
    # 去重
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
# ══════════════════════════════════════════════════════════════
# 关键词规则打分 — 不依赖任何 AI API
# ══════════════════════════════════════════════════════════════

# 通用关键词
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

# 赛道专属加分词（命中即额外+8）
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

def _keyword_score(track_id, titles, pos_words, neg_words, base=58):
    text = " ".join(titles)
    pos = sum(1 for w in pos_words if w in text)
    neg = sum(1 for w in neg_words if w in text)
    # 赛道专属词加分
    bonus_words = TRACK_BONUS.get(track_id, [])
    bonus = sum(1 for w in bonus_words if w in text)
    score = base + pos * 5 - neg * 8 + bonus * 8
    return min(95, max(30, score))

def score_track(client, track, news_items):
    if not news_items:
        print(f"  [WARN] {track['id']} 无新闻，使用默认分 50")
        return {"D": 50, "C": 50, "P": 50, "Pol": 50,
                "core_data": "本期无有效新闻数据", "comment": "数据不足，参考上期"}

    titles = [i['title'] for i in news_items]

    tid = track["id"]
    D   = _keyword_score(tid, titles, POSITIVE_D,   NEGATIVE_D,   base=58)
    C   = _keyword_score(tid, titles, POSITIVE_C,   NEGATIVE_C,   base=55)
    P   = _keyword_score(tid, titles, POSITIVE_P,   NEGATIVE_P,   base=60)
    Pol = _keyword_score(tid, titles, POSITIVE_POL, NEGATIVE_POL, base=58)

    print(f"  [RULE] D={D} C={C} P={P} Pol={Pol}")
    return {
        "D": D, "C": C, "P": P, "Pol": Pol,
        "core_data": titles[0][:30] if titles else "",
        "comment":   f"基于{len(titles)}条新闻关键词打分",
    }


def calc_heat(scores):
    """加权公式：D×35% + C×30% + P×20% + Pol×15%"""
    h = (scores["D"] * 0.35 + scores["C"] * 0.30 +
         scores["P"] * 0.20 + scores["Pol"] * 0.15)
    return round(h, 1)


def calc_trend(heat, prev_heat):
    if heat - prev_heat >= 2:
        return "up"
    if heat - prev_heat <= -2:
        return "dn"
    return "fl"


# ══════════════════════════════════════════════════════════════
# 7. 制药装备行业动态（注入 pharma.html）
# ══════════════════════════════════════════════════════════════
PHARMA_FEEDS = [
    ("制药装备动态",
     "https://news.google.com/rss/search?q=制药装备&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("龙头企业",
     "https://news.google.com/rss/search?q=楚天科技+OR+东富龙+OR+森松国际&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国产替代",
     "https://news.google.com/rss/search?q=生物制药设备+国产替代&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("政策监管",
     "https://news.google.com/rss/search?q=制药装备+政策+NMPA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]

def fetch_pharma_news(days=30):
    items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for label, url in PHARMA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                items.append({
                    "title":   entry.get("title", "").strip(),
                    "link":    entry.get("link", ""),
                    "summary": entry.get("summary", "")[:300],
                    "source":  label,
                })
        except Exception as e:
            print(f"  [WARN] {label}: {e}")
    # 去重
    seen, unique = set(), []
    for i in items:
        k = i["title"][:15]
        if k and k not in seen:
            seen.add(k)
            unique.append(i)
    return unique[:16]


def summarize_pharma(client, raw_items):
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
            model="abab6.5s-chat",
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        for b in msg.content:
            if hasattr(b, "text") and b.text:
                raw = b.text.strip()
                break
        if not raw:
            raw = "[]"
        # strip markdown fences
        raw = re.sub(r"^```[a-z]*\s*|```$", "", raw, flags=re.MULTILINE).strip()
        # find JSON array
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        raw = m.group(0) if m else "[]"
        parsed = json.loads(raw)
        # 补充原始链接
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
if __name__ == "__main__":
    today     = datetime.date.today()
    period    = today.strftime("%Y%m")
    today_str = today.strftime("%Y-%m-%d")
    print(f"=== PULSE 2026 开始更新 {today_str} ===")

    client  = get_client()
    history = load_history()
    results = {}

    # ── Step 1：子赛道打分 ──────────────────────────────────
    print("\n--- Heat Score 打分 ---")
    for track in TRACKS:
        print(f"  处理: {track['id']}")
        news   = fetch_news_for_track(track)
        scores = score_track(client, track, news)
        heat   = calc_heat(scores)
        prev   = get_prev_heat(history, track["id"])
        trend  = calc_trend(heat, prev)
        results[track["id"]] = {
            "heat": heat, "trend": trend,
            "scores": scores, "prev_heat": prev,
        }
        print(f"    Heat={heat} ({trend})  D={scores['D']} C={scores['C']} "
              f"P={scores['P']} Pol={scores['Pol']}")

    # ── Step 2：板块综合分 ─────────────────────────────────
    board_heats = {}
    for board, weights in BOARD_WEIGHTS.items():
        total_w, total_score = 0, 0
        for tid, w in weights.items():
            if tid in results:
                total_score += results[tid]["heat"] * w
                total_w     += w
        board_heats[board] = round(total_score / total_w, 1) if total_w else 50.0

    print("\n板块综合分：")
    for b, h in board_heats.items():
        print(f"  {b}: {h}")

    # ── Step 3：保存历史 ───────────────────────────────────
    save_history(history, period, results)

    # ── Step 4：注入 index.html ────────────────────────────
    print("\n--- 注入 index.html ---")
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from inject_scores import inject_scores

        scores_payload = {
            "date":    today_str,
            "sectors": {},
            "tracks":  {},
        }

        # 板块级
        for b, heat in board_heats.items():
            # 用板块内子赛道的平均 prev 估算板块趋势
            tids = list(BOARD_WEIGHTS[b].keys())
            prev_heats = [results[t]["prev_heat"] for t in tids if t in results]
            prev_board = round(sum(prev_heats) / len(prev_heats), 1) if prev_heats else 50
            scores_payload["sectors"][b] = {
                "heat": heat,
                "tr":   calc_trend(heat, prev_board),
            }

        # 子赛道级
        for tid, r in results.items():
            delta = round(r["heat"] - r["prev_heat"], 1)
            scores_payload["tracks"][tid] = {
                "heat":  r["heat"],
                "tr":    r["trend"],
                "delta": delta,
                "D":     r["scores"]["D"],
                "C":     r["scores"]["C"],
                "P":     r["scores"]["P"],
                "Pol":   r["scores"]["Pol"],
            }

        # index.html 在仓库根目录，脚本在 scripts/，所以往上一级
        index_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "index.html")
        inject_scores(scores_payload, index_path=index_path)

    except Exception as e:
        print(f"  [WARN] inject_scores 失败，跳过 index.html 更新: {e}")

    # ── Step 5：制药装备行业动态 → pharma.html ─────────────
    print("\n--- 制药装备行业动态 ---")
    pharma_raw = fetch_pharma_news()
    print(f"  抓取 {len(pharma_raw)} 条原始新闻")
    if pharma_raw:
        pharma_data = summarize_pharma(client, pharma_raw)
        if pharma_data["items"]:
            pharma_path = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)), "..", "pharma.html"
            )
            inject_html(build_news_html(pharma_data), pharma_path)
        else:
            print("  [SKIP] Claude 未返回有效摘要")
    else:
        print("  [SKIP] 无新闻条目，跳过")

    print(f"\n=== 全部完成 {today_str} ===")
