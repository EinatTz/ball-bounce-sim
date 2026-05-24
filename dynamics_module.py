class DynamicsModule:
    def __init__(
        self,
        initial_position: float = 1.0,
        initial_velocity: float = 0.0,
        gravity: float = 9.81,
        restitution: float = 0.8,
        bounce_gain: float = 10.0,
        paddle_min: float = -1.0,
        rate_hz: float = 100.0,
    ):
        """
        Simulate ball physics in 1D vertical motion.

        initial_position : starting height (m)
        initial_velocity : starting vertical velocity (m/s)
        gravity          : gravitational acceleration (m/s²), positive value
        restitution      : coefficient of restitution e (0-1), energy lost on bounce
        bounce_gain      : k (1/s), upward velocity kick from paddle position
        paddle_min       : lower clamp on paddle position, must match controller config
        rate_hz          : The rate at which DynamicsModule step will be called
        """

        """Initialize ball state."""
        self._dt = 1.0 / rate_hz
        self._g = gravity
        self._e = restitution
        self._k = bounce_gain
        self._paddle_min = paddle_min
        self._position = initial_position
        self._velocity = initial_velocity

    def step(self, paddle_position: float, step_dt: float) -> tuple[float, float]:
        """
        Advance ball physics by one tick (step_dt s).

        paddle_position : current paddle height from the controller (m)

        Returns (ball_position, ball_velocity).
        """
        # ── Free flight: ẍ = -g ───────────────────────────────────────────────
        self._velocity -= self._g * step_dt
        self._position += self._velocity * step_dt

        # ── Impact with paddle: x ≤ x_paddle and ẋ < 0 ───────────────────────
        if self._position <= paddle_position and self._velocity < 0:
            self._position = paddle_position

            self._velocity = -self._e * self._velocity + self._k * (
                paddle_position - self._paddle_min
            )

        return self._position, self._velocity

    def reset(self, initial_position: float = 1.0, initial_velocity: float = 0.0):
        """Reset ball state."""
        self._position = initial_position
        self._velocity = initial_velocity

