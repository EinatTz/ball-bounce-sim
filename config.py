from dataclasses import dataclass

import yaml


@dataclass
class DynamicsConfig:
    initial_position: float
    initial_velocity: float
    gravity: float
    restitution: float
    bounce_gain: float
    rate_hz: float  # DYNAMICS_RATE_HZ


@dataclass
class ControllerConfig:
    kp: float
    ki: float
    kd: float
    target_height: float  # TARGET_HEIGHT
    tick_rate_hz: float  # CTRL_RATE_HZ
    paddle_min: float  # PADDLE_MIN
    paddle_max: float  # PADDLE_MAX


@dataclass
class SolverConfig:
    type: str  # SOLVER
    event_trigger: str  # EVENT_TRIGGER
    event_rate_hz: float  # EVENT_RATE_HZ
    bounce_position_threshold: float
    peak_velocity_threshold: float

""
@dataclass
class VisualizerConfig:
    target_height: float  # TARGET_HEIGHT
    paddle_min: float  # PADDLE_MIN
    paddle_max: float  # PADDLE_MAX


@dataclass
class SimConfig:
    num_ticks: int  # NUM_TICKS
    dynamics: DynamicsConfig
    controller: ControllerConfig
    solver: SolverConfig
    visualizer: VisualizerConfig


def load_config(path: str = "config.yaml") -> SimConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    return SimConfig(
        num_ticks=raw["num_ticks"],
        dynamics=DynamicsConfig(**raw["dynamics"]),
        controller=ControllerConfig(**raw["controller"]),
        solver=SolverConfig(**raw["solver"]),
        visualizer=VisualizerConfig(**raw["visualizer"]),
    )


CONFIG = load_config()
