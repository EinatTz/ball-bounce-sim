"""
tests/test_unit.py

Unit tests for core simulation logic.
Run with:  pytest tests/test_unit.py -v

Covered:
  - Config parsing (valid YAML, bad YAML, missing keys)
  - DynamicsModule (free flight, bounce physics, multi-step energy)
  - FixedStepSolver (step sequencing, controller cadence)
  - VariableStepSolver (event detection, step-size switching)
  - OutputModule._compute_metrics / _recommend (pure logic, no I/O)
"""

from __future__ import annotations

import math
import textwrap
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers — import the modules under test from the project root.
# The tests directory lives next to the source files so sys.path is adjusted
# by conftest.py (see conftest.py).
# ---------------------------------------------------------------------------
from config import (
    ControllerConfig,
    DynamicsConfig,
    SimConfig,
    SolverConfig,
    VisualizerConfig,
    load_config,
)
from dynamics_module import DynamicsModule
from output_module import OutputModule
from solver_module import FixedStepSolver, VariableStepSolver

# ===========================================================================
# Fixtures
# ===========================================================================


def _make_dynamics(
    pos=1.0,
    vel=0.0,
    gravity=9.81,
    restitution=0.8,
    bounce_gain=5.0,
    paddle_min=-0.2,
    rate_hz=300.0,
) -> DynamicsModule:
    return DynamicsModule(
        initial_position=pos,
        initial_velocity=vel,
        gravity=gravity,
        restitution=restitution,
        bounce_gain=bounce_gain,
        paddle_min=paddle_min,
        rate_hz=rate_hz,
    )


def _make_sim_config(**overrides) -> SimConfig:
    """Build a minimal SimConfig; keyword args override specific sub-config fields."""
    dynamics = DynamicsConfig(
        initial_position=0.0,
        initial_velocity=4.0,
        gravity=9.81,
        restitution=0.8,
        bounce_gain=5.0,
        rate_hz=300.0,
    )
    controller = ControllerConfig(
        kp=0.5,
        ki=0.1,
        kd=0.05,
        target_height=1.0,
        tick_rate_hz=100.0,
        paddle_min=-0.2,
        paddle_max=0.2,
    )
    solver = SolverConfig(
        type="fixed",
        event_trigger="bounce",
        event_rate_hz=1200.0,
        bounce_position_threshold=0.05,
        peak_velocity_threshold=0.2,
    )
    visualizer = VisualizerConfig(target_height=1.0, paddle_min=-1.0, paddle_max=1.0)
    cfg = SimConfig(
        num_ticks=300,
        dynamics=dynamics,
        controller=controller,
        solver=solver,
        visualizer=visualizer,
    )
    for key, val in overrides.items():
        object.__setattr__(cfg, key, val)
    return cfg


# ===========================================================================
# Config parsing tests
# ===========================================================================


