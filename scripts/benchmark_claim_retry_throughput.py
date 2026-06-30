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
WORKER_PREFIX = "agent"
MODES = ("uncoordinated", "claim_retry")
WORKLOADS = ("hot-page", "file-back")


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
            write_args.extend(["--output", str(args.output), "--no-journal", "--defer-projection"])
            run_grasp(
                args.store,
                *write_args,
                actor=args.worker_id,
                session_id=session_id,
            )
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
        "claim_retry_p95_claim_wait_seconds": claim_retry.get("p95_claim_wait_seconds"),
        "claim_retry_active_claim_overlap_count": claim_retry.get("active_claim_overlap_count"),
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
                        "overlap",
                        "p95_wait_s",
                    ],
                    comparison_rows,
                ),
            ]
        )
    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        return run_worker(argv[1:])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument(
        "--think-seconds",
        type=parse_float_list,
        action="append",
        help="Think time before write. Accepts comma-separated values and can be repeated. Default: 0.02.",
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
        help="Workload to run. Repeat for multiple workloads. Default: hot-page.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table", "both"],
        default="json",
        help="Output format. The table format is a Markdown gate summary.",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    think_seconds_values = flatten_float_lists(args.think_seconds, default=[0.02])
    if any(value < 0 for value in think_seconds_values):
        parser.error("--think-seconds values must be >= 0")
    if args.wait_seconds < 0:
        parser.error("--wait-seconds must be >= 0")
    if args.retry_interval_seconds <= 0:
        parser.error("--retry-interval-seconds must be > 0")

    modes = args.mode or list(MODES)
    workloads = args.workload or ["hot-page"]
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
                        iterations=args.iterations,
                        think_seconds=think_seconds,
                        wait_seconds=args.wait_seconds,
                        retry_interval_seconds=args.retry_interval_seconds,
                    )
                    for mode in modes
                ]
                scenarios.append(
                    {
                        "workload": workload,
                        "think_seconds": think_seconds,
                        "comparison": build_comparison(results),
                        "results": results,
                    }
                )
    output = {
        "benchmark": "claim_retry_throughput_gate",
        "workers": args.workers,
        "iterations_per_worker": args.iterations,
        "think_seconds_values": think_seconds_values,
        "workloads": workloads,
        "wait_seconds": args.wait_seconds,
        "retry_interval_seconds": args.retry_interval_seconds,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "scenarios": scenarios,
    }
    if args.format in ("table", "both"):
        print(render_tables(output))
    if args.format in ("json", "both"):
        if args.format == "both":
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
        or not result.get("strict_ok")
        or result.get("active_claim_overlap_count")
        or result.get("export_returncode")
        for result in claim_retry_results
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
