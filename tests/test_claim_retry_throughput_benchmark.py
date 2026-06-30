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

        self.assertFalse(scenario_gate["enabled"])
        self.assertIsNone(scenario_gate["ok"])
        self.assertEqual(scenario_gate["reason"], "thresholds_not_set")
        self.assertFalse(summary["enabled"])
        self.assertIsNone(summary["ok"])

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
        }

        table = benchmark.render_tables(output)

        self.assertIn("## Claim Retry Throughput Gate", table)
        self.assertIn("| workload | think_s | mode | attempted | survived | lost | log_lost | strict | overlap | p95_wait_s | completed/s | surviving/s | elapsed_s |", table)
        self.assertIn("| file-back | 0.02 | claim_retry | 50 | 50 | 0 | 0 | green | 0 | 0.439 | 2 | 2 | 25 |", table)
        self.assertIn("## Claim Retry vs Uncoordinated", table)
        self.assertIn("| file-back | 0.02 | 0.4 | 0.8 | -25 | 0 | 0 | 0.439 |", table)
        self.assertIn("## Optional Cutover Threshold Gate", table)
        self.assertIn("| file-back | 0.02 | pass |  |", table)


if __name__ == "__main__":
    unittest.main()
