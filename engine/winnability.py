"""赢面 v1（⚠ 临时粗代理，非 Nicole 本职 — 待 CI Radar L3 替换）。

5 层模型（ARCHITECTURE §0.5）下，**ESG 赢面 = L3 ESG Fit / L4 竞品，归 CI Radar**。
本模块只是冷启动桩：队列要把"撬不动的鲸鱼"压下去，但底层数据多半借自 CI Radar 域。
三个因子按层归属：
1. 绿地无在位（**L2，真属 Nicole**）：新建/拟建/环评 = 无在位可替换 → 挑战者甜点；
   纯技改/升级 = 在位者多半已在 → 替换难。**信号文本自带，不需要 CI。**
2. 竞品密度（**L4，借 CI Radar**，O3 从竞品据点派生）：某工况有 Gemü/Bürkert 据点则赢面低。
   据点数据（entities.yml strongholds）源自竞品分析 = CI Radar 域，现为手种。
3. spec 位（**L3，借 CI Radar**，O2 业主即装备商时生效）：ESG 进没进 OEM 的 BOM。
   = ESG 装机/spec 状态，正是边界纪律里 Nicole 不该断言的（手工确认填入，临时）。

→ CI Radar L3 上线后，竞品密度/spec位 应由其经契约供给，本模块退回只算绿地（L2）。
注：account-size/关系维度仍需更多客户档案，是后续。
"""

from __future__ import annotations

_GREENFIELD = ("新建", "拟建", "环评", "生产基地", "新建生产线", "新建项目", "开工建设")
_BROWNFIELD = ("技改", "升级改造", "技术改造")
_DENSITY = {"low": 0.2, "mid": 0.0, "high": -0.2}
_SPEC = {"in": 0.2, "target": -0.1}


def density_from_strongholds(condition_id: str, registry: dict) -> str:
    """O3：竞品密度从「竞品—据点(stronghold)→工况」关系派生，取代工况硬编码常量。

    该工况上有竞品 full 据点 → high；仅 partial → mid；无竞品据点 → low。
    根治 v1 生物合成误降——biosynthesis 不在任何竞品据点里，自然 low，无需特例。
    """
    grips = []
    for ent in registry.get("by_id", {}).values():
        if ent.get("type") != "competitor":
            continue
        for sh in (ent.get("profile") or {}).get("strongholds", []):
            if sh.get("condition") == condition_id:
                grips.append(sh.get("grip", "partial"))
    if "full" in grips:
        return "high"
    if grips:
        return "mid"
    return "low"


def incumbents_for_condition(condition_id: str, registry: dict) -> list[dict]:
    """该工况上在位的具名竞品（含威胁分），供前端「可能碰到的对手」展示。

    无据点 → 空列表（= 无外资在位、国产友好，本身是卖点）。
    """
    out = []
    for ent in registry.get("by_id", {}).values():
        if ent.get("type") != "competitor":
            continue
        prof = ent.get("profile") or {}
        for sh in prof.get("strongholds", []):
            if sh.get("condition") == condition_id:
                out.append({
                    "name": ent["name"],
                    "threat": prof.get("avg_threat_level"),
                    "grip": sh.get("grip", "partial"),
                })
                break
    out.sort(key=lambda x: x.get("threat") or 0, reverse=True)
    return out


def assess(text: str, competitor_density: str = "mid", spec_position: str | None = None,
           feedback_delta: float = 0.0) -> dict:
    score = 0.5
    basis = []
    if any(k in text for k in _GREENFIELD):
        score += 0.25
        basis.append("绿地无在位")
    elif any(k in text for k in _BROWNFIELD):
        score -= 0.1
        basis.append("棕地(在位风险)")
    score += _DENSITY.get(competitor_density, 0.0)
    basis.append(f"竞品{competitor_density}")
    if spec_position in _SPEC:
        score += _SPEC[spec_position]
        basis.append("spec位已进(顺风)" if spec_position == "in" else "spec位未进(需design-in)")
    # L5→L3 闭环反馈（engine/feedback.py）：某工况历史赢率高→顺风微调。
    # 现无真实处置标签（决策15），feedback_delta 默认 0=no-op；标签攒够后飞轮合上。
    if feedback_delta:
        score += feedback_delta
        basis.append(f"闭环反馈{feedback_delta:+g}(临时·待标签)")
    score = round(max(0.15, min(score, 1.0)), 3)
    return {"score": score, "basis": "+".join(basis)}
