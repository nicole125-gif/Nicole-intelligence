"""
DeepSeek 深度评分模块
输入：fetch_pharma.py 抓取的原始信号
输出：带 AI 研判的增强信号（valve_intelligence 字段）
"""

import json
import os
import time
import requests
from pathlib import Path

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
INPUT_FILE  = Path("data/pharma_signals.json")
OUTPUT_FILE = Path("data/pharma_scored.json")

SYSTEM_PROMPT = """你是一个专注制药行业的阀门市场分析师。
你的任务是判断一条情报信号对阀门销售的实际价值。
请严格用 JSON 格式回复，不要加任何解释文字。"""

SCORE_PROMPT = """分析以下制药行业情报信号，评估对卫生级阀门销售的价值：

信号来源：{source}
信号内容：{title}
信号类型：{signal_type}（compliance=合规整改 / expansion=产能扩张 / immediate=即时采购）

请返回 JSON：
{{
  "urgency": 1-10,           // 紧迫度（10=必须本月跟进）
  "valve_types": ["xxx"],    // 最可能需要的阀门类型
  "estimated_qty": "xxx",    // 估计采购规模（小批/中批/大批）
  "key_contact": "xxx",      // 建议联系岗位（采购/工程/设备部）
  "follow_up_timing": "xxx", // 建议跟进时机
  "risk_note": "xxx",        // 注意事项（如竞争激烈/认证门槛）
  "summary": "xxx"           // 一句话判断（≤30字）
}}"""


def call_deepseek(title, source, signal_type):
    if not DEEPSEEK_API_KEY:
        # 无 API Key 时返回占位数据
        return {
            "urgency": 5,
            "valve_types": ["卫生级隔膜阀"],
            "estimated_qty": "待评估",
            "key_contact": "设备/工程部",
            "follow_up_timing": "信号确认后1个月内",
            "risk_note": "需进一步核实项目规模",
            "summary": "待 DeepSeek API 接入后自动研判"
        }

    url = "https://api.deepseek.com/v1/chat/completions"
    prompt = SCORE_PROMPT.format(
        source=source,
        title=title,
        signal_type=signal_type
    )

    try:
        r = requests.post(url, json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 400
        }, headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }, timeout=20)

        content = r.json()["choices"][0]["message"]["content"]
        # 清理可能的 markdown 包裹
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(content)

    except Exception as e:
        print(f"  [DeepSeek] 调用失败: {e}")
        return {"summary": f"评分失败: {e}"}


def score_top_signals(n=10):
    """只对 top N 信号做 DeepSeek 深度评分（省 token）"""
    if not INPUT_FILE.exists():
        print("未找到 pharma_signals.json，请先运行 fetch_pharma.py")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    signals = data.get("top_signals", [])
    print(f"\n→ 对 Top {len(signals)} 条信号进行 DeepSeek 深度评分...\n")

    for i, sig in enumerate(signals):
        print(f"  [{i+1}/{len(signals)}] {sig['title'][:40]}...")
        intelligence = call_deepseek(
            title=sig["title"],
            source=sig["source"],
            signal_type=sig["signal_type"]
        )
        sig["valve_intelligence"] = intelligence
        time.sleep(0.5)  # 避免限速

    data["top_signals"] = signals
    data["deepseek_scored"] = True
    data["scored_at"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n→ 评分结果写入: {OUTPUT_FILE}")


if __name__ == "__main__":
    score_top_signals()
