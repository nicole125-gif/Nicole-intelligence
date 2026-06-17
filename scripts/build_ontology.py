"""把 entities.yml（O1/O4 registry）+ 最新 events 编译成 data/ontology.json。

本体图谱页（ontology.html）只 fetch 这一份 JSON，浏览器零依赖、零 YAML 解析；
实体数据仍以 config/entities.yml 为单一来源（守住 O4 单一语义层）。

节点：战略实体（含 spec_position / 威胁分 / profile 摘要）+ 事件业主 + 事件。
边：ESG—spec位→OEM（in/target）、事件—业主。
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import entities  # noqa: E402

OUT = ROOT / "data" / "ontology.json"


def _latest_events() -> dict | None:
    files = sorted(glob.glob(str(ROOT / "data" / "events" / "*.json")))
    return json.loads(Path(files[-1]).read_text(encoding="utf-8")) if files else None


def build() -> dict:
    reg = entities.load_registry()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    # 1) 战略实体节点（registry）
    for ent in reg["by_id"].values():
        prof = ent.get("profile") or {}
        nodes[ent["id"]] = {
            "id": ent["id"],
            "name": ent["name"],
            "type": ent["type"],  # oem | competitor | self | company
            "resolved": True,
            "spec_position": ent.get("spec_position"),
            "threat": prof.get("avg_threat_level"),
            "products": prof.get("esg_products") or [],
            "competitors": [c["company"] for c in prof.get("competitor_products", [])],
        }

    # 2) ESG—spec位→OEM 承重边
    esg_id = next((i for i, e in reg["by_id"].items() if e.get("type") == "self"), "esg")
    for ent in reg["by_id"].values():
        if ent.get("type") == "oem" and ent.get("spec_position"):
            edges.append({
                "source": esg_id, "target": ent["id"],
                "kind": "spec", "spec_position": ent["spec_position"],
            })

    # 3) 事件节点 + 事件—业主边
    pack = _latest_events()
    date = pack.get("date") if pack else None
    for ev in (pack or {}).get("events", []):
        owner = ev.get("owner") or {}
        oid = owner.get("id")
        if not oid:
            continue
        # 业主未在 registry（auto 实体）→ 补一个轻量 company 节点
        if oid not in nodes:
            nodes[oid] = {
                "id": oid, "name": owner.get("name") or "未知业主",
                "type": "company", "resolved": bool(owner.get("resolved")),
                "spec_position": None, "threat": None, "products": [], "competitors": [],
            }
        evid = "evt:" + ev["id"]
        nodes[evid] = {
            "id": evid, "type": "event",
            "name": ev.get("headline", "")[:42],
            "working_condition": (ev.get("working_condition") or [None])[0],
            "value_band": ev.get("value_band", {}).get("band"),
            "winnability": ev.get("winnability", {}).get("score"),
            "lead_time": ev.get("lead_time", {}).get("level"),
            "rank": ev.get("rank_score"),
            "spec_position": ev.get("spec_position"),
        }
        edges.append({"source": evid, "target": oid, "kind": "owner"})

    return {"date": date, "nodes": list(nodes.values()), "edges": edges}


def main() -> None:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n, e = len(data["nodes"]), len(data["edges"])
    spec = sum(1 for x in data["edges"] if x["kind"] == "spec")
    print(f"✓ 写入 {OUT}  节点 {n} / 边 {e}（spec 边 {spec}）")


if __name__ == "__main__":
    main()
