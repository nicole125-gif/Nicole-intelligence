import os
import re
import datetime
import feedparser
import anthropic


GOOGLE_NEWS_FEEDS = [
    ("制药装备动态", "https://news.google.com/rss/search?q=制药装备&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("龙头企业", "https://news.google.com/rss/search?q=楚天科技+OR+东富龙+OR+森松国际&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国产替代", "https://news.google.com/rss/search?q=生物制药设备+国产替代&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("政策监管", "https://news.google.com/rss/search?q=制药装备+政策+NMPA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]


def collect_raw_items():
    all_items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    for source_name, url in GOOGLE_NEWS_FEEDS:
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


def summarize_with_minimax(raw_items):
    client = anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
    )
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


def inject_into_html(news_html, html_path="pharma.html"):
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


if __name__ == "__main__":
    print("=== 开始抓取行业动态 ===")
    raw = collect_raw_items()
    print(f"[INFO] 抓取原始条目 {len(raw)} 条")
    if not raw:
        print("[WARN] 无有效条目，跳过更新")
        exit(0)
    print("[INFO] 调用 MiniMax 生成摘要...")
    data = summarize_with_minimax(raw)
    print(f"[OK] 返回 {len(data['items'])} 条摘要")
    if not data["items"]:
        print("[WARN] 摘要为空，跳过更新")
        exit(0)
    news_html = build_news_html(data)
    inject_into_html(news_html, html_path="pharma.html")
    print("=== 完成 ===")
