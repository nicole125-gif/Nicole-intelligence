"""从最新 data/events/<date>.json 派生 data/industry_heat.json（L2 行业热度信号）。

  python3 scripts/build_industry_heat.py          # 读最近可得的 events，写 industry_heat.json

产物 data/industry_heat.json 已 gitignore（同 events/ontology，生成物不入库）；
index.html 若能读到就把 L2 信号叠加到对应赛道，读不到则只显示 rubric heat（优雅降级）。
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.industry_heat import build_industry_heat  # noqa: E402

EVENTS_DIR = ROOT / "data" / "events"
OUT = ROOT / "data" / "industry_heat.json"


def _latest_pack(as_of: dt.date, lookback: int = 30):
    for i in range(lookback):
        d = as_of - dt.timedelta(days=i)
        f = EVENTS_DIR / f"{d.isoformat()}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8")), d
    return None, None


def main(argv=None) -> int:
    pack, pdate = _latest_pack(dt.date.today())
    if not pack:
        OUT.write_text(json.dumps({"generated_from": None, "by_industry": {}},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print("⚠ 无 events 数据，写空 industry_heat.json")
        return 0

    by = build_industry_heat(pack, pdate)
    OUT.write_text(json.dumps({
        "generated_from": pdate.isoformat(),
        "pack_date": pack.get("date"),
        "by_industry": by,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ L2 行业热度信号 ← {pdate}：{len(by)} 个行业")
    for tag, m in sorted(by.items(), key=lambda kv: kv[1]["l2_signal"], reverse=True):
        print(f"  {tag:14} 信号{m['l2_signal']:>3} · {m['event_count']}事件 · {m['account_count']}账户")
    return 0


if __name__ == "__main__":
    sys.exit(main())
