"""Hardware-independent winding and traverse calculations."""


def _clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


class SpeedController:
    """Conservative PI spindle controller using one pulse per revolution."""

    def __init__(
        self,
        target_rpm,
        startup_duty,
        minimum_duty,
        maximum_duty,
        ramp_per_second,
        kp,
        ki,
        filter_alpha,
        startup_grace,
        stall_revolutions,
        minimum_stall_timeout,
        maximum_stall_timeout,
        overspeed_ratio,
        overspeed_margin_rpm,
        minimum_pulse_interval,
    ):
        if target_rpm <= 0:
            raise ValueError("target_rpm must be positive")
        if not 0 <= minimum_duty <= startup_duty <= maximum_duty <= 100:
            raise ValueError("motor duty limits are invalid")
        if ramp_per_second <= 0 or kp < 0 or ki < 0:
            raise ValueError("controller tuning values are invalid")
        if not 0 < filter_alpha <= 1:
            raise ValueError("filter_alpha must be in (0, 1]")
        self.target_rpm = float(target_rpm)
        self.startup_duty = float(startup_duty)
        self.minimum_duty = float(minimum_duty)
        self.maximum_duty = float(maximum_duty)
        self.ramp_per_second = float(ramp_per_second)
        self.kp = float(kp)
        self.ki = float(ki)
        self.filter_alpha = float(filter_alpha)
        self.startup_grace = float(startup_grace)
        self.stall_revolutions = float(stall_revolutions)
        self.minimum_stall_timeout = float(minimum_stall_timeout)
        self.maximum_stall_timeout = float(maximum_stall_timeout)
        self.overspeed_ratio = float(overspeed_ratio)
        self.overspeed_margin_rpm = float(overspeed_margin_rpm)
        self.minimum_pulse_interval = float(minimum_pulse_interval)
        self.running = False
        self.fault = None
        self.duty = 0.0
        self.measured_rpm = None
        self._integral = 0.0
        self._started_at = None
        self._last_update = None
        self._last_pulse = None

    @property
    def stall_timeout(self):
        """Return timeout scaled to the period of the requested speed."""
        timeout = 60.0 * self.stall_revolutions / self.target_rpm
        return _clamp(timeout, self.minimum_stall_timeout, self.maximum_stall_timeout)

    def set_target(self, target_rpm):
        """Change the requested speed without clearing current regulation state."""
        if target_rpm <= 0:
            raise ValueError("target_rpm must be positive")
        self.target_rpm = float(target_rpm)

    def start(self, now):
        """Start from zero duty and clear prior measurements and faults."""
        self.running = True
        self.fault = None
        self.duty = 0.0
        self.measured_rpm = None
        self._integral = 0.0
        self._started_at = float(now)
        self._last_update = float(now)
        self._last_pulse = None

    def stop(self, reason=None):
        """Stop motor output, optionally latching a safety fault reason."""
        self.running = False
        self.fault = reason
        self.duty = 0.0

    def observe_pulse(self, now):
        """Record a pulse and update period-based RPM; return whether accepted."""
        now = float(now)
        if self._last_pulse is not None:
            period = now - self._last_pulse
            if period < self.minimum_pulse_interval:
                return False
            instantaneous = 60.0 / period
            if self.measured_rpm is None:
                self.measured_rpm = instantaneous
            else:
                alpha = self.filter_alpha
                self.measured_rpm += alpha * (instantaneous - self.measured_rpm)
        self._last_pulse = now
        return True

    def update(self, now):
        """Advance regulation and safety checks, returning motor duty percent."""
        now = float(now)
        if not self.running:
            return 0.0
        elapsed = max(0.0, now - self._last_update)
        self._last_update = now

        pulse_reference = self._last_pulse
        if pulse_reference is None:
            pulse_reference = self._started_at
            timed_out = now - pulse_reference > self.startup_grace
        else:
            timed_out = now - pulse_reference > self.stall_timeout
        if timed_out:
            self.stop("stall")
            return 0.0

        if self.measured_rpm is not None:
            overspeed_limit = max(
                self.target_rpm * self.overspeed_ratio,
                self.target_rpm + self.overspeed_margin_rpm,
            )
            if self.measured_rpm > overspeed_limit:
                self.stop("overspeed")
                return 0.0
            error = self.target_rpm - self.measured_rpm
            self._integral += error * elapsed
            if self.ki > 0:
                integral_limit = (self.maximum_duty - self.minimum_duty) / self.ki
                self._integral = _clamp(self._integral, -integral_limit, integral_limit)
            requested_duty = self.startup_duty + self.kp * error + self.ki * self._integral
        else:
            requested_duty = self.startup_duty

        requested_duty = _clamp(requested_duty, self.minimum_duty, self.maximum_duty)
        maximum_change = self.ramp_per_second * elapsed
        self.duty += _clamp(requested_duty - self.duty, -maximum_change, maximum_change)
        return self.duty


class WinderState:
    """Track turns and calculate a layer-synchronised traverse position."""

    def __init__(self, target_turns, winding_width_mm, wire_diameter_mm):
        if target_turns <= 0:
            raise ValueError("target_turns must be positive")
        if winding_width_mm <= 0 or wire_diameter_mm <= 0:
            raise ValueError("winding dimensions must be positive")
        self.target_turns = int(target_turns)
        self.winding_width_mm = float(winding_width_mm)
        self.wire_diameter_mm = float(wire_diameter_mm)
        self.turns = 0

    @property
    def turns_per_layer(self):
        """Return the nearest whole number of turns across the winding width."""
        return max(1, int(round(self.winding_width_mm / self.wire_diameter_mm)))

    @property
    def complete(self):
        """Return whether the configured target has been reached."""
        return self.turns >= self.target_turns

    @property
    def layer(self):
        """Return the zero-based layer containing the current traverse position."""
        return self.turns // self.turns_per_layer

    @property
    def traverse_fraction(self):
        """Return servo travel from 0.0 to 1.0, reversing on alternate layers."""
        position = self.turns % self.turns_per_layer
        fraction = position / self.turns_per_layer
        return fraction if self.layer % 2 == 0 else 1.0 - fraction

    def add_turns(self, count):
        """Add newly observed spindle revolutions and return the accepted count."""
        count = int(count)
        if count < 0:
            raise ValueError("count must not be negative")
        available = max(0, self.target_turns - self.turns)
        accepted = min(count, available)
        self.turns += accepted
        return accepted

    def reset(self):
        """Reset winding progress to zero turns."""
        self.turns = 0


def servo_duty_cycle(fraction, frequency_hz, min_pulse_us, max_pulse_us):
    """Convert a normalised traverse fraction into a 16-bit PWM duty cycle."""
    fraction = min(1.0, max(0.0, float(fraction)))
    pulse_us = min_pulse_us + fraction * (max_pulse_us - min_pulse_us)
    period_us = 1_000_000 / frequency_hz
    return round(65535 * pulse_us / period_us)
