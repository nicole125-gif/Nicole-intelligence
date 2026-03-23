#!/usr/bin/env python3
"""
宏观Dashboard自动更新脚本
用法: python update_macro.py
依赖: pip install requests
"""

import re
import json
import os
import subprocess
from datetime import datetime

# ── 配置区 ────────────────────────────────────────────────
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")  # 从环境变量读取
MINIMAX_GROUP_ID = os.environ.get("MINIMAX_GROUP_ID", "")
HTML_FILE = "index.html"  # 相对于仓库根目录

# ── 要更新的数据结构 ──────────────────────────────────────
# 目前只更新summaryStats（最安全的起点）
# 后续可扩展到METRICS数组、SBU_LIST等

PROMPT_SUMMARY_STATS = """
你是一位中国宏观经济分析师。请根据当前（{date}）最新数据，
生成以下4个宏观指标的简短判断，严格按JSON格式返回，不要任何多余文字：

{{
  "summaryStats": [
    {{ "label": "综合景气度", "value": "Expansionary" }},
    {{ "label": "政策向量",   "value": "Targeted Easing" }},
    {{ "label": "外部压力指数", "value": "Moderate" }},
    {{ "label": "数字经济比重", "value": "43.7%" }}
  ],
  "updateNote": "一句话说明本次更新的主要变化"
}}

value字段保持英文或数字，要求简洁（1-2个词或数字+单位）。
""".format(date=datetime.now().strftime("%Y-%m-%d"))


# ── 核心函数 ──────────────────────────────────────────────

def call_minimax(prompt: str) -> dict:
    """调用MiniMax API，返回解析后的JSON"""
    import urllib.request
    
    url = f"https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINIMAX_API_KEY}"
    }
    payload = {
        "model": "abab6.5s-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    
    # 提取文本内容
    content = result["choices"][0]["message"]["content"]
    
    # 清理可能的markdown代码块
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()
    
    return json.loads(content)


def read_html(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_html(filepath: str, content: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ 已写入 {filepath}")


def update_summary_stats(html: str, new_stats: list) -> str:
    """
    替换JS数据中的summaryStats数组。
    目标模式（来自index.html第22-27行）：
      summaryStats: [
        { label: "...", value: "..." },
        ...
      ],
    """
    # 构建新的summaryStats字符串
    lines = ["    summaryStats: ["]
    for i, stat in enumerate(new_stats):
        comma = "," if i < len(new_stats) - 1 else ""
        lines.append(f'      {{ label: "{stat["label"]}",   value: "{stat["value"]}" }}{comma}')
    lines.append("    ],")
    new_block = "\n".join(lines)
    
    # 正则替换：匹配从summaryStats:[到下一个],
    pattern = r'    summaryStats:\s*\[.*?\],'
    new_html = re.sub(pattern, new_block, html, flags=re.DOTALL)
    
    if new_html == html:
        print("⚠️  summaryStats未找到匹配，跳过更新")
    else:
        print("✓ summaryStats已更新")
    
    return new_html


def update_meta_timestamp(html: str) -> str:
    """更新文件头部的更新时间戳"""
    today = datetime.now().strftime("%Y-%m-%d")
    # 匹配 "2026-02-28" 这类日期字符串（在注释行）
    pattern = r'("20\d{2}-\d{2}-\d{2}")'
    new_html = re.sub(pattern, f'"{today}"', html, count=1)
    print(f"✓ 时间戳已更新为 {today}")
    return new_html


def git_commit_push(filepath: str, message: str):
    """自动commit并push到GitHub"""
    cmds = [
        ["git", "add", filepath],
        ["git", "commit", "-m", message],
        ["git", "push"]
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  {' '.join(cmd)} 失败: {result.stderr}")
        else:
            print(f"✓ {' '.join(cmd)}")


# ── 主流程 ────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")
    
    # 1. 读取HTML
    html = read_html(HTML_FILE)
    print(f"✓ 已读取 {HTML_FILE}（{len(html):,} 字符）")
    
    # 2. 调用MiniMax生成新数据
    if MINIMAX_API_KEY:
        print("\n[ 调用 MiniMax API... ]")
        try:
            data = call_minimax(PROMPT_SUMMARY_STATS)
            new_stats = data.get("summaryStats", [])
            note = data.get("updateNote", "")
            print(f"✓ API返回 {len(new_stats)} 个指标")
            if note:
                print(f"  更新说明: {note}")
        except Exception as e:
            print(f"⚠️  API调用失败: {e}")
            print("  使用备用数据...")
            new_stats = [
                {"label": "综合景气度", "value": "Expansionary"},
                {"label": "政策向量",   "value": "Targeted Easing"},
                {"label": "外部压力指数", "value": "Moderate"},
                {"label": "数字经济比重", "value": "43.7%"}
            ]
    else:
        print("⚠️  未设置MINIMAX_API_KEY，使用测试数据")
        new_stats = [
            {"label": "综合景气度", "value": "Expansionary"},
            {"label": "政策向量",   "value": "Targeted Easing"},
            {"label": "外部压力指数", "value": "Moderate"},
            {"label": "数字经济比重", "value": "44.1%"}  # 模拟一个变化
        ]
    
    # 3. 写入HTML
    print("\n[ 更新HTML... ]")
    html = update_summary_stats(html, new_stats)
    html = update_meta_timestamp(html)
    write_html(HTML_FILE, html)
    
    # 4. Git提交
    commit_msg = f"auto: 宏观数据更新 {datetime.now().strftime('%Y-%m-%d')}"
    print(f"\n[ Git提交... ]")
    git_commit_push(HTML_FILE, commit_msg)
    
    print(f"\n{'='*50}")
    print("✅ 更新完成")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
