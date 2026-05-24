"""
tests/test_performance.py

Performance / regression tests.

Runs a fixed, deterministic scenario end-to-end (no file I/O, no visualizer,
no controller shared library) and asserts that key metrics stay within the
tolerances recorded in tests/baseline.json.

The test is intentionally self-contained so it can run in CI without any
compiled artefacts beyond what Python provides.

Updating the baseline
---------------------
Run the helper script:

    python tests/generate_baseline.py

and commit the updated tests/baseline.json.

Tolerances
----------
Each metric in baseline.json has a specific direction (max / min).
The test fails if the live run exceeds the allowed drift:

  rmse_m                 <= baseline["rmse_m_max"]         * TOLERANCE_FACTOR
  steady_state_rmse_m    <= baseline["steady_state_rmse_m_max"] * TOLERANCE_FACTOR
  num_peaks_detected     >= baseline["num_peaks_detected_min"]
  ticks_per_second       >= baseline["ticks_per_second_min"] * PERF_FACTOR
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Project imports (conftest.py adds the root to sys.path)
# ---------------------------------------------------------------------------
from config import (
    ControllerConfig,
    DynamicsConfig,
    SimConfig,
    SolverConfig,
    VisualizerConfig,
)
from dynamics_module import DynamicsModule
from output_module import OutputModule
from solver_module import FixedStepSolver

# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------
TOLERANCE_FACTOR = 1.20   # RMSE may be up to 20 % worse than baseline before failing
PERF_FACTOR = 0.60        # ticks/s may be up to 40 % slower than baseline before failing

BASELINE_PATH = Path(__file__).parent / "baseline.json"

# ---------------------------------------------------------------------------
# Scenario definition (mirrors config.yaml default — kept here explicitly
# so the test is immune to config.yaml changes)
# ---------------------------------------------------------------------------
SCENARIO = dict(
    num_ticks=300,
    dynamics=dict(
        initial_position=0.0,
        initial_velocity=4.0,
        gravity=9.81,
        restitution=0.8,
        bounce_gain=5.0,
        rate_hz=300.0,
        paddle_min=-0.2,
    ),
    controller=dict(
        kp=0.5,
        ki=0.1,
        kd=0.05,
        target_height=1.0,
        tick_rate_hz=100.0,
        paddle_min=-0.2,
        paddle_max=0.2,
    ),
)


# ---------------------------------------------------------------------------
# Stub controller (avoids needing the compiled shared library in CI)
# ---------------------------------------------------------------------------

class _StubController:
    """
    Simple PID controller implemented in pure Python.
    Matches the C controller's public interface so FixedStepSolver works
    without the compiled .so/.dylib/.dll.
    """

    def __init__(self, kp, ki, kd, target_height, tick_rate_hz, paddle_min, paddle_max):
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._target = target_height
        self._dt = 1.0 / tick_rate_hz
        self._paddle_min = paddle_min
        self._paddle_max = paddle_max
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_peak: float = float("nan")
        self._prev_vel = 0.0

    def step(self, ball_position: float, ball_velocity: float) -> float:
        # Peak detection: velocity sign flip from + to -
        if self._prev_vel > 0 and ball_velocity <= 0:
            self._last_peak = ball_position
        self._prev_vel = ball_velocity

        error = self._target - ball_position
        self._integral += error * self._dt
        derivative = (error - self._prev_error) / self._dt
        self._prev_error = error
        output = self._kp * error + self._ki * self._integral + self._kd * derivative
        return max(self._paddle_min, min(self._paddle_max, output))

    def last_peak(self) -> float:
        return self._last_peak

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_peak = float("nan")
        self._prev_vel = 0.0

    def destroy(self):
        pass


# ---------------------------------------------------------------------------
# Run the scenario
# ---------------------------------------------------------------------------

def _run_scenario() -> dict:
    """
    Run the fixed-scenario simulation and return the performance metrics dict.
    No file I/O, no visualizer.
    """
    sc = SCENARIO
    dc = sc["dynamics"]
    cc = sc["controller"]

    dynamics = DynamicsModule(
        initial_position=dc["initial_position"],
        initial_velocity=dc["initial_velocity"],
        gravity=dc["gravity"],
        restitution=dc["restitution"],
        bounce_gain=dc["bounce_gain"],
        paddle_min=dc["paddle_min"],
        rate_hz=dc["rate_hz"],
    )

    ctrl = _StubController(**cc)

    solver = FixedStepSolver(
        dynamics,
        ctrl,
        dynamics_rate_hz=dc["rate_hz"],
        ctrl_rate_hz=cc["tick_rate_hz"],
    )

    # Build a minimal SimConfig so OutputModule is happy
    cfg = SimConfig(
        num_ticks=sc["num_ticks"],
        dynamics=DynamicsConfig(**{k: v for k, v in dc.items() if k != "paddle_min"}),
        controller=ControllerConfig(**cc),
        solver=SolverConfig(
            type="fixed",
            event_trigger="bounce",
            event_rate_hz=1200.0,
            bounce_position_threshold=0.05,
            peak_velocity_threshold=0.2,
        ),
        visualizer=VisualizerConfig(target_height=1.0, paddle_min=-1.0, paddle_max=1.0),
    )

    # Suppress file writes from OutputModule
    with patch("output_module.OUTPUT_DIR") as mock_dir:
        mock_dir.mkdir = MagicMock()
        out = OutputModule.__new__(OutputModule)
        out._cfg = cfg
        out._target = cfg.controller.target_height
        out._rows = []
        out._peaks = []
        out._prev_peak = float("nan")
        out._settling_tick = None
        out._start_wall = time.perf_counter()
        from datetime import datetime, timezone
        out._start_iso = datetime.now(timezone.utc).isoformat()

    sim_time = 0.0
    dt = 1.0 / cc["tick_rate_hz"]

    for tick in range(sc["num_ticks"]):
        ball_position, ball_velocity, paddle = solver.step()
        sim_time += dt
        peak = ctrl.last_peak()

        out.record(
            tick=tick,
            sim_time=sim_time,
            ball_position=ball_position,
            ball_velocity=ball_velocity,
            paddle=paddle,
            last_peak=peak,
            event="none",
            step_dt=dt,
        )

    elapsed = time.perf_counter() - out._start_wall
    return out._compute_metrics(elapsed)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scenario_metrics():
    """Run the scenario once per module; share results across all tests."""
    return _run_scenario()


@pytest.fixture(scope="module")
def baseline():
    assert BASELINE_PATH.exists(), (
        f"Baseline file not found: {BASELINE_PATH}\n"
        "Run `python tests/generate_baseline.py` to create it."
    )
    return json.loads(BASELINE_PATH.read_text())


class TestPerformanceRegression:
    def test_peaks_detected(self, scenario_metrics, baseline):
        """Simulation must detect at least as many bounce peaks as baseline."""
        n = scenario_metrics["num_peaks_detected"]
        threshold = baseline["num_peaks_detected_min"]
        assert n >= threshold, (
            f"Only {n} bounce peaks detected; expected >= {threshold}. "
            "Check dynamics or solver configuration."
        )

    def test_overall_rmse_within_tolerance(self, scenario_metrics, baseline):
        """Peak RMSE must not exceed baseline × TOLERANCE_FACTOR."""
        rmse = scenario_metrics["rmse_m"]
        if rmse is None:
            pytest.skip("No peaks detected — covered by test_peaks_detected")
        limit = baseline["rmse_m_max"] * TOLERANCE_FACTOR
        assert rmse <= limit, (
            f"Overall RMSE {rmse:.4f} m exceeds tolerance limit {limit:.4f} m "
            f"(baseline={baseline['rmse_m_max']:.4f}, factor={TOLERANCE_FACTOR})."
        )

    def test_steady_state_rmse_within_tolerance(self, scenario_metrics, baseline):
        """Steady-state RMSE (last 25 % of peaks) must stay within tolerance."""
        ss = scenario_metrics["steady_state_rmse_m"]
        if ss is None:
            pytest.skip("Insufficient peaks for steady-state RMSE")
        limit = baseline["steady_state_rmse_m_max"] * TOLERANCE_FACTOR
        assert ss <= limit, (
            f"Steady-state RMSE {ss:.4f} m exceeds tolerance limit {limit:.4f} m "
            f"(baseline={baseline['steady_state_rmse_m_max']:.4f}, factor={TOLERANCE_FACTOR})."
        )

    def test_throughput_acceptable(self, scenario_metrics, baseline):
        """Simulation must run at least PERF_FACTOR × baseline ticks/s."""
        tps = scenario_metrics["ticks_per_second"]
        limit = baseline["ticks_per_second_min"] * PERF_FACTOR
        assert tps >= limit, (
            f"Throughput {tps:.0f} ticks/s is below limit {limit:.0f} "
            f"(baseline={baseline['ticks_per_second_min']}, factor={PERF_FACTOR})."
        )

    def test_metrics_schema(self, scenario_metrics):
        """Returned metrics dict must contain all expected keys."""
        required = {
            "rmse_m", "steady_state_rmse_m", "num_peaks_detected",
            "peak_heights_m", "mean_error_m", "max_abs_error_m",
            "ticks_per_second", "wall_time_s", "optimization",
        }
        missing = required - scenario_metrics.keys()
        assert not missing, f"Metrics dict missing keys: {missing}"

    def test_optimization_block_present(self, scenario_metrics):
        """optimization sub-dict must have status and actions."""
        opt = scenario_metrics["optimization"]
        assert "status" in opt
        assert isinstance(opt.get("actions", []), list)
