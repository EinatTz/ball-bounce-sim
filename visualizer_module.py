import matplotlib
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np


def _ensure_gui_backend() -> bool:
    """
    Try to switch to an interactive backend if the current one is non-GUI.
    Returns True if a GUI backend is active, False if falling back to headless.

    Priority order:
      Windows/macOS : TkAgg  (ships with most Python installs)
      Linux         : TkAgg → Qt5Agg → Qt6Agg → wxAgg
    Headless fallback: Agg (no window — show_final() saves a PNG instead).
    """
    current = matplotlib.get_backend().lower()
    # Already interactive
    if current not in ("agg", "pdf", "ps", "svg", "cairo"):
        return True

    gui_candidates = ["TkAgg", "Qt5Agg", "Qt6Agg", "wxAgg", "GTK3Agg"]
    for backend in gui_candidates:
        try:
            matplotlib.use(backend)
            import matplotlib.pyplot as _plt  # re-import after switch

            _plt.figure()  # test that a window can open
            _plt.close("all")
            return True
        except Exception:
            continue

    # Nothing worked — stay with Agg (headless)
    matplotlib.use("Agg")
    return False


_GUI_AVAILABLE = _ensure_gui_backend()


class Visualizer:
    def __init__(self, target_height: float, paddle_min: float, paddle_max: float):
        self._target_height = target_height
        self._paddle_min = paddle_min
        self._paddle_max = paddle_max
        self._gui = _GUI_AVAILABLE

        self._times = []
        self._positions = []
        self._velocities = []
        self._paddles = []
        self._t = 0.0
        self._trail = []

        if not self._gui:
            print(
                "[visualizer] No GUI backend available — live animation disabled. "
                "Final plot will be saved to output/final_plot.png"
            )

        # ── Figure ────────────────────────────────────────────────────────────
        plt.style.use("dark_background")
        self._fig = plt.figure(figsize=(14, 7))
        self._fig.patch.set_facecolor("#0d0d0d")

        # ── Left: animation panel ─────────────────────────────────────────────
        self._ax = self._fig.add_axes([0.03, 0.05, 0.30, 0.90])
        self._ax.set_facecolor("#111111")
        self._ax.set_xlim(0, 1)
        self._ax.set_ylim(-0.1, 3.2)
        self._ax.set_xticks([])
        self._ax.set_yticks(np.arange(0, 3.5, 0.5))
        self._ax.tick_params(colors="gray")
        self._ax.set_ylabel("Height (m)", color="white", fontsize=11)
        self._ax.set_title("Live Simulation", color="white", fontsize=13, pad=10)

        # Walls
        self._ax.axvline(0.02, color="#444444", linewidth=2)
        self._ax.axvline(0.98, color="#444444", linewidth=2)

        # Floor
        self._ax.fill_between([0, 1], -0.1, 0, color="#333333")
        self._ax.axhline(0, color="#888888", linewidth=1.5)

        # Target height line
        self._ax.axhline(
            target_height,
            color="#00ff88",
            linestyle="--",
            linewidth=1.2,
            alpha=0.7,
            label=f"Target {target_height}m",
        )
        self._ax.legend(
            loc="upper right",
            fontsize=8,
            facecolor="#222222",
            edgecolor="#444444",
            labelcolor="white",
        )

        # Grid
        self._ax.yaxis.grid(True, color="#222222", linewidth=0.8)
        self._ax.set_axisbelow(True)

        # Paddle
        self._paddle_patch = patches.FancyBboxPatch(
            (0.15, 0),
            0.70,
            0.04,
            boxstyle="round,pad=0.01",
            linewidth=2,
            edgecolor="#ff4444",
            facecolor="#ff224488",
        )
        self._ax.add_patch(self._paddle_patch)

        # Ball trail
        self._trail_dots = [
            self._ax.plot(
                [], [], "o", markersize=6 - i * 0.5, color="#44aaff", alpha=0.15 + i * 0.07
            )[0]
            for i in range(8)
        ]

        # Ball glow and ball
        (self._ball_glow,) = self._ax.plot([], [], "o", markersize=28, color="#44aaff", alpha=0.15)
        (self._ball,) = self._ax.plot(
            [],
            [],
            "o",
            markersize=18,
            color="#44aaff",
            markeredgecolor="white",
            markeredgewidth=1.5,
        )

        # Speed text
        self._speed_text = self._ax.text(
            0.5,
            3.0,
            "",
            ha="center",
            va="top",
            color="#aaaaaa",
            fontsize=9,
            transform=self._ax.transData,
        )

        # ── Right: graphs ─────────────────────────────────────────────────────
        gs = self._fig.add_gridspec(
            3,
            1,
            left=0.40,
            right=0.97,
            top=0.93,
            bottom=0.08,
            hspace=0.45,
        )

        # Position
        self._ax_pos = self._fig.add_subplot(gs[0])
        self._ax_pos.set_facecolor("#111111")
        self._ax_pos.set_title("Ball Height", color="white", fontsize=10)
        self._ax_pos.set_ylabel("m", color="#aaaaaa", fontsize=9)
        self._ax_pos.axhline(
            target_height, color="#00ff88", linestyle="--", linewidth=0.9, alpha=0.7
        )
        self._ax_pos.tick_params(colors="gray", labelsize=8)
        self._ax_pos.yaxis.grid(True, color="#222222")
        (self._line_pos,) = self._ax_pos.plot([], [], color="#44aaff", linewidth=1.2)

        # Velocity
        self._ax_vel = self._fig.add_subplot(gs[1])
        self._ax_vel.set_facecolor("#111111")
        self._ax_vel.set_title("Ball Velocity", color="white", fontsize=10)
        self._ax_vel.set_ylabel("m/s", color="#aaaaaa", fontsize=9)
        self._ax_vel.axhline(0, color="#555555", linestyle="--", linewidth=0.8)
        self._ax_vel.tick_params(colors="gray", labelsize=8)
        self._ax_vel.yaxis.grid(True, color="#222222")
        (self._line_vel,) = self._ax_vel.plot([], [], color="#ffaa00", linewidth=1.2)

        # Paddle
        self._ax_pad = self._fig.add_subplot(gs[2])
        self._ax_pad.set_facecolor("#111111")
        self._ax_pad.set_title("Paddle Position", color="white", fontsize=10)
        self._ax_pad.set_ylabel("m", color="#aaaaaa", fontsize=9)
        self._ax_pad.set_xlabel("Time (s)", color="#aaaaaa", fontsize=9)
        self._ax_pad.tick_params(colors="gray", labelsize=8)
        self._ax_pad.yaxis.grid(True, color="#222222")
        (self._line_pad,) = self._ax_pad.plot([], [], color="#ff4444", linewidth=1.2)

        for ax in [self._ax_pos, self._ax_vel, self._ax_pad]:
            for spine in ax.spines.values():
                spine.set_edgecolor("#333333")

        if self._gui:
            plt.ion()
            plt.show()

    def update(self, ball_position: float, ball_velocity: float, paddle_position: float, dt: float):
        """Call every controller tick."""
        self._t += dt
        self._times.append(self._t)
        self._positions.append(ball_position)
        self._velocities.append(ball_velocity)
        self._paddles.append(paddle_position)

        # ── Ball trail ────────────────────────────────────────────────────────
        self._trail.append(ball_position)
        if len(self._trail) > 8:
            self._trail.pop(0)
        for i, dot in enumerate(self._trail_dots):
            if i < len(self._trail):
                dot.set_data([0.5], [self._trail[i]])

        # ── Ball & glow ───────────────────────────────────────────────────────
        self._ball.set_data([0.5], [ball_position])
        self._ball_glow.set_data([0.5], [ball_position])

        # Color ball by speed
        speed = abs(ball_velocity)
        r = min(1.0, speed / 10.0)
        self._ball.set_color((r, 0.4 + (1 - r) * 0.4, 1.0 - r * 0.6))

        # ── Paddle ────────────────────────────────────────────────────────────
        self._paddle_patch.set_y(paddle_position - 0.02)

        # ── Speed label ───────────────────────────────────────────────────────
        self._speed_text.set_text(f"v = {ball_velocity:+.2f} m/s")
        self._speed_text.set_y(min(ball_position + 0.15, 3.0))

        # ── Graphs ────────────────────────────────────────────────────────────
        t = self._times
        window = max(0, self._t - 10)

        self._line_pos.set_data(t, self._positions)
        self._ax_pos.set_xlim(window, self._t + 0.1)
        self._ax_pos.set_ylim(-0.1, 3.2)

        self._line_vel.set_data(t, self._velocities)
        self._ax_vel.set_xlim(window, self._t + 0.1)
        v_range = max(abs(v) for v in self._velocities[-100:]) + 1
        self._ax_vel.set_ylim(-v_range, v_range)

        self._line_pad.set_data(t, self._paddles)
        self._ax_pad.set_xlim(window, self._t + 0.1)
        self._ax_pad.set_ylim(self._paddle_min - 0.1, self._paddle_max + 0.1)

        if self._gui:
            plt.pause(0.001)

    def show_final(self):
        if self._gui:
            plt.ioff()
            plt.show()
        else:
            # Headless: save to output/ instead
            from pathlib import Path

            out_dir = Path("output")
            out_dir.mkdir(parents=True, exist_ok=True)
            save_path = out_dir / "final_plot.png"
            self._fig.savefig(
                save_path, dpi=150, bbox_inches="tight", facecolor=self._fig.get_facecolor()
            )
            print(f"[visualizer] Final plot saved → {save_path}")

    def destroy(self):
        plt.close(self._fig)
