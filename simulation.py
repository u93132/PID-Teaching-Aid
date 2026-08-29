# -*- coding: utf-8 -*-
# Pure computation layer: PID simulation and performance metrics.
# No GUI dependency, so tests/ can drive it headlessly.
import numpy as np
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class SimResult:
    t: np.ndarray   # time axis (s)
    y: np.ndarray   # mass position (m)
    u: np.ndarray   # control force (N)


@dataclass(slots=True, kw_only=True)
class Metrics:
    converged: bool             # settled inside the band within the run
    settling_time: float        # last time |y - target| left the band
    steady_error: float | None  # |target - y[-1]|, None when not converged
    rise_time: float | None     # 10% -> 90% duration, None when not reached
    t10: float | None
    t90: float | None
    overshoot_pct: float
    peak_val: float
    peak_time: float


def pid_control(error, integral_e, derivative_e, *, kp, ki, kd):
    # PID control law: force from the tracking error and its
    # accumulated / differentiated history
    return kp * error + ki * integral_e + kd * derivative_e


def plant_accel(x, v, u, *, m, c, k):
    # Equation of motion of the mass-spring-damper plant:
    #   m*x'' + c*x' + k*x = u   ->   x'' = (u - c*v - k*x) / m
    return (u - c * v - k * x) / m


def simulate(kp, ki, kd, *, m=1.0, c=0.5, k=2.0,
             target=1.0, t_total=16.0, dt=0.02):
    # Forward Euler: pid_control() closes the loop on the error,
    # plant_accel() answers with the plant's acceleration
    steps = int(t_total / dt) + 1
    t = np.linspace(0.0, t_total, steps)
    y = np.zeros(steps)
    u_out = np.zeros(steps)
    v = 0.0
    x = 0.0
    integral_e = 0.0
    prev_e = target   # error at t = 0
    for i in range(steps):
        error = target - x
        integral_e += error * dt
        derivative_e = (error - prev_e) / dt
        u = pid_control(error, integral_e, derivative_e,
                        kp=kp, ki=ki, kd=kd)
        u_out[i] = u
        a = plant_accel(x, v, u, m=m, c=c, k=k)
        v += a * dt
        x += v * dt
        y[i] = x
        prev_e = error
    return SimResult(t=t, y=y, u=u_out)


def analyze(t, y, *, target=1.0, band=0.05):
    # Settling time: walk back from the end to the last sample outside
    # the band; the run converged only when the final sample is inside
    converged = False
    settling_time = 0.0
    for i in range(len(y) - 1, -1, -1):
        if abs(y[i] - target) > band:
            settling_time = t[i]
            converged = (i != len(y) - 1)
            break
    else:
        # Every sample already inside the band
        converged = True
    steady_error = abs(target - y[-1]) if converged else None

    # Rise time: first crossings of 10% and 90% of the target
    idx10 = np.where(y >= 0.1 * target)[0]
    idx90 = np.where(y >= 0.9 * target)[0]
    if len(idx10) > 0 and len(idx90) > 0:
        t10, t90 = t[idx10[0]], t[idx90[0]]
        rise_time = t90 - t10
    else:
        t10 = t90 = rise_time = None

    # Overshoot: a response that dies far below the target is treated
    # as no-overshoot instead of reporting a meaningless peak
    peak_idx = int(np.argmax(y))
    peak_val = float(y[peak_idx])
    peak_time = float(t[peak_idx])
    if y[-1] > target / 2:
        overshoot_pct = max(0.0, (peak_val - target) / target * 100.0)
    else:
        overshoot_pct = 0.0

    return Metrics(converged=converged, settling_time=settling_time,
                   steady_error=steady_error, rise_time=rise_time,
                   t10=t10, t90=t90, overshoot_pct=overshoot_pct,
                   peak_val=peak_val, peak_time=peak_time)
