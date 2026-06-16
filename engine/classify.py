"""提前量与驱动维度分类。移植自 scripts/p4_opportunities.py L63-89，改为按纯文本操作。"""

from __future__ import annotations


def classify_lead_time(text: str, explicit: str = "") -> dict:
    """归一化到 L0/L1/L2。explicit 是源给出的提前量提示（如 "3-9"）。"""
    explicit = str(explicit or "")
    if explicit:
        if explicit.startswith("0-2"):
            return {"level": "L0", "months": "0-2"}
        if explicit.startswith(("3-9", "1-6", "6-12")):
            return {"level": "L1", "months": "3-9"}
        if explicit.startswith("12-18"):
            return {"level": "L2", "months": "12-18"}

    if any(word in text for word in ("招标", "中标", "采购公告", "询价")):
        return {"level": "L0", "months": "0-2"}
    if any(word in text for word in ("环评", "规划", "受理", "拟建", "获批")):
        return {"level": "L2", "months": "12-18"}
    return {"level": "L1", "months": "3-9"}


def classify_driver(text: str) -> str:
    """D/C/P/Pol：需求/资本/价格/政策。"""
    if any(word in text for word in ("政策", "监管", "GMP", "飞检", "警告信", "合规")):
        return "Pol"
    if any(word in text for word in ("涨价", "降价", "价格", "集采")):
        return "P"
    if any(word in text for word in ("融资", "募资", "投资", "Capex", "扩产", "新建", "扩建")):
        return "C"
    return "D"
