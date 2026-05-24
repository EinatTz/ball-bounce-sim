#!/usr/bin/env python3
"""
run_scenarios.py

Runs all four demonstration scenarios and saves plots for each.

Usage (from project root, with venv active):
    python run_scenarios.py

Output:
    scenarios/<name>/scenario_results.csv
    scenarios/<name>/runtime_log.json
    scenarios/<name>/performance_metrics.json
    scenarios/<name>/plots/ball_height.png
    scenarios/<name>/plots/ball_velocity.png
    scenarios/<name>/plots/paddle_command.png
    scenarios/<name>/plots/combined.png
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "id": "a_fixed_reasonable",
        "label": "A — Fixed solver, reasonable step size (300 Hz)",
        "config": "scenarios/a_fixed_reasonable/config.yaml",
    },
    {
        "id": "b_fixed_degraded",
        "label": "B — Fixed solver, degraded step size (10 Hz)",
        "config": "scenarios/b_fixed_degraded/config.yaml",
    },
    {
        "id": "c_variable_tight",
        "label": "C — Variable solver, tight tolerances",
        "config": "scenarios/c_variable_tight/config.yaml",
    },
    {
        "id": "d_variable_loose",
        "label": "D — Variable solver, loose tolerances",
        "config": "scenarios/d_variable_loose/config.yaml",
    },
]

PLOT_STYLE = {
    "ball_height": {"col": "ball_position_m", "ylabel": "Ball height (m)", "color": "#2176AE"},
    "ball_velocity": {
        "col": "ball_velocity_ms",
        "ylabel": "Ball velocity (m/s)",
        "color": "#E84855",
    },
    "paddle": {"col": "paddle_position_m", "ylabel": "Paddle command (m)", "color": "#3BB273"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_scenario(scenario: dict) -> Path:
    """Run main.py with the scenario config and return the output directory."""
    sid = scenario["id"]
    out_dir = Path("scenarios") / sid
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─' * 60}")
    print(f"  Running scenario {sid}")
    print(f"{'─' * 60}")

    result = subprocess.run(
        [sys.executable, "main.py", "--config", scenario["config"]],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  [WARNING] main.py exited with code {result.returncode}")

    # Move output files into the scenario folder
    for fname in ("scenario_results.csv", "runtime_log.json", "performance_metrics.json"):
        src = Path("output") / fname
        if src.exists():
            shutil.copy(src, out_dir / fname)

    return out_dir


def load_csv(path: Path) -> dict[str, list]:
    """Load scenario_results.csv into column lists."""
    data: dict[str, list] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                data.setdefault(k, [])
                try:
                    data[k].append(float(v))
                except (ValueError, TypeError):
                    data[k].append(v)
    return data


def load_metrics(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def _apply_common_style(ax: plt.Axes, xlabel: str, ylabel: str, title: str):
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.spines[["top", "right"]].set_visible(False)


def plot_individual(data: dict, out_dir: Path, scenario_label: str):
    """Save one PNG per metric."""
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    time = data["time_s"]
    target = None

    # Read target height from metrics if available
    metrics_path = out_dir / "performance_metrics.json"
    if metrics_path.exists():
        m = load_metrics(metrics_path)
        target = m.get("target_height_m")

    for name, cfg in PLOT_STYLE.items():
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(time, data[cfg["col"]], color=cfg["color"], linewidth=0.9, label=cfg["col"])

        if name == "ball_height" and target is not None:
            ax.axhline(
                target, color="gray", linestyle="--", linewidth=0.8, label=f"target = {target} m"
            )
            ax.legend(fontsize=9)

        _apply_common_style(ax, "Time (s)", cfg["ylabel"], f"{scenario_label}\n{cfg['ylabel']}")
        fig.tight_layout()
        path = plots_dir / f"{name}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  [plot] {path}")


def plot_combined(data: dict, out_dir: Path, scenario_label: str):
    """Save a single 3-panel figure."""
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    time = data["time_s"]
    target = None
    metrics_path = out_dir / "performance_metrics.json"
    if metrics_path.exists():
        m = load_metrics(metrics_path)
        target = m.get("target_height_m")
        rmse = m.get("rmse_m")
        ss_rmse = m.get("steady_state_rmse_m")
    else:
        rmse = ss_rmse = None

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.suptitle(scenario_label, fontsize=13, fontweight="bold", y=0.98)

    items = list(PLOT_STYLE.items())
    for i, (name, cfg) in enumerate(items):
        ax = axes[i]
        ax.plot(time, data[cfg["col"]], color=cfg["color"], linewidth=0.9)

        if name == "ball_height" and target is not None:
            ax.axhline(
                target, color="gray", linestyle="--", linewidth=0.8, label=f"target = {target} m"
            )
            label_parts = [f"target = {target} m"]
            if rmse is not None:
                label_parts.append(f"RMSE = {rmse:.4f} m")
            if ss_rmse is not None:
                label_parts.append(f"SS RMSE = {ss_rmse:.4f} m")
            ax.legend(labels=label_parts, fontsize=8, loc="upper right")

        xlabel = "Time (s)" if i == 2 else ""
        _apply_common_style(ax, xlabel, cfg["ylabel"], "")
        ax.set_ylabel(cfg["ylabel"], fontsize=10)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    path = plots_dir / "combined.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [plot] {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("Ball Simulation — Demonstration Scenarios")

    for scenario in SCENARIOS:
        out_dir = run_scenario(scenario)

        csv_path = out_dir / "scenario_results.csv"
        if not csv_path.exists():
            print(f"  [SKIP] No CSV found for {scenario['id']} — did main.py run correctly?")
            continue

        data = load_csv(csv_path)
        plot_individual(data, out_dir, scenario["label"])
        plot_combined(data, out_dir, scenario["label"])

    print(f"\n{'─' * 60}")
    print("  All scenarios complete. Plots saved to scenarios/<name>/plots/")
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()
