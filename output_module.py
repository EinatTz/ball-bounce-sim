"""
output_module.py — Handles all simulation output:
  1. scenario_results.csv   — per-tick time-series data
  2. runtime_log.json       — versions, config, and run metadata
  3. performance_metrics.json — bounce-peak RMSE and optimization recommendation
"""

from __future__ import annotations

import csv
import json
import math
import platform
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import SimConfig

# ── Optional imports (graceful fallback if not installed) ──────────────────────
try:
    import numpy as np

    _NUMPY = True
except ImportError:
    _NUMPY = False

try:
    import matplotlib

    _MPL_VERSION = matplotlib.__version__
except ImportError:
    _MPL_VERSION = "not installed"

try:
    import yaml

    _YAML_VERSION = yaml.__version__
except ImportError:
    _YAML_VERSION = "not installed"

OUTPUT_DIR = Path("output")

# ── CSV field names ────────────────────────────────────────────────────────────
_CSV_FIELDS = [
    "tick",
    "time_s",
    "ball_position_m",
    "ball_velocity_ms",
    "paddle_position_m",
    "last_peak_m",
    "event",
    "step_dt_s",
]


class OutputModule:
    """Collects simulation data and writes all three output artefacts on finish."""

    def __init__(self, cfg: "SimConfig"):
        self._cfg = cfg
        self._target = cfg.controller.target_height
        self._rows: list[dict] = []
        self._peaks: list[float] = []  # detected bounce peaks
        self._prev_peak = float("nan")
        self._settling_tick: int | None = None  # first tick within 5 % of target
        self._start_wall: float = time.perf_counter()
        self._start_iso: str = datetime.now(timezone.utc).isoformat()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def record(
        self,
        tick: int,
        sim_time: float,
        ball_position: float,
        ball_velocity: float,
        paddle: float,
        last_peak: float,
        event: str,
        step_dt: float,
    ) -> None:
        """Call once per tick from the simulation loop."""
        self._rows.append(
            {
                "tick": tick,
                "time_s": round(sim_time, 6),
                "ball_position_m": round(ball_position, 6),
                "ball_velocity_ms": round(ball_velocity, 6),
                "paddle_position_m": round(paddle, 6),
                "last_peak_m": round(last_peak, 6) if not math.isnan(last_peak) else "",
                "event": event,
                "step_dt_s": round(step_dt, 8),
            }
        )

        # Track new peaks (controller reports them; deduplicate on change)
        if not math.isnan(last_peak) and last_peak != self._prev_peak:
            self._peaks.append(last_peak)
            self._prev_peak = last_peak

        # Settling: first tick where ball is within 5 % of target and stays
        if self._settling_tick is None:
            if abs(ball_position - self._target) / max(self._target, 1e-9) <= 0.05:
                self._settling_tick = tick

    def finish(self) -> dict:
        """
        Write all output files.
        Returns the performance metrics dict so main.py can print a summary.
        """
        elapsed = time.perf_counter() - self._start_wall
        metrics = self._compute_metrics(elapsed)

        self._write_csv()
        self._write_runtime_log(elapsed)
        self._write_metrics(metrics)

        return metrics

    # ── Writers ────────────────────────────────────────────────────────────────

    def _write_csv(self) -> None:
        path = OUTPUT_DIR / "scenario_results.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(self._rows)
        print(f"[output] scenario_results  → {path}  ({len(self._rows)} rows)")

    def _write_runtime_log(self, elapsed: float) -> None:
        cfg = self._cfg
        log = {
            "run": {
                "started_utc": self._start_iso,
                "wall_time_s": round(elapsed, 4),
                "num_ticks": cfg.num_ticks,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "os": sys.platform,
            },
            "versions": {
                "numpy": np.__version__ if _NUMPY else "not installed",
                "matplotlib": _MPL_VERSION,
                "pyyaml": _YAML_VERSION,
            },
            "config": {
                "dynamics": asdict(cfg.dynamics),
                "controller": asdict(cfg.controller),
                "solver": asdict(cfg.solver),
                "visualizer": asdict(cfg.visualizer),
            },
        }
        path = OUTPUT_DIR / "runtime_log.json"
        with open(path, "w") as f:
            json.dump(log, f, indent=2)
        print(f"[output] runtime_log       → {path}")

    def _write_metrics(self, metrics: dict) -> None:
        path = OUTPUT_DIR / "performance_metrics.json"
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"[output] performance_metrics → {path}")

    # ── Metric computation ─────────────────────────────────────────────────────

    def _compute_metrics(self, elapsed: float) -> dict:
        target = self._target
        peaks = self._peaks

        # ── RMSE of bounce peaks vs target ────────────────────────────────────
        if peaks:
            errors = [p - target for p in peaks]
            rmse = math.sqrt(sum(e**2 for e in errors) / len(errors))
            mean_err = sum(errors) / len(errors)
            max_err = max(abs(e) for e in errors)

            # Steady-state RMSE: last 25 % of peaks
            ss_start = max(0, int(len(peaks) * 0.75))
            ss_peaks = peaks[ss_start:]
            ss_rmse = (
                math.sqrt(sum((p - target) ** 2 for p in ss_peaks) / len(ss_peaks))
                if ss_peaks
                else float("nan")
            )
        else:
            rmse = mean_err = max_err = ss_rmse = float("nan")

        # ── Settling time ─────────────────────────────────────────────────────
        settling_tick = self._settling_tick
        settling_time = (
            self._rows[settling_tick]["time_s"]
            if settling_tick is not None and settling_tick < len(self._rows)
            else None
        )

        # ── Ticks per second ──────────────────────────────────────────────────
        ticks_per_sec = len(self._rows) / elapsed if elapsed > 0 else float("nan")

        # ── Optimization recommendation ───────────────────────────────────────
        recommendation = self._recommend(rmse, ss_rmse, peaks)

        return {
            "metric": "bounce_peak_rmse_vs_target",
            "description": (
                "Root-mean-square error of detected ball bounce peaks "
                "relative to the controller target height (m). "
                "Lower is better."
            ),
            "target_height_m": target,
            "num_peaks_detected": len(peaks),
            "peak_heights_m": [round(p, 6) for p in peaks],
            "rmse_m": round(rmse, 6) if not math.isnan(rmse) else None,
            "steady_state_rmse_m": round(ss_rmse, 6) if not math.isnan(ss_rmse) else None,
            "mean_error_m": round(mean_err, 6) if not math.isnan(mean_err) else None,
            "max_abs_error_m": round(max_err, 6) if not math.isnan(max_err) else None,
            "settling_tick": settling_tick,
            "settling_time_s": settling_time,
            "wall_time_s": round(elapsed, 4),
            "ticks_per_second": round(ticks_per_sec, 1),
            "optimization": recommendation,
        }

    def _recommend(self, rmse: float, ss_rmse: float, peaks: list[float]) -> dict:
        """
        Analyse peak error trend and recommend tuning actions.
        Compares early vs late peak RMSE to detect whether the system
        is converging, diverging, or already settled.
        """
        cfg = self._cfg
        ccfg = cfg.controller

        if len(peaks) < 4:
            return {
                "status": "insufficient_data",
                "message": "Too few bounce peaks to make a recommendation.",
            }

        mid = len(peaks) // 2
        early = peaks[:mid]
        late = peaks[mid:]
        target = self._target

        early_rmse = math.sqrt(sum((p - target) ** 2 for p in early) / len(early))
        late_rmse = math.sqrt(sum((p - target) ** 2 for p in late) / len(late))
        improving = late_rmse < early_rmse
        ratio = late_rmse / early_rmse if early_rmse > 0 else 1.0

        actions = []

        # ── Diverging or barely improving ─────────────────────────────────────
        if not improving or ratio > 0.8:
            if ccfg.kp < 1.0:
                actions.append(
                    f"Increase kp (currently {ccfg.kp}) — proportional gain is low; "
                    "the controller is under-responding to height error."
                )
            if ccfg.ki < 0.05:
                actions.append(
                    f"Increase ki (currently {ccfg.ki}) — integral gain is low; "
                    "steady-state offset will persist."
                )
            if cfg.solver.type == "fixed":
                actions.append(
                    "Switch solver to 'variable' with event_trigger='bounce' — "
                    "higher resolution near impacts improves bounce accuracy."
                )

        # ── Converging well ───────────────────────────────────────────────────
        else:
            if ratio < 0.2 and not math.isnan(ss_rmse) and ss_rmse < 0.02:
                actions.append(
                    "System is well-tuned. Consider reducing kd slightly to "
                    "speed up settling without sacrificing steady-state accuracy."
                )
            else:
                actions.append(
                    f"System is converging (early RMSE {early_rmse:.4f} m → "
                    f"late RMSE {late_rmse:.4f} m). "
                    "Increase num_ticks to allow full settling."
                )

        status = "converging" if improving else "not_converging"

        return {
            "status": status,
            "early_rmse_m": round(early_rmse, 6),
            "late_rmse_m": round(late_rmse, 6),
            "improvement_ratio": round(ratio, 4),
            "actions": actions,
        }
