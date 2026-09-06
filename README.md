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
- Calculated turns per layer: 233

Insulation increases the effective wire diameter. Measure the actual wire or
calibrate the traverse experimentally, then update `WIRE_DIAMETER_MM`. The
servo mechanism is also nonlinear unless its linkage is designed to compensate;
adjust its endpoints and geometry before winding a pickup.

## Default pinout

| Function | QT Py silk | CircuitPython | Notes |
|---|---|---|---|
| Revolution sensor | RX | `board.D7` | Rising-edge input; PWM slice 2B |
| Motor HAT data | SDA | `board.D4` | I2C SDA to HAT SDA |
| Motor HAT clock | SCL | `board.D5` | I2C SCL to HAT SCL |
| Traverse servo signal | A3 | `board.D3` | 50 Hz PWM; slice 5A |

The HAT uses its default I2C address `0x60`; connect the DC spindle motor to M1.
Connect the QT Py and HAT grounds. Do not connect the motor supply to the QT Py.
Power the motor through the HAT motor-power input and power the traverse servo
from a suitable separate supply. Add a physical emergency stop that removes
motor power.

The QT Py is a 3.3 V logic device. Confirm the exact HAT revision accepts 3.3 V
I2C signalling before powering the system. Do not connect Raspberry Pi 5 V
power pins to QT Py GPIO pins.

The sensor input currently expects six clean 3.3 V rising edges per revolution.
The winding count advances only after a complete group of six. Never apply 5 V
to a QT Py GPIO. Use the appropriate pull-up or level conversion for the chosen
Hall sensor. `pull=None` is deliberate because the sensor output type is not yet
specified.

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
status
```

`speed +` and `speed -` change the closed-loop target by 5 RPM, bounded to the
configured 10--300 RPM range. RPM is measured from pulse intervals and divided
by the configured six pulses per revolution. A conservative PI controller
adjusts PWM gradually between configured minimum and maximum limits.

`mode debug` disables PI speed correction and drives M1 at a fixed throttle.
The `pwm <percent>` command selects that throttle from 0 through the configured
60% safety limit; status continues to report measured RPM. Stop the motor before
changing between `debug` and `closed` modes. Debug mode still retains target-turn
stopping, missing-pulse detection, and an independent 300 RPM overspeed shutdown.
`mode closed` restores normal PI regulation. Debug mode is disabled by default
after every reset.

At startup, PWM ramps toward a known starting value while the controller waits
for feedback. It stops and reports a `stall` fault if no first pulse arrives
within four seconds, or if later pulses disappear for roughly three expected
revolutions. It also stops on measured overspeed. Issue `start` to clear a
latched fault only after correcting its physical cause.

The traverse is based on counted revolutions, not elapsed time. Changing motor
speed therefore does not change nominal wire spacing.

## Install

1. Install current CircuitPython for the Adafruit QT Py RP2040.
2. Copy `code.py`, `config.py`, and `winder.py` to the `CIRCUITPY` drive.
3. Install `adafruit_motorkit` and its dependencies as listed in
   `CIRCUITPY_LIBRARIES.md`.
4. With motor power disconnected, verify that the HAT responds at I2C address
   `0x60` and calibrate servo pulse endpoints in `config.py`.
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
