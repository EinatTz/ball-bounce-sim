#!/usr/bin/env python
"""
tests/generate_baseline.py

Run this script to (re)generate tests/baseline.json from a live simulation run.
Commit the updated file after any intentional change to dynamics, controller
tuning, or num_ticks.

Usage:
    python tests/generate_baseline.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the project root or the tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Re-use the same scenario dict and StubController from test_performance
# (imported here so the baseline is always generated from the same setup)
from test_performance import SCENARIO, _run_scenario

BASELINE_PATH = Path(__file__).parent / "baseline.json"


def main():
    print("Running scenario to generate baseline …")
    metrics = _run_scenario()

    rmse = metrics["rmse_m"]
    ss = metrics["steady_state_rmse_m"]
    tps = metrics["ticks_per_second"]
    n_peaks = metrics["num_peaks_detected"]

    if rmse is None:
        print("ERROR: No bounce peaks detected — cannot generate baseline.")
        sys.exit(1)

    baseline = {
        "_comment": (f"Generated {datetime.now(timezone.utc).isoformat()} by generate_baseline.py"),
        "_scenario": (
            "fixed solver, 300 ticks, "
            f"kp={SCENARIO['controller']['kp']} "
            f"ki={SCENARIO['controller']['ki']} "
            f"kd={SCENARIO['controller']['kd']}, "
            f"target={SCENARIO['controller']['target_height']}m"
        ),
        # Lower bounds / upper bounds stored as the raw measured value.
        # test_performance.py applies the tolerance multipliers at test time.
        "num_peaks_detected_min": n_peaks,
        "rmse_m_max": round(rmse, 6),
        "steady_state_rmse_m_max": round(ss, 6) if ss is not None else None,
        "ticks_per_second_min": round(tps, 1),
    }

    BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"Baseline written to {BASELINE_PATH}")
    print(f"  num_peaks  : {n_peaks}")
    print(f"  rmse_m     : {rmse:.6f}")
    print(f"  ss_rmse_m  : {ss:.6f}" if ss is not None else "  ss_rmse_m : N/A")
    print(f"  ticks/s    : {tps:.1f}")


if __name__ == "__main__":
    main()