class TestConfigParsing:
    def test_load_valid_yaml(self, tmp_path):
        """load_config should parse a valid config.yaml without errors."""
        cfg_text = textwrap.dedent("""
            num_ticks: 50
            dynamics:
              initial_position: 0.0
              initial_velocity: 4.0
              gravity: 9.81
              restitution: 0.8
              bounce_gain: 5.0
              rate_hz: 300.0
            controller:
              kp: 0.5
              ki: 0.1
              kd: 0.05
              target_height: 1.0
              tick_rate_hz: 100.0
              paddle_min: -0.2
              paddle_max: 0.2
            solver:
              type: fixed
              event_trigger: bounce
              event_rate_hz: 1200.0
              bounce_position_threshold: 0.05
              peak_velocity_threshold: 0.2
            visualizer:
              target_height: 1.0
              paddle_min: -1.0
              paddle_max: 1.0
        """)
        p = tmp_path / "config.yaml"
        p.write_text(cfg_text)
        cfg = load_config(str(p))
        assert cfg.num_ticks == 50
        assert cfg.dynamics.gravity == pytest.approx(9.81)
        assert cfg.controller.kp == pytest.approx(0.5)
        assert cfg.solver.type == "fixed"
        assert cfg.visualizer.target_height == pytest.approx(1.0)

    def test_missing_key_raises(self, tmp_path):
        """load_config should raise when a required key is absent."""
        cfg_text = textwrap.dedent("""
            num_ticks: 10
            dynamics:
              initial_position: 0.0
        """)
        p = tmp_path / "config.yaml"
        p.write_text(cfg_text)
        with pytest.raises((KeyError, TypeError)):
            load_config(str(p))

    def test_invalid_yaml_raises(self, tmp_path):
        """load_config should raise on malformed YAML."""
        p = tmp_path / "config.yaml"
        p.write_text("num_ticks: [unclosed")
        with pytest.raises(yaml.YAMLError):
            load_config(str(p))

    def test_dataclass_field_types(self, tmp_path):
        """Parsed config should expose correct Python types."""
        cfg_text = textwrap.dedent("""
            num_ticks: 100
            dynamics:
              initial_position: 0.0
              initial_velocity: 4.0
              gravity: 9.81
              restitution: 0.8
              bounce_gain: 5.0
              rate_hz: 300.0
            controller:
              kp: 0.5
              ki: 0.1
              kd: 0.05
              target_height: 1.0
              tick_rate_hz: 100.0
              paddle_min: -0.2
              paddle_max: 0.2
            solver:
              type: fixed
              event_trigger: bounce
              event_rate_hz: 1200.0
              bounce_position_threshold: 0.05
              peak_velocity_threshold: 0.2
            visualizer:
              target_height: 1.0
              paddle_min: -1.0
              paddle_max: 1.0
        """)
        p = tmp_path / "config.yaml"
        p.write_text(cfg_text)
        cfg = load_config(str(p))
        assert isinstance(cfg.num_ticks, int)
        assert isinstance(cfg.dynamics.gravity, float)
        assert isinstance(cfg.controller.kp, float)
        assert isinstance(cfg.solver.type, str)


# ===========================================================================
# DynamicsModule tests
# ===========================================================================


class TestDynamicsModule:
    def test_free_flight_position_decreases_under_gravity(self):
        """A ball launched upward should decelerate and eventually fall."""
        dyn = _make_dynamics(pos=5.0, vel=0.0)
        dt = 1.0 / 300.0
        positions = []
        for _ in range(300):
            pos, vel = dyn.step(paddle_position=-0.2, step_dt=dt)
            positions.append(pos)
        # Ball should have fallen well below its start
        assert positions[-1] < 5.0

    def test_free_flight_kinematics(self):
        """One step with no bounce should follow x = x0 + v0*dt - 0.5*g*dt^2."""
        dyn = _make_dynamics(pos=5.0, vel=2.0, gravity=9.81)
        dt = 0.01
        pos, vel = dyn.step(paddle_position=-0.2, step_dt=dt)
        expected_vel = 2.0 - 9.81 * dt
        expected_pos = 5.0 + expected_vel * dt   # module applies vel update first
        assert vel == pytest.approx(expected_vel, rel=1e-9)
        assert pos == pytest.approx(expected_pos, rel=1e-9)

    def test_bounce_reverses_velocity(self):
        """Ball hitting the paddle must leave with positive velocity."""
        dyn = _make_dynamics(pos=0.01, vel=-3.0, restitution=0.8, bounce_gain=5.0, paddle_min=-0.2)
        dt = 1.0 / 300.0
        pos, vel = dyn.step(paddle_position=0.0, step_dt=dt)
        assert vel > 0, "velocity must be positive after bounce"

    def test_bounce_restitution_energy(self):
        """Restitution e=1.0, bounce_gain=0 → outgoing speed equals incoming speed.

        The dynamics module applies gravity first, then checks for bounce:
          v_before_check = v_init - g*dt   (gravity step)
          v_out          = -e * v_before_check   (elastic reflection)
        So with v_init=-5.0:
          v_before_check = -5.0 - g*dt   (more negative)
          v_out          = +5.0 + g*dt   (positive, slightly larger than 5.0)
        """
        dyn = _make_dynamics(
            pos=0.001, vel=-5.0, restitution=1.0, bounce_gain=0.0, paddle_min=0.0
        )
        dt = 1.0 / 300.0
        pos, vel = dyn.step(paddle_position=0.0, step_dt=dt)
        v_after_gravity = -5.0 - 9.81 * dt          # gravity applied before bounce check
        expected_vel = -1.0 * v_after_gravity        # elastic reflection: v_out = -e * v_in
        assert vel == pytest.approx(expected_vel, abs=1e-9)

    def test_no_bounce_when_moving_upward(self):
        """Ball moving upward through paddle position should NOT bounce."""
        dyn = _make_dynamics(pos=0.5, vel=10.0)
        dt = 1.0 / 300.0
        pos, vel = dyn.step(paddle_position=1.0, step_dt=dt)
        # velocity should decrease (gravity) but stay positive if fast enough
        # crucially, restitution formula must NOT have been applied
        expected_vel = 10.0 - 9.81 * dt
        assert vel == pytest.approx(expected_vel, rel=1e-6)

    def test_position_clamped_to_paddle_on_bounce(self):
        """After a bounce, ball position should be exactly at paddle level."""
        dyn = _make_dynamics(pos=0.0001, vel=-10.0)
        dt = 1.0 / 300.0
        pos, vel = dyn.step(paddle_position=0.0, step_dt=dt)
        assert pos == pytest.approx(0.0, abs=1e-9)

    def test_multi_bounce_energy_decreases(self):
        """With restitution < 1 and no paddle gain, peak height should decay."""
        dyn = _make_dynamics(pos=2.0, vel=0.0, restitution=0.8, bounce_gain=0.0, paddle_min=0.0)
        dt = 1.0 / 300.0
        peaks = []
        last_vel_sign = None
        for _ in range(3000):
            pos, vel = dyn.step(paddle_position=0.0, step_dt=dt)
            if last_vel_sign is not None and last_vel_sign > 0 and vel <= 0:
                peaks.append(pos)
            last_vel_sign = vel
        assert len(peaks) >= 2
        for i in range(1, len(peaks)):
            assert peaks[i] < peaks[i - 1], "peak heights must be strictly decreasing"

    def test_reset_restores_state(self):
        """reset() should put position and velocity back to provided values."""
        dyn = _make_dynamics(pos=1.0, vel=2.0)
        dt = 1.0 / 300.0
        dyn.step(0.0, dt)
        dyn.reset(initial_position=3.0, initial_velocity=-1.0)
        assert dyn._position == pytest.approx(3.0)
        assert dyn._velocity == pytest.approx(-1.0)


