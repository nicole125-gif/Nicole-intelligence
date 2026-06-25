"""把一条原始信号装配成 Event，并聚合成 events pack。

以 scripts/p4_opportunities.py build_opportunity / build_opportunity_pack 为蓝本重写：
- 删除别名客户匹配 → 换成工况分类 + 买方角色推断
- track 热度 → working_condition 工况标签
- 主排序键 heat → rank_score
"""

from __future__ import annotations

import datetime as dt
import hashlib

from engine import buyer_role as br
from engine import classify, conditions, entities, ranking, schema, valuation, winnability


def _text(signal: dict) -> str:
    return " ".join(filter(None, [
        signal.get("title", ""),
        signal.get("summary", ""),
        signal.get("source", ""),
    ]))


def _is_stale(signal: dict, as_of: dt.date) -> bool:
    raw = signal.get("pub_date") or signal.get("date")
    if not raw:
        return False
    try:
        published = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return (as_of - published).days > 45


def build_event(signal: dict, cfg: dict, as_of: dt.date, registry: dict | None = None) -> dict | None:
    """装配单条事件。不属于任何 ESG 工况（match_score==0）则返回 None（丢弃）。"""
    text = _text(signal)
    source_type = signal.get("source_type", "")

    cond = conditions.classify_condition(text, source_type, cfg)

    owner_raw = signal.get("company") or signal.get("owner") or ""
    owner = entities.resolve(owner_raw, registry)
    owner["raw"] = owner_raw
    owner_name = owner["name"]
    is_oem = bool(owner.get("resolved") and owner.get("type") == "oem")

    # 无工况（match_score==0）：终端项目丢弃；但「业主即在册装备商」是订单簿信号——
    # P1#4：OEM 自身有单 = ESG 顺风（尤其东富龙已 spec 进），保留并用 OEM 的 O4 档案兜底阀型/行业。
    if cond["match_score"] <= 0:
        if not is_oem:
            return None
        prof = (entities.get(owner["id"], registry) or {}).get("profile") or {}
        cond = {**cond,
                "working_condition": ["装备商订单簿"],
                "industry_tag": (prof.get("match_keywords") or ["制药装备"])[0],
                "valve_type": {"primary": (prof.get("esg_products") or [])[:3],
                               "basis": f"{owner_name} 对口阀型（O4 档案）"},
                "buyer_role_cfg": {"primary": "设备OEM", "secondary": "采购部"}}

    lead_time = classify.classify_lead_time(text, signal.get("lead_time_months", ""))
    est_value = valuation.estimate_value(
        text, cfg["capex_ratio"], cfg.get("value_overrides"),
    )
    signal_type = signal.get("signal_type", schema.SIGNAL_EXPANSION)
    role = br.infer_buyer_role(
        cond["buyer_role_cfg"], signal_type, source_type, cond["match_score"],
    )

    source_url = signal.get("url") or signal.get("link") or ""
    source_name = signal.get("source", "")
    stale = _is_stale(signal, as_of)

    confidence = 30
    if source_url and source_name:
        confidence += 20
    if owner_name:
        confidence += 20
    if est_value["status"] != "unknown":
        confidence += 10
    if cond["match_score"] >= 6:
        confidence += 15
    confidence = min(confidence, 100)

    if stale:
        review_flag = schema.FLAG_STALE
    elif not owner_name:
        review_flag = schema.FLAG_UNRESOLVED
    elif not source_url or not source_name:
        review_flag = schema.FLAG_NEEDS_REVIEW
    elif confidence < 70:
        review_flag = schema.FLAG_NEEDS_REVIEW
    else:
        review_flag = schema.FLAG_OK

    urgency = {"L0": 9, "L1": 7, "L2": 5}[lead_time["level"]]
    if est_value["status"] != "unknown":
        urgency = min(10, urgency + 1)
    if review_flag != schema.FLAG_OK:
        urgency = min(urgency, 5)

    # O2：业主即装备商时，沿 owner→OEM 边取 ESG spec 位（进/未进），喂赢面 + 分流动作
    spec_position = None
    if owner.get("resolved") and owner.get("type") == "oem":
        oem_ent = entities.get(owner["id"], registry)
        spec_position = (oem_ent or {}).get("spec_position")

    # O3：竞品密度从「竞品据点→工况」关系派生（取代工况硬编码常量，根治生物合成误降）
    reg = registry or entities.load_registry()
    density = winnability.density_from_strongholds(cond.get("primary_id"), reg)
    incumbents = winnability.incumbents_for_condition(cond.get("primary_id"), reg)  # B1：具名在位竞品
    band = valuation.value_band(text, est_value)
    win = winnability.assess(text, density, spec_position)
    rank = ranking.rank_score(
        band["band"], lead_time["level"], cond["match_score"], win["score"])

    valves = "、".join(cond["valve_type"]["primary"][:2]) or "对口阀型"
    who = owner_name or "该项目业主"
    role_text = role["inferred"] or "目标买方"
    if spec_position == "in":
        action = f"{who}已为 ESG spec 位在册，{lead_time['months']}个月窗口盯其订单簿/扩产，{valves}随产线复制。"
    elif spec_position == "target":
        action = f"{who}尚未导入 ESG，{lead_time['months']}个月窗口主推设计导入(design-in)，以{valves}切入标准 BOM。"
    else:
        action = f"{lead_time['months']}个月窗口内，锁定{who}的{role_text}，以{valves}切入。"

    event_id = hashlib.md5(
        f"{signal.get('title', '')}|{source_url}".encode()
    ).hexdigest()[:12]

    return {
        "id": event_id,
        "headline": signal.get("title", ""),
        "owner": owner,
        "spec_position": spec_position,
        "competitors": incumbents,
        "buyer_role": role,
        "working_condition": cond["working_condition"],
        "industry_tag": signal.get("industry_pull") or cond["industry_tag"],
        "signal_type": signal_type,
        "driver": classify.classify_driver(text),
        "lead_time": lead_time,
        "valve_type": cond["valve_type"],
        "est_value": est_value,
        "value_band": band,
        "winnability": win,
        "urgency": urgency,
        "match_score": cond["match_score"],
        "rank_score": rank,
        "action": action,
        "source": {
            "name": source_name,
            "type": source_type,
            "url": source_url,
            "published_at": signal.get("pub_date") or signal.get("date"),
        },
        "confidence": confidence,
        "review_flag": review_flag,
        "quality": {
            "has_capex": est_value["status"] != "unknown",
            "has_owner": bool(owner_name),
            "stale": stale,
        },
    }


