import argparse
import math

from config import load_config
from controller_module import ControllerModule
from dynamics_module import DynamicsModule
from output_module import OutputModule
from solver_module import FixedStepSolver, VariableStepSolver
from visualizer_module import Visualizer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ball bounce simulation")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML file (default: config.yaml)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    dcfg = cfg.dynamics
    ccfg = cfg.controller
    scfg = cfg.solver
    vcfg = cfg.visualizer

    dynamics = DynamicsModule(
        initial_position=dcfg.initial_position,
        initial_velocity=dcfg.initial_velocity,
        gravity=dcfg.gravity,
        restitution=dcfg.restitution,
        bounce_gain=dcfg.bounce_gain,
        paddle_min=ccfg.paddle_min,
        rate_hz=dcfg.rate_hz,
    )

    ctrl = ControllerModule(
        kp=ccfg.kp,
        ki=ccfg.ki,
        kd=ccfg.kd,
        target_height=ccfg.target_height,
        tick_rate_hz=ccfg.tick_rate_hz,
        paddle_min=ccfg.paddle_min,
        paddle_max=ccfg.paddle_max,
    )

    viz = Visualizer(
        target_height=vcfg.target_height,
        paddle_min=ccfg.paddle_min,
        paddle_max=ccfg.paddle_max,
    )

    out = OutputModule(cfg)

    # ── Select solver ─────────────────────────────────────────────────────────
    if scfg.type == "fixed":
        solver = FixedStepSolver(
            dynamics, ctrl, dynamics_rate_hz=dcfg.rate_hz, ctrl_rate_hz=ccfg.tick_rate_hz
        )
    elif scfg.type == "variable":
        solver = VariableStepSolver(
            dynamics,
            ctrl,
            dynamics_rate_hz=dcfg.rate_hz,
            ctrl_rate_hz=ccfg.tick_rate_hz,
            event_trigger=scfg.event_trigger,
            event_rate_hz=scfg.event_rate_hz,
            bounce_position_threshold=scfg.bounce_position_threshold,
            peak_velocity_threshold=scfg.peak_velocity_threshold,
        )
    else:
        raise ValueError(f"Unknown solver: '{scfg.type}'. Use 'fixed' or 'variable'.")

    # ── Simulation loop ───────────────────────────────────────────────────────
    sim_time = 0.0

    for tick in range(cfg.num_ticks):
        if scfg.type == "variable":
            ball_position, ball_velocity, paddle, event, current_dt = solver.step()
        else:
            ball_position, ball_velocity, paddle = solver.step()
            event = "none"
            current_dt = 1.0 / ccfg.tick_rate_hz

        sim_time += current_dt
        peak = ctrl.last_peak()
        peak_str = f"{peak:.4f}" if not math.isnan(peak) else "N/A"

        """print(
            f"tick {tick:04d} | "
            f"ball_pos={ball_position:.4f} | "
            f"ball_vel={ball_velocity:.4f} | "
            f"paddle={paddle:.4f} | "
            f"last_peak={peak_str} | "
            f"event={event} | "
            f"current_dt={current_dt}"
        )"""

       #viz.update(ball_position, ball_velocity, paddle, current_dt)

        out.record(
            tick=tick,
            sim_time=sim_time,
            ball_position=ball_position,
            ball_velocity=ball_velocity,
            paddle=paddle,
            last_peak=peak,
            event=event,
            step_dt=current_dt,
        )

    # ── Output ────────────────────────────────────────────────────────────────
    metrics = out.finish()

    print("\n── Performance Summary ───────────────────────────────────────────────")
    print(f"  Bounce peaks detected : {metrics['num_peaks_detected']}")
    rmse = metrics["rmse_m"]
    ss = metrics["steady_state_rmse_m"]
    print(f"  Peak RMSE (all)       : {rmse:.4f} m" if rmse is not None else "  Peak RMSE: N/A")
    print(
        f"  Peak RMSE (steady-state): {ss:.4f} m" if ss is not None else "  Steady-state RMSE: N/A"
    )
    st = metrics["settling_time_s"]
    print(
        f"  Settling time         : {st:.3f} s"
        if st is not None
        else "  Settling time: did not settle"
    )
    print(f"  Throughput            : {metrics['ticks_per_second']:.0f} ticks/s")
    opt = metrics["optimization"]
    print(f"  Optimization status   : {opt['status']}")
    for action in opt.get("actions", []):
        print(f"    → {action}")
    print("─────────────────────────────────────────────────────────────────────")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    #viz.show_final()
    ctrl.destroy()
    viz.destroy()
