import argparse
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_claim_retry_throughput.py"
SPEC = importlib.util.spec_from_file_location("benchmark_claim_retry_throughput", SCRIPT)
assert SPEC is not None
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark)


class ClaimRetryThroughputBenchmarkTests(unittest.TestCase):
    def test_float_list_parsing_supports_matrix_values(self):
        self.assertEqual(benchmark.parse_float_list("0,0.02, 0.05"), [0.0, 0.02, 0.05])
        self.assertEqual(
            benchmark.flatten_float_lists([[0.0, 0.02], [0.05]], default=[0.02]),
            [0.0, 0.02, 0.05],
        )
        self.assertEqual(benchmark.flatten_float_lists(None, default=[0.02]), [0.02])

    def test_profile_defaults_keep_quick_small_and_cutover_broad(self):
        quick = benchmark.resolve_run_config(
            argparse.Namespace(
                profile="quick",
                iterations=None,
                think_seconds=None,
                workload=None,
                format=None,
            )
        )
        cutover = benchmark.resolve_run_config(
            argparse.Namespace(
                profile="cutover",
                iterations=None,
                think_seconds=None,
                workload=None,
                format=None,
            )
        )
        overridden = benchmark.resolve_run_config(
            argparse.Namespace(
                profile="cutover",
                iterations=3,
                think_seconds=[[0.01]],
                workload=["file-back"],
                format="json",
            )
        )

        self.assertEqual(
            quick,
            {
                "iterations": 25,
                "think_seconds_values": [0.02],
                "workloads": ["hot-page"],
                "format": "json",
            },
        )
        self.assertEqual(
            cutover,
            {
                "iterations": 25,
                "think_seconds_values": [0.0, 0.02, 0.05],
                "workloads": ["hot-page", "file-back"],
                "format": "table",
            },
        )
        self.assertEqual(
            overridden,
            {
                "iterations": 3,
                "think_seconds_values": [0.01],
                "workloads": ["file-back"],
                "format": "json",
            },
        )

    def test_comparison_reports_completed_and_surviving_throughput_ratios(self):
        comparison = benchmark.build_comparison(
            [
                {
                    "mode": "uncoordinated",
                    "completed_writes_per_second": 10.0,
                    "surviving_markers_per_second": 5.0,
                    "lost_markers": 25,
                    "lost_log_markers": 2,
                },
                {
                    "mode": "claim_retry",
                    "completed_writes_per_second": 4.0,
                    "surviving_markers_per_second": 4.0,
                    "lost_markers": 0,
                    "lost_log_markers": 0,
                    "p95_claim_wait_seconds": 0.42,
                    "active_claim_overlap_count": 0,
                },
            ]
        )

        self.assertEqual(comparison["claim_retry_completed_writes_per_second_ratio"], 0.4)
        self.assertEqual(comparison["claim_retry_surviving_markers_per_second_ratio"], 0.8)
        self.assertEqual(comparison["claim_retry_lost_marker_delta"], -25)
        self.assertEqual(comparison["claim_retry_lost_log_marker_delta"], -2)
        self.assertEqual(comparison["claim_retry_active_claim_overlap_count"], 0)
        self.assertEqual(comparison["claim_retry_p95_claim_wait_seconds"], 0.42)

    def test_gate_requires_lossless_strict_non_overlapping_claim_retry(self):
        thresholds = {
            "min_surviving_throughput_ratio": 0.75,
            "max_p95_claim_wait_seconds": 0.5,
        }

        passing = benchmark.evaluate_scenario_gate(
            results=[
                {"mode": "uncoordinated", "lost_markers": 20, "strict_ok": False},
                {
                    "mode": "claim_retry",
                    "lost_markers": 0,
                    "lost_log_markers": 0,
                    "strict_ok": True,
                    "strict_failures": [],
                    "active_claim_overlap_count": 0,
                },
            ],
            comparison={
                "claim_retry_surviving_markers_per_second_ratio": 0.8,
                "claim_retry_p95_claim_wait_seconds": 0.42,
            },
            thresholds=thresholds,
        )
        self.assertTrue(passing["ok"])
        self.assertEqual(passing["failures"], [])

        failing = benchmark.evaluate_scenario_gate(
            results=[
                {
                    "mode": "claim_retry",
                    "lost_markers": 1,
                    "lost_log_markers": 1,
                    "strict_ok": False,
                    "strict_failures": [{"type": "concurrent_page_update_overwrite"}],
                    "active_claim_overlap_count": 2,
                },
            ],
            comparison={
                "claim_retry_surviving_markers_per_second_ratio": 0.7,
                "claim_retry_p95_claim_wait_seconds": 0.6,
            },
            thresholds=thresholds,
        )

        self.assertFalse(failing["ok"])
        self.assertEqual(
            [failure["type"] for failure in failing["failures"]],
            [
                "lost_markers",
                "lost_log_markers",
                "strict_not_green",
                "active_claim_overlap",
                "surviving_throughput_ratio_below_threshold",
                "p95_claim_wait_above_threshold",
            ],
        )

    def test_cutover_metric_summary_reports_worst_case_without_thresholds(self):
        summary = benchmark.summarize_cutover_metrics(
            [
                {
                    "workload": "hot-page",
                    "think_seconds": 0.0,
                    "comparison": {
                        "claim_retry_completed_writes_per_second_ratio": 0.4,
                        "claim_retry_surviving_markers_per_second_ratio": 0.8,
                        "claim_retry_p95_claim_wait_seconds": 0.42,
                    },
                    "results": [
                        {"mode": "uncoordinated", "lost_markers": 25},
                        {
                            "mode": "claim_retry",
                            "lost_markers": 0,
                            "lost_log_markers": 0,
                            "strict_ok": True,
                            "active_claim_overlap_count": 0,
                        },
                    ],
                },
                {
                    "workload": "file-back",
                    "think_seconds": 0.05,
                    "comparison": {
                        "claim_retry_completed_writes_per_second_ratio": 0.35,
                        "claim_retry_surviving_markers_per_second_ratio": 0.71,
                        "claim_retry_p95_claim_wait_seconds": 0.56,
                    },
                    "results": [
                        {
                            "mode": "claim_retry",
                            "lost_markers": 0,
                            "lost_log_markers": 0,
                            "strict_ok": True,
                            "active_claim_overlap_count": 0,
                        },
                    ],
                },
            ]
        )

        self.assertEqual(summary["scenario_count"], 2)
        self.assertEqual(summary["compared_scenario_count"], 2)
        self.assertEqual(summary["claim_retry_scenario_count"], 2)
        self.assertEqual(summary["min_claim_retry_surviving_throughput_ratio"], 0.71)
        self.assertEqual(summary["min_claim_retry_completed_throughput_ratio"], 0.35)
        self.assertEqual(summary["max_claim_retry_p95_claim_wait_seconds"], 0.56)
        self.assertEqual(summary["max_claim_retry_active_claim_overlap_count"], 0)
        self.assertEqual(summary["total_claim_retry_lost_markers"], 0)
        self.assertEqual(summary["total_claim_retry_lost_log_markers"], 0)
        self.assertTrue(summary["all_claim_retry_strict_green"])

    def test_threshold_args_are_optional_until_owner_sets_cutover_values(self):
        args = argparse.Namespace(
            min_surviving_throughput_ratio=None,
            max_p95_claim_wait_seconds=None,
        )
        thresholds = benchmark.gate_thresholds(args)
        scenario_gate = benchmark.evaluate_scenario_gate(
            results=[],
            comparison=None,
            thresholds=thresholds,
        )
        summary = benchmark.summarize_gate(
            [{"workload": "file-back", "think_seconds": 0.02, "gate": scenario_gate}],
            thresholds,
        )
        required = benchmark.summarize_gate(
            [{"workload": "file-back", "think_seconds": 0.02, "gate": scenario_gate}],
            thresholds,
            require_thresholds=True,
        )

        self.assertFalse(scenario_gate["enabled"])
        self.assertIsNone(scenario_gate["ok"])
        self.assertEqual(scenario_gate["reason"], "thresholds_not_set")
        self.assertFalse(summary["enabled"])
        self.assertFalse(summary["required"])
        self.assertIsNone(summary["ok"])
        self.assertFalse(required["enabled"])
        self.assertTrue(required["required"])
        self.assertFalse(required["ok"])
        self.assertEqual(required["failures"], [{"type": "thresholds_not_set"}])

    def test_required_threshold_gate_requires_both_owner_values(self):
        thresholds = {
            "min_surviving_throughput_ratio": 0.75,
            "max_p95_claim_wait_seconds": None,
        }
        scenario_gate = benchmark.evaluate_scenario_gate(
            results=[
                {
                    "mode": "claim_retry",
                    "lost_markers": 0,
                    "lost_log_markers": 0,
                    "strict_ok": True,
                    "strict_failures": [],
                    "active_claim_overlap_count": 0,
                }
            ],
            comparison={
                "claim_retry_surviving_markers_per_second_ratio": 0.8,
                "claim_retry_p95_claim_wait_seconds": 0.42,
            },
            thresholds=thresholds,
        )
        required = benchmark.summarize_gate(
            [{"workload": "file-back", "think_seconds": 0.02, "gate": scenario_gate}],
            thresholds,
            require_thresholds=True,
        )

        self.assertTrue(scenario_gate["ok"])
        self.assertTrue(required["enabled"])
        self.assertTrue(required["required"])
        self.assertFalse(required["ok"])
        self.assertEqual(required["reason"], "required_thresholds_missing")
        self.assertEqual(
            required["failures"],
            [
                {
                    "type": "required_thresholds_missing",
                    "missing": ["max_p95_claim_wait_seconds"],
                }
            ],
        )

    def test_rendered_tables_include_cutover_metrics_for_file_back_workload(self):
        output = {
            "scenarios": [
                {
                    "workload": "file-back",
                    "think_seconds": 0.02,
                    "results": [
                        {
                            "mode": "uncoordinated",
                            "attempted_markers": 50,
                            "survived_markers": 25,
                            "lost_markers": 25,
                            "lost_log_markers": 0,
                            "strict_ok": False,
                            "active_claim_overlap_count": 0,
                            "p95_claim_wait_seconds": None,
                            "completed_writes_per_second": 5.0,
                            "surviving_markers_per_second": 2.5,
                            "elapsed_seconds": 10.0,
                        },
                        {
                            "mode": "claim_retry",
                            "attempted_markers": 50,
                            "survived_markers": 50,
                            "lost_markers": 0,
                            "lost_log_markers": 0,
                            "strict_ok": True,
                            "active_claim_overlap_count": 0,
                            "p95_claim_wait_seconds": 0.439,
                            "completed_writes_per_second": 2.0,
                            "surviving_markers_per_second": 2.0,
                            "elapsed_seconds": 25.0,
                        },
                    ],
                    "comparison": {
                        "claim_retry_completed_writes_per_second_ratio": 0.4,
                        "claim_retry_surviving_markers_per_second_ratio": 0.8,
                        "claim_retry_lost_marker_delta": -25,
                        "claim_retry_lost_log_marker_delta": 0,
                        "claim_retry_active_claim_overlap_count": 0,
                        "claim_retry_p95_claim_wait_seconds": 0.439,
                    },
                    "gate": {"enabled": True, "ok": True, "failures": []},
                }
            ],
            "gate": {"enabled": True, "ok": True},
            "metric_summary": {
                "scenario_count": 1,
                "compared_scenario_count": 1,
                "claim_retry_scenario_count": 1,
                "min_claim_retry_surviving_throughput_ratio": 0.8,
                "min_claim_retry_completed_throughput_ratio": 0.4,
                "max_claim_retry_p95_claim_wait_seconds": 0.439,
                "max_claim_retry_active_claim_overlap_count": 0,
                "total_claim_retry_lost_markers": 0,
                "total_claim_retry_lost_log_markers": 0,
                "all_claim_retry_strict_green": True,
            },
        }

        table = benchmark.render_tables(output)

        self.assertIn("## Claim Retry Throughput Gate", table)
        self.assertIn("| workload | think_s | mode | attempted | survived | lost | log_lost | strict | overlap | p95_wait_s | completed/s | surviving/s | elapsed_s |", table)
        self.assertIn("| file-back | 0.02 | claim_retry | 50 | 50 | 0 | 0 | green | 0 | 0.439 | 2 | 2 | 25 |", table)
        self.assertIn("## Cutover Metric Summary", table)
        self.assertIn("| claim_retry_scenarios | 1/1 |", table)
        self.assertIn("| compared_scenarios | 1/1 |", table)
        self.assertIn("| min_surviving_ratio | 0.8 |", table)
        self.assertIn("| max_p95_wait_s | 0.439 |", table)
        self.assertIn("| all_strict_green | yes |", table)
        self.assertIn("## Claim Retry vs Uncoordinated", table)
        self.assertIn("| file-back | 0.02 | 0.4 | 0.8 | -25 | 0 | 0 | 0.439 |", table)
        self.assertIn("## Cutover Threshold Gate", table)
        self.assertIn("| file-back | 0.02 | pass |  |", table)

    def test_rendered_required_threshold_gate_fails_when_thresholds_are_missing(self):
        output = {
            "scenarios": [
                {
                    "workload": "file-back",
                    "think_seconds": 0.02,
                    "results": [
                        {
                            "mode": "claim_retry",
                            "attempted_markers": 2,
                            "survived_markers": 2,
                            "lost_markers": 0,
                            "lost_log_markers": 0,
                            "strict_ok": True,
                            "active_claim_overlap_count": 0,
                            "p95_claim_wait_seconds": 0.42,
                            "completed_writes_per_second": 1.0,
                            "surviving_markers_per_second": 1.0,
                            "elapsed_seconds": 2.0,
                        }
                    ],
                    "comparison": None,
                    "gate": {"enabled": False, "ok": None, "failures": [], "reason": "thresholds_not_set"},
                }
            ],
            "gate": {
                "enabled": False,
                "required": True,
                "ok": False,
                "failures": [{"type": "thresholds_not_set"}],
                "reason": "thresholds_not_set",
            },
            "metric_summary": {},
        }

        table = benchmark.render_tables(output)

        self.assertIn("## Cutover Threshold Gate", table)
        self.assertIn("| all | all | fail | thresholds_not_set |", table)

    def test_rendered_required_threshold_gate_reports_partial_thresholds(self):
        output = {
            "scenarios": [],
            "gate": {
                "enabled": True,
                "required": True,
                "ok": False,
                "failures": [
                    {
                        "type": "required_thresholds_missing",
                        "missing": ["max_p95_claim_wait_seconds"],
                    }
                ],
                "reason": "required_thresholds_missing",
            },
            "metric_summary": {},
        }

        table = benchmark.render_tables(output)

        self.assertIn("## Cutover Threshold Gate", table)
        self.assertIn("| all | all | fail | required_thresholds_missing:max_p95_claim_wait_seconds |", table)


if __name__ == "__main__":
    unittest.main()
