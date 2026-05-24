# Ball Simulation

A 1D physics simulation of a bouncing ball kept at a target height by a PID-controlled paddle. The ball launches upward, bounces off the paddle, and the controller adjusts the paddle position each tick to minimise height error.

## Requirements

- Python 3.10 or newer — [download here](https://www.python.org/downloads/)
- Git — [download here](https://git-scm.com/downloads)
- `make` — pre-installed on macOS and Linux; Windows users can install via [Chocolatey](https://chocolatey.org/): `choco install make`

## Quickstart

```bash
git clone https://github.com/EinatTz/ball-bounce-sim.git
cd ball-bounce-sim
make
```

That's it. `make` creates a virtual environment, installs dependencies, and runs the simulation. Results appear in the `output/` folder:

- `scenario_results.csv` — ball position, velocity, and paddle position at every tick
- `performance_metrics.json` — bounce peak RMSE, settling time, and tuning recommendations
- `runtime_log.json` — config snapshot and dependency versions used for the run

## Other commands

```bash
make test    # run the full test suite
make lint    # run the linter
make clean   # remove the venv and output folder
```

## Configuration

All settings are in `config.yaml`. The most useful ones to experiment with:

| Setting | What it does |
|---|---|
| `num_ticks` | How long the simulation runs |
| `controller.target_height` | Target bounce height in metres |
| `controller.kp` | Proportional gain — higher means faster response |
| `dynamics.restitution` | Bounciness (0.0 = no bounce, 1.0 = perfectly elastic) |
| `solver.type` | `fixed` (default) or `variable` (higher accuracy near bounces) |

## Running Tests

```bash
make test
```

If a performance test fails, a recent change caused results to drift beyond the tolerance in `tests/baseline.json`. To accept new results as the reference after an intentional change:

```bash
venv/bin/python tests/generate_baseline.py
git add tests/baseline.json
git commit -m "chore: update performance baseline"
```

## Project Structure

```
├── Makefile                 One-command setup and run
├── requirements.txt         Python dependencies
├── main.py                  Entry point
├── config.yaml              All simulation settings
├── dynamics_module.py       Ball physics
├── controller_module.py     PID controller (wraps compiled C library)
├── solver_module.py         Fixed and variable step solvers
├── output_module.py         Writes output files and computes metrics
├── tests/
│   ├── test_unit.py
│   ├── test_performance.py
│   ├── baseline.json
│   └── generate_baseline.py
└── output/                  Created on first run
```
