#!/usr/bin/env python3
"""
宏观Dashboard更新脚本
数据来源：AkShare（封装东方财富等境内外数据源）
git操作由workflow负责
"""

import re
import sys
from datetime import datetime

HTML_FILE = "index.html"

# ── 数据源配置 ────────────────────────────────────────────
SOURCES = [
    {
        "label":           "工业增加值",
        "ak_func":         "macro_china_industrial_production_yoy",
        "value_col":       "今值",       # AkShare返回的数值列名
        "date_col":        "日期",
        "trend_template":  "↑ {date}同比",
        "insight":         "工业生产持续扩张",
        "sparkData_2024":  5.1,
        "sparkData_2025":  5.7,
    },
    {
        "label":           "PPI 走势",
        "ak_func":         "macro_china_ppi",
        "value_col":       "今值",
        "date_col":        "日期",
        "trend_template":  "{date}同比",
        "insight":         "中下游利润空间重构",
        "sparkData_2024":  -2.7,
        "sparkData_2025":  -0.8,
    },
]

# 无法自动获取的指标，保持固定值
STATIC_METRICS = [
    {"label": "GDP 增速",  "value": 5.0, "trend": "目标值",   "insight": "结构性增长优于规模扩张",   "sparkData": [4.6, 4.8, 5.0]},
    {"label": "制造业固投","value": 3.1, "trend": "1-2月同比","insight": "制造业投资稳步推进",       "sparkData": [9.2, 10.8, 3.1]},
    {"label": "出口增速",  "value": 4.8, "trend": "Shift",    "insight": "高附加值组件替代传统代工", "sparkData": [5.9, 4.2, 4.8]},
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


def fetch_akshare(source: dict) -> dict | None:
    """通过AkShare获取最新宏观数据"""
    import akshare as ak
    label = source["label"]
    try:
        func = getattr(ak, source["ak_func"])
        df = func()
        # 取最新一行
        latest = df.iloc[-1]
        value = float(latest[source["value_col"]])
        date_raw = str(latest[source["date_col"]])[:7]  # 取年月，如"2026-02"
        trend = source["trend_template"].format(date=date_raw)
        spark = [source["sparkData_2024"], source["sparkData_2025"], value]
        print(f"✅ {label}: {value}%（{date_raw}，AkShare）")
        return {
            "label": label, "value": value,
            "trend": trend, "insight": source["insight"],
            "sparkData": spark,
        }
    except Exception as e:
        print(f"⚠️  {label}: AkShare获取失败（{e}）")
        return None


def update_metric(html: str, label: str, value, trend: str, insight: str, sparkData: list) -> str:
    spark_str = "[" + ",".join(str(v) for v in sparkData) + "]"
    positions = [m.start() for m in re.finditer(rf'"{re.escape(label)}"', html)]
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
    print(f"{'✅' if changed else '⚠️ '} {label}: {changed}处更新 → {value}%")
    return html


def update_summary(html: str, stats: list) -> str:
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

    # 1. AkShare实时数据
    print("[ 获取AkShare实时数据... ]")
    for src in SOURCES:
        result = fetch_akshare(src)
        if result:
            html = update_metric(html, result["label"], result["value"],
                                 result["trend"], result["insight"], result["sparkData"])

    # 2. 静态指标
    print("\n[ 更新静态指标... ]")
    for m in STATIC_METRICS:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    # 3. summaryStats
    print("\n[ 更新summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 写入完成")
    print(f"\n{'='*52}")
    print("✅ 脚本完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
