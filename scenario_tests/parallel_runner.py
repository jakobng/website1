"""
Parallel scenario test runner for CoPro Calculator.

Runs comprehensive scenario tests in parallel using ThreadPoolExecutor.
Reuses all test definitions and report logic from comprehensive_test_runner.

Usage:
    cd backend
    python ../scenario_tests/parallel_runner.py                   # all scenarios, default workers
    python ../scenario_tests/parallel_runner.py --workers 4       # 4 parallel workers
    python ../scenario_tests/parallel_runner.py --category SWEEP_AM --workers 6
    python ../scenario_tests/parallel_runner.py --scenario doc_france_standard
    python ../scenario_tests/parallel_runner.py --summary-only    # skip individual reports
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Import from comprehensive_test_runner ───────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from comprehensive_test_runner import (
    build_all_scenarios,
    run_scenario,
    write_summary_report,
    ensure_seeded,
    REPORTS_DIR,
)


def main():
    parser = argparse.ArgumentParser(description="Parallel CoPro Calculator scenario tests")
    parser.add_argument('--category', help='Run only this category (A/B/C/D/E/F/SWEEP/SWEEP_EU/SWEEP_AM/SWEEP_AS/SWEEP_AF/SWEEP_OC/SWEEP_OT)')
    parser.add_argument('--scenario', help='Run a single scenario by name')
    parser.add_argument('--summary-only', action='store_true', help='Skip individual report files')
    parser.add_argument('--workers', type=int, default=None, help='Number of parallel workers (default: min(8, cpu_count))')
    args = parser.parse_args()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    try:
        ensure_seeded()
    except RuntimeError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1) from err

    all_scenarios = build_all_scenarios()

    if args.scenario:
        all_scenarios = [s for s in all_scenarios if s['name'] == args.scenario]
    elif args.category:
        all_scenarios = [s for s in all_scenarios if s['category'].upper() == args.category.upper()]

    if not all_scenarios:
        print(f"No scenarios matched. Available categories: A B C D E F SWEEP SWEEP_EU SWEEP_AM SWEEP_AS SWEEP_AF SWEEP_OC SWEEP_OT")
        return

    # Determine worker count
    if args.workers is None:
        args.workers = min(8, os.cpu_count() or 4)
    elif args.workers < 1:
        args.workers = 1

    print(f"Running {len(all_scenarios)} scenario(s) with {args.workers} worker(s)...\n")

    results = []
    all_anomalies = {}

    # Thread-safe progress tracking
    lock = threading.Lock()
    completed_count = [0]  # Use list to allow modification in nested function

    def run_and_track(scenario_dict):
        """Run a scenario and return (result, anomalies) tuple."""
        result, anomalies = run_scenario(scenario_dict, write_report=not args.summary_only)

        with lock:
            completed_count[0] += 1
            reds = sum(1 for a in anomalies if a['level'] == 'red')
            oranges = sum(1 for a in anomalies if a['level'] == 'orange')

            status = f"{result.total_financing_pct:.1f}% ({result.financing_currency} {result.total_financing_amount:,.0f})"
            if result.error:
                status = f"ERROR: {result.error[:60]}"
            flags = ""
            if reds:
                flags += f" [RED x{reds}]"
            if oranges:
                flags += f" [WARN x{oranges}]"

            print(f"[{completed_count[0]:3d}/{len(all_scenarios)}] {result.category:8s} {result.name:40s} {status}{flags}")

        return result, anomalies

    # Submit all scenarios and collect results as they complete
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_and_track, s): s for s in all_scenarios}

        for future in as_completed(futures):
            try:
                result, anomalies = future.result()
                results.append(result)
                all_anomalies[result.name] = anomalies
            except Exception as e:
                scenario = futures[future]
                with lock:
                    print(f"[ERR] {scenario['category']:8s} {scenario['name']:40s} Exception: {str(e)[:60]}")

    # Generate summary report
    write_summary_report(results, all_anomalies)

    # Final summary
    total_reds = sum(1 for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'red')
    total_oranges = sum(1 for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'orange')
    print(f"\nDone. {len(results)} scenarios | RED {total_reds} | WARN {total_oranges}")
    print(f"Reports: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
