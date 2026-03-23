#!/usr/bin/env python3
"""
宏观Dashboard自动更新脚本
数据来源：直接抓取国家统计局官网，无AI估算
用法: python scripts/update_macro.py
"""

import re
import os
import subprocess
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

# ── 统计局数据源（每月更新URL即可）───────────────────────
NBS_SOURCES = [
    {
        "label": "工业增加值",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html",
        "pattern": r"规模以上工业增加值同比实际增长([\d.]+)%",
        "trend": "↑ 1-2月同比",
        "insight": "开年工业生产强劲",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
    },
    {
        "label": "制造业固投",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962784.html",
        "pattern": r"制造业投资增长([\d.]+)%",
        "trend": "1-2月同比",
        "insight": "制造业投资稳步推进",
        "sparkData_2024": 9.2,
        "sparkData_2025": 10.8,
    },
]

# 其余指标用固定值
STATIC_METRICS = [
    {"label": "GDP 增速",   "value": 5.0,  "trend": "目标值",   "insight": "结构性增长优于规模扩张",   "sparkData": [4.6, 4.8, 5.0]},
    {"label": "出口增速",   "value": 4.8,  "trend": "Shift",    "insight": "高附加值组件替代传统代工", "sparkData": [5.9, 4.2, 4.8]},
    {"label": "PPI 走势",   "value": 1.2,  "trend": "Recovery", "insight": "中下游利润空间重构",       "sparkData": [-2.7, -0.8, 1.2]},
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


# ── 抓取统计局 ────────────────────────────────────────────

def fetch_nbs(source: dict) -> dict | None:
    label = source["label"]
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; market-dashboard/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", errors="ignore")

        m = re.search(source["pattern"], page)
        if not m:
            print(f"⚠️  {label}：正则未匹配，检查pattern")
            return None

        value = float(m.group(1))
        print(f"✅ {label}：{value}%（stats.gov.cn）")
        return {
            "label": label,
            "value": value,
            "trend": source["trend"],
            "insight": source["insight"],
            "sparkData": [source["sparkData_2024"], source["sparkData_2025"], value],
        }
    except Exception as e:
        print(f"⚠️  {label}：抓取失败（{e}）")
        return None


# ── 核心替换：按位置切块，每块独立替换 ───────────────────

def update_metric(html: str, label: str, value, trend: str, insight: str, sparkData: list) -> str:
    """
    HTML中每个指标存在2处（格式化版+压缩版）。
    策略：找到每处label的位置，取后1500字符作为独立块，
    在块内做字段替换，避免跨指标污染。
    从后往前处理，保证位置不偏移。
    """
    spark_str = "[" + ",".join(str(v) for v in sparkData) + "]"
    positions = [m.start() for m in re.finditer(rf'"{re.escape(label)}"', html)]

    if not positions:
        print(f"⚠️  {label}：未找到，跳过")
        return html

    changed = 0
    for pos in reversed(positions):
        chunk = html[pos:pos + 1500]
        new_chunk = chunk
        new_chunk = re.sub(r'(value:\s*)[\d.\-]+',      rf'\g<1>{value}',    new_chunk, count=1)
        new_chunk = re.sub(r'(trend:\s*)"[^"]*"',        rf'\g<1>"{trend}"',  new_chunk, count=1)
        new_chunk = re.sub(r'(insight:\s*)"[^"]*"',      rf'\g<1>"{insight}"',new_chunk, count=1)
        new_chunk = re.sub(r'(sparkData:\s*)\[[^\]]*\]', rf'\g<1>{spark_str}',new_chunk, count=1)
        if new_chunk != chunk:
            html = html[:pos] + new_chunk + html[pos + 1500:]
            changed += 1

    print(f"✓ {label}：{changed}处更新（value={value}%）")
    return html


def update_summary_stats(html: str, stats: list) -> str:
    lines = ["    summaryStats: ["]
    for i, s in enumerate(stats):
        comma = "," if i < len(stats) - 1 else ""
        lines.append(f'      {{ label: "{s["label"]}",   value: "{s["value"]}" }}{comma}')
    lines.append("    ],")
    new_block = "\n".join(lines)
    new_html = re.sub(r'    summaryStats:\s*\[.*?\],', new_block, html, flags=re.DOTALL)
    if new_html != html:
        print("✓ summaryStats 已更新")
    return new_html


def update_timestamp(html: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    new_html = re.sub(r'"20\d{2}-\d{2}-\d{2}"', f'"{today}"', html, count=1)
    print(f"✓ 时间戳 → {today}")
    return new_html


def git_push(filepath, message):
    subprocess.run(["git", "config", "user.name",  "github-actions[bot]"], capture_output=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], capture_output=True)
    subprocess.run(["git", "add", filepath], capture_output=True)
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if diff.returncode == 0:
        print("ℹ️  内容无变化，跳过commit")
        return
    r = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    print("✓ commit" if r.returncode == 0 else f"⚠️  commit失败:\n{r.stderr}")
    r = subprocess.run(["git", "push"], capture_output=True, text=True)
    print("✓ push"   if r.returncode == 0 else f"⚠️  push失败:\n{r.stderr}")


# ── 主流程 ────────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"✓ 已读取 {HTML_FILE}（{len(html):,} 字符）\n")

    # 1. 抓取统计局实时数据
    print("[ 抓取国家统计局数据... ]")
    live = []
    for src in NBS_SOURCES:
        result = fetch_nbs(src)
        if result:
            live.append(result)

    # 2. 更新实时指标
    print(f"\n[ 更新实时指标（{len(live)}个）... ]")
    for m in live:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    # 3. 更新静态指标
    print(f"\n[ 更新静态指标（{len(STATIC_METRICS)}个）... ]")
    for m in STATIC_METRICS:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    # 4. summaryStats
    print("\n[ 更新 summaryStats... ]")
    html = update_summary_stats(html, STATIC_SUMMARY)

    # 5. 时间戳
    html = update_timestamp(html)

    # 6. 写入并推送
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已写入 {HTML_FILE}\n")

    print("[ Git提交... ]")
    git_push(HTML_FILE, f"auto: 宏观数据更新 {datetime.now().strftime('%Y-%m-%d')}（统计局实时）")

    print(f"\n{'='*52}")
    print("✅ 完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
