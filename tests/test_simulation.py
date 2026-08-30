# -*- coding: utf-8 -*-
# Automated tests for the pure computation layer (simulation.py).
# Run from the repo root:  py -3 -m unittest discover tests
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from simulation import (simulate, simulate_theory, analyze,
                        pid_control, plant_accel)


class TestControlLaw(unittest.TestCase):
    def test_each_term_alone(self):
        # Each gain scales exactly its own error channel
        self.assertEqual(pid_control(2.0, 0.0, 0.0, kp=10, ki=0, kd=0), 20.0)
        self.assertEqual(pid_control(0.0, 3.0, 0.0, kp=0, ki=10, kd=0), 30.0)
        self.assertEqual(pid_control(0.0, 0.0, 4.0, kp=0, ki=0, kd=10), 40.0)

    def test_terms_sum(self):
        self.assertEqual(pid_control(1.0, 1.0, 1.0, kp=1, ki=2, kd=3), 6.0)


class TestPlant(unittest.TestCase):
    def test_rest_at_origin_with_force(self):
        # From rest at the origin only the applied force accelerates
        self.assertEqual(plant_accel(0.0, 0.0, 5.0, m=2.0, c=0.5, k=2.0),
                         2.5)

    def test_spring_and_damper_oppose_motion(self):
        # x = 1, v = 1, no force: a = -(c*v + k*x)/m
        self.assertEqual(plant_accel(1.0, 1.0, 0.0, m=1.0, c=0.5, k=2.0),
                         -2.5)

    def test_static_equilibrium(self):
        # The force that exactly balances the spring gives zero accel
        self.assertEqual(plant_accel(1.0, 0.0, 2.0, m=1.0, c=0.5, k=2.0),
                         0.0)


class TestSimulate(unittest.TestCase):
    def test_time_axis_and_shapes(self):
        res = simulate(20.0, 0.0, 0.0, t_total=16.0, dt=0.02)
        self.assertEqual(len(res.t), 801)
        self.assertEqual(len(res.y), 801)
        self.assertEqual(len(res.u), 801)
        self.assertEqual(res.t[0], 0.0)
        self.assertAlmostEqual(res.t[-1], 16.0)

    def test_zero_gains_no_motion(self):
        # No control force -> the mass never moves
        res = simulate(0.0, 0.0, 0.0)
        self.assertTrue(np.all(res.u == 0.0))
        self.assertTrue(np.all(res.y == 0.0))

    def test_p_only_steady_state(self):
        # P control balances the spring: x_ss = kp / (kp + k).
        # Heavy derivative damping keeps the run settled within 16 s
        res = simulate(60.0, 0.0, 8.0, k=2.0)
        self.assertAlmostEqual(res.y[-1], 60.0 / 62.0, delta=0.005)

    def test_integral_removes_offset(self):
        # An integral term drives the steady-state error to zero
        res = simulate(20.0, 10.0, 10.0)
        self.assertAlmostEqual(res.y[-1], 1.0, delta=0.02)

    def test_first_step_force_is_kp(self):
        # At t=0 the error is 1 and the derivative term is zero, so
        # the first output is kp*1 + ki*1*dt
        res = simulate(20.0, 0.0, 5.0, dt=0.02)
        self.assertAlmostEqual(res.u[0], 20.0, delta=1e-9)


