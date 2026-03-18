import os
import re
import datetime
import feedparser
import anthropic


GOOGLE_NEWS_FEEDS_PHARMA = [
    ("制药装备动态", "https://news.google.com/rss/search?q=制药装备&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("龙头企业", "https://news.google.com/rss/search?q=楚天科技+OR+东富龙+OR+森松国际&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国产替代", "https://news.google.com/rss/search?q=生物制药设备+国产替代&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("政策监管", "https://news.google.com/rss/search?q=制药装备+政策+NMPA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]

GOOGLE_NEWS_FEEDS_MACRO = [
    ("宏观经济", "https://news.google.com/rss/search?q=中国GDP增速+国家统计局&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("工业数据", "https://news.google.com/rss/search?q=中国工业增加值+制造业固定资产投资&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("外贸数据", "https://news.google.com/rss/search?q=中国出口增速+商务部&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("PPI数据", "https://news.google.com/rss/search?q=中国PPI+生产者价格指数&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]


def get_minimax_client():
    return anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
    )


def collect_news(feeds):
    all_items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    for source_name, url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                published = entry.get("published_parsed")
                if published:
                    pub_dt = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                all_items.append({
                    "source": source_name,
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:300],
                    "date": entry.get("published", ""),
                })
            print(f"[OK] {source_name}: {len(feed.entries)} 条")
        except Exception as e:
            print(f"[WARN] {source_name} 抓取失败: {e}")
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:20]


# ── 制药装备：生成新闻摘要 ────────────────────────────────────

def summarize_pharma_news(raw_items):
    client = get_minimax_client()
    items_text = "\n\n".join([
        f"[{idx+1}] 来源：{i['source']}\n标题：{i['title']}\n链接：{i['link']}"
        for idx, i in enumerate(raw_items[:12])
    ])
    today = datetime.date.today().strftime("%Y年%m月%d日")
    prompt = f"""你是制药装备行业分析师。从以下新闻中筛选8条最相关的，每条写一句50字摘要。

只返回如下格式，每条一行，不要其他文字：
序号|来源|标题|摘要|链接

新闻列表：
{items_text}"""

    message = client.messages.create(
        model="MiniMax-M2.5-highspeed",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = next(b.text for b in message.content if b.type == "text").strip()
    items = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("序号"):
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            items.append({
                "source": parts[1].strip(),
                "title": parts[2].strip(),
                "summary": parts[3].strip(),
                "link": parts[4].strip(),
                "date": ""
            })
    return {"updated": today, "items": items[:10]}


# ── 宏观数据：提取最新指标数值 ───────────────────────────────

def extract_macro_data(raw_items):
    client = get_minimax_client()
    items_text = "\n\n".join([
        f"标题：{i['title']}\n内容：{i['summary']}"
        for i in raw_items[:15]
    ])
    prompt = f"""你是中国宏观经济数据分析师。从以下最新新闻中提取五个指标的最新数值。

如果某个指标在新闻中找不到明确数据，保留原值不变（原值已在括号中给出）。
只返回如下格式，不要其他文字：

GDP增速|数值|趋势描述
工业增加值|数值|趋势描述
制造业固投|数值|趋势描述
出口增速|数值|趋势描述
PPI|数值|趋势描述

原值参考（找不到新数据时保留）：
GDP增速|5.0|+0.2%
工业增加值|6.2|↑ Upward
制造业固投|11.4|Stable
出口增速|4.8|Shift
PPI|1.2|Recovery

新闻内容：
{items_text}"""

    message = client.messages.create(
        model="MiniMax-M2.5-highspeed",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = next(b.text for b in message.content if b.type == "text").strip()

    result = {}
    for line in raw_text.strip().split("\n"):
        parts = line.strip().split("|")
        if len(parts) >= 3:
            result[parts[0].strip()] = {
                "value": parts[1].strip(),
                "trend": parts[2].strip()
            }
    return result


def update_data_js(macro_data):
    """把提取到的宏观数据写入 data.js"""
    with open("data.js", "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.date.today().strftime("%Y-%m-%d")

    # 更新 lastUpdated
    content = re.sub(
        r'lastUpdated:\s*"[^"]*"',
        f'lastUpdated: "{today}"',
        content
    )

    # 指标名映射
    field_map = {
        "GDP增速":   ("GDP GROWTH",    "GDP 增速"),
        "工业增加值": ("IND. VALUE ADD", "工业增加值"),
        "制造业固投": ("MFG. CAPEX",    "制造业固投"),
        "出口增速":   ("EXPORT GROWTH", "出口增速"),
        "PPI":       ("PPI TREND",     "PPI 走势"),
    }

    for key, (label_en, label_zh) in field_map.items():
        if key not in macro_data:
            continue
        new_value = macro_data[key]["value"]
        new_trend = macro_data[key]["trend"]

        # 尝试转为数字
        try:
            num = float(new_value.replace("%", "").replace("+", "").strip())
        except ValueError:
            num = None

        if num is not None:
            # 更新 value（找到对应 labelEn 后的 value 字段）
            content = re.sub(
                rf'(labelEn:\s*"{re.escape(label_en)}"[^}}]*?value:\s*)[0-9.-]+',
                rf'\g<1>{num}',
                content,
                flags=re.DOTALL
            )

        # 更新 trend
        content = re.sub(
            rf'(labelEn:\s*"{re.escape(label_en)}"[^}}]*?trend:\s*")[^"]*"',
            rf'\g<1>{new_trend}"',
            content,
            flags=re.DOTALL
        )

    with open("data.js", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] data.js 宏观数据已更新：{today}")
    for k, v in macro_data.items():
        print(f"     {k}: {v['value']} / {v['trend']}")


# ── HTML 新闻模块 ────────────────────────────────────────────

def build_news_html(data):
    items_html = ""
    for item in data["items"]:
        link_open = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else "<span>"
        link_close = "</a>" if item["link"] else "</span>"
        items_html += f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-source">{item["source"]}</span>
          </div>
          <div class="news-title">{link_open}{item["title"]}{link_close}</div>
          <div class="news-summary">{item["summary"]}</div>
        </div>"""

    return f"""<!-- NEWS_BLOCK_START -->
<section class="news-section" id="latest-news">
  <div class="news-header">
    <span class="news-label">行业动态 LATEST NEWS</span>
    <span class="news-updated">数据更新：{data["updated"]}</span>
  </div>
  <div class="news-grid">
    {items_html}
  </div>
</section>
<style>
.news-section {{
  margin: 60px auto 40px;
  max-width: 1200px;
  padding: 0 24px;
  font-family: inherit;
}}
.news-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #ff2d78;
  padding-bottom: 10px;
  margin-bottom: 24px;
}}
.news-label {{
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .12em;
  color: #ff2d78;
  text-transform: uppercase;
}}
.news-updated {{
  font-size: 11px;
  color: #888;
  letter-spacing: .04em;
}}
.news-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}}
.news-item {{
  background: #111;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 16px 18px;
  transition: border-color .2s;
}}
.news-item:hover {{
  border-color: #ff2d78;
}}
.news-meta {{
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}}
.news-source {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  color: #ff2d78;
  background: rgba(255,45,120,.1);
  padding: 2px 8px;
  border-radius: 20px;
  text-transform: uppercase;
}}
.news-title a,
.news-title span {{
  font-size: 13px;
  font-weight: 600;
  color: #eee;
  text-decoration: none;
  line-height: 1.5;
  display: block;
  margin-bottom: 6px;
}}
.news-title a:hover {{
  color: #ff2d78;
}}
.news-summary {{
  font-size: 12px;
  color: #888;
  line-height: 1.7;
}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_into_html(news_html, html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(
            r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
            news_html,
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 已更新 {html_path}")


# ── 主流程 ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 开始更新 ===")

    # 1. 制药装备新闻
    print("\n--- 制药装备行业动态 ---")
    pharma_raw = collect_news(GOOGLE_NEWS_FEEDS_PHARMA)
    print(f"[INFO] 抓取 {len(pharma_raw)} 条")
    if pharma_raw:
        pharma_data = summarize_pharma_news(pharma_raw)
        print(f"[OK] 生成 {len(pharma_data['items'])} 条摘要")
        if pharma_data["items"]:
            news_html = build_news_html(pharma_data)
            inject_into_html(news_html, "pharma.html")

    # 2. 宏观数据更新
    print("\n--- 宏观经济指标 ---")
    macro_raw = collect_news(GOOGLE_NEWS_FEEDS_MACRO)
    print(f"[INFO] 抓取 {len(macro_raw)} 条")
    if macro_raw:
        macro_data = extract_macro_data(macro_raw)
        print(f"[OK] 提取 {len(macro_data)} 个指标")
        if macro_data:
            update_data_js(macro_data)

    print("\n=== 全部完成 ===")
