"""黄金评估集回归（martinfowler「变更触发数据集评估」在确定性引擎上的落地）。

把真实信号跑过引擎，与人工锁定的期望比对——调 esg_conditions.yml / entities.yml /
valuation / winnability 后，这里会抓到工况分类/估值/赢面的悄悄退化。

  python3 -m unittest tests.test_golden     # 回归门禁（偏离即 FAIL）
  python3 -m tests.test_golden              # 报告模式：打印准确率 + 逐条 mismatch
"""

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import build, conditions, entities  # noqa: E402

CASES = json.loads((ROOT / "tests" / "golden" / "cases.json").read_text(encoding="utf-8"))["cases"]
_AS_OF = dt.date(2026, 6, 30)


def _run_case(case: dict, cfg: dict, registry: dict) -> list[str]:
    """跑一条用例，返回 mismatch 描述列表（空 = 通过）。"""
    exp = case["expect"]
    text, st = case["text"], case.get("source_type", "capex")
    fails = []

    if exp.get("match_zero"):
        cond = conditions.classify_condition(text, st, cfg)
        if cond["match_score"] > 0:
            fails.append(f"应 NO_MATCH 但 match_score={cond['match_score']}（判成 {cond['primary_id']}）")
        return fails

    e = build.build_event(
        {"title": text, "source_type": st, "company": case.get("company", ""),
         "url": "http://golden", "source": "golden", "date": _AS_OF.isoformat()},
        cfg, _AS_OF, registry)
    if e is None:
        return [f"build_event 返回 None（期望分类为 {exp.get('condition_id')}）"]

    got_cid = (e.get("working_condition_ids") or [None])[0]
    if "condition_id" in exp and got_cid != exp["condition_id"]:
        fails.append(f"工况 期望={exp['condition_id']} 实得={got_cid}")
    if "industry_tag" in exp and e.get("industry_tag") != exp["industry_tag"]:
        fails.append(f"行业 期望={exp['industry_tag']} 实得={e.get('industry_tag')}")
    if "value_band" in exp and e["value_band"]["band"] != exp["value_band"]:
        fails.append(f"价值档 期望={exp['value_band']} 实得={e['value_band']['band']}")
    win = e["winnability"]["score"]
    if "win_min" in exp and win < exp["win_min"]:
        fails.append(f"赢面 期望≥{exp['win_min']} 实得={win}")
    if "win_max" in exp and win > exp["win_max"]:
        fails.append(f"赢面 期望≤{exp['win_max']} 实得={win}")
    ms = e["match_score"]
    if "match_max" in exp and ms > exp["match_max"]:
        fails.append(f"match_score 期望≤{exp['match_max']} 实得={ms}（泛词降权守门）")
    if "match_min" in exp and ms < exp["match_min"]:
        fails.append(f"match_score 期望≥{exp['match_min']} 实得={ms}")
    return fails


class GoldenEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = conditions.load_conditions()
        cls.registry = entities.load_registry()

    def test_golden_cases(self):
        all_fails = []
        for case in CASES:
            fails = _run_case(case, self.cfg, self.registry)
            if fails:
                all_fails.append(f"[{case['name']}] " + "；".join(fails))
        if all_fails:
            self.fail(f"{len(all_fails)}/{len(CASES)} 黄金用例偏离：\n  " + "\n  ".join(all_fails))


def _report() -> int:
    cfg = conditions.load_conditions()
    registry = entities.load_registry()
    passed = 0
    print(f"黄金评估集 · {len(CASES)} 用例\n" + "─" * 48)
    for case in CASES:
        fails = _run_case(case, cfg, registry)
        if fails:
            print(f"✗ {case['name']}\n    " + "\n    ".join(fails))
        else:
            passed += 1
            print(f"✓ {case['name']}")
    print("─" * 48)
    print(f"准确率 {passed}/{len(CASES)} = {round(100*passed/len(CASES))}%")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(_report())
