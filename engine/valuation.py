"""Capex → 阀门采购额估算。移植自 scripts/p4_opportunities.py L92-128，几乎原样。

三态返回：manual_override / model_estimate / unknown。抓不到金额 → unknown，不猜。
"""

from __future__ import annotations

import re


# 负向单位：紧跟金额单位后的量词，说明这是产量/面积而非钱（如"年产6万吨"）
_QUANTITY_UNIT = "吨千克斤平方公里立方件台套支瓶盒只双株米瓦方度㎡"


def parse_capex_cny(text: str) -> int | None:
    """从文本提取金额（亿/万），统一换算成元，取最大值。

    排除"万吨/亿吨/万件"等量词——它们是产量不是金额（修复制药链的误判）。
    """
    matches = re.findall(
        rf"(\d+(?:\.\d+)?)\s*(亿元|万元|亿|万)(?![{_QUANTITY_UNIT}])", text)
    if not matches:
        return None
    values = []
    for raw, unit in matches:
        amount = float(raw)
        values.append(round(amount * (100_000_000 if unit in {"亿元", "亿"} else 10_000)))
    return max(values)


def estimate_value(text: str, capex_ratio: dict, value_overrides: list | None = None) -> dict:
    for override in (value_overrides or []):
        if override.get("match") and override["match"] in text:
            return {
                "status": "manual_override",
                "currency": "CNY",
                "low": override["low"],
                "high": override["high"],
                "basis": override.get("basis", "人工覆盖"),
            }

    capex = parse_capex_cny(text)
    if capex is None:
        return {"status": "unknown", "currency": "CNY", "low": None, "high": None}
    return {
        "status": "model_estimate",
        "currency": "CNY",
        "project_capex": capex,
        "low": round(capex * float(capex_ratio["low"])),
        "high": round(capex * float(capex_ratio["high"])),
        "ratio_low": float(capex_ratio["low"]),
        "ratio_high": float(capex_ratio["high"]),
        "basis": capex_ratio.get("label", "模型估算"),
    }


# ── 价值分档（大/中/小/未知）─────────────────────────────────
# 用"档"代替"点"：金额在标题里 ~95% 缺失，但产能规模几乎总在。把产能捡回来当
# 规模证据，让没写金额的大项目也能浮上来，且不装精度（假精度毁团队信任）。

_CAP_YI = re.compile(r"\d+(?:\.\d+)?\s*亿\s*(?:吨|平方米|㎡|只|件|支|条|粒|片|颗|个)")
_CAP_GWH = re.compile(r"(\d+(?:\.\d+)?)\s*GWh")
_CAP_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*万\s*(?:吨|平方米|㎡|只|件|支|条|台|套|千升|标方|立方米|颗|片)")

_BIG_TYPE = ("生产基地", "新建", "整线", "模块化", "智能工厂", "产业园", "总部工厂")
_SMALL_TYPE = ("升级改造", "维修", "更换", "备件", "零星采购")


def capacity_scale(text: str) -> int:
    """产能规模信号：2=大产能, 1=有产能, 0=无。与金额解析互补（专看万吨/GWh 等量词）。"""
    if _CAP_YI.search(text):
        return 2
    g = _CAP_GWH.search(text)
    if g:
        return 2 if float(g.group(1)) >= 3 else 1
    wan = _CAP_WAN.findall(text)
    if wan:
        return 2 if any(float(v) >= 10 for v in wan) else 1
    return 0


def value_band(text: str, est_value: dict) -> dict:
    """综合 [金额 + 产能规模 + 项目类型] 给价值档。不掺工况（那是排序的 condition_factor）。"""
    score = 0
    basis = []
    if est_value.get("status") in ("model_estimate", "manual_override"):
        capex = est_value.get("project_capex") or est_value.get("high") or 0
        if capex >= 500_000_000:
            score += 3
            basis.append("金额≥5亿")
        elif capex >= 100_000_000:
            score += 2
            basis.append("金额1-5亿")
        else:
            score += 1
            basis.append("金额<1亿")
    cap = capacity_scale(text)
    if cap == 2:
        score += 3
        basis.append("大产能")
    elif cap == 1:
        score += 1
        basis.append("有产能")
    if any(k in text for k in _BIG_TYPE):
        score += 1
        basis.append("新建/基地")
    if any(k in text for k in _SMALL_TYPE):
        score -= 1

    if score >= 3:
        band = "大"
    elif score == 2:
        band = "中"
    elif score == 1:
        band = "小"
    else:
        band = "未知"
    return {"band": band, "basis": "+".join(basis) or "无规模信号"}
