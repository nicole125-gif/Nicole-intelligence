import os
import re
import json
import datetime
import feedparser
import requests
import anthropic
from urllib.parse import quote
from bs4 import BeautifulSoup

# ── 子赛道配置 ─────────────────────────────────────────────
TRACKS = [
    # EI
    {"id": "EI·液冷数据中心", "board": "EI", "keywords": [
        "AI液冷+数据中心",
        "液冷+英维克+申菱+高澜股份",
        "冷板液冷+IDC",
    ]},
    {"id": "EI·半导体设备国产化", "board": "EI", "keywords": [
        "中微公司+北方华创+拓荆科技+盛美上海+业绩",
        "先进封装+CoWoS+TSV+国产设备",
        "晶圆厂+扩产+国产设备+采购+招标",
    ]},
    {"id": "EI·绿氢电解槽", "board": "EI", "keywords": [
        "PEM电解槽+AEM电解槽+SOEC+SOFC+招标+中标",
        "隆基氢能+阳光氢能+考克利尔+三环集团+扩产",
        "绿氢+制氢+十五五+补贴+国家战略",
        "绿氢项目+制氢基地+开工+投产",
        "PEM+AEM+SOEC+SOFC+量产+商业化",
    ]},
    {"id": "EI·燃料电池", "board": "EI", "keywords": [
        "氢燃料电池+FCEV+重卡+客车+销量",
        "亿华通+国鸿氢能+重塑能源+捷氢科技+科威尔+订单",
        "燃料电池+氢能汽车+补贴+示范城市",
        "加氢站+新建+投产+规划",
        "燃料电池+电堆+功率密度+降本",
    ]},
    {"id": "EI·光伏设备", "board": "EI", "keywords": [
        "迈为股份+捷佳伟创+奥特维+帝尔激光+订单+业绩",
        "HJT+TOPCon+钙钛矿+扩产+产线+投资",
        "光伏+组件+东南亚建厂+欧洲工厂+海外产能",
        "光伏+新能源+装机目标+补贴+十五五",
        "光伏设备+硅片+兼并重组+产能出清",
    ]},
    # GI
    {"id": "GI·锂电设备", "board": "GI", "keywords": [
        "宁德时代+比亚迪+亿纬锂能+设备采购+招标+扩产",
        "涂布机+注液机+电解液+精密泵+质量流量计+阀门",
        "固态电池+干法电极+大圆柱电池+试产线+商业化",
        "锂电出海+欧洲工厂+补贴+中标+设备交付",
        "电池护照+碳足迹+欧盟电池法规",
    ]},
    {"id": "GI·3D打印", "board": "GI", "keywords": [
        "铂力特+华曙高科+易加三维+鑫精合+订单+业绩",
        "3D打印+增材制造+航空航天+发动机+叶片+量产",
        "3D打印+增材制造+医疗器械+植入物+骨科+获批",
        "金属3D打印+增材制造+新建产线+扩产+投资",
        "3D打印+增材制造+AI设计+数字孪生+智能制造",
    ]},
    # P&B
    {"id": "P&B·合成生物学", "board": "P&B", "keywords": [
        "凯赛生物+华恒生物+川宁生物+嘉必优+扩产+新建+投资",
        "发酵罐+生物反应器+扩产+中标+新签+投资",
        "合成生物学+生物制造+十五五+国家战略+补贴+投资",
        "胶原蛋白+透明质酸+多肽+DHA+磷脂+生物合成+发酵+扩产",
        "赖氨酸+色氨酸+有机酸+维生素+赤藓糖醇+工业酶+扩产+投资",
        "PHA+PLA+生物塑料+生物基材料+量产+商业化+投资",
    ]},
    {"id": "P&B·生物药融资", "board": "P&B", "keywords": [
        "生物医药+生物药+融资+A轮+B轮+C轮+IPO+定增",
        "生物医药+创新药+亿元+过亿+超10亿",
        "ADC+mRNA+细胞治疗+GLP-1+融资+投资+建厂",
        "募资用途+募集资金+生产基地+智能化改造+产能扩充",
        "生物医药+医疗器械+设备更新+贴息贷款+技术改造",
        "生物医药+创新药+科创板+港股+上市募资",
    ]},
    {"id": "P&B·制药装备Capex", "board": "P&B", "keywords": [
        "森松+东富龙+楚天+奥星+合同负债+在手订单+业绩",
        "制药装备+EPC+发酵+层析+纯化+灌装+注液+冻干+中标+新签",
        "森松+东富龙+楚天+海外订单+德国工厂+东南亚+中东",
        "辉瑞+阿斯利康+诺华+莫德纳+赛诺菲+中国建厂+投资扩产",
        "生物制药+原料药+GMP车间+扩产+新建",
        "一次性技术+Single-use+SUS+扩产+应用",
    ]},
    {"id": "P&B·CDMO", "board": "P&B", "keywords": [
        "药明康德+凯莱英+博腾+订单+签约+业绩",
        "药明康德+凯莱英+博腾+FDA认证+海外客户+国际订单",
        "CDMO+合同研发+海外建厂+东南亚产能+爱尔兰工厂",
    ]},
    # L&M
    {"id": "L&M·质谱色谱仪器", "board": "L&M", "keywords": [
        "禾信仪器+谱育科技+天瑞仪器+皖仪科技+订单+业绩+中标",
        "质谱仪+色谱仪+国产替代+进口替代+国产化率",
        "环境监测+食品检测+药品检测+仪器采购+招标",
        "科学仪器+分析仪器+国产化+政府采购+补贴",
        "岛津+沃特世+安捷伦+赛默飞+中国市场+竞争",
    ]},
    {"id": "L&M·基因测序", "board": "L&M", "keywords": [
        "华大智造+诺禾致源+贝瑞基因+合同负债+业绩+中标",
        "测序仪+基因测序+国产替代+自主可控+核心零部件",
        "微流控芯片+Lab-on-a-chip+高通量+集成化+自动配液",
        "肿瘤早筛+MCED+无创产检+商业化+纳入医保+获批",
        "Illumina+Thermo+Fisher+出口管制+供应链风险+本土化",
        "华大智造+迈瑞+贝瑞基因+出口+海外市场+国际订单+海外建厂",
    ]},
    {"id": "L&M·医疗IVD", "board": "L&M", "keywords": [
        "迈瑞+安图生物+迈克生物+亚辉龙+迪瑞医疗+合同负债+扩产+募投项目",
        "万孚生物+英诺特+基蛋生物+美康生物+凯普生物+扩产+新建+募投项目",
        "达安基因+科华生物+理邦精密+睿昂基因+扩产+新建+募投项目",
        "迈瑞+安图生物+迈克生物+海外工厂+海外研发中心+全球本地化",
        "募资用途+募集资金+IVD+诊断仪器+生产基地+智能化改造",
        "IVD+实验室自动化+流水线+模块化集成",
        "化学发光仪+全自动生化+血液分析仪+新品+发布+高通量+紧凑型",
        "分子诊断仪+PCR仪+测序仪+新品+发布+量产+自动化",
        "POCT设备+即时检测仪+新品+发布+小型化+高通量",
        "IVD+体外诊断+出口+CE认证+FDA+海外市场",
        "化学发光+生化试剂+IVD+集采+降价+价格战",
        "IVD+实验室自动化+降本+模块化+系统集成",
        "医疗设备+诊断仪器+设备更新+以旧换新+两新政策",
        "体外诊断+IVD+基层医疗+分级诊疗+县域医院",
    ]},
    # F&B
    {"id": "F&B·食品制造FAI", "board": "F&B", "keywords": [
        "食品制造+食品加工+中标+产线+自动化改造+投资",
        "雀巢+卡夫亨氏+百事+可口可乐+中国建厂+扩产+投资",
    ]},
    {"id": "F&B·酒饮料制造FAI", "board": "F&B", "keywords": [
        "伊利+蒙牛+光明+三元+建厂+扩产+投资",
        "农夫山泉+东鹏+华润饮料+元气森林+建厂+扩产+投资",
        "华润啤酒+青岛啤酒+百威+燕京+建厂+扩产+投资",
        "茅台+五粮液+泸州老窖+洋河+技改+扩产+投资",
        "中粮+金龙鱼+益海嘉里+建厂+扩产+投资",
        "永创智能+达意隆+新美星+乐惠国际+Krones+中亚股份+东富龙承欢+GEA+利乐+订单+中标+扩产",
    ]},
    {"id": "F&B·食品饮料消费", "board": "F&B", "keywords": [
        "食品饮料+餐饮+零售额+消费增速+社零",
        "即时零售+外卖+市场规模+增速",
    ]},
    {"id": "F&B·食品添加剂", "board": "F&B", "keywords": [
        "安琪酵母+保龄宝+华康股份+梅花生物+扩产+投资+业绩",
        "益生菌+天然甜味剂+食用香精+产能+扩产+建厂",
        "食品添加剂+大发酵+新建+扩产+投资",
    ]},
    # Macro — 由统计局爬取，keywords 留空
    {"id": "Macro·制造业PMI",     "board": "Macro", "keywords": []},
    {"id": "Macro·M2社融CPIPPI",  "board": "Macro", "keywords": []},
    {"id": "Macro·投资工业增加值", "board": "Macro", "keywords": []},
]

