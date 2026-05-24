/*
 * controller.h
 *
 * Bouncing-ball paddle controller. Provided for the simulator take-home
 * assignment. Candidates: do not modify this file or the implementation.
 *
 * The controller owns its own clock. Each call to controller_tick is
 * assumed to advance simulation time by exactly 1 / tick_rate_hz. The
 * controller uses that internal clock (not a caller-supplied time) to
 * compute the elapsed time between consecutive peak observations for
 * its PID integral and derivative terms.
 *
 * Consequence: controller_tick MUST be called at exactly the configured
 * tick_rate_hz. Calling at a different rate (including letting your
 * solver step past a controller tick without calling controller_tick at
 * that exact time) will desynchronize the internal clock from real
 * simulation time and produce incorrect PID behavior. Honoring the
 * tick-rate contract is the simulator's responsibility.
 *
 * The interface is exposed as plain C so it can be linked from C, C++,
 * Rust (via FFI), Python (via ctypes/cffi/pybind11), and similar.
 */

#ifndef CONTROLLER_H
#define CONTROLLER_H

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque handle. The simulator should treat this as a black box. */
typedef struct ControllerState ControllerState;

/* Configuration for a new controller instance. */
typedef struct {
    double kp;              /* Proportional gain on peak-height error.    */
    double ki;              /* Integral gain on peak-height error.        */
    double kd;              /* Derivative gain on peak-height error.      */
    double target_height;   /* Desired bounce peak height (meters).       */
    double tick_rate_hz;    /* Required rate at which controller_tick    *
                             * will be called. Must be > 0. The internal *
                             * clock advances by 1 / tick_rate_hz per    *
                             * call.                                      */
    double paddle_min;      /* Lower clamp on commanded paddle position. */
    double paddle_max;      /* Upper clamp on commanded paddle position. */
} ControllerConfig;

/*
 * Create a new controller instance.
 *
 * Returns NULL if cfg is NULL or contains invalid values (non-positive
 * tick_rate_hz, paddle_min >= paddle_max, NaN/Inf in any field).
 *
 * The caller owns the returned pointer and must release it with
 * controller_destroy().
 */
ControllerState* controller_create(const ControllerConfig* cfg);

/*
 * Destroy a controller instance. Safe to call with NULL.
 */
void controller_destroy(ControllerState* state);

/*
 * Reset internal state (integrator, peak tracker, last error, last
 * command, internal clock) to initial values. Configuration is
 * preserved.
 */
void controller_reset(ControllerState* state);

/*
 * Advance the controller by one tick and return the commanded paddle
 * position (meters).
 *
 *   ball_position : current ball vertical position (m)
 *   ball_velocity : current ball vertical velocity (m/s)
 *
 * MUST be called at exactly the configured tick_rate_hz. The internal
 * clock advances by 1 / tick_rate_hz on each call regardless of how
 * much real simulation time has elapsed.
 *
 * On the very first call after creation or reset, the controller has no
 * peak estimate yet and returns the midpoint of [paddle_min, paddle_max].
 *
 * If state is NULL, returns 0.0.
 */
double controller_tick(ControllerState* state,
                       double ball_position,
                       double ball_velocity);

/*
 * Inspect the most recent peak height the controller observed (m).
 * Returns NaN if no peak has been detected yet, or if state is NULL.
 * Useful for plotting / debugging from the simulator.
 */
double controller_last_peak(const ControllerState* state);

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif  /* CONTROLLER_H */
