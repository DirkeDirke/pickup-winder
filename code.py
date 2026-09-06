"""CircuitPython entry point for the QT Py RP2040 pickup winder."""

import sys
import time

import board
import countio
import pwmio
import supervisor

import config
from winder import SpeedController, WinderState, servo_duty_cycle


SENSOR_PIN = board.D7       # RX silk label, PWM slice 2B (required by countio)
MOTOR_PWM_PIN = board.D10   # MO silk label, PWM slice 1B
SERVO_PWM_PIN = board.D3    # A3 silk label, PWM slice 5A


state = WinderState(
    config.TARGET_TURNS,
    config.WINDING_WIDTH_MM,
    config.WIRE_DIAMETER_MM,
)
sensor = countio.Counter(SENSOR_PIN, edge=countio.Edge.RISE, pull=None)
motor = pwmio.PWMOut(MOTOR_PWM_PIN, frequency=config.MOTOR_PWM_FREQUENCY_HZ)
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
)
last_raw_count = sensor.count
last_status = time.monotonic()
command_buffer = ""


def apply_motor_output():
    """Apply the controller's bounded duty request to the physical PWM."""
    motor.duty_cycle = round(65535 * speed.duty / 100) if speed.running else 0


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
        "STATUS turns={} target={} layer={} rpm={:.1f} target_rpm={} "
        "motor={:.1f} running={} fault={}".format(
            state.turns,
            state.target_turns,
            state.layer + 1,
            speed.measured_rpm or 0.0,
            target_rpm,
            speed.duty,
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
        if parts[1] == "+":
            target_rpm = min(config.MAX_TARGET_RPM, target_rpm + config.RPM_STEP)
            speed.set_target(target_rpm)
        elif parts[1] == "-":
            target_rpm = max(config.MIN_TARGET_RPM, target_rpm - config.RPM_STEP)
            speed.set_target(target_rpm)
        else:
            print("ERROR use: speed + | speed -")
    elif parts[0] == "status":
        print_status()
    else:
        print("ERROR commands: start, stop, reset, speed +, speed -, status")


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
            state.add_turns(new_edges)
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
