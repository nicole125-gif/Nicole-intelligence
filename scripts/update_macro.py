#!/usr/bin/env python3
"""
宏观Dashboard更新脚本
数据来源：tradingeconomics.com（无需API key）
自动对比Last vs Previous，生成方向判断trend
卡片右上角显示数据日期（格式：Feb/26）
git操作由workflow负责
"""

import re
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

INDICATOR_MAP = {
    "工业增加值": {
        "te_name":        "Industrial Production",
        "insight":        "开年生产强劲，好于预期",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
    },
    "出口增速": {
        "te_name":        "Exports YoY",
        "insight":        "出口超预期，抢出口效应显著",
        "sparkData_2024": 5.9,
        "sparkData_2025": 4.2,
    },
    "GDP 增速": {
        "te_name":        "GDP Annual Growth Rate",
        "insight":        "增速温和，内需仍待提振",
        "sparkData_2024": 4.6,
        "sparkData_2025": 4.8,
    },
    "制造业PMI": {
        "te_name":        "NBS Manufacturing PMI",
        "insight":        "连续扩张，景气度回升",
        "sparkData_2024": 50.2,
        "sparkData_2025": 50.1,
    },
}

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def make_trend(value, previous, label="") -> str:
    if previous is None:
        return "最新数据"
    diff = round(value - previous, 2)
    if "PPI" in label:
        if value > previous:   return f"↑ 通缩收窄 ({diff:+.1f})"
        elif value < previous: return f"↓ 通缩扩大 ({diff:+.1f})"
        else:                  return "→ 持平上期"
    if "PMI" in label:
        if value >= 50 and previous < 50:   return "↑ 重回扩张区"
        elif value < 50 and previous >= 50: return "↓ 跌入收缩区"
        elif value > previous:  return f"↑ 较上期改善 ({diff:+.1f})"
        elif value < previous:  return f"↓ 较上期回落 ({diff:+.1f})"
        else:                   return "→ 持平上期"
    if value > previous:   return f"↑ 较上期加速 ({diff:+.1f}%)"
    elif value < previous: return f"↓ 较上期放缓 ({diff:+.1f}%)"
    else:                  return "→ 持平上期"


def fetch_te_table() -> dict:
    """抓取总览表格，返回 {名称: {last, previous, date}} 字典"""
    url = "https://tradingeconomics.com/china/indicators"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", errors="ignore")

    results = {}
    # 格式：名称\n</a></td>\n<td>Last</td>\n<td>Previous</td>\n...\n<td>Date</td>
    # 先抓 Last + Previous
    rows = re.findall(
        r'([^\n<]+)\s*\n\s*</a></td>\s*\n\s*<td>([-\d.]+)</td>\s*\n\s*<td>([-\d.]+)</td>(?:.*?<td>(\w+/\d+)</td>)?',
        page, re.DOTALL
    )
    for row in rows:
        name = row[0].strip()
        try:
            last = float(row[1])
            prev = float(row[2])
            date = row[3] if row[3] else ""
            results[name] = {"last": last, "previous": prev, "date": date}
        except ValueError:
            pass
    return results


def fetch_ppi() -> dict | None:
    """单独抓取PPI页面"""
    url = "https://tradingeconomics.com/china/producer-prices-change"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", errors="ignore")

    m = re.search(
        r'Producer Prices in China (decreased|increased|fell|rose) ([\d.]+) percent in (\w+) of (\d{4})',
        page
    )
    if not m:
        print("⚠️  PPI: 未匹配")
        return None

    direction, raw_value = m.group(1), float(m.group(2))
    month, year = m.group(3)[:3], m.group(4)[2:]
    value = -raw_value if direction in ("decreased", "fell") else raw_value
    date_str = f"{month}/{year}"

    prev_m = re.search(r'(?:easing|slowing|accelerating) from (?:a |an )?([\d.]+)%', page)
    previous = -float(prev_m.group(1)) if prev_m else None

    trend = make_trend(value, previous, label="PPI")
    print(f"✅ PPI 走势: {value}% → {trend} | {date_str}")
    return {
        "label":   "PPI 走势",
        "value":   value,
        "trend":   trend,
        "insight": "通缩持续收窄，价格企稳信号",
        "spark":   [-2.7, -0.8, value],
        "date":    date_str,
    }