BOARD_WEIGHTS = {
    "EI":    {
        "EI·液冷数据中心": 0.25,
        "EI·半导体设备国产化": 0.25,
        "EI·绿氢电解槽": 0.15,
        "EI·燃料电池": 0.10,
        "EI·光伏设备": 0.25,
    },
    "GI":    {
        "GI·锂电设备": 0.70,
        "GI·3D打印": 0.30,
    },
    "P&B":   {
        "P&B·合成生物学": 0.20,
        "P&B·生物药融资": 0.15,
        "P&B·制药装备Capex": 0.35,
        "P&B·CDMO": 0.30,
    },
    "L&M":   {
        "L&M·质谱色谱仪器": 0.30,
        "L&M·基因测序": 0.30,
        "L&M·医疗IVD": 0.40,
    },
    "F&B":   {
        "F&B·食品制造FAI": 0.25,
        "F&B·酒饮料制造FAI": 0.30,
        "F&B·食品饮料消费": 0.20,
        "F&B·食品添加剂": 0.25,
    },
    "Macro": {
        "Macro·制造业PMI": 0.35,
        "Macro·M2社融CPIPPI": 0.35,
        "Macro·投资工业增加值": 0.30,
    },
}

# ── Macro 负信号赛道（打分时Price反向）────────────────────
NEGATIVE_SIGNAL_TRACKS = {
    "P&B·CDMO": ["CDMO+合同研发+海外建厂+东南亚产能+爱尔兰工厂"],
    "EI·光伏设备": ["光伏设备+硅片+兼并重组+产能出清"],
    "L&M·医疗IVD": ["化学发光+生化试剂+IVD+集采+降价+价格战"],
}


