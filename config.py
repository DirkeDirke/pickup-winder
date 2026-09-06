"""User-adjustable pickup-winder hardware and winding settings."""

# Physical winding configuration.
TARGET_TURNS = 7000
WINDING_WIDTH_MM = 14.8
PULSES_PER_REVOLUTION = 6
# Nominal bare diameter for 42 AWG. Measure insulated wire and adjust this value.
WIRE_DIAMETER_MM = 0.0635

# Closed-loop spindle speed settings. Tune these on the completed mechanism.
START_RPM = 60
RPM_STEP = 5
MIN_TARGET_RPM = 10
MAX_TARGET_RPM = 300
STATUS_INTERVAL_SECONDS = 1.0

# Adafruit PCA9685 DC + Stepper Motor HAT. Motor output uses terminal M1.
MOTOR_HAT_I2C_ADDRESS = 0x64
MOTOR_HAT_PWM_FREQUENCY_HZ = 1600

# Motor throttle limits. Keep these conservative until the mechanism is proven safe.
START_MOTOR_DUTY_PERCENT = 50
MIN_MOTOR_DUTY_PERCENT = 45
MAX_MOTOR_DUTY_PERCENT = 100
MOTOR_RAMP_UP_PERCENT_PER_SECOND = 8.0
MOTOR_RAMP_DOWN_PERCENT_PER_SECOND = 60.0
MOTOR_START_KICK_DUTY_PERCENT = 60
MOTOR_START_KICK_SECONDS = 0.5

# Open-loop diagnostic mode. It is disabled at boot unless explicitly enabled.
DEBUG_MODE_DEFAULT = False
DEBUG_FIXED_DUTY_PERCENT = 15
DEBUG_OVERSPEED_RPM = 300

# PI gains produce PWM percentage correction from RPM error. Start conservatively.
SPEED_KP = 0.12
SPEED_KI = 0.025
RPM_FILTER_ALPHA = 0.35

# Safety thresholds. A missing-pulse timeout is also scaled to target speed.
STARTUP_GRACE_SECONDS = 4.0
STALL_REVOLUTIONS = 3.0
MIN_STALL_TIMEOUT_SECONDS = 3.0
MAX_STALL_TIMEOUT_SECONDS = 20.0
OVERSPEED_RATIO = 2.0
OVERSPEED_MARGIN_RPM = 30.0
OVERSPEED_CONFIRMATIONS = 2

# Servo geometry and measured pulse calibration. The original 1336--1664 us
# span produced 10 mm; these symmetric endpoints compensate for the measured
# servo/linkage scale while preserving the 1500 us center.
SERVO_ARM_LENGTH_MM = 15.0
SERVO_SWEEP_DEGREES = 59.1
SERVO_PWM_FREQUENCY_HZ = 50
SERVO_CENTER_PULSE_US = 1500
SERVO_MIN_PULSE_US = 1251
SERVO_MAX_PULSE_US = 1749

# Ignore further noisy batches for 25 ms after one accepted notch closure. This
# still permits six pulses/revolution at the configured 300 RPM maximum.
SENSOR_MIN_INTERVAL_SECONDS = 0.025
