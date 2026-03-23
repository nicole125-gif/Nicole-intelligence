#!/usr/bin/env python3
"""
宏观Dashboard更新脚本
数据来源：tradingeconomics.com（无需API key）
自动对比Last vs Previous，生成方向判断trend
git操作由workflow负责
"""

import re
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

INDICATOR_MAP = {
    "工业增加值": {
        "te_name":        "Industrial Production",
        "insight_tmpl":   "开年生产强劲，好于预期",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
    },
    "出口增速": {
        "te_name":        "Exports YoY",
        "insight_tmpl":   "出口超预期，抢出口效应显著",
        "sparkData_2024": 5.9,
        "sparkData_2025": 4.2,
    },
    "GDP 增速": {
        "te_name":        "GDP Annual Growth Rate",
        "insight_tmpl":   "增速温和，内需仍待提振",
        "sparkData_2024": 4.6,
        "sparkData_2025": 4.8,
    },
    "制造业PMI": {
        "te_name":        "NBS Manufacturing PMI",
        "insight_tmpl":   "连续扩张，景气度回升",
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
    """对比当期vs上期，生成方向判断文字"""
    if previous is None:
        return "最新数据"
    diff = round(value - previous, 2)
    # PPI是负值越接近0越好（通缩收窄）
    if "PPI" in label:
        if value > previous:
            return f"↑ 通缩收窄 ({diff:+.1f})"
        elif value < previous:
            return f"↓ 通缩扩大 ({diff:+.1f})"
        else:
            return "→ 持平上期"
    # PMI以50为荣枯线
    if "PMI" in label:
        if value >= 50 and previous < 50:
            return "↑ 重回扩张区"
        elif value < 50 and previous >= 50:
            return "↓ 跌入收缩区"
        elif value > previous:
            return f"↑ 较上期改善 ({diff:+.1f})"
        elif value < previous:
            return f"↓ 较上期回落 ({diff:+.1f})"
        else:
            return "→ 持平上期"
    # 其他指标
    if value > previous:
        return f"↑ 较上期加速 ({diff:+.1f}%)"
    elif value < previous:
        return f"↓ 较上期放缓 ({diff:+.1f}%)"
    else:
        return "→ 持平上期"


def fetch_te_table() -> dict:
    """
    抓取 /china/indicators 总览表格
    返回 {指标名: {"last": float, "previous": float}} 字典
    同时抓 Last 和 Previous 两列
    """
    url = "https://tradingeconomics.com/china/indicators"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", errors="ignore")

    results = {}
    # 格式：名称\n</a></td>\n<td>Last</td>\n<td>Previous</td>
    rows = re.findall(
        r'([^\n<]+)\s*\n\s*</a></td>\s*\n\s*<td>([-\d.]+)</td>\s*\n\s*<td>([-\d.]+)</td>',
        page
    )
    for name, last, prev in rows:
        name = name.strip()
        try:
            results[name] = {"last": float(last), "previous": float(prev)}
        except ValueError:
            pass
    return results


def fetch_ppi() -> dict | None:
    """单独抓取PPI页面，同时从页面提取当期和上期值"""
    url = "https://tradingeconomics.com/china/producer-prices-change"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", errors="ignore")

    # 当期值
    m = re.search(
        r'Producer Prices in China (decreased|increased|fell|rose) ([\d.]+) percent in (\w+ of \d{4})',
        page
    )
    if not m:
        print("⚠️  PPI: 未匹配")
        return None

    direction, raw_value, date_str = m.group(1), float(m.group(2)), m.group(3)
    value = -raw_value if direction in ("decreased", "fell") else raw_value

    # 上期值：从"easing from a X.X% decline"或"slowing from a X.X% fall"提取
    prev_m = re.search(r'(?:easing|slowing|accelerating) from (?:a |an )?([\d.]+)%', page)
    previous = None
    if prev_m:
        prev_raw = float(prev_m.group(1))
        # 上期也是decline/fall，所以是负值
        previous = -prev_raw

    trend = make_trend(value, previous, label="PPI")
    print(f"✅ PPI 走势: {value}% vs 上期{previous}% → {trend}")
    return {
        "label":     "PPI 走势",
        "value":     value,
        "trend":     trend,
        "insight":   "通缩持续收窄，价格企稳信号",
        "sparkData": [-2.7, -0.8, value],
    }


def update_metric(html, label, value, trend, insight, sparkData):
    """替换HTML中某指标的value/trend/insight/sparkData，两处都改"""
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
        if new_chunk != chunk:
            html = html[:pos] + new_chunk + html[pos+1500:]
            changed += 1
    print(f"{'✅' if changed else '⚠️ '} {label}: {changed}处写入 → {value} | {trend}")
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

    # 1. 总览表格
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
            last     = te_data[te_name]["last"]
            previous = te_data[te_name]["previous"]
            trend    = make_trend(last, previous, label=label)
            insight  = cfg["insight_tmpl"]
            spark    = [cfg["sparkData_2024"], cfg["sparkData_2025"], last]
            print(f"✅ {label}: {last} vs 上期{previous} → {trend}")
            html = update_metric(html, label, last, trend, insight, spark)
        else:
            print(f"⚠️  {label}: 表格中未找到 '{te_name}'")

    # 2. PPI单独抓取
    print("\n[ 抓取PPI... ]")
    try:
        ppi = fetch_ppi()
        if ppi:
            html = update_metric(html, ppi["label"], ppi["value"],
                                 ppi["trend"], ppi["insight"], ppi["sparkData"])
    except Exception as e:
        print(f"❌ PPI抓取失败: {e}")

    # 3. summaryStats
    print("\n[ summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 写入完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
