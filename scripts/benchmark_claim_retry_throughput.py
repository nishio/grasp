#!/usr/bin/env python3
"""Benchmark hot-page write throughput with and without claim retry.

This is intentionally a small CLI/subprocess benchmark, not a unit test.  It
keeps timing out of the normal test suite while making the mode2 cutover gate
rerunnable from a clean checkout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


PROJECT = "wiki"
PAGE = "A"
WORKER_PREFIX = "agent"


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
    parser.add_argument("--mode", choices=["uncoordinated", "claim_retry"], required=True)
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
            claim_attempts += int((claim or {}).get("claim_attempts") or 1)
            claim_waited_seconds += float((claim or {}).get("claim_waited_seconds") or 0)
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
        "markers": markers,
        "claim_attempts": claim_attempts,
        "claim_waited_seconds": round(claim_waited_seconds, 3),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def worker_command(
    *,
    store: Path,
    output: Path,
    mode: str,
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


def run_mode(
    *,
    tmpdir: Path,
    mode: str,
    workers: int,
    iterations: int,
    think_seconds: float,
    wait_seconds: float,
    retry_interval_seconds: float,
) -> dict[str, Any]:
    root = tmpdir / mode / "wiki"
    root.mkdir(parents=True)
    (root / "A.md").write_text("# A\n- old A\n", encoding="utf-8")
    store = tmpdir / mode / "store.sqlite"
    run_grasp(store, "import", "--markdown", str(root))

    processes = [
        subprocess.Popen(
            worker_command(
                store=store,
                output=root,
                mode=mode,
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
        stdout, stderr = process.communicate(timeout=max(wait_seconds * iterations + 30, 60))
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
    elapsed = time.perf_counter() - started
    if worker_errors:
        return {
            "mode": mode,
            "ok": False,
            "worker_errors": worker_errors,
            "elapsed_seconds": round(elapsed, 3),
        }

    export, export_completed = run_grasp(store, "export-markdown", "--output", str(root), check=False)
    status, status_completed = run_grasp(
        store,
        "write-status",
        "--output",
        str(root),
        "--no-journal",
        "--strict",
        check=False,
    )
    read, _completed = run_grasp(store, "read", PAGE)
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
    return {
        "mode": mode,
        "ok": not lost_markers and status_completed.returncode == 0,
        "workers": workers,
        "iterations_per_worker": iterations,
        "attempted_markers": attempted_markers,
        "completed_markers": len(completed_markers),
        "survived_markers": len(survived_markers),
        "lost_markers": len(lost_markers),
        "lost_marker_samples": lost_markers[:10],
        "elapsed_seconds": round(elapsed, 3),
        "completed_writes_per_second": round(len(completed_markers) / elapsed, 3) if elapsed else None,
        "surviving_markers_per_second": round(len(survived_markers) / elapsed, 3) if elapsed else None,
        "claim_attempts": claim_attempts,
        "claim_waited_seconds": round(claim_waited_seconds, 3),
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        return run_worker(argv[1:])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--think-seconds", type=float, default=0.02)
    parser.add_argument("--wait-seconds", type=float, default=10.0)
    parser.add_argument("--retry-interval-seconds", type=float, default=0.02)
    parser.add_argument(
        "--mode",
        choices=["uncoordinated", "claim_retry"],
        action="append",
        help="Mode to run. Repeat for multiple modes. Default: both modes.",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if args.think_seconds < 0:
        parser.error("--think-seconds must be >= 0")
    if args.wait_seconds < 0:
        parser.error("--wait-seconds must be >= 0")
    if args.retry_interval_seconds <= 0:
        parser.error("--retry-interval-seconds must be > 0")

    modes = args.mode or ["uncoordinated", "claim_retry"]
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        results = [
            run_mode(
                tmpdir=tmpdir,
                mode=mode,
                workers=args.workers,
                iterations=args.iterations,
                think_seconds=args.think_seconds,
                wait_seconds=args.wait_seconds,
                retry_interval_seconds=args.retry_interval_seconds,
            )
            for mode in modes
        ]
    by_mode = {str(result.get("mode")): result for result in results}
    uncoordinated = by_mode.get("uncoordinated")
    claim_retry = by_mode.get("claim_retry")
    comparison = None
    if uncoordinated is not None and claim_retry is not None:
        comparison = {
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
        }
    output = {
        "benchmark": "claim_retry_hot_page_throughput",
        "workers": args.workers,
        "iterations_per_worker": args.iterations,
        "think_seconds": args.think_seconds,
        "wait_seconds": args.wait_seconds,
        "retry_interval_seconds": args.retry_interval_seconds,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "comparison": comparison,
        "results": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if claim_retry and (claim_retry.get("lost_markers") or not claim_retry.get("strict_ok")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
