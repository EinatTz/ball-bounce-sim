# Ball Simulation

A 1D physics simulation of a bouncing ball kept at a target height by a PID-controlled paddle. The ball launches upward, bounces off the paddle, and the controller adjusts the paddle position each tick to minimise height error.

Works on Windows, macOS, and Linux.

## Requirements

- Python 3.10 or newer — [download here](https://www.python.org/downloads/)
- Git — [download here](https://git-scm.com/downloads)

## Quickstart

```bash
git clone https://github.com/EinatTz/ball-bounce-sim.git
cd ball-bounce-sim
python setup.py
```

`setup.py` creates a virtual environment, installs dependencies, and runs the simulation. Results appear in the `output/` folder:

- `scenario_results.csv` — ball position, velocity, and paddle position at every tick
- `performance_metrics.json` — bounce peak RMSE, settling time, and tuning recommendations
- `runtime_log.json` — config snapshot and dependency versions used for the run

## Other commands

```bash
python setup.py scenarios   # run all four demonstration scenarios and save plots
python setup.py test        # run the full test suite
python setup.py lint        # run the linter
python setup.py clean       # remove the venv and output folder
```

## Demonstration scenarios

Running `python setup.py scenarios` executes four pre-configured runs and saves plots of ball height, velocity, and paddle command to `scenarios/<name>/plots/`:

| Scenario | Solver | Description |
|---|---|---|
| A | Fixed | Reasonable step size (300 Hz) — baseline behaviour |
| B | Fixed | Degraded step size (10 Hz) — visibly coarse results |
| C | Variable | Tight tolerances — high resolution near every bounce |
| D | Variable | Loose tolerances — reduced resolution, visible error |

Config files for each scenario are in `scenarios/<name>/config.yaml`.

## Configuration

All settings for the default run are in `config.yaml`. The most useful ones to experiment with:

| Setting | What it does |
|---|---|
| `num_ticks` | How long the simulation runs |
| `controller.target_height` | Target bounce height in metres |
| `controller.kp` | Proportional gain — higher means faster response |
| `dynamics.restitution` | Bounciness (0.0 = no bounce, 1.0 = perfectly elastic) |
| `solver.type` | `fixed` (default) or `variable` (higher accuracy near bounces) |

## Running Tests

```bash
python setup.py test
```

If a performance test fails, a recent change caused results to drift beyond the tolerance in `tests/baseline.json`. To accept new results as the reference after an intentional change:

```bash
venv/bin/python tests/generate_baseline.py       # macOS / Linux
venv\Scripts\python tests\generate_baseline.py   # Windows

git add tests/baseline.json
git commit -m "chore: update performance baseline"
```

## Project Structure

```
├── setup.py                 Cross-platform setup and run (Windows, macOS, Linux)
├── requirements.txt         Python dependencies
├── pyproject.toml           Linter configuration (ruff)
├── main.py                  Entry point — accepts --config <path>
├── run_scenarios.py         Runs all four scenarios and saves plots
├── config.yaml              Default simulation settings
├── config.py                Loads config.yaml into Python dataclasses
├── dynamics_module.py       Ball physics
├── controller_module.py     PID controller (wraps compiled C library)
├── controller.so            Compiled controller — Linux
├── controller.dylib         Compiled controller — macOS
├── controller.dll           Compiled controller — Windows
├── solver_module.py         Fixed and variable step solvers
├── output_module.py         Writes output files and computes metrics
├── visualizer_module.py     Real-time visualizer
├── .github/
│   └── workflows/
│       └── ci.yml           CI pipeline (runs on Windows, macOS, Linux)
├── scenarios/
│   ├── a_fixed_reasonable/  config.yaml (results and plots generated on run)
│   ├── b_fixed_degraded/
│   ├── c_variable_tight/
│   └── d_variable_loose/
├── tests/
│   ├── conftest.py
│   ├── test_unit.py
│   ├── test_performance.py
│   ├── baseline.json
│   └── generate_baseline.py
└── output/                  Created on first run (not committed)
```