"""
将制药情报结果注入 PULSE data.js
更新 pharma 赛道的 heat score 和 news 数组
"""

import json
import re
from pathlib import Path
from datetime import datetime

SCORED_FILE = Path("data/pharma_scored.json")
SIGNALS_FILE = Path("data/pharma_signals.json")
DATA_JS = Path("data.js")  # 相对路径，指向 PULSE 根目录

def load_scored():
    f = SCORED_FILE if SCORED_FILE.exists() else SIGNALS_FILE
    with open(f, encoding="utf-8") as fp:
        return json.load(fp)

def format_news_items(signals, max_items=8):
    """把信号转成 PULSE news 格式"""
    items = []
    source_emoji = {
        "NMPA飞检":    "🔴",
        "CDE优先审评": "🟡",
        "巨潮募投公告":"🟢",
        "环评公示":    "🔵",
        "政府采购招标":"⚡",
    }

    for s in signals[:max_items]:
        emoji = source_emoji.get(s["source"], "•")
        intel = s.get("valve_intelligence", {})
        summary = intel.get("summary", s["title"][:40])
        urgency = intel.get("urgency", s["valve_relevance"])

        items.append({
            "date":      s["date"],
            "source":    s["source"],
            "title":     s["title"][:60],
            "summary":   summary,
            "url":       s.get("url", "#"),
            "score":     s["valve_relevance"],
            "urgency":   urgency,
            "action":    s.get("action", ""),
            "lead_time": s.get("lead_time_months", ""),
            "emoji":     emoji
        })

    return items

def inject_to_data_js(data):
    """更新 data.js 中的 pharma 赛道数据"""
    if not DATA_JS.exists():
        print(f"  data.js 不存在于 {DATA_JS}，跳过注入")
        print("  （请把 pharma_scored.json 手动合并到 data.js）")
        return False

    with open(DATA_JS, encoding="utf-8") as f:
        content = f.read()

    heat = data.get("heat_score", 0)
    news = format_news_items(data.get("top_signals", []))
    updated = data.get("updated", datetime.now().strftime("%Y-%m-%d"))

    # 构建替换块
    news_js = json.dumps(news, ensure_ascii=False, indent=4)
    new_block = f"""pharma: {{
        name: "制药·生物制品",
        heat: {heat},
        updated: "{updated}",
        score_breakdown: {json.dumps(data.get("score_breakdown", {}), ensure_ascii=False)},
        signal_counts: {json.dumps(data.get("signal_counts", {}), ensure_ascii=False)},
        news: {news_js}
    }}"""

    # 替换 data.js 中的 pharma 块
    pattern = r'pharma:\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}'
    if re.search(pattern, content):
        content = re.sub(pattern, new_block, content, flags=re.DOTALL)
        with open(DATA_JS, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  data.js 更新成功 → pharma heat: {heat}")
        return True
    else:
        print("  未找到 pharma 块，请手动添加以下内容到 data.js:")
        print(new_block)
        return False

def main():
    print(f"\n{'='*50}")
    print("制药情报注入 PULSE data.js")
    print(f"{'='*50}\n")

    data = load_scored()
    print(f"→ 热度分: {data.get('heat_score')}")
    print(f"→ 信号数: {data.get('signal_counts', {}).get('total', 0)}")

    inject_to_data_js(data)

    # 无论是否注入成功，都输出独立 JSON 供手动使用
    summary_file = Path("data/pharma_summary.json")
    summary = {
        "heat_score": data.get("heat_score"),
        "updated": data.get("updated"),
        "score_breakdown": data.get("score_breakdown"),
        "top_signals": format_news_items(data.get("top_signals", []))
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"→ 摘要文件: {summary_file}")

if __name__ == "__main__":
    main()
