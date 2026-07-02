"""引擎入口：跑三源 → build → 写 data/events/<date>.json，并做健康检查。

  python -m engine.run                 # 抓真实数据
  python -m engine.run --date 2026-06-10
  python -m engine.run --sample        # 离线样例信号，端到端演示（不打网络）
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from engine import build, conditions
from engine.sources import cde, cninfo, eia, orderbook, rss, tender

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "events"

# 健康门槛（套用 completeness_audit.py L93-98 思路）
CORE_CONDITIONS = ["卫生级工艺", "锂电注液", "橡塑硫化"]
MIN_PER_CORE = 3


SAMPLE_SIGNALS = [
    {"title": "某乳业｜年产20万吨无菌灌装乳品生产线新建项目，投资5亿元",
     "company": "某乳业股份", "url": "http://example.com/a", "source": "巨潮募投公告",
     "source_type": "capex", "signal_type": "expansion", "lead_time_months": "3-9",
     "date": dt.date.today().isoformat()},
    {"title": "【江苏】年产6GWh动力电池电芯注液化成扩建项目环评受理",
     "company": "某新能源科技", "url": "http://example.com/b", "source": "环评公示",
     "source_type": "project_filing", "signal_type": "expansion", "lead_time_months": "12-18",
     "industry_pull": "电池制造", "date": dt.date.today().isoformat()},
    {"title": "某轮胎｜全钢子午线轮胎硫化车间技改项目，投资3.2亿元",
     "company": "某轮胎集团", "url": "http://example.com/c", "source": "巨潮募投公告",
     "source_type": "capex", "signal_type": "expansion", "lead_time_months": "3-9",
     "date": dt.date.today().isoformat()},
    {"title": "某药业无菌原料药生产基地卫生级隔膜阀采购招标公告",
     "company": "", "url": "http://example.com/d", "source": "政府采购招标",
     "source_type": "tender", "signal_type": "immediate", "lead_time_months": "0-2",
     "date": dt.date.today().isoformat()},
    {"title": "某食品饮料厂CIP清洗系统及灌装产线设备采购",
     "company": "某食品", "url": "http://example.com/e", "source": "政府采购招标",
     "source_type": "tender", "signal_type": "immediate", "lead_time_months": "0-2",
     "date": dt.date.today().isoformat()},
    {"title": "关于召开2025年第三次临时股东大会的通知",
     "company": "某公司", "url": "http://example.com/f", "source": "巨潮募投公告",
     "source_type": "capex", "signal_type": "expansion",
     "date": dt.date.today().isoformat()},
    {"title": "上海东富龙｜冻干生物制药无菌制剂装备产业化基地扩建项目，投资8亿元",
     "company": "东富龙", "url": "http://example.com/g", "source": "巨潮募投公告",
     "source_type": "capex", "signal_type": "expansion", "lead_time_months": "3-9",
     "date": dt.date.today().isoformat()},
    {"title": "楚天科技｜生物工程无菌制剂智能工厂新建项目，投资6亿元",
     "company": "楚天科技", "url": "http://example.com/h", "source": "巨潮募投公告",
     "source_type": "capex", "signal_type": "expansion", "lead_time_months": "3-9",
     "date": dt.date.today().isoformat()},
    {"title": "上海东富龙：2025年度新签订单同比增长47%，海外占比持续提升",
     "company": "东富龙", "url": "http://example.com/i", "source": "装备商订单簿",
     "source_type": "capex", "signal_type": "expansion", "lead_time_months": "3-9",
     "date": dt.date.today().isoformat()},
]


def collect(cfg: dict, sample: bool, with_cde: bool = False) -> list[dict]:
    if sample:
        print("→ 使用离线样例信号")
        return list(SAMPLE_SIGNALS)
    signals = []
    signals += cninfo.fetch(cfg)
    signals += orderbook.fetch(cfg)  # P1#4 装备商订单簿（盯 OEM 自身新签/扩产）
    signals += rss.fetch(cfg)        # 产业新闻流（RSS / 微信公众号，许可型，扩量）
    signals += eia.fetch(cfg)
    signals += tender.fetch(cfg)
    if with_cde:  # CDE 走 Playwright 过瑞数 WAF，较慢，故 opt-in
        signals += cde.fetch(cfg)
    return signals


def health_check(pack: dict) -> list[str]:
    problems = []
    if pack["summary"]["total"] == 0:
        problems.append("零事件")
    by_cond = pack["summary"]["by_condition"]
    for cond in CORE_CONDITIONS:
        if by_cond.get(cond, 0) < MIN_PER_CORE:
            problems.append(f"{cond} 仅 {by_cond.get(cond, 0)} 条（需 ≥{MIN_PER_CORE}）")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ESG 事件引擎")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--sample", action="store_true", help="用离线样例信号演示")
    parser.add_argument("--strict", action="store_true", help="健康检查不达标则 exit 1")
    parser.add_argument("--with-cde", action="store_true",
                        help="额外抓 CDE 优先审评（Playwright 过瑞数 WAF，较慢）")
    args = parser.parse_args(argv)

    as_of = dt.date.fromisoformat(args.date)
    cfg = conditions.load_conditions()
    signals = collect(cfg, args.sample, args.with_cde)
    print(f"→ 收到 {len(signals)} 条原始信号，开始装配事件...")

    pack = build.build_pack(signals, as_of, cfg)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{args.date}.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    s = pack["summary"]
    print(f"\n✓ 写入 {out}")
    print(f"  总事件 {s['total']}｜工况分布 {s['by_condition']}")
    print(f"  提前量 {s['by_lead_time']}｜ok {s['ok']} / unresolved {s['unresolved']}"
          f" / needs_review {s['needs_review']} / stale {s['stale']}")
    print(f"  无金额线索 {s['unknown_value']} 条")

    problems = health_check(pack)
    if problems:
        print(f"\n⚠ 健康检查: {'; '.join(problems)}")
        if args.strict:
            return 1
    else:
        print("\n✓ 健康检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
