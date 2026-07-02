"""高频未解析业主报告（O1 实体解析质量诊断 / ER 促进）。

扫描 data/events/*.json 里所有 resolved=False 的业主，按出现频次 + 累积信号排序，
产出"该提升进 config/entities.yml registry 的候选"工作清单；并用轻启发式聚出
「疑似同一实体、不同写法」的碎片簇——这正是 L2 簇(corroboration)/L5 处置回流
被静默腐蚀的根因（同公司两种写法 → 两个 auto-id → 印证被低估、回流对不上）。

跨所有 pack 聚合（不止最新一天）：既算真频次，又暴露"对象活不过一次 run"的
持久化缺口——同一实体在不同日期反复以 auto-id 出现、从不沉淀成稳定 Object。

  python3 scripts/unresolved_owners.py            # 扫所有 pack，打印候选清单
  python3 scripts/unresolved_owners.py --top 15   # 只看前 15

只读诊断，不改任何文件。提升动作=人工把高频候选加进 config/entities.yml 的 entities:。
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.entities import _normalize  # noqa: E402  复用真实解析的规范化，口径一致

EVENTS_GLOB = str(ROOT / "data" / "events" / "*.json")


def collect_unresolved(paths: list[str]) -> dict:
    """跨 pack 聚合未解析业主 → {auto_id: 指标}。"""
    agg: dict[str, dict] = {}
    for p in paths:
        try:
            pack = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        pack_date = pack.get("date", Path(p).stem)
        for e in pack.get("events", []):
            owner = e.get("owner") or {}
            name = owner.get("name")
            if not name or owner.get("resolved"):
                continue
            key = owner.get("id") or ("auto:" + _normalize(name))
            g = agg.setdefault(key, {
                "auto_id": key, "norm": _normalize(name),
                "raw_names": {}, "count": 0, "signal": 0.0,
                "industries": {}, "dates": set(), "examples": [],
            })
            g["count"] += 1
            g["raw_names"][name] = g["raw_names"].get(name, 0) + 1
            g["signal"] += float(e.get("rank_score") or 0)
            tag = e.get("industry_tag") or "?"
            g["industries"][tag] = g["industries"].get(tag, 0) + 1
            g["dates"].add(pack_date)
            if len(g["examples"]) < 3:
                g["examples"].append(e.get("headline", "")[:40])
    return agg


def fragment_clusters(agg: dict) -> list[list[str]]:
    """轻启发式：规范化名互为包含 → 疑似同一实体的碎片（不同写法拆成多 auto-id）。"""
    ids = [g["auto_id"] for g in agg.values() if len(agg[g["auto_id"]]["norm"]) >= 2]
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = agg[ids[i]]["norm"], agg[ids[j]]["norm"]
            if a and b and (a in b or b in a):
                parent[find(ids[i])] = find(ids[j])
    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)
    return [c for c in clusters.values() if len(c) > 1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="高频未解析业主报告（ER 促进）")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)

    paths = sorted(glob.glob(EVENTS_GLOB))
    if not paths:
        print("⚠ 无 event 数据（先 python3 -m engine.run [--sample]）")
        return 0

    agg = collect_unresolved(paths)
    if not agg:
        print(f"✓ 扫描 {len(paths)} 个 pack：无未解析业主（全部命中 registry）")
        return 0

    ranked = sorted(agg.values(), key=lambda g: (g["count"], g["signal"]), reverse=True)
    print(f"未解析业主候选 · 扫描 {len(paths)} 个 pack · 共 {len(agg)} 个未登记实体")
    print(f"（按频次×信号排序，前 {min(args.top, len(ranked))}）")
    print("─" * 72)
    print(f"{'次':>2} {'信号':>5}  {'跨天':>3}  业主 → 行业")
    for g in ranked[:args.top]:
        inds = "/".join(sorted(g["industries"], key=g["industries"].get, reverse=True)[:2])
        multi = f"  ⚠{len(g['raw_names'])}种写法" if len(g["raw_names"]) > 1 else ""
        name = max(g["raw_names"], key=g["raw_names"].get)
        print(f"{g['count']:>2} {g['signal']:>5.2f}  {len(g['dates']):>3}  {name} → {inds}{multi}")

    clusters = fragment_clusters(agg)
    if clusters:
        print("\n" + "─" * 72)
        print(f"⚠ 疑似同一实体的碎片簇（不同写法拆成多 auto-id，腐蚀 L2 印证）：{len(clusters)} 组")
        for c in clusters:
            names = [max(agg[i]["raw_names"], key=agg[i]["raw_names"].get) for i in c]
            print(f"  · {' ｜ '.join(names)}")

    print("\n提升动作：把高频候选（尤其跨天/多写法）加进 config/entities.yml 的 entities:，")
    print("给正规 id + aliases（含各写法），resolved 变 True → L2 簇与 L5 回流不再碎片化。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
