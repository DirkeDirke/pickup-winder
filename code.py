"""CircuitPython entry point for the QT Py RP2040 pickup winder."""

import sys
import time

import board
import countio
import pwmio
import supervisor
from adafruit_motorkit import MotorKit

import config
from winder import SpeedController, WinderState, motor_throttle, servo_duty_cycle


SENSOR_PIN = board.D7      # RX silk label, PWM slice 2B (required by countio)
SERVO_PWM_PIN = board.D3   # A3 silk label, PWM slice 5A


state = WinderState(
    config.TARGET_TURNS,
    config.WINDING_WIDTH_MM,
    config.WIRE_DIAMETER_MM,
    config.PULSES_PER_REVOLUTION,
)
sensor = countio.Counter(SENSOR_PIN, edge=countio.Edge.RISE, pull=None)
i2c = board.I2C()  # QT Py SDA/D4 and SCL/D5 pins
motor_hat = MotorKit(
    i2c=i2c,
    address=config.MOTOR_HAT_I2C_ADDRESS,
    pwm_frequency=config.MOTOR_HAT_PWM_FREQUENCY_HZ,
)
motor = motor_hat.motor1
servo = pwmio.PWMOut(SERVO_PWM_PIN, frequency=config.SERVO_PWM_FREQUENCY_HZ)

target_rpm = config.START_RPM
speed = SpeedController(
    target_rpm=target_rpm,
    startup_duty=config.START_MOTOR_DUTY_PERCENT,
    minimum_duty=config.MIN_MOTOR_DUTY_PERCENT,
    maximum_duty=config.MAX_MOTOR_DUTY_PERCENT,
    ramp_per_second=config.MOTOR_RAMP_PERCENT_PER_SECOND,
    kp=config.SPEED_KP,
    ki=config.SPEED_KI,
    filter_alpha=config.RPM_FILTER_ALPHA,
    startup_grace=config.STARTUP_GRACE_SECONDS,
    stall_revolutions=config.STALL_REVOLUTIONS,
    minimum_stall_timeout=config.MIN_STALL_TIMEOUT_SECONDS,
    maximum_stall_timeout=config.MAX_STALL_TIMEOUT_SECONDS,
    overspeed_ratio=config.OVERSPEED_RATIO,
    overspeed_margin_rpm=config.OVERSPEED_MARGIN_RPM,
    minimum_pulse_interval=config.SENSOR_MIN_INTERVAL_SECONDS,
    pulses_per_revolution=config.PULSES_PER_REVOLUTION,
    open_loop=config.DEBUG_MODE_DEFAULT,
    fixed_duty=config.DEBUG_FIXED_DUTY_PERCENT,
    debug_overspeed_rpm=config.DEBUG_OVERSPEED_RPM,
)
last_raw_count = sensor.count
last_status = time.monotonic()
command_buffer = ""


def apply_motor_output():
    """Apply the controller's bounded duty request to Motor HAT terminal M1."""
    motor.throttle = motor_throttle(speed.duty, speed.running)


def set_servo():
    """Move the traverse servo to the position dictated by winding count."""
    servo.duty_cycle = servo_duty_cycle(
        state.traverse_fraction,
        config.SERVO_PWM_FREQUENCY_HZ,
        config.SERVO_MIN_PULSE_US,
        config.SERVO_MAX_PULSE_US,
    )


def print_status():
    """Print one machine-readable status line to USB serial."""
    print(
        "STATUS mode={} turns={} pulses={} target={} layer={} rpm={:.1f} "
        "target_rpm={} motor={:.1f} fixed_pwm={:.1f} running={} fault={}".format(
            "debug" if speed.open_loop else "closed",
            state.turns,
            state.pending_pulses,
            state.target_turns,
            state.layer + 1,
            speed.measured_rpm or 0.0,
            target_rpm,
            speed.duty,
            speed.fixed_duty,
            int(speed.running),
            speed.fault or "none",
        )
    )


def handle_command(command):
    """Execute one newline-terminated USB serial command."""
    global target_rpm
    parts = command.lower().split()
    if not parts:
        return
    if parts[0] == "start" and not state.complete:
        speed.start(time.monotonic())
        apply_motor_output()
    elif parts[0] == "stop":
        speed.stop()
        apply_motor_output()
    elif parts[0] == "reset" and not speed.running:
        state.reset()
        set_servo()
    elif parts[0] == "speed" and len(parts) == 2:
        if speed.open_loop:
            print("ERROR speed commands require closed-loop mode")
        elif parts[1] == "+":
            target_rpm = min(config.MAX_TARGET_RPM, target_rpm + config.RPM_STEP)
            speed.set_target(target_rpm)
        elif parts[1] == "-":
            target_rpm = max(config.MIN_TARGET_RPM, target_rpm - config.RPM_STEP)
            speed.set_target(target_rpm)
        else:
            print("ERROR use: speed + | speed -")
    elif parts[0] == "mode" and len(parts) == 2:
        if speed.running:
            print("ERROR stop motor before changing mode")
        elif parts[1] == "debug":
            speed.set_open_loop(True)
        elif parts[1] == "closed":
            speed.set_open_loop(False)
        else:
            print("ERROR use: mode debug | mode closed")
    elif parts[0] == "pwm" and len(parts) == 2:
        if not speed.open_loop:
            print("ERROR pwm command requires debug mode")
        else:
            try:
                speed.set_fixed_duty(float(parts[1]))
                apply_motor_output()
            except ValueError as error:
                print("ERROR {}".format(error))
    elif parts[0] == "status":
        print_status()
    else:
        print(
            "ERROR commands: start, stop, reset, speed +, speed -, "
            "mode debug, mode closed, pwm <percent>, status"
        )


apply_motor_output()
set_servo()
print("Pickup winder ready; motor is stopped")
print_status()

while True:
    now = time.monotonic()
    raw_count = sensor.count
    new_edges = raw_count - last_raw_count
    last_raw_count = raw_count

    if speed.running and new_edges > 0:
        # The controller observes the latest arrival time. Countio retains turns if
        # serial output briefly delays the main loop and several edges accumulate.
        if speed.observe_pulse(now):
            completed_turns = state.add_pulses(new_edges)
            if completed_turns:
                set_servo()
            if state.complete:
                speed.stop()
                apply_motor_output()
                print("COMPLETE target reached")

    was_running = speed.running
    speed.update(now)
    apply_motor_output()
    if was_running and not speed.running and speed.fault:
        print("FAULT {}: motor stopped".format(speed.fault))

    while supervisor.runtime.serial_bytes_available:
        character = sys.stdin.read(1)
        if character in ("\r", "\n"):
            if command_buffer:
                handle_command(command_buffer.strip())
                command_buffer = ""
        else:
            command_buffer += character

    if now - last_status >= config.STATUS_INTERVAL_SECONDS:
        print_status()
        last_status = now

    time.sleep(0.005)