def get_client():
    return anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
    )


def get_text(msg):
    for b in msg.content:
        if hasattr(b, "type") and b.type == "text":
            return b.text.strip()
    return ""


# ── 统计局爬取 Macro 数据 ──────────────────────────────────

STATS_PATTERNS = {
    "PMI":    r"制造业[采购经理指数PMI]*[为是](\d+\.?\d*)%",
    "PPI":    r"PPI[同比]*[下降上涨增长]*(\-?\d+\.?\d*)%",
    "工业增加值": r"规模以上工业增加值[同比实际增长]*(\d+\.?\d*)%",
    "社融":   r"社会融资规模[存量同比]*增长(\d+\.?\d*)%",
    "CPI":    r"CPI[同比]*[上涨下降]*(\-?\d+\.?\d*)%",
    "食品制造FAI": r"食品制造业[固定资产投资同比增长]*(\-?\d+\.?\d*)%",
    "酒饮料FAI":   r"酒[、饮料和精制茶制造业固定资产投资同比增长]*(\-?\d+\.?\d*)%",
}

def fetch_stats_gov_macro():
    """爬取国家统计局最新发布页，提取宏观数据"""
    result = {}
    try:
        url = "https://www.stats.gov.cn/sj/zxfb/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=True)
        articles = []
        for a in links:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("统计局" in title or "PMI" in title or
                "PPI" in title or "工业" in title or "CPI" in title or
                "固定资产" in title or "社会融资" in title):
                if href.startswith("/"):
                    href = "https://www.stats.gov.cn" + href
                articles.append((title, href))
        print(f"  [OK] 统计局发布页找到 {len(articles)} 条相关标题")

        # 从标题直接提取数字
        for title, href in articles[:30]:
            for key, pattern in STATS_PATTERNS.items():
                if key not in result:
                    m = re.search(pattern, title)
                    if m:
                        val = float(m.group(1))
                        result[key] = val
                        print(f"  [OK] {key}: {val}% (from: {title[:40]})")

        # 对没找到的指标，尝试进入详情页
        missing = [k for k in ["PMI","PPI","工业增加值"] if k not in result]
        for title, href in articles[:10]:
            if not missing:
                break
            try:
                r2 = requests.get(href, headers=headers, timeout=10)
                r2.encoding = "utf-8"
                text = BeautifulSoup(r2.text, "html.parser").get_text()
                for key in missing[:]:
                    m = re.search(STATS_PATTERNS[key], text)
                    if m:
                        val = float(m.group(1))
                        result[key] = val
                        missing.remove(key)
                        print(f"  [OK] {key}: {val}% (from detail page)")
            except Exception:
                pass

    except Exception as e:
        print(f"  [WARN] 统计局爬取失败: {e}")
    return result


