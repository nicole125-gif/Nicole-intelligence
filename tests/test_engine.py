"""ESG 事件引擎离线单测。不打网络，用 fixture 标题覆盖核心逻辑。

镜像 test_intelligence_pipeline.py：把 ROOT 加入 sys.path 后直接 import engine 包。
"""

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import build, buyer_role, conditions, entities, ranking, valuation, winnability  # noqa: E402
from engine.sources import rss  # noqa: E402


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

    def test_oem_carries_spec_position(self):
        # O2：spec 位承重边落在 OEM 实体上（只东富龙已进）
        self.assertEqual(entities.get("tofflon")["spec_position"], "in")
        self.assertEqual(entities.get("truking")["spec_position"], "target")
        self.assertEqual(entities.get("morimatsu")["spec_position"], "target")


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

    def test_spec_in_boosts_target_lowers(self):
        # O2：spec 位已进=顺风调升，未进=需 design-in 调降
        base = winnability.assess("某扩产项目", "mid")["score"]
        self.assertGreater(winnability.assess("某扩产项目", "mid", "in")["score"], base)
        self.assertLess(winnability.assess("某扩产项目", "mid", "target")["score"], base)


class CompetitorDensityTests(unittest.TestCase):
    # O3：密度从「竞品据点→工况」派生，取代工况硬编码常量
    def setUp(self):
        self.reg = entities.load_registry()

    def _d(self, cid):
        return winnability.density_from_strongholds(cid, self.reg)

    def test_full_stronghold_is_high(self):
        self.assertEqual(self._d("hygienic"), "high")     # Bürkert+Gemü full
        self.assertEqual(self._d("pharma_ref"), "high")

    def test_partial_stronghold_is_mid(self):
        self.assertEqual(self._d("heavy_process"), "mid")  # 仅 Gemü partial

    def test_no_stronghold_is_low(self):
        # 真因修复：生物合成不在任何竞品据点 → 自然 low，不靠工况特例
        self.assertEqual(self._d("biosynthesis"), "low")
        self.assertEqual(self._d("lithium_injection"), "low")
        self.assertEqual(self._d("rubber_curing"), "low")

    def test_incumbents_named_for_stronghold(self):
        # B1：具名在位竞品；无据点工况返回空（国产友好）
        names = [c["name"] for c in winnability.incumbents_for_condition("hygienic", self.reg)]
        self.assertIn("Bürkert", names)
        self.assertIn("Gemü", names)
        self.assertEqual(winnability.incumbents_for_condition("biosynthesis", self.reg), [])

    def test_biosynthesis_beats_pharma_ref_via_derived_density(self):
        # 同为新建，生物合成(无据点)赢面应高于无菌制剂(Gemü 护城河)
        bio = winnability.assess("某生物合成发酵基地新建", self._d("biosynthesis"))["score"]
        ref = winnability.assess("某无菌注射剂车间新建", self._d("pharma_ref"))["score"]
        self.assertGreater(bio, ref)


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

    def test_oem_owner_spec_in_tailors_action(self):
        # O2：业主即东富龙(spec 已进) → spec_position=in，动作转"盯订单簿"
        ev = build.build_event(
            self._sig(title="无菌灌装制剂产线扩建，投资5亿元", company="东富龙"),
            self.cfg, self.as_of)
        self.assertEqual(ev["spec_position"], "in")
        self.assertIn("订单簿", ev["action"])

    def test_oem_owner_spec_target_recommends_design_in(self):
        # O2：业主即楚天(spec 未进) → spec_position=target，动作转"设计导入"
        ev = build.build_event(
            self._sig(title="无菌灌装制剂产线扩建，投资5亿元", company="楚天科技"),
            self.cfg, self.as_of)
        self.assertEqual(ev["spec_position"], "target")
        self.assertIn("design-in", ev["action"])

    def test_non_oem_owner_has_no_spec_position(self):
        # 终端业主(非 OEM) → 不触发 spec 位逻辑
        ev = build.build_event(
            self._sig(title="无菌灌装乳品线新建投资5亿元", company="某乳业"),
            self.cfg, self.as_of)
        self.assertIsNone(ev["spec_position"])

    def test_event_carries_named_competitors(self):
        # B1：卫生级工况事件带具名在位竞品；锂电(无据点)为空
        hyg = build.build_event(
            self._sig(title="无菌灌装乳品线新建投资5亿元", company="某乳业"),
            self.cfg, self.as_of)
        self.assertTrue(any(c["name"] == "Bürkert" for c in hyg["competitors"]))
        li = build.build_event(
            self._sig(title="动力电池注液化成扩建", company="电池B",
                      source_type="project_filing"),
            self.cfg, self.as_of)
        self.assertEqual(li["competitors"], [])

    def test_oem_orderbook_survives_without_condition(self):
        # P1#4：业主即在册 OEM 的订单簿信号（无工况关键词）→ 保留，用 O4 档案兜底
        ev = build.build_event(
            self._sig(title="2025年度新签订单同比增长47%，海外占比持续提升", company="东富龙"),
            self.cfg, self.as_of)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["working_condition"], ["装备商订单簿"])
        self.assertEqual(ev["working_condition_ids"], [])         # 契约：非真工况 → NO_MATCH 空 ids
        self.assertIn("卫生级隔膜阀", ev["valve_type"]["primary"])  # 来自 tofflon esg_products
        self.assertEqual(ev["spec_position"], "in")               # 东富龙已 spec → 盯订单簿
        self.assertIn("订单簿", ev["action"])

    def test_event_carries_contract_condition_ids(self):
        # 契约就绪：working_condition_ids 与 labels 平行，且取自合法枚举
        ev = build.build_event(
            self._sig(title="无菌灌装乳品线新建投资5亿元", company="某乳业"),
            self.cfg, self.as_of)
        self.assertEqual(len(ev["working_condition_ids"]), len(ev["working_condition"]))
        self.assertIn("hygienic", ev["working_condition_ids"])
        allowed = {"biosynthesis", "hygienic", "lithium_injection",
                   "rubber_curing", "heavy_process", "pharma_ref"}
        self.assertTrue(set(ev["working_condition_ids"]) <= allowed)

    def test_non_oem_without_condition_still_dropped(self):
        # 非 OEM 业主 + 无工况 → 仍丢弃（订单簿放行只对在册 OEM）
        ev = build.build_event(
            self._sig(title="2025年度新签订单同比增长47%", company="某贸易公司"),
            self.cfg, self.as_of)
        self.assertIsNone(ev)

    def test_l1_enrichment_fields(self):
        # L1：金额显式 + 命中证据 + ok 事件无复核理由
        ev = build.build_event(
            self._sig(title="某乳业无菌灌装乳品线新建投资5亿元", company="某乳业"),
            self.cfg, self.as_of)
        self.assertEqual(ev["capex_amount"], 500_000_000)
        self.assertEqual(ev["capex_currency"], "CNY")
        self.assertIn("无菌", ev["matched_keywords"])
        self.assertEqual(ev["extraction_notes"], "")

    def test_l1_extraction_notes_unresolved_and_nomatch(self):
        # L1：unresolved 给理由；订单簿即使 ok 也标 NO_MATCH
        unres = build.build_event(
            self._sig(title="某无菌原料药基地卫生级隔膜阀采购招标", company="",
                      source_type="tender", signal_type="immediate"),
            self.cfg, self.as_of)
        self.assertEqual(unres["review_flag"], "unresolved")
        self.assertTrue(unres["extraction_notes"])
        ob = build.build_event(
            self._sig(title="2025年度新签订单同比增长47%", company="东富龙"),
            self.cfg, self.as_of)
        self.assertIn("NO_MATCH", ob["extraction_notes"])

    def test_l2_clusters_corroborate_by_owner(self):
        # L2：同一主体多条事件聚合成账户级信号簇，corroboration≥2 提置信
        signals = [
            self._sig(title="上海东富龙冻干无菌制剂基地扩建投资8亿元", company="东富龙"),
            self._sig(title="东富龙2025年新签订单同比增长47%", company="东富龙"),
            self._sig(title="某乳业无菌灌装乳品线新建投资5亿元", company="某乳业"),
        ]
        pack = build.build_pack(signals, self.as_of, self.cfg)
        tof = next(c for c in pack["clusters"] if c["owner"]["id"] == "tofflon")
        self.assertEqual(tof["corroboration"], 2)
        self.assertEqual(tof["spec_position"], "in")
        self.assertGreaterEqual(tof["confidence"], 85)
        self.assertEqual(pack["summary"]["corroborated"], 1)  # 仅东富龙印证≥2

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


