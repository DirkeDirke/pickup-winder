# RP2040 QT Py Guitar Pickup Winder

CircuitPython firmware for a single-spindle guitar pickup winder with one pulse
per spindle revolution, motor PWM, servo traverse, and a USB serial interface.

## Initial configuration

- Target: 7,000 turns
- Requested starting speed: 60 RPM (one revolution per second)
- Winding width: 14.8 mm
- Wire: 42 AWG, nominal bare diameter 0.0635 mm
- Calculated turns per layer: 233

Insulation increases the effective wire diameter. Measure the actual wire or
calibrate the traverse experimentally, then update `WIRE_DIAMETER_MM`. The
servo mechanism is also nonlinear unless its linkage is designed to compensate;
adjust its endpoints and geometry before winding a pickup.

## Default pinout

| Function | QT Py silk | CircuitPython | Notes |
|---|---|---|---|
| Revolution sensor | RX | `board.D7` | Rising-edge input; PWM slice 2B |
| Motor controller PWM | MO | `board.D10` | 20 kHz PWM; slice 1B |
| Traverse servo signal | A3 | `board.D3` | 50 Hz PWM; slice 5A |

The three functions use separate RP2040 PWM slices. Connect all signal grounds.
Power the motor and servo from suitable external supplies, not from the QT Py.
The motor driver must accept 3.3 V logic and isolate motor current from the
microcontroller. Add a physical emergency stop that removes motor power.

The sensor input currently expects a clean 3.3 V rising edge. Never apply 5 V
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
status
```

`speed +` and `speed -` change the closed-loop target by 5 RPM, bounded to the
configured 10--300 RPM range. RPM is measured from the interval between sensor
pulses. A conservative PI controller adjusts PWM gradually between configured
minimum and maximum limits.

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
3. With motor power disconnected, calibrate servo pulse endpoints in `config.py`.
4. Verify sensor counting by rotating the spindle manually.
5. Test at low motor power before fitting wire.

Controller gains, duty limits, startup timing, and safety thresholds are initial
conservative values, not validated values for an unknown motor and driver. Test
and tune them with no wire fitted. A single pulse per revolution provides slow
feedback at low RPM, so aggressive gains will cause surging.

This firmware has no persistence; resetting the board clears the count. Do not
rely on software as the only emergency stop or overspeed protection.

## Host tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

The pytest configuration disables its debugger plugin because CircuitPython's
required `code.py` filename otherwise shadows Python's standard `code` module.
