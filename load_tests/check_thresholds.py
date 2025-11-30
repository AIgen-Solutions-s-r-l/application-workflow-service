#!/usr/bin/env python
"""
Threshold checker for load test results.

Analyzes Locust CSV output and compares against defined thresholds.
Exits with code 1 if any threshold is exceeded.

Usage:
    python check_thresholds.py --csv-prefix results --scenario standard
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Import thresholds from config
try:
    from config import THRESHOLDS
except ImportError:
    # Default thresholds if config not available
    THRESHOLDS = {
        "standard": {
            "error_rate_percent": 1.0,
            "p95_response_time_ms": 500,
            "p99_response_time_ms": 2000,
            "min_requests_per_second": 50,
        }
    }


@dataclass
class ThresholdResult:
    """Result of a threshold check."""

    name: str
    threshold: float
    actual: float
    passed: bool
    message: str


@dataclass
class LoadTestReport:
    """Complete load test report."""

    scenario: str
    timestamp: str
    total_requests: int
    total_failures: int
    error_rate: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    threshold_results: list[ThresholdResult]
    passed: bool


def parse_stats_csv(csv_path: Path) -> dict[str, Any]:
    """Parse Locust stats CSV file."""
    stats = {
        "total_requests": 0,
        "total_failures": 0,
        "avg_response_time": 0,
        "p50_response_time": 0,
        "p95_response_time": 0,
        "p99_response_time": 0,
        "endpoints": [],
    }

    if not csv_path.exists():
        print(f"Warning: Stats file not found: {csv_path}")
        return stats

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name") == "Aggregated":
                stats["total_requests"] = int(row.get("Request Count", 0))
                stats["total_failures"] = int(row.get("Failure Count", 0))
                stats["avg_response_time"] = float(row.get("Average Response Time", 0))
                stats["p50_response_time"] = float(row.get("50%", 0))
                stats["p95_response_time"] = float(row.get("95%", 0))
                stats["p99_response_time"] = float(row.get("99%", 0))
            elif row.get("Name"):
                stats["endpoints"].append(
                    {
                        "name": row.get("Name"),
                        "method": row.get("Type"),
                        "requests": int(row.get("Request Count", 0)),
                        "failures": int(row.get("Failure Count", 0)),
                        "avg_response_time": float(row.get("Average Response Time", 0)),
                        "p95": float(row.get("95%", 0)),
                        "p99": float(row.get("99%", 0)),
                    }
                )

    return stats


def parse_stats_history_csv(csv_path: Path) -> dict[str, Any]:
    """Parse Locust stats history CSV file for RPS calculation."""
    history = {"requests_per_second": 0, "data_points": []}

    if not csv_path.exists():
        print(f"Warning: Stats history file not found: {csv_path}")
        return history

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rps_values = []
        for row in reader:
            try:
                rps = float(row.get("Requests/s", 0))
                if rps > 0:
                    rps_values.append(rps)
            except (ValueError, TypeError):
                continue

    if rps_values:
        # Use average RPS, excluding warmup period (first 10%)
        warmup_cutoff = max(1, len(rps_values) // 10)
        stable_rps = rps_values[warmup_cutoff:]
        history["requests_per_second"] = sum(stable_rps) / len(stable_rps) if stable_rps else 0

    return history


def check_thresholds(
    stats: dict[str, Any], history: dict[str, Any], scenario: str
) -> list[ThresholdResult]:
    """Check if stats meet threshold requirements."""
    results = []
    thresholds = THRESHOLDS.get(scenario, THRESHOLDS.get("standard", {}))

    # Calculate error rate
    error_rate = 0
    if stats["total_requests"] > 0:
        error_rate = (stats["total_failures"] / stats["total_requests"]) * 100

    # Check error rate threshold
    if "error_rate_percent" in thresholds:
        threshold = thresholds["error_rate_percent"]
        passed = error_rate <= threshold
        results.append(
            ThresholdResult(
                name="Error Rate",
                threshold=threshold,
                actual=round(error_rate, 2),
                passed=passed,
                message=f"Error rate {error_rate:.2f}% {'<=' if passed else '>'} {threshold}%",
            )
        )

    # Check P95 response time
    if "p95_response_time_ms" in thresholds:
        threshold = thresholds["p95_response_time_ms"]
        actual = stats["p95_response_time"]
        passed = actual <= threshold
        results.append(
            ThresholdResult(
                name="P95 Response Time",
                threshold=threshold,
                actual=round(actual, 2),
                passed=passed,
                message=f"P95 response time {actual:.0f}ms {'<=' if passed else '>'} {threshold}ms",
            )
        )

    # Check P99 response time
    if "p99_response_time_ms" in thresholds:
        threshold = thresholds["p99_response_time_ms"]
        actual = stats["p99_response_time"]
        passed = actual <= threshold
        results.append(
            ThresholdResult(
                name="P99 Response Time",
                threshold=threshold,
                actual=round(actual, 2),
                passed=passed,
                message=f"P99 response time {actual:.0f}ms {'<=' if passed else '>'} {threshold}ms",
            )
        )

    # Check RPS
    if "min_requests_per_second" in thresholds:
        threshold = thresholds["min_requests_per_second"]
        actual = history["requests_per_second"]
        passed = actual >= threshold
        results.append(
            ThresholdResult(
                name="Requests Per Second",
                threshold=threshold,
                actual=round(actual, 2),
                passed=passed,
                message=f"RPS {actual:.1f} {'>=' if passed else '<'} {threshold}",
            )
        )

    return results


def generate_report(
    stats: dict[str, Any],
    history: dict[str, Any],
    threshold_results: list[ThresholdResult],
    scenario: str,
) -> LoadTestReport:
    """Generate a complete load test report."""
    error_rate = 0
    if stats["total_requests"] > 0:
        error_rate = (stats["total_failures"] / stats["total_requests"]) * 100

    all_passed = all(r.passed for r in threshold_results)

    return LoadTestReport(
        scenario=scenario,
        timestamp=datetime.utcnow().isoformat(),
        total_requests=stats["total_requests"],
        total_failures=stats["total_failures"],
        error_rate=round(error_rate, 2),
        avg_response_time=round(stats["avg_response_time"], 2),
        p50_response_time=round(stats["p50_response_time"], 2),
        p95_response_time=round(stats["p95_response_time"], 2),
        p99_response_time=round(stats["p99_response_time"], 2),
        requests_per_second=round(history["requests_per_second"], 2),
        threshold_results=threshold_results,
        passed=all_passed,
    )


def print_report(report: LoadTestReport) -> None:
    """Print report to console."""
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)

    print(f"\nScenario: {report.scenario}")
    print(f"Timestamp: {report.timestamp}")

    print("\n--- Summary ---")
    print(f"Total Requests: {report.total_requests:,}")
    print(f"Total Failures: {report.total_failures:,}")
    print(f"Error Rate: {report.error_rate}%")
    print(f"Requests/sec: {report.requests_per_second}")

    print("\n--- Response Times ---")
    print(f"Average: {report.avg_response_time}ms")
    print(f"P50: {report.p50_response_time}ms")
    print(f"P95: {report.p95_response_time}ms")
    print(f"P99: {report.p99_response_time}ms")

    print("\n--- Threshold Checks ---")
    for result in report.threshold_results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} {result.message}")

    print("\n" + "=" * 60)
    if report.passed:
        print("✅ ALL THRESHOLDS PASSED")
    else:
        print("❌ SOME THRESHOLDS FAILED")
    print("=" * 60 + "\n")


def save_report(report: LoadTestReport, output_path: Path) -> None:
    """Save report to JSON file."""
    report_dict = {
        "scenario": report.scenario,
        "timestamp": report.timestamp,
        "summary": {
            "total_requests": report.total_requests,
            "total_failures": report.total_failures,
            "error_rate": report.error_rate,
            "requests_per_second": report.requests_per_second,
        },
        "response_times": {
            "avg_ms": report.avg_response_time,
            "p50_ms": report.p50_response_time,
            "p95_ms": report.p95_response_time,
            "p99_ms": report.p99_response_time,
        },
        "threshold_checks": [
            {
                "name": r.name,
                "threshold": r.threshold,
                "actual": r.actual,
                "passed": r.passed,
                "message": r.message,
            }
            for r in report.threshold_results
        ],
        "passed": report.passed,
    }

    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    print(f"Report saved to: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check load test thresholds")
    parser.add_argument(
        "--csv-prefix",
        type=str,
        default="results",
        help="Prefix for Locust CSV files (default: results)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="standard",
        choices=["standard", "spike", "soak", "stress"],
        help="Test scenario for threshold selection (default: standard)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="threshold_report.json",
        help="Output file for JSON report (default: threshold_report.json)",
    )

    args = parser.parse_args()

    # Determine base path
    base_path = Path(__file__).parent

    # Parse CSV files
    stats_csv = base_path / f"{args.csv_prefix}_stats.csv"
    history_csv = base_path / f"{args.csv_prefix}_stats_history.csv"

    stats = parse_stats_csv(stats_csv)
    history = parse_stats_history_csv(history_csv)

    # Check thresholds
    threshold_results = check_thresholds(stats, history, args.scenario)

    # Generate and print report
    report = generate_report(stats, history, threshold_results, args.scenario)
    print_report(report)

    # Save JSON report
    output_path = base_path / args.output
    save_report(report, output_path)

    # Return appropriate exit code
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
