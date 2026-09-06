"""Tests for hardware-independent winding calculations."""

import pytest

from winder import (
    SpeedController,
    WinderState,
    coalesce_counter_edges,
    motor_throttle,
    servo_sweep_degrees,
    servo_duty_cycle,
)


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
        pulses_per_revolution=1,
        open_loop=False,
        fixed_duty=15,
        debug_overspeed_rpm=300,
        startup_kick_duty=0,
        startup_kick_seconds=0,
        overspeed_confirmations=1,
        ramp_down_per_second=None,
    )
    values.update(overrides)
    return SpeedController(**values)


def test_noisy_counter_batch_is_one_candidate_pulse():
    assert coalesce_counter_edges(0) == 0
    assert coalesce_counter_edges(1) == 1
    assert coalesce_counter_edges(14) == 1


def test_negative_counter_batch_is_invalid():
    with pytest.raises(ValueError, match="negative"):
        coalesce_counter_edges(-1)


def test_servo_sweep_matches_pickup_geometry():
    assert servo_sweep_degrees(14.8, 15.0) == pytest.approx(59.12, abs=0.01)


def test_servo_sweep_rejects_impossible_travel():
    with pytest.raises(ValueError, match="diameter"):
        servo_sweep_degrees(31, 15)


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


def test_six_sensor_pulses_complete_one_winding():
    state = WinderState(7000, 14.8, 0.0635, pulses_per_revolution=6)
    assert state.add_pulses(5) == 0
    assert state.turns == 0
    assert state.pending_pulses == 5
    assert state.add_pulses(1) == 1
    assert state.turns == 1
    assert state.pending_pulses == 0


def test_pulse_batches_preserve_partial_revolution():
    state = WinderState(7000, 14.8, 0.0635, pulses_per_revolution=6)
    assert state.add_pulses(14) == 2
    assert state.turns == 2
    assert state.pending_pulses == 2


def test_servo_duty_cycle_for_standard_pulses():
    assert servo_duty_cycle(0.0, 50, 1000, 2000) == 3277
    assert servo_duty_cycle(1.0, 50, 1000, 2000) == 6554


def test_motor_throttle_converts_percent_and_stops_safely():
    assert motor_throttle(20, True) == pytest.approx(0.2)
    assert motor_throttle(60, True) == pytest.approx(0.6)
    assert motor_throttle(60, False) == 0.0


def test_motor_throttle_never_requests_reverse_or_overdrive():
    assert motor_throttle(-10, True) == 0.0
    assert motor_throttle(120, True) == 1.0


def test_speed_is_calculated_from_pulse_period():
    control = controller()
    control.start(0.0)
    assert control.observe_pulse(1.0)
    assert control.observe_pulse(2.0)
    assert control.measured_rpm == pytest.approx(60.0)


def test_speed_uses_configured_pulses_per_revolution():
    control = controller(pulses_per_revolution=6)
    control.start(0.0)
    control.observe_pulse(1.0)
    for pulse_number in range(1, 7):
        control.observe_pulse(1.0 + pulse_number * 0.5)
    assert control.measured_rpm == pytest.approx(20.0)


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


def test_downward_correction_uses_faster_ramp():
    control = controller(
        startup_duty=50,
        minimum_duty=10,
        maximum_duty=100,
        ramp_per_second=8,
        ramp_down_per_second=60,
    )
    control.start(0.0)
    control.duty = 60.0
    assert control.update(0.1) == pytest.approx(54.0)


def test_closed_loop_startup_kick_is_separate_from_baseline():
    control = controller(
        startup_duty=50,
        minimum_duty=45,
        maximum_duty=100,
        startup_kick_duty=60,
        startup_kick_seconds=0.5,
    )
    control.start(10.0)
    assert control.update(10.1) == pytest.approx(60.0)
    assert control.update(10.49) == pytest.approx(60.0)
    assert control.update(10.5) < 60.0


def test_debug_mode_bypasses_startup_kick():
    control = controller(
        open_loop=True,
        fixed_duty=25,
        startup_kick_duty=60,
        startup_kick_seconds=0.5,
    )
    control.start(0.0)
    assert control.update(0.1) == pytest.approx(25.0)


def test_debug_mode_holds_fixed_duty_while_measuring_rpm():
    control = controller(open_loop=True, fixed_duty=25, pulses_per_revolution=6)
    control.start(0.0)
    assert control.update(0.1) == pytest.approx(25.0)
    control.observe_pulse(1.0)
    for pulse_number in range(1, 7):
        control.observe_pulse(1.0 + pulse_number * 0.2)
    assert control.measured_rpm == pytest.approx(50.0)
    assert control.update(2.21) == pytest.approx(25.0)


def test_debug_fixed_duty_can_change_while_running():
    control = controller(open_loop=True, fixed_duty=15)
    control.start(0.0)
    control.update(0.1)
    control.set_fixed_duty(30)
    assert control.duty == pytest.approx(30.0)


def test_control_mode_change_requires_stopped_motor():
    control = controller()
    control.start(0.0)
    with pytest.raises(RuntimeError, match="stop"):
        control.set_open_loop(True)


def test_debug_mode_retains_independent_overspeed_stop():
    control = controller(
        open_loop=True,
        fixed_duty=20,
        pulses_per_revolution=6,
        debug_overspeed_rpm=100,
    )
    control.start(0.0)
    control.observe_pulse(1.0)
    for pulse_number in range(1, 7):
        control.observe_pulse(1.0 + pulse_number * 0.05)
    control.update(1.31)
    assert control.fault == "overspeed"
    assert control.duty == 0.0


def test_one_transient_overspeed_does_not_stop_when_confirmation_required():
    control = controller(overspeed_confirmations=2)
    control.start(0.0)
    control.observe_pulse(1.0)
    control.observe_pulse(1.5)
    control.update(1.51)
    assert control.running
    assert control.overspeed_count == 1


def test_two_consecutive_overspeed_revolutions_stop_motor():
    control = controller(overspeed_confirmations=2)
    control.start(0.0)
    control.observe_pulse(1.0)
    control.observe_pulse(1.5)
    control.update(1.51)
    control.observe_pulse(2.0)
    control.update(2.01)
    assert not control.running
    assert control.fault == "overspeed"


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
