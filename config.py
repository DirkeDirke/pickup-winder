"""User-adjustable pickup-winder hardware and winding settings."""

# Physical winding configuration.
TARGET_TURNS = 7000
WINDING_WIDTH_MM = 14.8
# Nominal bare diameter for 42 AWG. Measure insulated wire and adjust this value.
WIRE_DIAMETER_MM = 0.0635

# Closed-loop spindle speed settings. Tune these on the completed mechanism.
START_RPM = 60
RPM_STEP = 5
MIN_TARGET_RPM = 10
MAX_TARGET_RPM = 300
STATUS_INTERVAL_SECONDS = 1.0

# Motor PWM output. Keep this below 100 until the mechanism is proven safe.
MOTOR_PWM_FREQUENCY_HZ = 20_000
START_MOTOR_DUTY_PERCENT = 20
MIN_MOTOR_DUTY_PERCENT = 8
MAX_MOTOR_DUTY_PERCENT = 60
MOTOR_RAMP_PERCENT_PER_SECOND = 8.0

# PI gains produce PWM percentage correction from RPM error. Start conservatively.
SPEED_KP = 0.12
SPEED_KI = 0.025
RPM_FILTER_ALPHA = 0.35

# Safety thresholds. A missing-pulse timeout is also scaled to target speed.
STARTUP_GRACE_SECONDS = 4.0
STALL_REVOLUTIONS = 3.0
MIN_STALL_TIMEOUT_SECONDS = 3.0
MAX_STALL_TIMEOUT_SECONDS = 20.0
OVERSPEED_RATIO = 1.5
OVERSPEED_MARGIN_RPM = 20.0

# Servo pulse calibration. Tune these with the motor disconnected.
SERVO_PWM_FREQUENCY_HZ = 50
SERVO_MIN_PULSE_US = 1000
SERVO_MAX_PULSE_US = 2000

# Ignore a second sensor edge inside this interval. At 60 RPM, valid edges are 1 s apart.
SENSOR_MIN_INTERVAL_SECONDS = 0.020
