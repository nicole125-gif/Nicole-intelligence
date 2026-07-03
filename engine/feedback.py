"""L5→L3 动能闭环消费：把处置标签(赢/输)聚合成 winnability 的按工况反馈微调。

⚠ 机制就绪、当前无真实标签（决策15 先采集后消费）：处置写在 Upstash KV，需先导出为
`data/feedback.json`（{condition_id: delta}，gitignore）。无该文件 → 反馈为空 →
winnability 不变（no-op）。真实"赢/输给谁"标签攒够后，本模块让飞轮合上：某工况历史
赢率高→赢面顺风微调，反之调降——把处置从"死写的日记"变成"改变对象输入的状态转移"。

纯函数，engine 保持确定性（不联网读 KV；join 走已落盘的 events）。
"""

from __future__ import annotations

WON, LOST = "赢", "输"        # 其余(跟进中/忽略/无效)中性，不计入胜负
MIN_SAMPLE = 2               # 总样本<2 → 不调（证据不足，避免单点噪声左右赢面）
MAX_DELTA = 0.15            # 反馈微调上限，不喧宾夺主（主因子仍是绿地/竞品/spec）


def win_stats(dispositions: list[dict], events_by_id: dict) -> dict:
    """按工况聚合处置胜负 → {condition_id: {"won":n, "lost":m}}。

    处置记录本身不带工况（只有 event_id）→ join events 取 working_condition_ids[0]。
    """
    stats: dict[str, dict] = {}
    for d in dispositions:
        st = d.get("status")
        if st not in (WON, LOST):
            continue
        ev = events_by_id.get(d.get("event_id"))
        cids = (ev or {}).get("working_condition_ids") or []
        if not cids:
            continue
        s = stats.setdefault(cids[0], {"won": 0, "lost": 0})
        s["won" if st == WON else "lost"] += 1
    return stats


def condition_delta(won: int, lost: int) -> float:
    """胜负 → 有界赢面微调。样本不足或平衡→0；全胜→+MAX_DELTA，全负→−MAX_DELTA。"""
    n = won + lost
    if n < MIN_SAMPLE:
        return 0.0
    return round((won - lost) / n * MAX_DELTA, 3)


def build_feedback(dispositions: list[dict], events_by_id: dict) -> dict:
    """→ {condition_id: delta}，供 winnability.assess 的 feedback_delta 消费。"""
    return {cid: condition_delta(s["won"], s["lost"])
            for cid, s in win_stats(dispositions, events_by_id).items()}