def build_pack(signals: list[dict], as_of: dt.date, cfg: dict | None = None) -> dict:
    cfg = cfg or conditions.load_conditions()
    registry = entities.load_registry()
    events = []
    for signal in signals:
        if not signal.get("title"):
            continue
        event = build_event(signal, cfg, as_of, registry)
        if event is not None:
            events.append(event)
    ranking.sort_events(events)

    by_condition: dict[str, int] = {}
    by_band: dict[str, int] = {}
    for e in events:
        label = e["working_condition"][0] if e["working_condition"] else "未分类"
        by_condition[label] = by_condition.get(label, 0) + 1
        b = e["value_band"]["band"]
        by_band[b] = by_band.get(b, 0) + 1

    return {
        "schema_version": schema.SCHEMA_VERSION,
        "date": as_of.isoformat(),
        "status": "ready",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "events": events,
        "summary": {
            "total": len(events),
            "by_condition": by_condition,
            "by_band": by_band,
            "by_lead_time": {
                "L0": sum(e["lead_time"]["level"] == "L0" for e in events),
                "L1": sum(e["lead_time"]["level"] == "L1" for e in events),
                "L2": sum(e["lead_time"]["level"] == "L2" for e in events),
            },
            "ok": sum(e["review_flag"] == "ok" for e in events),
            "unresolved": sum(e["review_flag"] == "unresolved" for e in events),
            "needs_review": sum(e["review_flag"] == "needs_review" for e in events),
            "stale": sum(e["review_flag"] == "stale" for e in events),
            "unknown_value": sum(e["est_value"]["status"] == "unknown" for e in events),
        },
    }