def build_macro_scores(stats):
    """将统计局数据转为 Macro 赛道的 Heat Score"""
    scores = {}

    # 制造业PMI
    pmi = stats.get("PMI")
    if pmi:
        d = 75 if pmi >= 51 else (60 if pmi >= 50 else (45 if pmi >= 49 else 30))
        scores["Macro·制造业PMI"] = {"D": d, "C": d, "P": 60, "Pol": 60,
            "core_data": f"制造业PMI {pmi}%", "comment": "扩张" if pmi >= 50 else "收缩"}

    # M2社融CPIPPI
    ppi = stats.get("PPI")
    she = stats.get("社融")
    if ppi is not None or she is not None:
        p_score = 65 if (ppi or 0) > 0 else (50 if (ppi or 0) > -1 else 35)
        c_score = 70 if (she or 0) > 8 else (55 if (she or 0) > 6 else 40)
        core = f"PPI {ppi}%" if ppi else ""
        if she: core += f" 社融 {she}%"
        scores["Macro·M2社融CPIPPI"] = {"D": 55, "C": c_score, "P": p_score, "Pol": 60,
            "core_data": core, "comment": "货币环境"}

    # 投资工业增加值
    fai = stats.get("工业增加值")
    if fai:
        d = 75 if fai >= 7 else (65 if fai >= 6 else (50 if fai >= 5 else 38))
        scores["Macro·投资工业增加值"] = {"D": d, "C": d, "P": 55, "Pol": 60,
            "core_data": f"工业增加值 {fai}%", "comment": "工业产出"}

    return scores


# ── Heat Score 打分 ────────────────────────────────────────

def fetch_news_for_track(track, days=35):
    items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for kw in track["keywords"]:
        url = f"https://news.google.com/rss/search?q={quote(kw)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
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
            print(f"  [WARN] {kw}: {e}")
    seen, unique = set(), []
    for i in items:
        k = i["title"][:15]
        if k and k not in seen:
            seen.add(k)
            unique.append(i)
    return unique[:15]


