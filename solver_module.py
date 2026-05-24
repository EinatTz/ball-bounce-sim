from controller_module import ControllerModule
from dynamics_module import DynamicsModule


class FixedStepSolver:
    def __init__(
        self,
        dynamics: DynamicsModule,
        ctrl: ControllerModule,
        dynamics_rate_hz: float,
        ctrl_rate_hz: float,
    ):
        """
        Fixed step solver — advances time in equal steps of 1/dynamics_rate_hz.
        Stops exactly at controller ticks to invoke the controller.

        dynamics          : DynamicsModule instance
        ctrl              : ControllerModule instance
        dynamics_rate_hz  : dynamics simulation rate (Hz)
        ctrl_rate_hz      : controller tick rate (Hz)
        """
        self._dynamics = dynamics
        self._ctrl = ctrl
        self._dynamics_dt = 1.0 / dynamics_rate_hz
        self._ctrl_dt = 1.0 / ctrl_rate_hz
        self._t = 0.0
        self._next_ctrl_t = 0.0
        self._paddle = 0.0

    def step(self) -> tuple[float, float, float]:
        """
        If a controller tick is due, advance one dynamics step (1/dynamics_rate_hz s) and
        invoke the controller.
        Else If the controller tick is due but the dynamics is not
        advance the dynamics one step (1/(next_ctrl_t-t) s)
        Else advance one dynamics step (1/dynamics_rate_hz s).

        Returns (ball_position, ball_velocity, paddle_position).
        """

        # ── Controller tick due? ──────────────────────────────────────────────
        if self._t == self._next_ctrl_t:
            ball_position, ball_velocity = self._dynamics.step(self._paddle, self._dynamics_dt)
            self._paddle = self._ctrl.step(ball_position, ball_velocity)
            self._t += self._dynamics_dt
            self._next_ctrl_t += self._ctrl_dt
        elif self._next_ctrl_t - self._t < self._dynamics_dt:
            temp_dt = self._next_ctrl_t - self._t
            ball_position, ball_velocity = self._dynamics.step(self._paddle, temp_dt)
            self._paddle = self._ctrl.step(self._dynamics._position, self._dynamics._velocity)
            self._t += temp_dt
            self._next_ctrl_t += self._ctrl_dt
        else:
            ball_position, ball_velocity = self._dynamics.step(self._paddle, self._dynamics_dt)
            self._t += self._dynamics_dt

        return ball_position, ball_velocity, self._paddle

    def reset(self):
        self._t = 0.0
        self._next_ctrl_t = 0.0
        self._paddle = 0.0


class VariableStepSolver:
    def __init__(
        self,
        dynamics: DynamicsModule,
        ctrl: ControllerModule,
        dynamics_rate_hz: float,
        ctrl_rate_hz: float,
        event_trigger: str = "bounce",
        event_rate_hz: float = 1e-2,
        bounce_position_threshold: float = 0.05,
        peak_velocity_threshold: float = 0.8,
    ):
        """
        Variable step solver — adjusts DynamicsModule step size dynamically.
        Always stops exactly at controller ticks.

        dynamics            : DynamicsModule instance
        ctrl                : ControllerModule instance
        dynamics_rate_hz    : dynamics simulation rate (Hz)
        ctrl_rate_hz        : controller tick rate (Hz)
        event_trigger.      : which event causes step size to shrink:
                              "bounce" — shrink near paddle/floor impact
                              "peak"   — shrink near ball peak (velocity → 0)
        event_rate_hz       : dynamics rate during the event
        bounce_position_threshold
                            : m — how close to paddle counts as near-bounce
        peak_velocity_threshold
                            : m/s — how close to zero counts as near-peak
        """
        if event_trigger not in ("bounce", "peak"):
            raise ValueError(f"event_trigger must be 'bounce' or 'peak', got '{event_trigger}'")

        self._dynamics = dynamics
        self._ctrl = ctrl
        self._dynamics_dt = 1.0 / dynamics_rate_hz
        self._ctrl_dt = 1.0 / ctrl_rate_hz
        self._event_dt = 1.0 / event_rate_hz
        self._event_trigger = event_trigger
        self._t = 0.0
        self._next_ctrl_t = 0.0
        self._paddle = 0.0

        # ── Thresholds from config ────────────────────────────────────────────
        self._bounce_position_threshold = bounce_position_threshold
        self._peak_velocity_threshold = peak_velocity_threshold

    def _detect_event(self) -> str:
        """Detect only the configured event trigger."""
        pos = self._dynamics._position
        vel = self._dynamics._velocity

        if self._event_trigger == "bounce":
            near_paddle = (pos - self._paddle) < self._bounce_position_threshold
            if near_paddle:
                return "bounce"

        elif self._event_trigger == "peak":
            near_peak = (
                abs(vel) < self._peak_velocity_threshold
                and (pos - self._paddle) > self._bounce_position_threshold
            )
            if near_peak:
                return "peak"

        return "none"

    def step(self) -> tuple[float, float, float, str, float]:
        """
        Advance one dynamics step .
        If a controller tick is due, invoke the controller.

        Returns (ball_position, ball_velocity, paddle_position).
        """
        old_t = self._t
        # ── Detect event ──────────────────────────────────────────────────────
        self._event = self._detect_event()

        # ── Controller tick due? ──────────────────────────────────────────────
        if self._event == "bounce" or self._event == "peak":
            if self._t == self._next_ctrl_t:
                ball_position, ball_velocity = self._dynamics.step(self._paddle, self._event_dt)
                self._paddle = self._ctrl.step(self._dynamics._position, self._dynamics._velocity)
                self._t += self._event_dt
                self._next_ctrl_t += self._ctrl_dt

            elif self._next_ctrl_t - self._t < self._event_dt:
                temp_dt = self._next_ctrl_t - self._t
                ball_position, ball_velocity = self._dynamics.step(self._paddle, temp_dt)
                self._paddle = self._ctrl.step(self._dynamics._position, self._dynamics._velocity)
                self._t += temp_dt
                self._next_ctrl_t += self._ctrl_dt

            else:
                ball_position, ball_velocity = self._dynamics.step(self._paddle, self._event_dt)
                self._t += self._event_dt

        else:
            if self._t == self._next_ctrl_t:
                ball_position, ball_velocity = self._dynamics.step(self._paddle, self._dynamics_dt)
                self._paddle = self._ctrl.step(self._dynamics._position, self._dynamics._velocity)
                self._t += self._dynamics_dt
                self._next_ctrl_t += self._ctrl_dt

            elif self._next_ctrl_t - self._t < self._dynamics_dt:
                temp_dt = self._next_ctrl_t - self._t
                ball_position, ball_velocity = self._dynamics.step(self._paddle, temp_dt)
                self._paddle = self._ctrl.step(self._dynamics._position, self._dynamics._velocity)
                self._t += temp_dt
                self._next_ctrl_t += self._ctrl_dt
            else:
                ball_position, ball_velocity = self._dynamics.step(self._paddle, self._dynamics_dt)
                self._t += self._dynamics_dt

        return ball_position, ball_velocity, self._paddle, self._event, self._t - old_t

    def reset(self):
        self._t = 0.0
        self._next_ctrl_t = 0.0
        self._paddle = 0.0
        self._event = "none"
