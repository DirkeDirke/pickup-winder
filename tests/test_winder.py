"""Tests for hardware-independent winding calculations."""

import pytest

from winder import SpeedController, WinderState, servo_duty_cycle


def controller(**overrides):
    values = dict(
        target_rpm=60,
        startup_duty=20,
        minimum_duty=8,
        maximum_duty=60,
        ramp_per_second=10,
        kp=0.1,
        ki=0.02,
        filter_alpha=0.5,
        startup_grace=4,
        stall_revolutions=3,
        minimum_stall_timeout=3,
        maximum_stall_timeout=20,
        overspeed_ratio=1.5,
        overspeed_margin_rpm=20,
        minimum_pulse_interval=0.02,
    )
    values.update(overrides)
    return SpeedController(**values)


def test_default_geometry_uses_233_turns_per_layer():
    state = WinderState(7000, 14.8, 0.0635)
    assert state.turns_per_layer == 233


def test_traverse_reverses_at_layer_boundary():
    state = WinderState(7000, 14.8, 0.0635)
    state.add_turns(232)
    assert state.traverse_fraction == pytest.approx(232 / 233)
    state.add_turns(1)
    assert state.layer == 1
    assert state.traverse_fraction == 1.0
    state.add_turns(232)
    assert state.traverse_fraction == pytest.approx(1 / 233)


def test_turn_count_stops_at_target():
    state = WinderState(10, 1.0, 0.1)
    assert state.add_turns(12) == 10
    assert state.turns == 10
    assert state.complete


def test_servo_duty_cycle_for_standard_pulses():
    assert servo_duty_cycle(0.0, 50, 1000, 2000) == 3277
    assert servo_duty_cycle(1.0, 50, 1000, 2000) == 6554


def test_speed_is_calculated_from_pulse_period():
    control = controller()
    control.start(0.0)
    assert control.observe_pulse(1.0)
    assert control.observe_pulse(2.0)
    assert control.measured_rpm == pytest.approx(60.0)


def test_pi_controller_raises_duty_when_spindle_is_slow():
    control = controller(ramp_per_second=100)
    control.start(0.0)
    control.update(0.2)
    control.observe_pulse(1.0)
    control.observe_pulse(3.0)  # 30 RPM
    before = control.duty
    control.update(3.1)
    assert control.duty > before


def test_output_ramp_limits_startup_change():
    control = controller(ramp_per_second=8)
    control.start(0.0)
    assert control.update(0.5) == pytest.approx(4.0)


def test_missing_startup_pulse_stops_motor():
    control = controller(startup_grace=4)
    control.start(0.0)
    control.update(4.01)
    assert not control.running
    assert control.duty == 0
    assert control.fault == "stall"


def test_missing_running_pulse_uses_speed_scaled_timeout():
    control = controller(target_rpm=30)
    assert control.stall_timeout == pytest.approx(6.0)
    control.start(0.0)
    control.observe_pulse(1.0)
    control.update(7.01)
    assert control.fault == "stall"


def test_overspeed_stops_motor():
    control = controller()
    control.start(0.0)
    control.observe_pulse(1.0)
    control.observe_pulse(1.5)  # 120 RPM exceeds the 90 RPM limit
    control.update(1.51)
    assert not control.running
    assert control.fault == "overspeed"


def test_short_noise_pulse_is_rejected():
    control = controller()
    control.start(0.0)
    assert control.observe_pulse(1.0)
    assert not control.observe_pulse(1.01)
    assert control.measured_rpm is None
