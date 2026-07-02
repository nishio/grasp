#!/usr/bin/env python3
"""Benchmark write throughput with and without claim retry.

This is intentionally a small CLI/subprocess benchmark, not a unit test.  It
keeps timing out of the normal test suite while making the mode2 cutover gate
rerunnable from a clean checkout.  It can run a matrix of think times and
workloads, including a file-back-like read -> write-page -> append-log ->
projection path.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


PROJECT = "wiki"
PAGE = "A"
LOG_PAGE = "Log"
WORKER_PREFIX = "agent"
MODES = ("uncoordinated", "claim_retry")
WORKLOADS = ("hot-page", "file-back")
THROUGHPUT_GATES = (
    "surviving-ratio",
    "completed-ratio",
    "claim-retry-surviving-per-second",
    "none",
)
THROUGHPUT_GATE_KEY = "throughput_gate"
THROUGHPUT_THRESHOLD_BY_GATE = {
    "surviving-ratio": "min_surviving_throughput_ratio",
    "completed-ratio": "min_completed_throughput_ratio",
    "claim-retry-surviving-per-second": "min_claim_retry_surviving_throughput_per_second",
    "none": None,
}
REQUIRED_CUTOVER_THRESHOLD_KEYS = (
    "max_p95_claim_wait_seconds",
)
NUMERIC_THRESHOLD_KEYS = (
    "min_surviving_throughput_ratio",
    "min_completed_throughput_ratio",
    "min_claim_retry_surviving_throughput_per_second",
    "max_p95_claim_wait_seconds",
)
DEFAULT_CUTOVER_THRESHOLDS = {
    "throughput_gate": "surviving-ratio",
    "min_surviving_throughput_ratio": 0.70,
    "min_completed_throughput_ratio": None,
    "min_claim_retry_surviving_throughput_per_second": None,
    "max_p95_claim_wait_seconds": 0.75,
}
PROFILES: dict[str, dict[str, Any]] = {
    "quick": {
        "iterations": 25,
        "think_seconds_values": [0.02],
        "workloads": ["hot-page"],
        "format": "json",
    },
    "cutover": {
        "iterations": 25,
        "think_seconds_values": [0.0, 0.02, 0.05],
        "workloads": list(WORKLOADS),
        "format": "table",
    },
    "sustained-cutover": {
        "iterations": 100,
        "think_seconds_values": [0.0, 0.02, 0.05],
        "workloads": list(WORKLOADS),
        "format": "table",
    },
}


def run_grasp(
    store: Path,
    *args: str,
    actor: str = "",
    session_id: str = "",
    check: bool = True,
) -> tuple[dict[str, Any] | None, subprocess.CompletedProcess[str]]:
    command = [
        sys.executable,
        "-m",
        "grasp",
        "--json",
        "--store",
        str(store),
        "--project",
        PROJECT,
    ]
    if actor:
        command.extend(["--actor", actor])
    if session_id:
        command.extend(["--session-id", session_id])
    command.extend(args)
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"grasp command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    payload = None
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            if check:
                raise
    return payload, completed


def run_worker(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--workload", choices=WORKLOADS, required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--think-seconds", type=float, required=True)
    parser.add_argument("--wait-seconds", type=float, required=True)
    parser.add_argument("--retry-interval-seconds", type=float, required=True)
    args = parser.parse_args(argv)

    session_id = f"{args.worker_id}-session"
    markers: list[str] = []
    claim_attempts = 0
    claim_waited_seconds = 0.0
    claim_attempt_samples: list[int] = []
    claim_wait_samples_seconds: list[float] = []

    for index in range(args.iterations):
        marker = f"- {args.worker_id} marker {index}"
        claim_event_id = ""
        if args.mode == "claim_retry":
            claim, _completed = run_grasp(
                args.store,
                "claim-page",
                PAGE,
                "--ttl-seconds",
                "30",
                "--wait-seconds",
                str(args.wait_seconds),
                "--retry-interval-seconds",
                str(args.retry_interval_seconds),
                actor=args.worker_id,
                session_id=session_id,
            )
            attempts = int((claim or {}).get("claim_attempts") or 1)
            waited_seconds = float((claim or {}).get("claim_waited_seconds") or 0)
            claim_attempts += attempts
            claim_waited_seconds += waited_seconds
            claim_attempt_samples.append(attempts)
            claim_wait_samples_seconds.append(waited_seconds)
            claim_event_id = str(((claim or {}).get("claim") or {}).get("claim_event_id") or "")
        try:
            read, _completed = run_grasp(
                args.store,
                "read",
                PAGE,
                actor=args.worker_id,
                session_id=session_id,
            )
            lines = [str(line["text"]) for line in (read or {}).get("lines", [])]
            if marker not in lines:
                lines.append(marker)
            if args.think_seconds > 0:
                time.sleep(args.think_seconds)
            write_args = ["write-page", PAGE]
            for line in lines:
                write_args.extend(["--line", line])
            if claim_event_id:
                write_args.extend(["--release-claim", claim_event_id])
            write_args.extend(["--output", str(args.output), "--no-journal", "--defer-projection"])
            run_grasp(
                args.store,
                *write_args,
                actor=args.worker_id,
                session_id=session_id,
            )
            if claim_event_id:
                claim_event_id = ""
            if args.workload == "file-back":
                run_grasp(
                    args.store,
                    "append-log",
                    "--op",
                    "benchmark",
                    "--summary",
                    f"{args.worker_id} marker {index}",
                    "--line",
                    f"{marker} [[{PAGE}]]",
                    "--output",
                    str(args.output),
                    "--no-journal",
                    "--defer-projection",
                    actor=args.worker_id,
                    session_id=session_id,
                )
            markers.append(marker)
        finally:
            if claim_event_id:
                run_grasp(
                    args.store,
                    "release-claim",
                    claim_event_id,
                    actor=args.worker_id,
                    session_id=session_id,
                )

    summary = {
        "worker": args.worker_id,
        "mode": args.mode,
        "workload": args.workload,
        "markers": markers,
        "claim_attempts": claim_attempts,
        "claim_attempt_samples": claim_attempt_samples,
        "claim_waited_seconds": round(claim_waited_seconds, 3),
        "claim_wait_samples_seconds": [round(value, 3) for value in claim_wait_samples_seconds],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def worker_command(
    *,
    store: Path,
    output: Path,
    mode: str,
    workload: str,
    worker_id: str,
    iterations: int,
    think_seconds: float,
    wait_seconds: float,
    retry_interval_seconds: float,
) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--store",
        str(store),
        "--output",
        str(output),
        "--mode",
        mode,
        "--workload",
        workload,
        "--worker-id",
        worker_id,
        "--iterations",
        str(iterations),
        "--think-seconds",
        str(think_seconds),
        "--wait-seconds",
        str(wait_seconds),
        "--retry-interval-seconds",
        str(retry_interval_seconds),
    ]


def scenario_slug(*parts: Any) -> str:
    return "-".join(str(part).replace(".", "p").replace("_", "-") for part in parts)


def prepare_markdown_fixture(root: Path, workload: str) -> None:
    root.mkdir(parents=True)
    (root / "A.md").write_text("# A\n- old A\n", encoding="utf-8")
    if workload == "file-back":
        (root / "log.md").write_text("# Log\n", encoding="utf-8")


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((percentile_value / 100.0) * len(ordered)) - 1))
    return round(float(ordered[index]), 3)


def claim_overlap_summary(store: Path) -> dict[str, Any]:
    active_by_page: dict[str, dict[str, dict[str, Any]]] = {}
    page_by_claim_id: dict[str, str] = {}
    overlap_samples: list[dict[str, Any]] = []
    with sqlite3.connect(store) as connection:
        rows = connection.execute(
            """
            SELECT event_sequence, event_id, event_type, actor, session_id, payload_json
            FROM events
            WHERE project = ?
              AND event_type IN ('page_claim', 'page_claim_release')
            ORDER BY event_sequence
            """,
            (PROJECT,),
        ).fetchall()
    for event_sequence, event_id, event_type, actor, session_id, payload_json in rows:
        payload = json.loads(payload_json)
        if event_type == "page_claim":
            page_id = str(payload.get("page_id") or "")
            active = active_by_page.setdefault(page_id, {})
            if active:
                overlap_samples.append(
                    {
                        "event_sequence": event_sequence,
                        "claim_event_id": event_id,
                        "page_id": page_id,
                        "session_id": session_id,
                        "actor": actor,
                        "overlapping_claim_ids": sorted(active),
                    }
                )
            active[str(event_id)] = {
                "event_sequence": event_sequence,
                "session_id": session_id,
                "actor": actor,
            }
            page_by_claim_id[str(event_id)] = page_id
        elif event_type == "page_claim_release":
            claim_event_id = str(payload.get("claim_event_id") or "")
            page_id = str(payload.get("page_id") or page_by_claim_id.get(claim_event_id) or "")
            if page_id:
                active_by_page.setdefault(page_id, {}).pop(claim_event_id, None)
    return {
        "active_claim_overlap_count": len(overlap_samples),
        "active_claim_overlap_samples": overlap_samples[:10],
    }


def run_mode(
    *,
    tmpdir: Path,
    workload: str,
    mode: str,
    workers: int,
    iterations: int,
    think_seconds: float,
    wait_seconds: float,
    retry_interval_seconds: float,
) -> dict[str, Any]:
    root = tmpdir / scenario_slug(workload, f"think-{think_seconds}", mode) / "wiki"
    prepare_markdown_fixture(root, workload)
    store = root.parent / "store.sqlite"
    run_grasp(store, "import", "--markdown", str(root))

    processes = [
        subprocess.Popen(
            worker_command(
                store=store,
                output=root,
                mode=mode,
                workload=workload,
                worker_id=f"{WORKER_PREFIX}-{index + 1}",
                iterations=iterations,
                think_seconds=think_seconds,
                wait_seconds=wait_seconds,
                retry_interval_seconds=retry_interval_seconds,
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for index in range(workers)
    ]
    started = time.perf_counter()
    worker_summaries: list[dict[str, Any]] = []
    worker_errors: list[dict[str, Any]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=max(wait_seconds * iterations + think_seconds * iterations + 30, 60))
        if process.returncode != 0:
            worker_errors.append(
                {
                    "returncode": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            continue
        worker_summaries.append(json.loads(stdout))
    worker_elapsed = time.perf_counter() - started
    if worker_errors:
        return {
            "workload": workload,
            "mode": mode,
            "ok": False,
            "worker_errors": worker_errors,
            "worker_elapsed_seconds": round(worker_elapsed, 3),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }

    export_started = time.perf_counter()
    export, export_completed = run_grasp(store, "export-markdown", "--output", str(root), check=False)
    export_elapsed = time.perf_counter() - export_started
    status_started = time.perf_counter()
    status, status_completed = run_grasp(
        store,
        "write-status",
        "--output",
        str(root),
        "--no-journal",
        "--strict",
        check=False,
    )
    status_elapsed = time.perf_counter() - status_started
    read, _completed = run_grasp(store, "read", PAGE)
    log_line_texts: list[str] = []
    if workload == "file-back":
        log_read, _completed = run_grasp(store, "read", LOG_PAGE)
        log_line_texts = [str(line["text"]) for line in (log_read or {}).get("lines", [])]
    elapsed = time.perf_counter() - started
    line_texts = [str(line["text"]) for line in (read or {}).get("lines", [])]
    attempted_markers = workers * iterations
    completed_markers = [
        marker
        for summary in worker_summaries
        for marker in list(summary.get("markers") or [])
    ]
    survived_markers = [marker for marker in completed_markers if marker in line_texts]
    lost_markers = sorted(set(completed_markers) - set(survived_markers))
    completed_log_markers = [f"{marker} [[{PAGE}]]" for marker in completed_markers] if workload == "file-back" else []
    survived_log_markers = [marker for marker in completed_log_markers if marker in log_line_texts]
    lost_log_markers = sorted(set(completed_log_markers) - set(survived_log_markers))
    claim_attempts = sum(int(summary.get("claim_attempts") or 0) for summary in worker_summaries)
    claim_waited_seconds = sum(float(summary.get("claim_waited_seconds") or 0) for summary in worker_summaries)
    claim_wait_samples_seconds = [
        float(sample)
        for summary in worker_summaries
        for sample in list(summary.get("claim_wait_samples_seconds") or [])
    ]
    claim_overlap = claim_overlap_summary(store)
    return {
        "workload": workload,
        "mode": mode,
        "ok": (
            not lost_markers
            and not lost_log_markers
            and status_completed.returncode == 0
            and export_completed.returncode == 0
            and int(claim_overlap["active_claim_overlap_count"]) == 0
        ),
        "workers": workers,
        "iterations_per_worker": iterations,
        "think_seconds": think_seconds,
        "attempted_markers": attempted_markers,
        "completed_markers": len(completed_markers),
        "survived_markers": len(survived_markers),
        "lost_markers": len(lost_markers),
        "lost_marker_samples": lost_markers[:10],
        "completed_log_markers": len(completed_log_markers),
        "survived_log_markers": len(survived_log_markers),
        "lost_log_markers": len(lost_log_markers),
        "lost_log_marker_samples": lost_log_markers[:10],
        "worker_elapsed_seconds": round(worker_elapsed, 3),
        "export_elapsed_seconds": round(export_elapsed, 3),
        "write_status_elapsed_seconds": round(status_elapsed, 3),
        "elapsed_seconds": round(elapsed, 3),
        "completed_writes_per_second": round(len(completed_markers) / elapsed, 3) if elapsed else None,
        "surviving_markers_per_second": round(len(survived_markers) / elapsed, 3) if elapsed else None,
        "claim_attempts": claim_attempts,
        "claim_waited_seconds": round(claim_waited_seconds, 3),
        "p95_claim_wait_seconds": percentile(claim_wait_samples_seconds, 95),
        "max_claim_wait_seconds": round(max(claim_wait_samples_seconds), 3) if claim_wait_samples_seconds else None,
        **claim_overlap,
        "write_status_returncode": status_completed.returncode,
        "strict_ok": bool((status or {}).get("strict_ok")),
        "strict_failures": list((status or {}).get("strict_failures") or []),
        "export_returncode": export_completed.returncode,
        "export_written_files": list((export or {}).get("written_files") or []),
    }


def ratio(numerator: Any, denominator: Any) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator), 3)


def parse_float_list(raw: str) -> list[float]:
    values: list[float] = []
    for part in raw.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        values.append(float(stripped))
    if not values:
        raise argparse.ArgumentTypeError("expected at least one float")
    return values


def flatten_float_lists(values: list[list[float]] | None, *, default: list[float]) -> list[float]:
    if not values:
        return default
    flattened: list[float] = []
    for group in values:
        flattened.extend(group)
    return flattened


def build_comparison(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_mode = {str(result.get("mode")): result for result in results}
    uncoordinated = by_mode.get("uncoordinated")
    claim_retry = by_mode.get("claim_retry")
    if uncoordinated is None or claim_retry is None:
        return None
    return {
        "claim_retry_completed_writes_per_second_ratio": ratio(
            claim_retry.get("completed_writes_per_second"),
            uncoordinated.get("completed_writes_per_second"),
        ),
        "claim_retry_surviving_markers_per_second_ratio": ratio(
            claim_retry.get("surviving_markers_per_second"),
            uncoordinated.get("surviving_markers_per_second"),
        ),
        "claim_retry_lost_marker_delta": int(claim_retry.get("lost_markers") or 0)
        - int(uncoordinated.get("lost_markers") or 0),
        "claim_retry_lost_log_marker_delta": int(claim_retry.get("lost_log_markers") or 0)
        - int(uncoordinated.get("lost_log_markers") or 0),
        "claim_retry_p95_claim_wait_seconds": claim_retry.get("p95_claim_wait_seconds"),
        "claim_retry_active_claim_overlap_count": claim_retry.get("active_claim_overlap_count"),
    }


def gate_thresholds(args: argparse.Namespace) -> dict[str, float | str | None]:
    defaults: dict[str, float | str | None] = {THROUGHPUT_GATE_KEY: "surviving-ratio"}
    if getattr(args, "profile", None) in {"cutover", "sustained-cutover"}:
        defaults = dict(DEFAULT_CUTOVER_THRESHOLDS)
    throughput_gate = getattr(args, "throughput_gate", None) or defaults.get(THROUGHPUT_GATE_KEY)
    return {
        THROUGHPUT_GATE_KEY: throughput_gate,
        "min_surviving_throughput_ratio": getattr(args, "min_surviving_throughput_ratio", None)
        if getattr(args, "min_surviving_throughput_ratio", None) is not None
        else defaults.get("min_surviving_throughput_ratio"),
        "min_completed_throughput_ratio": getattr(args, "min_completed_throughput_ratio", None)
        if getattr(args, "min_completed_throughput_ratio", None) is not None
        else defaults.get("min_completed_throughput_ratio"),
        "min_claim_retry_surviving_throughput_per_second": getattr(
            args,
            "min_claim_retry_surviving_throughput_per_second",
            None,
        )
        if getattr(args, "min_claim_retry_surviving_throughput_per_second", None) is not None
        else defaults.get("min_claim_retry_surviving_throughput_per_second"),
        "max_p95_claim_wait_seconds": getattr(args, "max_p95_claim_wait_seconds", None)
        if getattr(args, "max_p95_claim_wait_seconds", None) is not None
        else defaults.get("max_p95_claim_wait_seconds"),
    }


def gate_enabled(thresholds: dict[str, float | str | None]) -> bool:
    return any(thresholds.get(key) is not None for key in NUMERIC_THRESHOLD_KEYS)


def missing_cutover_thresholds(thresholds: dict[str, float | str | None]) -> list[str]:
    missing = [
        key
        for key in REQUIRED_CUTOVER_THRESHOLD_KEYS
        if thresholds.get(key) is None
    ]
    throughput_gate = str(thresholds.get(THROUGHPUT_GATE_KEY) or "surviving-ratio")
    throughput_threshold = THROUGHPUT_THRESHOLD_BY_GATE.get(throughput_gate)
    if throughput_threshold and thresholds.get(throughput_threshold) is None:
        missing.append(throughput_threshold)
    return missing


def resolve_run_config(args: argparse.Namespace) -> dict[str, Any]:
    profile = PROFILES[str(args.profile)]
    return {
        "iterations": int(args.iterations if args.iterations is not None else profile["iterations"]),
        "think_seconds_values": flatten_float_lists(
            args.think_seconds,
            default=list(profile["think_seconds_values"]),
        ),
        "workloads": list(args.workload or profile["workloads"]),
        "format": str(args.format or profile["format"]),
    }


def evaluate_scenario_gate(
    *,
    results: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    thresholds: dict[str, float | str | None],
) -> dict[str, Any]:
    enabled = gate_enabled(thresholds)
    if not enabled:
        return {
            "enabled": False,
            "ok": None,
            "failures": [],
            "reason": "thresholds_not_set",
        }
    failures: list[dict[str, Any]] = []
    claim_retry = next((result for result in results if result.get("mode") == "claim_retry"), None)
    if claim_retry is None:
        failures.append({"type": "missing_claim_retry_result"})
    else:
        if claim_retry.get("lost_markers"):
            failures.append({"type": "lost_markers", "actual": claim_retry.get("lost_markers"), "expected": 0})
        if claim_retry.get("lost_log_markers"):
            failures.append({"type": "lost_log_markers", "actual": claim_retry.get("lost_log_markers"), "expected": 0})
        if not claim_retry.get("strict_ok"):
            failures.append({"type": "strict_not_green", "strict_failures": claim_retry.get("strict_failures")})
        if claim_retry.get("active_claim_overlap_count"):
            failures.append(
                {
                    "type": "active_claim_overlap",
                    "actual": claim_retry.get("active_claim_overlap_count"),
                    "expected": 0,
                }
            )
    throughput_gate = str(thresholds.get(THROUGHPUT_GATE_KEY) or "surviving-ratio")
    if throughput_gate == "surviving-ratio":
        min_surviving = thresholds.get("min_surviving_throughput_ratio")
        actual = None if comparison is None else comparison.get("claim_retry_surviving_markers_per_second_ratio")
        if min_surviving is not None and actual is None:
            failures.append({"type": "missing_surviving_throughput_ratio", "threshold": min_surviving})
        elif min_surviving is not None and float(actual) < float(min_surviving):
            failures.append(
                {
                    "type": "surviving_throughput_ratio_below_threshold",
                    "actual": actual,
                    "threshold": min_surviving,
                }
            )
    elif throughput_gate == "completed-ratio":
        min_completed = thresholds.get("min_completed_throughput_ratio")
        actual = None if comparison is None else comparison.get("claim_retry_completed_writes_per_second_ratio")
        if min_completed is not None and actual is None:
            failures.append({"type": "missing_completed_throughput_ratio", "threshold": min_completed})
        elif min_completed is not None and float(actual) < float(min_completed):
            failures.append(
                {
                    "type": "completed_throughput_ratio_below_threshold",
                    "actual": actual,
                    "threshold": min_completed,
                }
            )
    elif throughput_gate == "claim-retry-surviving-per-second":
        min_claim_retry_surviving = thresholds.get("min_claim_retry_surviving_throughput_per_second")
        actual = None if claim_retry is None else claim_retry.get("surviving_markers_per_second")
        if min_claim_retry_surviving is not None and actual is None:
            failures.append(
                {
                    "type": "missing_claim_retry_surviving_throughput_per_second",
                    "threshold": min_claim_retry_surviving,
                }
            )
        elif min_claim_retry_surviving is not None and float(actual) < float(min_claim_retry_surviving):
            failures.append(
                {
                    "type": "claim_retry_surviving_throughput_below_threshold",
                    "actual": actual,
                    "threshold": min_claim_retry_surviving,
                }
            )
    elif throughput_gate == "none":
        pass
    max_p95 = thresholds.get("max_p95_claim_wait_seconds")
    if max_p95 is not None:
        actual = None if claim_retry is None else claim_retry.get("p95_claim_wait_seconds")
        if actual is None and comparison is not None:
            actual = comparison.get("claim_retry_p95_claim_wait_seconds")
        if actual is None:
            failures.append({"type": "missing_p95_claim_wait_seconds", "threshold": max_p95})
        elif float(actual) > float(max_p95):
            failures.append(
                {
                    "type": "p95_claim_wait_above_threshold",
                    "actual": actual,
                    "threshold": max_p95,
                }
            )
    return {
        "enabled": True,
        "ok": not failures,
        "failures": failures,
    }


def summarize_gate(
    scenarios: list[dict[str, Any]],
    thresholds: dict[str, float | str | None],
    *,
    require_thresholds: bool = False,
) -> dict[str, Any]:
    enabled = gate_enabled(thresholds)
    missing_required = missing_cutover_thresholds(thresholds) if require_thresholds else []
    if not enabled:
        return {
            "enabled": False,
            "required": require_thresholds,
            "ok": False if require_thresholds else None,
            "thresholds": thresholds,
            "failures": [{"type": "thresholds_not_set"}] if require_thresholds else [],
            "reason": "thresholds_not_set",
        }
    if missing_required:
        return {
            "enabled": True,
            "required": True,
            "ok": False,
            "thresholds": thresholds,
            "failures": [
                {
                    "type": "required_thresholds_missing",
                    "missing": missing_required,
                }
            ],
            "reason": "required_thresholds_missing",
        }
    failures = [
        {
            "workload": scenario.get("workload"),
            "think_seconds": scenario.get("think_seconds"),
            "failures": list((scenario.get("gate") or {}).get("failures") or []),
        }
        for scenario in scenarios
        if (scenario.get("gate") or {}).get("failures")
    ]
    return {
        "enabled": True,
        "required": require_thresholds,
        "ok": not failures,
        "thresholds": thresholds,
        "failures": failures,
    }


def summarize_cutover_metrics(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons = [
        scenario.get("comparison")
        for scenario in scenarios
        if scenario.get("comparison") is not None
    ]
    claim_retry_results = [
        result
        for scenario in scenarios
        for result in list(scenario.get("results") or [])
        if result.get("mode") == "claim_retry"
    ]
    surviving_ratios = [
        float(comparison["claim_retry_surviving_markers_per_second_ratio"])
        for comparison in comparisons
        if comparison.get("claim_retry_surviving_markers_per_second_ratio") is not None
    ]
    completed_ratios = [
        float(comparison["claim_retry_completed_writes_per_second_ratio"])
        for comparison in comparisons
        if comparison.get("claim_retry_completed_writes_per_second_ratio") is not None
    ]
    p95_waits = [
        float(result["p95_claim_wait_seconds"])
        for result in claim_retry_results
        if result.get("p95_claim_wait_seconds") is not None
    ]
    surviving_rates = [
        float(result["surviving_markers_per_second"])
        for result in claim_retry_results
        if result.get("surviving_markers_per_second") is not None
    ]
    completed_rates = [
        float(result["completed_writes_per_second"])
        for result in claim_retry_results
        if result.get("completed_writes_per_second") is not None
    ]
    overlap_counts = [
        int(result.get("active_claim_overlap_count") or 0)
        for result in claim_retry_results
    ]
    return {
        "scenario_count": len(scenarios),
        "compared_scenario_count": len(comparisons),
        "claim_retry_scenario_count": len(claim_retry_results),
        "min_claim_retry_surviving_throughput_ratio": round(min(surviving_ratios), 3) if surviving_ratios else None,
        "min_claim_retry_completed_throughput_ratio": round(min(completed_ratios), 3) if completed_ratios else None,
        "min_claim_retry_surviving_markers_per_second": round(min(surviving_rates), 3) if surviving_rates else None,
        "min_claim_retry_completed_writes_per_second": round(min(completed_rates), 3) if completed_rates else None,
        "max_claim_retry_p95_claim_wait_seconds": round(max(p95_waits), 3) if p95_waits else None,
        "max_claim_retry_active_claim_overlap_count": max(overlap_counts) if overlap_counts else None,
        "total_claim_retry_lost_markers": sum(int(result.get("lost_markers") or 0) for result in claim_retry_results),
        "total_claim_retry_lost_log_markers": sum(int(result.get("lost_log_markers") or 0) for result in claim_retry_results),
        "all_claim_retry_strict_green": all(bool(result.get("strict_ok")) for result in claim_retry_results)
        if claim_retry_results
        else None,
    }


def format_cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _header in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(value) for value in row) + " |")
    return "\n".join(lines)


def render_tables(output: dict[str, Any]) -> str:
    result_rows: list[list[Any]] = []
    comparison_rows: list[list[Any]] = []
    gate_rows: list[list[Any]] = []
    for scenario in output["scenarios"]:
        workload = scenario["workload"]
        think_seconds = scenario["think_seconds"]
        for result in scenario["results"]:
            result_rows.append(
                [
                    workload,
                    think_seconds,
                    result.get("mode"),
                    result.get("attempted_markers"),
                    result.get("survived_markers"),
                    result.get("lost_markers"),
                    result.get("lost_log_markers"),
                    "green" if result.get("strict_ok") else "fail",
                    result.get("active_claim_overlap_count"),
                    result.get("p95_claim_wait_seconds"),
                    result.get("completed_writes_per_second"),
                    result.get("surviving_markers_per_second"),
                    result.get("elapsed_seconds"),
                ]
            )
        comparison = scenario.get("comparison")
        if comparison:
            comparison_rows.append(
                [
                    workload,
                    think_seconds,
                    comparison.get("claim_retry_completed_writes_per_second_ratio"),
                    comparison.get("claim_retry_surviving_markers_per_second_ratio"),
                    comparison.get("claim_retry_lost_marker_delta"),
                    comparison.get("claim_retry_lost_log_marker_delta"),
                    comparison.get("claim_retry_active_claim_overlap_count"),
                    comparison.get("claim_retry_p95_claim_wait_seconds"),
                ]
            )
    sections = [
        "## Claim Retry Throughput Gate",
        markdown_table(
            [
                "workload",
                "think_s",
                "mode",
                "attempted",
                "survived",
                "lost",
                "log_lost",
                "strict",
                "overlap",
                "p95_wait_s",
                "completed/s",
                "surviving/s",
                "elapsed_s",
            ],
            result_rows,
        ),
    ]
    metric_summary = output.get("metric_summary") or {}
    if metric_summary:
        sections.extend(
            [
                "",
                "## Cutover Metric Summary",
                markdown_table(
                    ["metric", "value"],
                    [
                        [
                            "claim_retry_scenarios",
                            f"{metric_summary.get('claim_retry_scenario_count')}/{metric_summary.get('scenario_count')}",
                        ],
                        [
                            "compared_scenarios",
                            f"{metric_summary.get('compared_scenario_count')}/{metric_summary.get('scenario_count')}",
                        ],
                        [
                            "min_surviving_ratio",
                            metric_summary.get("min_claim_retry_surviving_throughput_ratio"),
                        ],
                        [
                            "min_completed_ratio",
                            metric_summary.get("min_claim_retry_completed_throughput_ratio"),
                        ],
                        [
                            "min_claim_retry_surviving/s",
                            metric_summary.get("min_claim_retry_surviving_markers_per_second"),
                        ],
                        [
                            "min_claim_retry_completed/s",
                            metric_summary.get("min_claim_retry_completed_writes_per_second"),
                        ],
                        [
                            "max_p95_wait_s",
                            metric_summary.get("max_claim_retry_p95_claim_wait_seconds"),
                        ],
                        [
                            "max_overlap",
                            metric_summary.get("max_claim_retry_active_claim_overlap_count"),
                        ],
                        [
                            "total_lost",
                            metric_summary.get("total_claim_retry_lost_markers"),
                        ],
                        [
                            "total_log_lost",
                            metric_summary.get("total_claim_retry_lost_log_markers"),
                        ],
                        [
                            "all_strict_green",
                            metric_summary.get("all_claim_retry_strict_green"),
                        ],
                    ],
                ),
            ]
        )
    if comparison_rows:
        sections.extend(
            [
                "",
                "## Claim Retry vs Uncoordinated",
                markdown_table(
                    [
                        "workload",
                        "think_s",
                        "completed_ratio",
                        "surviving_ratio",
                        "lost_delta",
                        "log_lost_delta",
                        "overlap",
                        "p95_wait_s",
                    ],
                    comparison_rows,
                ),
            ]
        )
    gate = output.get("gate") or {}
    if gate.get("enabled") or gate.get("required"):
        for scenario in output["scenarios"]:
            scenario_gate = scenario.get("gate") or {}
            failures = scenario_gate.get("failures") or []
            gate_rows.append(
                [
                    scenario.get("workload"),
                    scenario.get("think_seconds"),
                    "pass" if scenario_gate.get("ok") else "fail",
                    "; ".join(str(failure.get("type")) for failure in failures) if failures else "",
                ]
            )
        if gate.get("required") and gate.get("reason") in {"thresholds_not_set", "required_thresholds_missing"}:
            failures = list(gate.get("failures") or [])
            failure = failures[0] if failures else {"type": str(gate.get("reason"))}
            failure_text = str(failure.get("type"))
            missing = failure.get("missing")
            if missing:
                failure_text = f"{failure_text}:{','.join(str(item) for item in missing)}"
            gate_rows = [["all", "all", "fail", failure_text]]
        sections.extend(
            [
                "",
                "## Cutover Threshold Gate",
                markdown_table(["workload", "think_s", "gate", "failures"], gate_rows),
            ]
        )
    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        return run_worker(argv[1:])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="quick",
        help=(
            "Default matrix preset. quick preserves the original single hot-page scenario; "
            "cutover runs hot-page and file-back workloads across think times 0,0.02,0.05 and prints a table; "
            "sustained-cutover uses the same matrix with 100 iterations per worker."
        ),
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument(
        "--think-seconds",
        type=parse_float_list,
        action="append",
        help="Think time before write. Accepts comma-separated values and can be repeated. Defaults to the selected profile.",
    )
    parser.add_argument("--wait-seconds", type=float, default=10.0)
    parser.add_argument("--retry-interval-seconds", type=float, default=0.02)
    parser.add_argument(
        "--mode",
        choices=MODES,
        action="append",
        help="Mode to run. Repeat for multiple modes. Default: both modes.",
    )
    parser.add_argument(
        "--workload",
        choices=WORKLOADS,
        action="append",
        help="Workload to run. Repeat for multiple workloads. Defaults to the selected profile.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table", "both"],
        default=None,
        help="Output format. The table format is a Markdown gate summary. Defaults to the selected profile.",
    )
    parser.add_argument(
        "--min-surviving-throughput-ratio",
        type=float,
        default=None,
        help=(
            "Owner cutover threshold. Fail if claim_retry surviving/s divided by uncoordinated "
            "surviving/s is below this value. Defaults to 0.70 for --profile cutover."
        ),
    )
    parser.add_argument(
        "--min-completed-throughput-ratio",
        type=float,
        default=None,
        help=(
            "Owner cutover threshold for --throughput-gate completed-ratio. Fail if claim_retry "
            "completed/s divided by uncoordinated completed/s is below this value."
        ),
    )
    parser.add_argument(
        "--min-claim-retry-surviving-throughput-per-second",
        type=float,
        default=None,
        help=(
            "Owner cutover threshold for --throughput-gate claim-retry-surviving-per-second. "
            "Fail if claim_retry surviving markers per second is below this absolute value."
        ),
    )
    parser.add_argument(
        "--throughput-gate",
        choices=THROUGHPUT_GATES,
        default=None,
        help=(
            "Which throughput metric participates in the threshold gate. Defaults to surviving-ratio, "
            "and cutover profiles keep the owner default 0.70 surviving-ratio gate."
        ),
    )
    parser.add_argument(
        "--max-p95-claim-wait-seconds",
        type=float,
        default=None,
        help=(
            "Owner cutover threshold. Fail if claim_retry p95 claim wait exceeds this many seconds. "
            "Defaults to 0.75 for --profile cutover."
        ),
    )
    parser.add_argument(
        "--require-cutover-thresholds",
        action="store_true",
        help=(
            "Exit 1 when owner cutover thresholds are omitted. Use this in cutover CI so "
            "correctness-only runs cannot be mistaken for a stable mode2 gate."
        ),
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    config = resolve_run_config(args)
    iterations = int(config["iterations"])
    think_seconds_values = list(config["think_seconds_values"])
    workloads = list(config["workloads"])
    output_format = str(config["format"])
    if iterations < 1:
        parser.error("--iterations must be >= 1")
    if any(value < 0 for value in think_seconds_values):
        parser.error("--think-seconds values must be >= 0")
    if args.wait_seconds < 0:
        parser.error("--wait-seconds must be >= 0")
    if args.retry_interval_seconds <= 0:
        parser.error("--retry-interval-seconds must be > 0")
    if args.min_surviving_throughput_ratio is not None and args.min_surviving_throughput_ratio < 0:
        parser.error("--min-surviving-throughput-ratio must be >= 0")
    if args.min_completed_throughput_ratio is not None and args.min_completed_throughput_ratio < 0:
        parser.error("--min-completed-throughput-ratio must be >= 0")
    if (
        args.min_claim_retry_surviving_throughput_per_second is not None
        and args.min_claim_retry_surviving_throughput_per_second < 0
    ):
        parser.error("--min-claim-retry-surviving-throughput-per-second must be >= 0")
    if args.max_p95_claim_wait_seconds is not None and args.max_p95_claim_wait_seconds < 0:
        parser.error("--max-p95-claim-wait-seconds must be >= 0")

    modes = args.mode or list(MODES)
    thresholds = gate_thresholds(args)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        scenarios = []
        for workload in workloads:
            for think_seconds in think_seconds_values:
                results = [
                    run_mode(
                        tmpdir=tmpdir,
                        workload=workload,
                        mode=mode,
                        workers=args.workers,
                        iterations=iterations,
                        think_seconds=think_seconds,
                        wait_seconds=args.wait_seconds,
                        retry_interval_seconds=args.retry_interval_seconds,
                    )
                    for mode in modes
                ]
                comparison = build_comparison(results)
                scenarios.append(
                    {
                        "workload": workload,
                        "think_seconds": think_seconds,
                        "comparison": comparison,
                        "results": results,
                        "gate": evaluate_scenario_gate(
                            results=results,
                            comparison=comparison,
                            thresholds=thresholds,
                        ),
                    }
                )
    gate = summarize_gate(
        scenarios,
        thresholds,
        require_thresholds=args.require_cutover_thresholds,
    )
    metric_summary = summarize_cutover_metrics(scenarios)
    output = {
        "benchmark": "claim_retry_throughput_gate",
        "profile": args.profile,
        "workers": args.workers,
        "iterations_per_worker": iterations,
        "think_seconds_values": think_seconds_values,
        "workloads": workloads,
        "wait_seconds": args.wait_seconds,
        "retry_interval_seconds": args.retry_interval_seconds,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "gate": gate,
        "metric_summary": metric_summary,
        "thresholds": thresholds,
        "scenarios": scenarios,
    }
    if output_format in ("table", "both"):
        print(render_tables(output))
    if output_format in ("json", "both"):
        if output_format == "both":
            print()
        print(json.dumps(output, indent=2, sort_keys=True))
    claim_retry_results = [
        result
        for scenario in scenarios
        for result in scenario["results"]
        if result.get("mode") == "claim_retry"
    ]
    if any(
        result.get("lost_markers")
        or result.get("lost_log_markers")
        or not result.get("strict_ok")
        or result.get("active_claim_overlap_count")
        or result.get("export_returncode")
        for result in claim_retry_results
    ):
        return 1
    if (gate.get("enabled") or gate.get("required")) and not gate.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