class TestTheory(unittest.TestCase):
    # simulate_theory() is the continuous-time closed loop GC/(1+GC);
    # every check below compares against linear-system theory

    def test_p_only_matches_closed_form(self):
        # P control on the plant is a plain damped oscillator
        #   m*x'' + c*x' + (k+kp)*x = kp
        # whose step response has an exact closed form
        m, c, k, kp = 1.0, 0.5, 2.0, 20.0
        res = simulate_theory(kp, 0.0, 0.0, m=m, c=c, k=k)
        gain  = kp / (k + kp)
        sigma = c / (2 * m)
        omega = np.sqrt((k + kp) / m - sigma ** 2)
        exact = gain * (1 - np.exp(-sigma * res.t)
                        * (np.cos(omega * res.t)
                           + sigma / omega * np.sin(omega * res.t)))
        self.assertLess(np.max(np.abs(res.y - exact)), 1e-4)

    def test_p_only_final_value(self):
        # Final value theorem: T(0) = kp / (k + kp)
        res = simulate_theory(20.0, 0.0, 0.0, k=2.0)
        self.assertAlmostEqual(res.y[-1], 20.0 / 22.0, delta=0.03)

    def test_integral_final_values(self):
        # With ki > 0, T(0) = 1; the force then balances the spring
        res = simulate_theory(20.0, 10.0, 10.0, k=2.0)
        self.assertAlmostEqual(res.y[-1], 1.0, delta=0.01)
        self.assertAlmostEqual(res.u[-1], 2.0, delta=0.05)

    def test_derivative_kick(self):
        # The ideal D-term differentiates the reference step: the
        # impulse leaves v(0+) = kd/m, so u(0+) = kp - kd*(kd/m)
        kp, kd, m = 20.0, 10.0, 1.0
        res = simulate_theory(kp, 0.0, kd, m=m)
        self.assertAlmostEqual(res.u[0], kp - kd ** 2 / m, places=9)
        # ...and the position rises immediately (v0*dt scale),
        # unlike the discrete simulation whose difference quotient
        # sees no kick at step 0
        self.assertAlmostEqual(res.y[1], kd / m * 0.02, delta=0.05)
        euler = simulate(kp, 0.0, kd, m=m)
        self.assertLess(euler.y[1], res.y[1] / 2)

    def test_grid_matches_simulate(self):
        # Theory and simulation share the same time axis, so the
        # charts can overlay them directly
        res = simulate(20.0, 0.0, 0.0)
        thr = simulate_theory(20.0, 0.0, 0.0)
        self.assertEqual(len(thr.t), len(res.t))
        self.assertTrue(np.array_equal(thr.t, res.t))


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.t = np.linspace(0.0, 16.0, 801)
        self.dt = self.t[1] - self.t[0]

    def test_exponential_rise(self):
        # y = 1 - exp(-t): analytic rise time is ln(9),
        # the last sample outside the 5% band sits at ln(20)
        y = 1.0 - np.exp(-self.t)
        met = analyze(self.t, y)
        self.assertIsNotNone(met.rise_time)
        self.assertAlmostEqual(met.rise_time, np.log(9.0),
                               delta=2 * self.dt)
        self.assertTrue(met.converged)
        self.assertAlmostEqual(met.settling_time, np.log(20.0),
                               delta=2 * self.dt)
        self.assertAlmostEqual(met.steady_error, np.exp(-16.0), delta=1e-6)
        self.assertEqual(met.overshoot_pct, 0.0)

    def test_overshoot_decaying_peak(self):
        # Starts at 1.25 and decays onto the target: 25% overshoot,
        # settled once 0.25*exp(-t) drops below 0.05 (t = ln 5)
        y = 1.0 + 0.25 * np.exp(-self.t)
        met = analyze(self.t, y)
        self.assertAlmostEqual(met.overshoot_pct, 25.0, delta=0.01)
        self.assertAlmostEqual(met.peak_val, 1.25, delta=1e-9)
        self.assertEqual(met.peak_time, 0.0)
        self.assertTrue(met.converged)
        self.assertAlmostEqual(met.settling_time, np.log(5.0),
                               delta=2 * self.dt)

    def test_not_converged_ramp(self):
        # A ramp ending at 2.0 never settles: no steady error value,
        # but the peak still reports as overshoot
        y = np.linspace(0.0, 2.0, len(self.t))
        met = analyze(self.t, y)
        self.assertFalse(met.converged)
        self.assertIsNone(met.steady_error)
        self.assertAlmostEqual(met.overshoot_pct, 100.0, delta=0.01)

    def test_low_final_value_suppresses_overshoot(self):
        # A response dying far below the target reports no overshoot
        # and no rise time
        y = np.full(len(self.t), 0.2)
        met = analyze(self.t, y)
        self.assertEqual(met.overshoot_pct, 0.0)
        self.assertIsNone(met.rise_time)
        self.assertFalse(met.converged)

    def test_all_samples_in_band(self):
        # Already on target the whole run: settled from t = 0
        y = np.ones(len(self.t))
        met = analyze(self.t, y)
        self.assertTrue(met.converged)
        self.assertEqual(met.settling_time, 0.0)
        self.assertEqual(met.steady_error, 0.0)


if __name__ == '__main__':
    unittest.main()