def update_metric(html, label, value, trend, insight, sparkData, date=""):
    """替换HTML中某指标的所有字段，两处都改"""
    spark_str = "[" + ",".join(str(v) for v in sparkData) + "]"
    positions = [m.start() for m in re.finditer(rf'"{re.escape(label)}"', html)]
    if not positions:
        print(f"⚠️  {label}: HTML中未找到")
        return html
    changed = 0
    for pos in reversed(positions):
        chunk = html[pos:pos+1500]
        new_chunk = chunk
        new_chunk = re.sub(r'(value:\s*)[\d.\-]+',      rf'\g<1>{value}',     new_chunk, count=1)
        new_chunk = re.sub(r'(trend:\s*)"[^"]*"',        rf'\g<1>"{trend}"',   new_chunk, count=1)
        new_chunk = re.sub(r'(insight:\s*)"[^"]*"',      rf'\g<1>"{insight}"', new_chunk, count=1)
        new_chunk = re.sub(r'(sparkData:\s*)\[[^\]]*\]', rf'\g<1>{spark_str}', new_chunk, count=1)
        # 更新date字段（如已存在则替换，否则追加）
        if date:
            if re.search(r'date:\s*"[^"]*"', new_chunk):
                new_chunk = re.sub(r'(date:\s*)"[^"]*"', rf'\1"{date}"', new_chunk, count=1)
            else:
                new_chunk = re.sub(
                    r'(sparkData:\s*\[[^\]]*\])',
                    rf'\1, date: "{date}"',
                    new_chunk, count=1
                )
        if new_chunk != chunk:
            html = html[:pos] + new_chunk + html[pos+1500:]
            changed += 1
    print(f"{'✅' if changed else '⚠️ '} {label}: {changed}处 → {value} | {trend} | {date}")
    return html


def update_summary(html, stats):
    lines = ["    summaryStats: ["]
    for i, s in enumerate(stats):
        comma = "," if i < len(stats)-1 else ""
        lines.append(f'      {{ label: "{s["label"]}",   value: "{s["value"]}" }}{comma}')
    lines.append("    ],")
    new_html = re.sub(r'    summaryStats:\s*\[.*?\],', "\n".join(lines), html, flags=re.DOTALL)
    if new_html != html:
        print("✅ summaryStats 已更新")
    return new_html


def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"✓ 读取 {HTML_FILE}（{len(html):,} 字符）\n")

    print("[ 抓取 tradingeconomics.com/china/indicators... ]")
    try:
        te_data = fetch_te_table()
        print(f"✓ 获取到 {len(te_data)} 个指标\n")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        te_data = {}

    for label, cfg in INDICATOR_MAP.items():
        te_name = cfg["te_name"]
        if te_name in te_data:
            d        = te_data[te_name]
            last     = d["last"]
            previous = d["previous"]
            date     = d.get("date", "")
            trend    = make_trend(last, previous, label=label)
            spark    = [cfg["sparkData_2024"], cfg["sparkData_2025"], last]
            print(f"✅ {label}: {last} vs {previous} → {trend} | {date}")
            html = update_metric(html, label, last, trend, cfg["insight"], spark, date)
        else:
            print(f"⚠️  {label}: 未找到 '{te_name}'")

    print("\n[ 抓取PPI... ]")
    try:
        ppi = fetch_ppi()
        if ppi:
            html = update_metric(html, ppi["label"], ppi["value"],
                                 ppi["trend"], ppi["insight"], ppi["spark"], ppi["date"])
    except Exception as e:
        print(f"❌ PPI失败: {e}")

    print("\n[ summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 写入完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
