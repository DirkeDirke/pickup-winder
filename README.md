# RP2040 QT Py Guitar Pickup Winder

CircuitPython firmware for a single-spindle guitar pickup winder with six sensor
pulses per spindle revolution, an Adafruit PCA9685 DC + Stepper Motor HAT, servo
traverse, and a USB serial interface.

## Initial configuration

- Target: 7,000 turns
- Requested starting speed: 60 RPM (one revolution per second)
- Winding width: 14.8 mm
- Wire: 42 AWG, nominal bare diameter 0.0635 mm
- Rotation feedback: 6 pulses per completed revolution
- Servo arm: 15 mm
- Provisional servo sweep: 59.1 degrees total
- Calculated turns per layer: 233

Insulation increases the effective wire diameter. Measure the actual wire or
calibrate the traverse experimentally, then update `WIRE_DIAMETER_MM`. The
servo mechanism is also nonlinear unless its linkage is designed to compensate;
adjust its endpoints and geometry before winding a pickup.

## Default pinout

| Function | QT Py silk | CircuitPython | Notes |
|---|---|---|---|
| Revolution switch | RX | `board.D7` | Active-low hardware-counter input |
| Motor HAT data | SDA | `board.D4` | I2C SDA to HAT SDA |
| Motor HAT clock | SCL | `board.D5` | I2C SCL to HAT SCL |
| Traverse servo signal | A3 | `board.D3` | 50 Hz PWM; slice 5A |

The HAT uses I2C address `0x64`; configure its address jumpers accordingly and
connect the DC spindle motor to M1.
Connect the QT Py and HAT grounds. Do not connect the motor supply to the QT Py.
Power the motor through the HAT motor-power input and power the traverse servo
from a suitable separate supply. Add a physical emergency stop that removes
motor power.

The QT Py is a 3.3 V logic device. Confirm the exact HAT revision accepts 3.3 V
I2C signalling before powering the system. Do not connect Raspberry Pi 5 V
power pins to QT Py GPIO pins.

Connect the rotation switch between `RX/D7` and ground. Use an external 10 kΩ
pull-up from D7 to 3.3 V and a 470 nF debounce capacitor from D7 to ground.
Firmware uses the RP2040 hardware counter to capture falling edges asynchronously
and does not enable an internal pull-up. The winding count advances after six
accepted closures. Raw edges received in one program-loop interval are collapsed
to one candidate closure, followed by a 25 ms rejection window. `raw_pulses`
therefore remains useful for diagnosing chatter but is not the authoritative
winding count. Never apply 5 V to a QT Py GPIO.

## Serial commands

Connect to the CircuitPython USB serial console and terminate commands with a
newline:

```text
start
stop
reset
speed +
speed -
mode debug
mode closed
pwm 15
servo 0
servo 50
servo 100
status
```

`speed +` and `speed -` change the closed-loop target by 5 RPM, bounded to the
configured 10--300 RPM range. RPM is measured over a complete six-pulse
revolution, avoiding false speed changes from uneven notch spacing. A
conservative PI controller adjusts PWM gradually between configured minimum
and maximum limits.

`mode debug` disables PI speed correction and drives M1 at a fixed throttle.
The `pwm <percent>` command selects that throttle from 0 through the configured
60% safety limit; status continues to report measured RPM. Stop the motor before
changing between `debug` and `closed` modes. Debug mode still retains target-turn
stopping, missing-pulse detection, and an independent 300 RPM overspeed shutdown.
`mode closed` restores normal PI regulation. Debug mode is disabled by default
after every reset.

With the motor stopped, `servo 0`, `servo 50`, and `servo 100` position the
guide at the two endpoints and center for mechanical setup. Starting the motor
always restores the count-derived traverse position. Initial 1336--1664 us
endpoints produced 10 mm of measured guide travel. The calibrated 1251--1749 us
endpoints compensate for the measured servo/linkage scale and should produce
approximately 14.8 mm. Verify the result without motor power and refine the
endpoints symmetrically if needed.

At startup, PWM ramps toward a known starting value while the controller waits
for feedback. Closed-loop mode first applies a 60% starting kick for 0.5 seconds,
then regulates around a 50% feed-forward baseline with a 45--100% output range.
Debug mode bypasses this kick. The controller stops and reports a `stall` fault if no first pulse arrives
within four seconds, or if later pulses disappear for roughly three expected
revolutions. Overspeed must be measured on two consecutive complete revolutions
before shutdown; the first high measurement is still available to PI correction.
Issue `start` to clear a latched fault only after correcting its physical cause.

Closed-loop output rises at no more than 8 percentage points per second but may
fall at 60 points per second so an overspeed correction is not delayed by the
gentle acceleration ramp. The confirmed closed-loop overspeed limit is 120 RPM
for the initial 60 RPM target.

The traverse is based on counted revolutions, not elapsed time. Changing motor
speed therefore does not change nominal wire spacing.

## Install

1. Install current CircuitPython for the Adafruit QT Py RP2040.
2. Copy `code.py`, `config.py`, and `winder.py` to the `CIRCUITPY` drive.
3. Install `adafruit_motorkit` and its dependencies as listed in
   `CIRCUITPY_LIBRARIES.md`.
4. With motor power disconnected, verify that the HAT responds at I2C address
   `0x64` and calibrate servo pulse endpoints in `config.py`.
5. Verify sensor counting by rotating the spindle manually.
6. Test M1 at low motor power before fitting wire.

Controller gains, duty limits, startup timing, and safety thresholds are initial
conservative values, not validated values for an unknown motor and driver. Test
and tune them with no wire fitted. Six pulses per revolution improve feedback
response, but aggressive gains can still cause surging.

This firmware has no persistence; resetting the board clears the count. Do not
rely on software as the only emergency stop or overspeed protection.

## Host tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

The pytest configuration disables its debugger plugin because CircuitPython's
required `code.py` filename otherwise shadows Python's standard `code` module.
