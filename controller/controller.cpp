/*
 * controller.cpp
 *
 * Implementation of the paddle controller declared in controller.h.
 *
 * Strategy: detect bounce peaks from the ball's velocity sign change
 * (positive -> negative), then run a PID on the error between the most
 * recently observed peak height and the configured target. The PID dt
 * is the elapsed time between consecutive peak detections, derived
 * from an internal clock that advances by 1 / tick_rate_hz on each
 * call to controller_tick. The output is a commanded paddle position,
 * clamped to the configured limits.
 *
 * Because the controller owns its clock, calling it at a rate other
 * than tick_rate_hz will desynchronize the internal time from real
 * simulation time and produce incorrect PID behavior. Honoring the
 * tick-rate contract is the simulator's responsibility.
 */

#include "controller.h"

#include <cmath>
#include <cstddef>
#include <limits>
#include <new>

namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

bool is_finite(double x) {
    return std::isfinite(x);
}

bool config_valid(const ControllerConfig& c) {
    if (!is_finite(c.kp) || !is_finite(c.ki) || !is_finite(c.kd)) return false;
    if (!is_finite(c.target_height)) return false;
    if (!is_finite(c.tick_rate_hz) || c.tick_rate_hz <= 0.0) return false;
    if (!is_finite(c.paddle_min) || !is_finite(c.paddle_max)) return false;
    if (c.paddle_min >= c.paddle_max) return false;
    return true;
}

double clamp(double x, double lo, double hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

}  // namespace

struct ControllerState {
    ControllerConfig cfg;
    double dt;                 // 1 / tick_rate_hz, cached.
    double current_t;          // Internal clock, advances by dt each call.

    // Peak detection state.
    double prev_velocity;
    bool   has_prev_velocity;
    double last_peak;
    bool   has_peak;

    // PID state. prev_peak_t holds the internal-clock time of the
    // previous peak so we can compute the actual elapsed time between
    // peak observations.
    double integral;
    double prev_error;
    bool   has_prev_error;
    double prev_peak_t;
    bool   has_prev_peak_t;
    double last_command;
};

static void reset_runtime(ControllerState* s) {
    s->current_t         = 0.0;

    s->prev_velocity     = 0.0;
    s->has_prev_velocity = false;
    s->last_peak         = kNaN;
    s->has_peak          = false;

    s->integral          = 0.0;
    s->prev_error        = 0.0;
    s->has_prev_error    = false;
    s->prev_peak_t       = 0.0;
    s->has_prev_peak_t   = false;

    s->last_command      = 0.5 * (s->cfg.paddle_min + s->cfg.paddle_max);
}

extern "C" ControllerState* controller_create(const ControllerConfig* cfg) {
    if (cfg == nullptr) return nullptr;
    if (!config_valid(*cfg)) return nullptr;

    ControllerState* s = new (std::nothrow) ControllerState();
    if (s == nullptr) return nullptr;

    s->cfg = *cfg;
    s->dt  = 1.0 / cfg->tick_rate_hz;
    reset_runtime(s);
    return s;
}

extern "C" void controller_destroy(ControllerState* state) {
    delete state;
}

extern "C" void controller_reset(ControllerState* state) {
    if (state == nullptr) return;
    reset_runtime(state);
}

extern "C" double controller_tick(ControllerState* state,
                                  double ball_position,
                                  double ball_velocity) {
    if (state == nullptr) return 0.0;

    if (state->has_prev_velocity &&
        state->prev_velocity > 0.0 &&
        ball_velocity <= 0.0) {
        state->last_peak = ball_position;
        state->has_peak  = true;

        const double error = state->cfg.target_height - state->last_peak;

        // Use elapsed internal-clock time between this and the previous
        // peak. On the first peak we have no reference, so I and D
        // contribute nothing this tick.
        double peak_dt = 0.0;
        const bool have_peak_dt =
            state->has_prev_peak_t && (state->current_t > state->prev_peak_t);
        if (have_peak_dt) {
            peak_dt = state->current_t - state->prev_peak_t;
            state->integral += error * peak_dt;
        }

        double derivative = 0.0;
        if (state->has_prev_error && have_peak_dt) {
            derivative = (error - state->prev_error) / peak_dt;
        }

        const double u = state->cfg.kp * error +
                         state->cfg.ki * state->integral +
                         state->cfg.kd * derivative;

        const double midpoint =
            0.5 * (state->cfg.paddle_min + state->cfg.paddle_max);

        state->last_command =
            clamp(midpoint + u, state->cfg.paddle_min, state->cfg.paddle_max);

        state->prev_error     = error;
        state->has_prev_error = true;
        state->prev_peak_t    = state->current_t;
        state->has_prev_peak_t = true;
    }

    state->prev_velocity     = ball_velocity;
    state->has_prev_velocity = true;

    // Advance the internal clock by one tick.
    state->current_t += state->dt;

    return state->last_command;
}

extern "C" double controller_last_peak(const ControllerState* state) {
    if (state == nullptr) return kNaN;
    if (!state->has_peak)  return kNaN;
    return state->last_peak;
}
