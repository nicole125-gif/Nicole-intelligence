"""ESG 事件引擎离线单测。不打网络，用 fixture 标题覆盖核心逻辑。

镜像 test_intelligence_pipeline.py：把 ROOT 加入 sys.path 后直接 import engine 包。
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import build, buyer_role, conditions, entities, ranking, valuation, winnability  # noqa: E402


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = conditions.load_conditions()

    def test_hygienic_maps_to_angle_seat_valve(self):
        cond = conditions.classify_condition("某乳品厂无菌灌装线新建", "capex", self.cfg)
        self.assertEqual(cond["primary_id"], "hygienic")
        self.assertIn("角座阀", cond["valve_type"]["primary"])
        self.assertGreater(cond["match_score"], 0)

    def test_lithium_maps_to_injection_valve(self):
        cond = conditions.classify_condition("动力电池电芯注液化成扩建", "project_filing", self.cfg)
        self.assertEqual(cond["primary_id"], "lithium_injection")
        self.assertIn("注液阀", cond["valve_type"]["primary"])

    def test_biosynthesis_is_domestic_friendly_not_downgraded(self):
        # 甜点区：发酵/生物合成上游应进 biosynthesis(low)，不被 pharma_ref(high) 误降
        cond = conditions.classify_condition("某生物合成原料药发酵生产基地新建", "capex", self.cfg)
        self.assertEqual(cond["primary_id"], "biosynthesis")
        self.assertEqual(cond["competitor_density"], "low")

    def test_sterile_drug_stays_gemu_moat(self):
        # 无菌制剂仍是 Gemü 护城河，留在 pharma_ref(high)
        cond = conditions.classify_condition("某生物药无菌注射剂冻干车间", "capex", self.cfg)
        self.assertEqual(cond["primary_id"], "pharma_ref")
        self.assertEqual(cond["competitor_density"], "high")

    def test_food_fermentation_stays_hygienic(self):
        # 带食品词的发酵仍归 hygienic(high)，不被新工况抢走
        cond = conditions.classify_condition("某乳品厂发酵灌装生产线新建", "capex", self.cfg)
        self.assertEqual(cond["primary_id"], "hygienic")

    def test_non_esg_text_scores_zero(self):
        cond = conditions.classify_condition("关于召开临时股东大会的通知", "capex", self.cfg)
        self.assertEqual(cond["match_score"], 0.0)
        self.assertIsNone(cond["primary_id"])

    def test_tender_source_boost_applied(self):
        # 招标源 +2.0，应高于同文本的 cninfo
        t = conditions.classify_condition("卫生级隔膜阀采购", "tender", self.cfg)
        c = conditions.classify_condition("卫生级隔膜阀采购", "capex", self.cfg)
        self.assertGreater(t["match_score"], c["match_score"])


class BuyerRoleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = conditions.load_conditions()

    def _role(self, text, source_type, signal_type):
        cond = conditions.classify_condition(text, source_type, self.cfg)
        return buyer_role.infer_buyer_role(
            cond["buyer_role_cfg"], signal_type, source_type, cond["match_score"])

    def test_hygienic_expansion_targets_oem(self):
        role = self._role("无菌灌装产线新建", "capex", "expansion")
        self.assertEqual(role["inferred"], "设备OEM")

    def test_rubber_targets_epc(self):
        role = self._role("轮胎硫化车间技改", "capex", "expansion")
        self.assertEqual(role["inferred"], "EPC")

    def test_tender_overrides_to_secondary(self):
        role = self._role("卫生级隔膜阀采购招标", "tender", "immediate")
        self.assertEqual(role["inferred"], "终端工厂")  # hygienic secondary


class ValuationTests(unittest.TestCase):
    def setUp(self):
        self.ratio = {"low": 0.005, "high": 0.015, "label": "x"}

    def test_capex_uses_point_five_to_one_point_five_percent(self):
        # 照抄 p4 断言精神：5亿 → 250万~750万
        est = valuation.estimate_value("投资5亿元新建车间", self.ratio)
        self.assertEqual(est["status"], "model_estimate")
        self.assertEqual(est["project_capex"], 500_000_000)
        self.assertEqual(est["low"], 2_500_000)
        self.assertEqual(est["high"], 7_500_000)

    def test_no_amount_is_unknown_not_guessed(self):
        est = valuation.estimate_value("新建生产线项目", self.ratio)
        self.assertEqual(est["status"], "unknown")
        self.assertIsNone(est["high"])

    def test_tonnage_not_misread_as_money(self):
        # "年产6万吨" 是产量不是钱 → unknown，不能算成 6万元
        est = valuation.estimate_value("年产6万吨钛白粉扩建项目", self.ratio)
        self.assertEqual(est["status"], "unknown")

    def test_yuan_amount_still_parsed_alongside_tonnage(self):
        # "年产5万吨...投资3.2亿元" → 取 3.2亿元
        est = valuation.estimate_value("年产5万吨电子纱，投资3.2亿元", self.ratio)
        self.assertEqual(est["status"], "model_estimate")
        self.assertEqual(est["project_capex"], 320_000_000)


class ValueBandTests(unittest.TestCase):
    def _band(self, text, status="unknown", capex=None):
        est = {"status": status, "project_capex": capex, "high": capex}
        return valuation.value_band(text, est)["band"]

    def test_big_capacity_no_money_is_big(self):
        # 标题没写金额、但 30万吨产能 → 不该被埋，应判"大"
        self.assertEqual(self._band("实施年产30万吨乙二醇项目技改"), "大")

    def test_yi_scale_capacity_is_big(self):
        self.assertEqual(self._band("投资建设年产72亿平方米锂电隔膜项目"), "大")

    def test_five_yi_money_is_big(self):
        self.assertEqual(self._band("投资5亿元新建车间", "model_estimate", 500_000_000), "大")

    def test_mid_money_is_zhong(self):
        self.assertEqual(self._band("某技改项目", "model_estimate", 300_000_000), "中")

    def test_pure_upgrade_is_unknown(self):
        self.assertEqual(self._band("设备升级改造"), "未知")

    def test_tonnage_capacity_complements_money_exclusion(self):
        # 6万吨：金额解析排除它(unknown)，但产能信号仍识别为"有产能"
        self.assertEqual(valuation.capacity_scale("年产6万吨钛白粉"), 1)


class EntityTests(unittest.TestCase):
    def test_alias_and_suffix_resolve_to_same_id(self):
        # 别名 + 后缀变体应解析到同一战略实体 id
        a = entities.resolve("楚天")
        b = entities.resolve("楚天科技股份有限公司")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(a["id"], "truking")
        self.assertTrue(a["resolved"])

    def test_unregistered_owner_gets_stable_auto_id(self):
        # 未登记业主 → 稳定 auto-id（同名/后缀变体同 id），resolved=False
        a = entities.resolve("某某新材料")
        b = entities.resolve("某某新材料有限公司")
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(a["id"].startswith("auto:"))
        self.assertFalse(a["resolved"])

    def test_auto_id_stable_when_core_name_ends_in_suffix_word(self):
        # 核心名本身以"公司"结尾时，长短变体也须收敛到同一 auto-id
        a = entities.resolve("某不在册公司")
        b = entities.resolve("某不在册公司有限公司")
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(a["id"].startswith("auto:"))

    def test_empty_owner_resolves_to_none(self):
        r = entities.resolve("")
        self.assertIsNone(r["id"])
        self.assertFalse(r["resolved"])

    def test_oem_and_competitor_independently_addressable(self):
        self.assertEqual(entities.get("burkert")["type"], "competitor")
        self.assertEqual(entities.get("truking")["type"], "oem")

    def test_oem_carries_merged_profile(self):
        # O4：OEM 实体带上 p4_opportunity_map 折叠进来的档案属性
        prof = entities.get("truking")["profile"]
        self.assertIn("设备部", prof["target_roles"])
        self.assertIn("卫生级隔膜阀", prof["esg_products"])
        self.assertEqual(prof["capex_ratio"]["high"], 0.015)

    def test_competitor_carries_threat_profile(self):
        # O4：竞品实体带上 products_analysis 折叠进来的威胁档
        self.assertEqual(entities.get("burkert")["profile"]["avg_threat_level"], 4.3)
        self.assertEqual(entities.get("gemu")["profile"]["avg_threat_level"], 4.0)


class WinnabilityTests(unittest.TestCase):
    def test_greenfield_beats_brownfield(self):
        gf = winnability.assess("新建生产基地项目", "mid")["score"]
        bf = winnability.assess("某产线技改升级改造", "mid")["score"]
        self.assertGreater(gf, bf)

    def test_low_competitor_density_beats_high(self):
        lo = winnability.assess("某扩产项目", "low")["score"]
        hi = winnability.assess("某扩产项目", "high")["score"]
        self.assertGreater(lo, hi)

    def test_score_clamped(self):
        s = winnability.assess("新建生产基地", "low")["score"]
        self.assertLessEqual(s, 1.0)
        self.assertGreaterEqual(winnability.assess("技改", "high")["score"], 0.15)


class RankingTests(unittest.TestCase):
    def test_big_band_beats_unknown(self):
        self.assertGreater(ranking.value_factor("大"), ranking.value_factor("未知"))

    def test_lead_factor_l0_beats_l2(self):
        self.assertGreater(ranking.lead_factor("L0"), ranking.lead_factor("L2"))

    def test_big_near_strong_outranks_unknown_far_weak(self):
        strong = ranking.rank_score("大", "L0", 9)
        weak = ranking.rank_score("未知", "L2", 2)
        self.assertGreater(strong, weak)

    def test_winnability_discounts_rank(self):
        high_win = ranking.rank_score("大", "L0", 9, 0.9)
        low_win = ranking.rank_score("大", "L0", 9, 0.3)
        self.assertGreater(high_win, low_win)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.cfg = conditions.load_conditions()
        self.as_of = dt.date(2026, 6, 10)

    def _sig(self, **kw):
        base = {"title": "", "url": "http://x", "source": "巨潮募投公告",
                "source_type": "capex", "signal_type": "expansion",
                "date": "2026-06-09"}
        base.update(kw)
        return base

    def test_non_esg_signal_discarded(self):
        ev = build.build_event(self._sig(title="临时股东大会通知"), self.cfg, self.as_of)
        self.assertIsNone(ev)

    def test_full_event_has_required_fields(self):
        ev = build.build_event(
            self._sig(title="年产20万吨无菌灌装乳品线新建，投资5亿元", company="某乳业"),
            self.cfg, self.as_of)
        self.assertIsNotNone(ev)
        self.assertTrue(ev["working_condition"])
        self.assertTrue(ev["valve_type"]["primary"])
        self.assertIsNotNone(ev["buyer_role"]["inferred"])
        self.assertIn(ev["lead_time"]["level"], {"L0", "L1", "L2"})
        self.assertEqual(ev["est_value"]["status"], "model_estimate")

    def test_missing_owner_flagged_unresolved(self):
        ev = build.build_event(
            self._sig(title="某无菌灌装产线设备采购招标", company="",
                      source_type="tender", signal_type="immediate"),
            self.cfg, self.as_of)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["review_flag"], "unresolved")

    def test_pack_summary_counts(self):
        signals = [
            self._sig(title="无菌灌装乳品线新建投资5亿元", company="乳业A"),
            self._sig(title="动力电池注液化成扩建", company="电池B",
                      source_type="project_filing", lead_time_months="12-18"),
            self._sig(title="临时股东大会通知", company="C"),  # 应被丢弃
        ]
        pack = build.build_pack(signals, self.as_of, self.cfg)
        self.assertEqual(pack["summary"]["total"], 2)
        self.assertEqual(pack["schema_version"], "1.0")
        # rank 降序
        scores = [e["rank_score"] for e in pack["events"] if e["review_flag"] == "ok"]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
