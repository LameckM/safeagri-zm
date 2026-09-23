"""Gate checks run on every reading before it counts as real data.

These are hard physical limits, not the ML anomaly detector. A value outside
them means the sensor is broken, so the reading is stored but flagged.
"""

LIMITS = {
    "soil_moisture": (0.0, 100.0),  # percent
    "temperature": (-5.0, 60.0),    # degrees C
    "humidity": (0.0, 100.0),       # percent
}


def check_reading(soil_moisture: float, temperature: float, humidity: float) -> str | None:
    """Return a flag like 'soil_moisture_out_of_range', or None if the reading is fine."""
    values = {
        "soil_moisture": soil_moisture,
        "temperature": temperature,
        "humidity": humidity,
    }
    for name, (low, high) in LIMITS.items():
        if not (low <= values[name] <= high):
            return f"{name}_out_of_range"
    return None
