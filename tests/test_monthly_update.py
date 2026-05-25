import copy
import importlib.util
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MonthlyUpdateTests(unittest.TestCase):
    def test_apply_overrides_updates_tracks_kpis_and_review_notes(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        payload = {
            "date": "2026-06-05",
            "tracks": {"e2": {"heat": 82.8, "D": 85, "C": 82, "P": 75, "Pol": 90}},
            "kpis": [],
        }
        overrides = {
            "period": "2026-06",
            "tracks": {
                "e2": {
                    "heat": 84.0,
                    "D": 86,
                    "C": 83,
                    "P": 76,
                    "Pol": 90,
                    "tw": "半导体设备国产替代仍是本月最高优先级之一。",
                    "act": "优先跟踪北方华创、中微及先进封装设备链。",
                }
            },
            "track_use": {"e2": ["国产替代机会", "用于判断半导体设备国产化客户优先级。"]},
            "kpis": [{"v": "84.0", "l": "最高 Heat", "d": "半导体设备国产化", "c": "exp"}],
            "review_notes": ["请重点核查 e2 的政策分。"],
        }

        result, applied = monthly.apply_overrides(copy.deepcopy(payload), overrides)

        self.assertEqual(result["tracks"]["e2"]["heat"], 84.0)
        self.assertEqual(result["tracks"]["e2"]["tw"], "半导体设备国产替代仍是本月最高优先级之一。")
        self.assertEqual(result["track_use"]["e2"], ["国产替代机会", "用于判断半导体设备国产化客户优先级。"])
        self.assertEqual(result["kpis"][0]["d"], "半导体设备国产化")
        self.assertEqual(applied, ["track:e2", "track_use:e2", "kpis", "review_notes"])

    def test_build_monthly_summary_contains_expected_sections(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "2026-06-summary.md"
            payload = {
                "tracks": {
                    "e2": {"heat": 84.0, "delta": 1.2, "tr": "up"},
                    "p4": {"heat": 52.2, "delta": -5.3, "tr": "dn"},
                }
            }
            source_report = {
                "downloaded": [{"path": "reports/2026-06/example.pdf"}],
                "failed": [{"query": "半导体设备 国产化 月度 2026", "reason": "no allowed result"}],
            }

            monthly.write_summary(
                path=summary_path,
                period="2026-06",
                payload=payload,
                source_report=source_report,
                applied_overrides=["track:e2"],
                review_notes=["请重点核查半导体设备。"],
                step_notes=["RAG rebuild skipped: command failed with exit code 1"],
            )

            text = summary_path.read_text(encoding="utf-8")
            self.assertIn("# Nicole Intelligence Monthly Update · 2026-06", text)
            self.assertIn("新增报告数量：1", text)
            self.assertIn("最高 Heat：e2 84.0", text)
            self.assertIn("最大下滑：p4 -5.3", text)
            self.assertIn("track:e2", text)
            self.assertIn("RAG rebuild skipped: command failed with exit code 1", text)
            self.assertIn("请重点核查半导体设备。", text)

    def test_build_injection_payload_uses_history_tracks_and_today_date(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        payload = {
            "tracks": {"e2": {"heat": 84.0, "delta": 1.2, "tr": "up"}},
            "track_use": {"e2": ["国产替代机会", "用于判断客户优先级。"]},
            "kpis": [{"v": "84.0", "l": "最高 Heat", "d": "半导体设备国产化", "c": "exp"}],
        }

        result = monthly.build_injection_payload("2026-05", payload, today=monthly.dt.date(2026, 5, 19))

        self.assertEqual(result["date"], "2026-05-19")
        self.assertEqual(result["tracks"]["e2"]["heat"], 84.0)
        self.assertEqual(result["track_use"]["e2"][0], "国产替代机会")
        self.assertEqual(result["kpis"][0]["d"], "半导体设备国产化")

    def test_resolve_run_date_parses_cli_date(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        self.assertEqual(str(monthly.resolve_run_date("2026-05-19")), "2026-05-19")

    def test_sync_data_js_metadata_updates_last_updated(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.js"
            path.write_text(
                'window.BURKERT_DATA = { meta: { lastUpdated: "2026-05-20", updatedBy: "Nicole" } };\n',
                encoding="utf-8",
            )

            ok = monthly.sync_data_js_metadata(path, today=monthly.dt.date(2026, 5, 25))

            self.assertTrue(ok)
            self.assertIn('lastUpdated: "2026-05-25"', path.read_text(encoding="utf-8"))

    def test_refresh_rss_restores_backup_when_refreshed_index_is_empty(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        with tempfile.TemporaryDirectory() as tmp:
            rss_dir = Path(tmp) / "rss"
            rss_dir.mkdir()
            original = '{"generated_at":"2026-05-19T04:10:46Z","verticals":{"semiconductor":{"item_count":14}}}\n'
            index_path = rss_dir / "index.json"
            index_path.write_text(original, encoding="utf-8")

            def fake_run_step(name, cmd, step_notes, dry_run=False):
                index_path.write_text(
                    '{"generated_at":"2026-05-19T05:00:00Z","verticals":{"semiconductor":{"item_count":0}}}\n',
                    encoding="utf-8",
                )
                return True

            with mock.patch.object(monthly, "RSS_DIR", rss_dir), mock.patch.object(monthly, "run_step", side_effect=fake_run_step):
                step_notes = []
                ok = monthly.refresh_rss(step_notes)

            self.assertFalse(ok)
            self.assertIn("RSS refresh rolled back: refreshed feed index was empty", step_notes)
            self.assertEqual(index_path.read_text(encoding="utf-8"), original)

    def test_inject_scores_can_patch_track_use(self):
        inject = load_module("scripts/inject_scores.py", "inject_scores_module")
        html = """
<script>
const TRACK_USE = {
  zh: {
    e2:['国产替代机会','旧说明'],
    p2:['中试放大','旧说明']
  },
  en: {}
};
</script>
<span>最近更新 2026-05-01</span>
<span>Last updated 2026-03-31</span>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.html"
            path.write_text(html, encoding="utf-8")

            inject.inject_scores(
                {
                    "date": "2026-05-19",
                    "track_use": {"e2": ["客户优先级", "用于判断半导体客户优先级。"]},
                },
                index_path=path,
                backup=False,
            )

            patched = path.read_text(encoding="utf-8")
            self.assertIn("e2:['客户优先级','用于判断半导体客户优先级。']", patched)
            self.assertIn("p2:['中试放大','旧说明']", patched)
            self.assertIn("最近更新 2026-05-19", patched)
            self.assertIn("Last updated 2026-05-19", patched)

    def test_cleanup_transient_artifacts_removes_only_generated_files(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pulse_vectordb").mkdir()
            (root / "pulse_vectordb" / "chroma.sqlite3").write_text("db", encoding="utf-8")
            (root / "scripts" / "__pycache__").mkdir(parents=True)
            (root / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"x")
            (root / "tests" / "__pycache__").mkdir(parents=True)
            (root / "tests" / "__pycache__" / "x.pyc").write_bytes(b"x")
            (root / "index.html.bak").write_text("backup", encoding="utf-8")
            (root / "data").mkdir()
            keep = root / "data" / "history.json"
            keep.write_text("{}", encoding="utf-8")

            with mock.patch.object(monthly, "ROOT", root):
                removed = monthly.cleanup_transient_artifacts()

            self.assertEqual(
                sorted(removed),
                ["index.html.bak", "pulse_vectordb", "scripts/__pycache__", "tests/__pycache__"],
            )
            self.assertFalse((root / "pulse_vectordb").exists())
            self.assertTrue(keep.exists())


if __name__ == "__main__":
    unittest.main()
