"""Gate checks run on every reading before it counts as real data.

These are hard physical limits, not the ML anomaly detector. A value outside
them means the sensor is broken, so the reading is stored but flagged.
"""

LIMITS = {
    "soil_moisture": (0.0, 100.0),  # percent
    "temperature": (-5.0, 60.0),    # degrees C
    "humidity": (0.0, 100.0),       # percent
}


def check_reading_flags(soil_moisture: float, temperature: float, humidity: float) -> list[str]:
    """Return every out-of-range metric, not just the first one."""
    values = {
        "soil_moisture": soil_moisture,
        "temperature": temperature,
        "humidity": humidity,
    }
    return [
        f"{name}_out_of_range"
        for name, (low, high) in LIMITS.items()
        if not (low <= values[name] <= high)
    ]


def check_reading(soil_moisture: float, temperature: float, humidity: float) -> str | None:
    """Backward-compatible first flag, or None when all metrics are valid."""
    flags = check_reading_flags(soil_moisture, temperature, humidity)
    return flags[0] if flags else None
