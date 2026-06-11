"""事件排序：rank_score = 价值 × 提前量 × 工况匹配度。取代老 heat_score。

三因子归一化到 0-1 后相乘——任一维度为零则该线索沉底，符合「必须同时有价值、
有时机、对口」的研判直觉。
"""

from __future__ import annotations

LEAD_FACTOR = {"L0": 1.0, "L1": 0.7, "L2": 0.45}
# 价值档 → 因子。未知给 0.35（降权但不归零），但已知"大"恒压过未知。
BAND_FACTOR = {"大": 1.0, "中": 0.6, "小": 0.3, "未知": 0.35}


def value_factor(band: str) -> float:
    return BAND_FACTOR.get(band, 0.35)


def lead_factor(level: str) -> float:
    return LEAD_FACTOR.get(level, 0.45)


def condition_factor(match_score: float) -> float:
    return round(match_score / 10.0, 4)


def rank_score(band: str, lead_level: str, match_score: float) -> float:
    return round(
        value_factor(band) * lead_factor(lead_level) * condition_factor(match_score),
        4,
    )


def sort_events(events: list[dict]) -> list[dict]:
    """稳定多键排序，沿用 p4 L248-254：待复核沉到分组后，主键 rank_score。"""
    events.sort(
        key=lambda e: (
            e["review_flag"] != "ok",
            -e["rank_score"],
            -e["urgency"],
            -e["confidence"],
        )
    )
    return events
