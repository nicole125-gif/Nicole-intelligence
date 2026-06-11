"""买方角色推断。

替代制药版的别名客户匹配（match_customer）：大量业主是陌生公司，无法依赖客户档案，
改为按工况规则推断「该找哪类角色」——这正是渠道全覆盖场景下最实用的研判输出。
"""

from __future__ import annotations


def infer_buyer_role(buyer_role_cfg: dict | None, signal_type: str,
                     source_type: str, match_score: float) -> dict:
    if not buyer_role_cfg:
        return {"inferred": None, "basis": "工况未知，无法推断买方", "confidence": 0.0}

    primary = buyer_role_cfg.get("primary")
    secondary = buyer_role_cfg.get("secondary")

    # 招标即时信号：多为终端工厂/EPC 直采，覆盖为 secondary 角色
    if signal_type == "immediate" or source_type == "tender":
        inferred = secondary or primary
        basis = "招标即时信号→终端/EPC 直采"
    # 环评：业主即终端，但真正下单的常是其设备总包
    elif source_type == "project_filing":
        inferred = primary
        basis = "环评业主→锁定其设备总包/OEM"
    else:
        inferred = primary
        basis = "按工况主渠道推断"

    confidence = 0.7 if match_score >= 6 else 0.4
    return {"inferred": inferred, "basis": basis, "confidence": confidence}