def score_track(client, track, news_items):
    if not news_items:
        return {"D": 50, "C": 50, "P": 50, "Pol": 50,
                "core_data": "本期无有效新闻数据", "comment": "数据不足，参考上期"}

    # 负信号说明
    neg_note = ""
    neg_kws = NEGATIVE_SIGNAL_TRACKS.get(track["id"], [])
    if neg_kws:
        neg_note = f"\n注意：以下关键词为负信号，出现时Price(P)维度应降分：{', '.join(neg_kws)}"

    news_text = "\n".join([f"- {i['title']}" for i in news_items[:12]])
    prompt = f"""你是中国B2B设备行业景气度分析师，对以下赛道进行打分。

打分方法论：
- Demand(需求动能,35%)：新订单/出货量/渗透率变化，领先指标为主
- Capex(投资强度,30%)：招标规模/融资额/固定资产投资/合同负债，最直接领先指标
- Price(价格盈利,20%)：反向指标！价格下跌/集采降价=低分
- Policy(政策情绪,15%)：产业补贴/政府支持/监管政策
{neg_note}

当前赛道：{track['id']}

本期相关新闻（{len(news_items)}条）：
{news_text}

只返回以下格式，不要其他文字：
D|C|P|Pol|核心数据摘要(30字以内)|一句话点评(40字以内)"""

    try:
        msg = client.messages.create(
            model="MiniMax-M2.5-highspeed",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = get_text(msg)
        parts = raw.split("|")
        if len(parts) >= 6:
            return {
                "D":   min(100, max(0, int(float(parts[0].strip())))),
                "C":   min(100, max(0, int(float(parts[1].strip())))),
                "P":   min(100, max(0, int(float(parts[2].strip())))),
                "Pol": min(100, max(0, int(float(parts[3].strip())))),
                "core_data": parts[4].strip(),
                "comment":   parts[5].strip(),
            }
        else:
            print(f"  [WARN] 格式不对 {track['id']}: {raw[:80]}")
    except Exception as e:
        print(f"  [WARN] 打分失败 {track['id']}: {e}")
    return {"D": 50, "C": 50, "P": 50, "Pol": 50, "core_data": "解析失败", "comment": ""}


def calc_heat(scores):
    return round(scores["D"]*0.35 + scores["C"]*0.30 + scores["P"]*0.20 + scores["Pol"]*0.15, 2)


def calc_trend(heat_now, heat_prev):
    if heat_prev is None:
        return "→"
    delta = heat_now - heat_prev
    if delta >= 2:  return "↑"
    if delta <= -2: return "↓"
    return "→"


# ── history.json ───────────────────────────────────────────

def load_history():
    try:
        with open("data/history.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history, period, results):
    history[period] = {t["id"]: results[t["id"]]["heat"] for t in TRACKS if t["id"] in results}
    with open("data/history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] history.json 已更新，新增 {period}")


def get_prev_heat(history, track_id):
    if not history:
        return None
    last_period = sorted(history.keys())[-1]
    return history[last_period].get(track_id)


# ── 更新 data.js ───────────────────────────────────────────

def update_data_js(stats, today_str):
    with open("data.js", "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'lastUpdated:\s*"[^"]*"', f'lastUpdated: "{today_str}"', content)
    field_map = {
        "工业增加值": "IND. VALUE ADD",
        "PPI":        "PPI TREND",
        "PMI":        "MFG. PMI",
    }
    trend_map = {
        "工业增加值": lambda v: "↑" if v > 5.5 else "→",
        "PPI":        lambda v: "↑" if v > 0 else "↓",
        "PMI":        lambda v: "↑" if v >= 50 else "↓",
    }
    for key, label_en in field_map.items():
        if key not in stats:
            continue
        val = stats[key]
        trend = trend_map[key](val)
        content = re.sub(
            rf'(labelEn:\s*"{re.escape(label_en)}"[^}}]*?value:\s*)[0-9.-]+',
            rf'\g<1>{val}', content, flags=re.DOTALL)
        content = re.sub(
            rf'(labelEn:\s*"{re.escape(label_en)}"[^}}]*?trend:\s*")[^"]*"',
            rf'\g<1>{trend}"', content, flags=re.DOTALL)
        print(f"  [OK] {label_en}: {val} / {trend}")
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] data.js 已更新")


# ── 制药装备新闻 ───────────────────────────────────────────

PHARMA_FEEDS = [
    ("制药装备动态", "https://news.google.com/rss/search?q=%E5%88%B6%E8%8D%AF%E8%A3%85%E5%A4%87&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("龙头企业",     "https://news.google.com/rss/search?q=%E6%A5%9A%E5%A4%A9%E7%A7%91%E6%8A%80+OR+%E4%B8%9C%E5%AF%8C%E9%BE%99+OR+%E6%A3%AE%E6%9D%BE%E5%9B%BD%E9%99%85&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国产替代",     "https://news.google.com/rss/search?q=%E7%94%9F%E7%89%A9%E5%88%B6%E8%8D%AF%E8%AE%BE%E5%A4%87+%E5%9B%BD%E4%BA%A7%E6%9B%BF%E4%BB%A3&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("政策监管",     "https://news.google.com/rss/search?q=%E5%88%B6%E8%8D%AF%E8%A3%85%E5%A4%87+%E6%94%BF%E7%AD%96+NMPA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]


def fetch_pharma_news():
    all_items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    for source_name, url in PHARMA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                all_items.append({
                    "source": source_name,
                    "title":  entry.get("title", "").strip(),
                    "link":   entry.get("link", ""),
                    "summary": entry.get("summary", "")[:300],
                })
            print(f"[OK] {source_name}: {len(feed.entries)} 条")
        except Exception as e:
            print(f"[WARN] {source_name}: {e}")
    seen, unique = set(), []
    for item in all_items:
        k = item["title"][:20]
        if k and k not in seen:
            seen.add(k)
            unique.append(item)
    return unique[:20]


def summarize_pharma(client, raw_items):
    items_text = "\n\n".join([
        f"[{i+1}] 来源：{x['source']}\n标题：{x['title']}\n链接：{x['link']}"
        for i, x in enumerate(raw_items[:12])
    ])
    today = datetime.date.today().strftime("%Y年%m月%d日")
    prompt = f"""你是制药装备行业分析师。从以下新闻中筛选8条最相关的，每条写一句50字摘要。
只返回如下格式，每条一行，不要其他文字：
序号|来源|标题|摘要|链接

新闻列表：
{items_text}"""
    msg = client.messages.create(
        model="MiniMax-M2.5-highspeed",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = get_text(msg)
    items = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("序号"):
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            items.append({"source": parts[1].strip(), "title": parts[2].strip(),
                          "summary": parts[3].strip(), "link": parts[4].strip()})
    return {"updated": today, "items": items[:10]}


def build_news_html(data):
    items_html = ""
    for item in data["items"]:
        lo = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else "<span>"
        lc = "</a>" if item["link"] else "</span>"
        items_html += f"""
        <div class="news-item">
          <div class="news-meta"><span class="news-source">{item["source"]}</span></div>
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
.news-header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ff2d78;padding-bottom:10px;margin-bottom:24px}}
.news-label{{font-size:13px;font-weight:700;letter-spacing:.12em;color:#ff2d78;text-transform:uppercase}}
.news-updated{{font-size:11px;color:#888;letter-spacing:.04em}}
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.news-item{{background:#111;border:1px solid #222;border-radius:8px;padding:16px 18px;transition:border-color .2s}}
.news-item:hover{{border-color:#ff2d78}}
.news-meta{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
.news-source{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#ff2d78;background:rgba(255,45,120,.1);padding:2px 8px;border-radius:20px;text-transform:uppercase}}
.news-title a,.news-title span{{font-size:13px;font-weight:600;color:#eee;text-decoration:none;line-height:1.5;display:block;margin-bottom:6px}}
.news-title a:hover{{color:#ff2d78}}
.news-summary{{font-size:12px;color:#888;line-height:1.7}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_html(news_html, path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
                         news_html, content, flags=re.DOTALL)
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 已更新 {path}")


# ── 主流程 ─────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.date.today()
    period = today.strftime("%Y%m")
    today_str = today.strftime("%Y-%m-%d")
    print(f"=== 开始更新 {period} ===")

    client = get_client()
    history = load_history()
    results = {}

    # 1. 统计局 Macro 数据
    print("\n--- 统计局宏观数据 ---")
    stats = fetch_stats_gov_macro()
    macro_scores = build_macro_scores(stats)

    # 2. Heat Score 打分
    print("\n--- Heat Score 打分 ---")
    for track in TRACKS:
        print(f"  处理: {track['id']}")
        # Macro 赛道用统计局数据
        if track["board"] == "Macro":
            scores = macro_scores.get(track["id"],
                {"D": 50, "C": 50, "P": 50, "Pol": 50,
                 "core_data": "统计局数据待更新", "comment": ""})
        else:
            news = fetch_news_for_track(track)
            print(f"    新闻: {len(news)}条")
            scores = score_track(client, track, news)
        heat = calc_heat(scores)
        prev_heat = get_prev_heat(history, track["id"])
        trend = calc_trend(heat, prev_heat)
        results[track["id"]] = {"heat": heat, "trend": trend, "scores": scores}
        print(f"    Heat={heat} Trend={trend} D={scores['D']} C={scores['C']} P={scores['P']} Pol={scores['Pol']}")
        if scores.get("core_data") and scores["core_data"] not in ("解析失败","本期无有效新闻数据","统计局数据待更新"):
            print(f"    摘要: {scores['core_data']}")

    # 3. 板块综合分
    board_heats = {}
    for board, weights in BOARD_WEIGHTS.items():
        total_w, total_score = 0, 0
        for tid, w in weights.items():
            if tid in results:
                total_score += results[tid]["heat"] * w
                total_w += w
        board_heats[board] = round(total_score / total_w, 1) if total_w else 50
    print("\n板块综合分:")
    for b, h in board_heats.items():
        print(f"  {b}: {h}")

    # 4. 保存历史
    save_history(history, period, results)

    # 5. 更新 data.js
    print("\n--- 更新 data.js ---")
    update_data_js(stats, today_str)

    # 6. 制药装备新闻
    print("\n--- 制药装备行业动态 ---")
    pharma_raw = fetch_pharma_news()
    print(f"[INFO] 抓取 {len(pharma_raw)} 条")
    if pharma_raw:
        pharma_data = summarize_pharma(client, pharma_raw)
        if pharma_data["items"]:
            inject_html(build_news_html(pharma_data), "pharma.html")

    print(f"\n=== 全部完成 {today_str} ===")
