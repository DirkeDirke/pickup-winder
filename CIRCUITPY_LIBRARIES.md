# CircuitPython libraries

Copy these libraries and all their dependencies from the Adafruit CircuitPython
Library Bundle into the `lib/` directory on the `CIRCUITPY` drive:

- `adafruit_motorkit.mpy`
- `adafruit_motor/`
- `adafruit_pca9685.mpy`
- `adafruit_register/`
- `adafruit_bus_device/`

Use the bundle matching the major version of CircuitPython installed on the QT
Py RP2040. The MotorKit package and its dependency list may change, so prefer
the bundle dependency installer or `circup install adafruit_motorkit` when
available.
