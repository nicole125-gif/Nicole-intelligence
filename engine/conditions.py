"""工况知识库：加载 esg_conditions.yml，做工况分类与阀型映射。

取代制药版写死的 score_for_valves —— 关键词按工况组织，同一套逻辑覆盖全部 ESG 工况。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "esg_conditions.yml"

# 关键词权重梯度，沿用 fetch_pharma.py L345-349
STRONG_WEIGHT = 1.5
MID_WEIGHT = 0.8
# weak：非工况判别的泛词（生产线/扩建/技改/管道/蒸汽/机组…）。给极低权重——
# 保留 recall（边界信号仍能浮出）但不让它决定工况或打破平局、不虚高排序分。
WEAK_WEIGHT = 0.3
MAX_SCORE = 10.0

# 句子切分：中英文句末标点 + 换行（用于抽"命中证据句"）
_SENT_SPLIT = re.compile(r"[。！？；!?;\n]+")


def load_conditions(path: Path = DEFAULT_CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _evidence_sentence(text: str, hits: list[str]) -> str:
    """从原文里挑出第一句含命中关键词的句子，作为可溯源证据（接地）。

    全文抽取（GNE）/未来 LLM 评分接入后，这就是"为什么判成这个工况"的人可读凭据。
    取不到（如标题本身就是全部文本、无标点）则回退整段截断。
    """
    for sent in _SENT_SPLIT.split(text):
        s = sent.strip()
        if s and any(h in s for h in hits):
            return s[:160]
    return text.strip()[:160]


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
        has_discriminative = False  # 至少一个 strong/mid 命中才立案——weak 泛词只加分不单独定工况
        for k in kw.get("strong", []):
            if k in text:
                score += STRONG_WEIGHT
                hits.append(k)
                has_discriminative = True
        for k in kw.get("mid", []):
            if k in text:
                score += MID_WEIGHT
                hits.append(k)
                has_discriminative = True
        for k in kw.get("weak", []):
            if k in text:
                score += WEAK_WEIGHT
                hits.append(k)
        # weak-only（无判别词）不立案：否则"风电机组扩建"仅凭泛词被误判成某工况（注释承诺不破平局）
        if score > 0 and has_discriminative:
            scored.append((score, cond, hits))

    if not scored:
        return {
            "primary_id": None,
            "working_condition": [],
            "condition_ids": [],
            "matched_keywords": [],
            "matched_sentence": "",
            "match_score": 0.0,
            "industry_tag": None,
            "valve_type": {"primary": [], "basis": "未命中任何 ESG 工况"},
            "buyer_role_cfg": None,
        }

    scored.sort(key=lambda s: s[0], reverse=True)
    top_score, primary, top_hits = scored[0]
    match_score = min(round(top_score + source_boost, 1), MAX_SCORE)

    return {
        "primary_id": primary["id"],
        "working_condition": [c["label"] for _, c, _ in scored],
        "condition_ids": [c["id"] for _, c, _ in scored],  # 契约 working_condition_ids（与 labels 平行）
        "matched_keywords": top_hits[:6],  # L1：命中的工况关键词（证据/可溯源）
        "matched_sentence": _evidence_sentence(text, top_hits),  # L1：命中证据句（接地，可溯源）
        "match_score": match_score,
        "industry_tag": (primary.get("industries") or [None])[0],
        "valve_type": {
            "primary": primary.get("valve_types", []),
            "basis": f"{primary['label']}工况信号（命中：{'、'.join(top_hits[:4])}）",
        },
        "buyer_role_cfg": primary.get("buyer_role"),
    }