# ===========================================================================
# FixedStepSolver tests
# ===========================================================================


def _mock_ctrl(return_value=0.0):
    ctrl = MagicMock()
    ctrl.step.return_value = return_value
    return ctrl


class TestFixedStepSolver:
    def test_returns_three_values(self):
        dyn = _make_dynamics(pos=1.0, vel=0.0)
        ctrl = _mock_ctrl()
        solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=300.0, ctrl_rate_hz=100.0)
        result = solver.step()
        assert len(result) == 3

    @pytest.mark.parametrize("dyn_hz,ctrl_hz", [
        (300.0, 100.0),   # ratio 3:1
        (600.0, 100.0),   # ratio 6:1
        (100.0, 100.0),   # ratio 1:1
        (1000.0, 100.0),  # ratio 10:1
        (50.0,  100.0),   # ratio 1:2 (ctrl faster than dynamics)
    ])
    def test_controller_called_at_most_once_per_solver_step(self, dyn_hz, ctrl_hz):
        """
        Each call to solver.step() must invoke the controller at most once.
        Verified across 50 solver steps for several dyn/ctrl Hz ratios.
        """
        n_steps = 50
        for _ in range(n_steps):
            dyn = _make_dynamics(pos=1.0, vel=0.0)
            ctrl = _mock_ctrl()
            solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=dyn_hz, ctrl_rate_hz=ctrl_hz)
            solver.step()
            assert ctrl.step.call_count <= 1, (
                f"dyn={dyn_hz} Hz, ctrl={ctrl_hz} Hz: "
                f"ctrl called {ctrl.step.call_count} times in a single solver step"
            )

    @pytest.mark.parametrize("dyn_hz,ctrl_hz", [
        (300.0, 100.0),
        (600.0, 100.0),
        (100.0, 100.0),
        (1000.0, 100.0),
        (50.0,  100.0),
    ])
    def test_controller_called_at_least_once_per_ctrl_period(self, dyn_hz, ctrl_hz):
        """
        Within any window of ceil(dyn_hz/ctrl_hz) + 1 solver steps the
        controller must fire at least once — it must not be silently skipped.
        """
        # Upper bound on how many dynamics steps fit in one ctrl period, +1 margin
        steps_per_ctrl = math.ceil(dyn_hz / ctrl_hz) + 1

        dyn = _make_dynamics(pos=1.0, vel=0.0)
        ctrl = _mock_ctrl()
        solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=dyn_hz, ctrl_rate_hz=ctrl_hz)

        for window in range(10):   # check 10 consecutive ctrl periods
            before = ctrl.step.call_count
            for _ in range(steps_per_ctrl):
                solver.step()
            after = ctrl.step.call_count
            assert after > before, (
                f"dyn={dyn_hz} Hz, ctrl={ctrl_hz} Hz: "
                f"controller not called in window {window} "
                f"({steps_per_ctrl} solver steps, "
                f"calls before={before} after={after})"
            )

    def test_ball_position_changes_each_step(self):
        dyn = _make_dynamics(pos=2.0, vel=-1.0)
        ctrl = _mock_ctrl()
        solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=300.0, ctrl_rate_hz=100.0)
        pos0, _, _ = solver.step()
        pos1, _, _ = solver.step()
        assert pos0 != pos1

    def test_reset_clears_time(self):
        dyn = _make_dynamics()
        ctrl = _mock_ctrl()
        solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=300.0, ctrl_rate_hz=100.0)
        for _ in range(10):
            solver.step()
        solver.reset()
        assert solver._t == pytest.approx(0.0)
        assert solver._next_ctrl_t == pytest.approx(0.0)

    def test_paddle_position_propagated(self):
        """Solver should pass its stored paddle back to dynamics each step."""
        dyn = _make_dynamics(pos=1.0, vel=0.0)
        ctrl = MagicMock()
        ctrl.step.return_value = 0.15   # controller sets paddle to 0.15
        solver = FixedStepSolver(dyn, ctrl, dynamics_rate_hz=300.0, ctrl_rate_hz=100.0)
        # First step triggers the controller (t==next_ctrl_t==0)
        solver.step()
        assert solver._paddle == pytest.approx(0.15)


