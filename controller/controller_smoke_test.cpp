/*
 * controller_smoke_test.cpp
 *
 * Tiny standalone driver to confirm the controller library builds and
 * links correctly. NOT a unit test or an integration test for your
 * simulator — it just feeds the controller a hand-rolled sequence of
 * "ball" states and prints the resulting paddle commands.
 *
 * Build (alongside controller.cpp):
 *     g++ -std=c++17 -O2 controller.cpp controller_smoke_test.cpp \
 *         -o controller_smoke_test
 *
 * Expected behavior: the controller should output the midpoint of the
 * paddle range until the first synthetic peak (velocity crossing from
 * positive to negative), then start adjusting its command.
 */

#include "controller.h"

#include <cmath>
#include <cstdio>

int main() {
    ControllerConfig cfg;
    cfg.kp            = 0.5;
    cfg.ki            = 0.1;
    cfg.kd            = 0.05;
    cfg.target_height = 1.0;     // 1.0 m target peak.
    cfg.tick_rate_hz  = 100.0;   // 100 Hz tick rate -> dt = 0.01 s.
    cfg.paddle_min    = -0.2;
    cfg.paddle_max    =  0.2;

    ControllerState* ctrl = controller_create(&cfg);
    if (ctrl == nullptr) {
        std::fprintf(stderr, "controller_create failed\n");
        return 1;
    }

    // Simulate a parabolic ball trajectory: position peaks then descends,
    // which should trigger the controller's peak detection.
    const double dt    = 1.0 / cfg.tick_rate_hz;
    const double g     = 9.81;
    double       v     = 4.0;   // initial upward velocity (m/s)
    double       x     = 0.0;   // initial position (m)
    const int    steps = 1000;

    std::printf("%6s %10s %10s %10s %10s\n",
                "step", "t", "x", "v", "u");

    for (int i = 0; i < steps; ++i) {
        const double t = i * dt;

        v -= g * dt;
        x += v * dt;

        const double u = controller_tick(ctrl, x, v);

        if (i % 5 == 0 || i == steps - 1) {
            std::printf("%6d %10.4f %10.4f %10.4f %10.4f\n", i, t, x, v, u);
        }
    }

    const double peak = controller_last_peak(ctrl);
    if (std::isnan(peak)) {
        std::printf("\nNo peak detected during smoke test.\n");
    } else {
        std::printf("\nObserved peak: %.4f m (target %.4f m)\n",
                    peak, cfg.target_height);
    }

    controller_destroy(ctrl);
    return 0;
}
