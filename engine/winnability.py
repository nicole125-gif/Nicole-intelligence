"""赢面 v1（粗代理）。ESG 是国产挑战者，不是在位者——队列要把"撬不动的鲸鱼"压下去。

两个有数据支撑、不依赖挂起未知的信号：
1. 绿地无在位：新建/拟建/环评 = 还没有在位供应商可被替换 → 挑战者甜点；
   纯技改/升级 = 在位者多半已在 → 替换难。
2. 竞品密度（O3：从竞品据点派生）：某工况上有 Gemü/Bürkert 据点则赢面低；无外资据点（锂电/橡塑/生物合成）国产友好赢面高。
3. spec 位（O2，业主即装备商时生效）：owner 解析为某 OEM 实体 → 取其 ESG spec 位——
   已进(in)=ESG 随产线复制，顺风；未进(target)=需先 design-in，撬动难。

注：account-size/关系维度的赢面仍需更多客户档案，是后续。
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


def assess(text: str, competitor_density: str = "mid", spec_position: str | None = None) -> dict:
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
    score = round(max(0.15, min(score, 1.0)), 3)
    return {"score": score, "basis": "+".join(basis)}