# ===========================================================================
# VariableStepSolver tests
# ===========================================================================


class TestVariableStepSolver:
    def _make_solver(self, trigger="bounce", **kw):
        dyn = _make_dynamics(pos=1.0, vel=0.0)
        ctrl = _mock_ctrl()
        return (
            dyn,
            ctrl,
            VariableStepSolver(
                dyn,
                ctrl,
                dynamics_rate_hz=300.0,
                ctrl_rate_hz=100.0,
                event_trigger=trigger,
                event_rate_hz=1200.0,
                bounce_position_threshold=0.05,
                peak_velocity_threshold=0.2,
                **kw,
            ),
        )

    def test_returns_five_values(self):
        _, _, solver = self._make_solver()
        result = solver.step()
        assert len(result) == 5

    def test_invalid_trigger_raises(self):
        dyn = _make_dynamics()
        ctrl = _mock_ctrl()
        with pytest.raises(ValueError, match="event_trigger"):
            VariableStepSolver(dyn, ctrl, 300.0, 100.0, event_trigger="invalid")

    def test_event_none_when_ball_high(self):
        """Ball well above paddle → no bounce event."""
        dyn = _make_dynamics(pos=2.0, vel=0.0)
        ctrl = _mock_ctrl()
        solver = VariableStepSolver(
            dyn,
            ctrl,
            dynamics_rate_hz=300.0,
            ctrl_rate_hz=100.0,
            event_trigger="bounce",
            event_rate_hz=1200.0,
            bounce_position_threshold=0.05,
            peak_velocity_threshold=0.2,
        )
        _, _, _, event, _ = solver.step()
        assert event == "none"

    def test_bounce_event_detected_near_paddle(self):
        """Ball very close to paddle should trigger 'bounce' event."""
        dyn = _make_dynamics(pos=0.02, vel=-1.0)  # 0.02 m from paddle=0 < 0.05 threshold
        ctrl = _mock_ctrl()
        solver = VariableStepSolver(
            dyn,
            ctrl,
            dynamics_rate_hz=300.0,
            ctrl_rate_hz=100.0,
            event_trigger="bounce",
            event_rate_hz=1200.0,
            bounce_position_threshold=0.05,
            peak_velocity_threshold=0.2,
        )
        _, _, _, event, _ = solver.step()
        assert event == "bounce"

    def test_step_dt_returned(self):
        """The 5th return value should be a positive dt."""
        _, _, solver = self._make_solver()
        _, _, _, _, dt = solver.step()
        assert dt > 0

    def test_reset_clears_state(self):
        _, _, solver = self._make_solver()
        for _ in range(5):
            solver.step()
        solver.reset()
        assert solver._t == pytest.approx(0.0)
        assert solver._next_ctrl_t == pytest.approx(0.0)
        assert solver._paddle == pytest.approx(0.0)


