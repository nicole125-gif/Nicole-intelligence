"""工况知识库：加载 esg_conditions.yml，做工况分类与阀型映射。

取代制药版写死的 score_for_valves —— 关键词按工况组织，同一套逻辑覆盖全部 ESG 工况。
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "esg_conditions.yml"

# 关键词权重梯度，沿用 fetch_pharma.py L345-349
STRONG_WEIGHT = 1.5
MID_WEIGHT = 0.8
MAX_SCORE = 10.0


def load_conditions(path: Path = DEFAULT_CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def classify_condition(text: str, source_type: str, cfg: dict) -> dict:
    """对一条文本判定工况。

    返回 primary_id（最高分工况）/ working_condition（命中的全部工况标签）/
    match_score（0-10，含源加权）/ industry_tag / valve_type。
    match_score==0 表示不属于任何 ESG 工况 → 调用方应丢弃。
    """
    source_boost = cfg.get("source_boost", {}).get(source_type, 0)
    scored = []
    for cond in cfg.get("conditions", []):
        kw = cond.get("keywords", {})
        hits = []
        score = 0.0
        for k in kw.get("strong", []):
            if k in text:
                score += STRONG_WEIGHT
                hits.append(k)
        for k in kw.get("mid", []):
            if k in text:
                score += MID_WEIGHT
                hits.append(k)
        if score > 0:
            scored.append((score, cond, hits))

    if not scored:
        return {
            "primary_id": None,
            "working_condition": [],
            "match_score": 0.0,
            "industry_tag": None,
            "valve_type": {"primary": [], "basis": "未命中任何 ESG 工况"},
            "buyer_role_cfg": None,
            "competitor_density": "mid",
        }

    scored.sort(key=lambda s: s[0], reverse=True)
    top_score, primary, top_hits = scored[0]
    match_score = min(round(top_score + source_boost, 1), MAX_SCORE)

    return {
        "primary_id": primary["id"],
        "working_condition": [c["label"] for _, c, _ in scored],
        "match_score": match_score,
        "industry_tag": (primary.get("industries") or [None])[0],
        "valve_type": {
            "primary": primary.get("valve_types", []),
            "basis": f"{primary['label']}工况信号（命中：{'、'.join(top_hits[:4])}）",
        },
        "buyer_role_cfg": primary.get("buyer_role"),
        "competitor_density": primary.get("competitor_density", "mid"),
    }
