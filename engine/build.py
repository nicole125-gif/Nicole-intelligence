"""把一条原始信号装配成 Event，并聚合成 events pack。

以 scripts/p4_opportunities.py build_opportunity / build_opportunity_pack 为蓝本重写：
- 删除别名客户匹配 → 换成工况分类 + 买方角色推断
- track 热度 → working_condition 工况标签
- 主排序键 heat → rank_score
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from engine import buyer_role as br
from engine import classify, conditions, entities, ranking, schema, valuation, winnability

_FEEDBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.json"


def _load_feedback() -> dict:
    """L5→L3 闭环：读已导出的 {condition_id: delta}（gitignore）。无文件=no-op（决策15）。"""
    try:
        return json.loads(_FEEDBACK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


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


def _extraction_notes(review_flag, est_value, owner, cond, stale, is_oem) -> str:
    """L1：生成复核理由，让下游/人知道为何待核或为何 NO_MATCH。"""
    notes = []
    # NO_MATCH：无工况枚举的 OEM 订单簿信号——即使 review_flag=ok 也标，供下游 NO_MATCH 决策
    if not cond.get("condition_ids") and is_oem:
        notes.append("装备商订单簿信号，无具体工况项目：possible NO_MATCH for ESG opportunity mapping")
    if review_flag != schema.FLAG_OK:
        flagged = len(notes)
        if stale:
            notes.append("信号偏旧（>45 天），可能已过期，勿当即时强机会")
        if not owner.get("name"):
            notes.append("业主未抽取/未解析，暂不可派明确销售动作")
        elif not owner.get("resolved"):
            notes.append("业主为 auto 实体未提升进 registry，身份待确认")
        if est_value.get("status") == "unknown":
            notes.append("无金额，估值未知，待核实项目规模")
        if len(notes) == flagged:  # 未命中具体原因
            notes.append("字段不全，待复核")
    return "；".join(notes)


def build_event(signal: dict, cfg: dict, as_of: dt.date, registry: dict | None = None,
                feedback: dict | None = None) -> dict | None:
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
                "condition_ids": [],  # 非真工况枚举 → 契约 NO_MATCH（导出留空 + needs_review）
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
    fb_delta = (feedback or {}).get(cond.get("primary_id"), 0.0)  # L5→L3 闭环（无标签时=0）
    win = winnability.assess(text, density, spec_position, fb_delta)
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

    # L1：每条事件自解释——金额显式 + 命中证据 + 复核理由
    capex_amount = est_value.get("project_capex") if est_value.get("status") == "model_estimate" else None
    capex_currency = "CNY" if capex_amount else "UNKNOWN"
    extraction_notes = _extraction_notes(review_flag, est_value, owner, cond, stale, is_oem)

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
        "working_condition_ids": cond.get("condition_ids", []),  # 契约枚举 id（与 labels 平行）
        "matched_keywords": cond.get("matched_keywords", []),    # L1：命中证据（可溯源）
        "matched_sentence": cond.get("matched_sentence", ""),    # L1：命中证据句（接地，"为什么判这个工况"）
        "industry_tag": signal.get("industry_pull") or cond["industry_tag"],
        "signal_type": signal_type,
        "driver": classify.classify_driver(text),
        "lead_time": lead_time,
        "valve_type": cond["valve_type"],
        "est_value": est_value,
        "capex_amount": capex_amount,        # L1：显式金额（契约 capex_amount）
        "capex_currency": capex_currency,    # L1：币种（契约 capex_currency）
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
        "extraction_notes": extraction_notes,  # L1：复核理由（契约 review_flag!=ok 时必填）
        "quality": {
            "has_capex": est_value["status"] != "unknown",
            "has_owner": bool(owner_name),
            "stale": stale,
        },
    }


def build_clusters(events: list[dict]) -> list[dict]:
    """L2：按 owner_id 把多条事件聚合成「实体信号簇」（账户级印证信号）。

    单条公告=数据点；同一主体多条独立信号印证 → 高置信"在动"账户线索
    （signal-based selling：信号密度跨多触发才从"可能"变"几乎肯定在买"）。
    """
    band_rank = {"大": 3, "中": 2, "小": 1, "未知": 0}
    level_rank = {"L0": 0, "L1": 1, "L2": 2}
    groups: dict[str, list] = {}
    for e in events:
        oid = (e.get("owner") or {}).get("id")
        if oid:
            groups.setdefault(oid, []).append(e)

    clusters = []
    for oid, evs in groups.items():
        owner = evs[0]["owner"]
        corro = len(evs)
        src_types = sorted({e["source"].get("type") for e in evs if e["source"].get("type")})
        cond_ids = sorted({c for e in evs for c in e.get("working_condition_ids", [])})
        confidence = min(100, max(e["confidence"] for e in evs) + 5 * (corro - 1))  # 印证→提置信
        top_band = max((e["value_band"]["band"] for e in evs), key=lambda b: band_rank.get(b, 0))
        soonest = min((e["lead_time"]["level"] for e in evs), key=lambda lv: level_rank.get(lv, 9))
        spec = next((e.get("spec_position") for e in evs if e.get("spec_position")), None)
        src_label = "、".join(
            f"{t}×{sum(1 for e in evs if e['source'].get('type') == t)}" for t in src_types)
        in_motion = (f"{corro} 个独立信号（{src_label}）"
                     + (f"，工况：{'/'.join(cond_ids)}" if cond_ids else "，OEM 订单簿动能")
                     + (f"，spec位={spec}" if spec else ""))
        clusters.append({
            "owner": {k: owner.get(k) for k in ("id", "name", "type", "resolved")},
            "corroboration": corro,
            "event_ids": [e["id"] for e in evs],
            "source_types": src_types,
            "working_condition_ids": cond_ids,
            "spec_position": spec,
            "value_band_top": top_band,
            "lead_time_soonest": soonest,
            "rank_score_top": max(e["rank_score"] for e in evs),
            "confidence": confidence,
            "in_motion": in_motion,
        })
    clusters.sort(key=lambda c: (c["corroboration"], c["confidence"], c["rank_score_top"]), reverse=True)
    return clusters


def build_pack(signals: list[dict], as_of: dt.date, cfg: dict | None = None) -> dict:
    cfg = cfg or conditions.load_conditions()
    registry = entities.load_registry()
    feedback = _load_feedback()  # L5→L3 闭环消费（决策15：无标签则空 dict，赢面不变）
    events = []
    for signal in signals:
        if not signal.get("title"):
            continue
        event = build_event(signal, cfg, as_of, registry, feedback)
        if event is not None:
            events.append(event)
    ranking.sort_events(events)
    clusters = build_clusters(events)  # L2：实体信号簇（账户级印证）

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
        "clusters": clusters,  # L2：账户级信号簇
        "summary": {
            "total": len(events),
            "accounts": len(clusters),
            "corroborated": sum(1 for c in clusters if c["corroboration"] >= 2),
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