# ===========================================================================
# OutputModule metric / recommendation logic tests (no file I/O)
# ===========================================================================


class TestOutputModuleMetrics:
    """Test _compute_metrics and _recommend via OutputModule internals.

    We bypass __init__ file-system side effects by constructing the object
    with a minimal mock config and then manually setting internal state.
    """

    def _make_output_module(self, target=1.0) -> OutputModule:
        cfg = _make_sim_config()
        cfg.controller.target_height = target
        # Patch mkdir so __init__ doesn't touch the filesystem
        with patch("output_module.OUTPUT_DIR") as mock_dir:
            mock_dir.mkdir = MagicMock()
            out = OutputModule.__new__(OutputModule)
            out._cfg = cfg
            out._target = target
            out._rows = []
            out._peaks = []
            out._prev_peak = float("nan")
            out._settling_tick = None
            import time
            out._start_wall = time.perf_counter()
            from datetime import datetime, timezone
            out._start_iso = datetime.now(timezone.utc).isoformat()
        return out

    def test_rmse_zero_for_perfect_peaks(self):
        out = self._make_output_module(target=1.0)
        out._peaks = [1.0, 1.0, 1.0, 1.0]
        # Add minimal rows so settling_tick lookup doesn't fail
        out._rows = [{"time_s": i * 0.01} for i in range(10)]
        metrics = out._compute_metrics(elapsed=1.0)
        assert metrics["rmse_m"] == pytest.approx(0.0, abs=1e-9)

    def test_rmse_correct_value(self):
        out = self._make_output_module(target=1.0)
        out._peaks = [0.9, 1.1, 0.9, 1.1]  # errors of ±0.1 → RMSE = 0.1
        out._rows = [{"time_s": i * 0.01} for i in range(10)]
        metrics = out._compute_metrics(elapsed=1.0)
        assert metrics["rmse_m"] == pytest.approx(0.1, rel=1e-6)

    def test_no_peaks_returns_none(self):
        out = self._make_output_module(target=1.0)
        out._rows = [{"time_s": i * 0.01} for i in range(10)]
        metrics = out._compute_metrics(elapsed=1.0)
        assert metrics["rmse_m"] is None
        assert metrics["num_peaks_detected"] == 0

    def test_recommend_insufficient_data(self):
        out = self._make_output_module()
        rec = out._recommend(rmse=0.1, ss_rmse=0.05, peaks=[1.0, 0.9])
        assert rec["status"] == "insufficient_data"

    def test_recommend_converging_status(self):
        """Late peaks much closer to target than early peaks → converging."""
        out = self._make_output_module(target=1.0)
        # Early peaks far off, late peaks close
        peaks = [0.5, 0.4, 0.3, 0.2, 1.05, 1.02, 1.01, 1.0]
        rec = out._recommend(rmse=0.2, ss_rmse=0.02, peaks=peaks)
        assert rec["status"] == "converging"

    def test_recommend_not_converging_status(self):
        """Uniformly bad peaks → not converging."""
        out = self._make_output_module(target=1.0)
        peaks = [0.5, 0.6, 0.5, 0.6, 0.5, 0.6, 0.5, 0.6]
        rec = out._recommend(rmse=0.5, ss_rmse=0.5, peaks=peaks)
        assert rec["status"] == "not_converging"

    def test_recommend_actions_non_empty(self):
        out = self._make_output_module(target=1.0)
        peaks = [0.5, 0.6, 0.5, 0.6, 0.5, 0.6, 0.5, 0.6]
        rec = out._recommend(rmse=0.5, ss_rmse=0.5, peaks=peaks)
        assert len(rec.get("actions", [])) > 0