class RssSourceTests(unittest.TestCase):
    """RSS/微信源管道：通吃任意 RSS 落盘文件，按工况词过滤、映射字段。"""

    def setUp(self):
        self.cfg = conditions.load_conditions()

    def _write(self, tmp: Path, items: list[dict]):
        (tmp / "vert.json").write_text(
            json.dumps({"vertical_id": "test", "items": items}, ensure_ascii=False),
            encoding="utf-8")

    def test_matching_item_becomes_news_signal(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._write(tmp, [
                {"id": "1", "title": "某药企无菌灌装制剂生产线新建项目开工",
                 "summary": "", "url": "https://mp.weixin.qq.com/s/abc",
                 "source": "蒲公英Ouryao", "pub_date": "2026-06-20T00:00:00+00:00"},
                {"id": "2", "title": "手机越卖越贵厂商越来越慌",  # 无工况词 → 丢
                 "summary": "", "url": "https://mp.weixin.qq.com/s/x",
                 "source": "半导体纵横", "pub_date": "2026-06-20T00:00:00+00:00"},
            ])
            out = rss.fetch(self.cfg, rss_dir=tmp)
        self.assertEqual(len(out), 1)
        s = out[0]
        self.assertEqual(s["source_type"], "news")
        self.assertEqual(s["source"], "蒲公英Ouryao")
        self.assertEqual(s["date"], "2026-06-20")
        self.assertEqual(s["company"], "")  # 新闻不臆造业主

    def test_missing_dir_returns_empty(self):
        self.assertEqual(rss.fetch(self.cfg, rss_dir=Path("/nonexistent/rss")), [])

    def test_news_item_builds_into_event(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._write(tmp, [
                {"id": "1", "title": "某乳企无菌灌装乳品线新建投资3亿元",
                 "summary": "", "url": "https://mp.weixin.qq.com/s/abc",
                 "source": "食品板", "pub_date": "2026-06-20T00:00:00+00:00"},
            ])
            sigs = rss.fetch(self.cfg, rss_dir=tmp)
        pack = build.build_pack(sigs, dt.date(2026, 6, 25), self.cfg)
        self.assertEqual(pack["summary"]["total"], 1)
        self.assertEqual(pack["events"][0]["source"]["type"], "news")


if __name__ == "__main__":
    unittest.main()
