"""Physical sensor limits. Invalid readings are stored but never trusted."""
LIMITS = {
    "soil_moisture": (0.0, 100.0),
    "temperature": (-5.0, 60.0),
    "humidity": (0.0, 100.0),
}


def check_reading_flags(soil_moisture: float, temperature: float, humidity: float) -> list[str]:
    values = {"soil_moisture": soil_moisture, "temperature": temperature, "humidity": humidity}
    return [
        f"{name}_out_of_range"
        for name, (low, high) in LIMITS.items()
        if not low <= values[name] <= high
    ]


def check_reading(soil_moisture: float, temperature: float, humidity: float) -> str | None:
    flags = check_reading_flags(soil_moisture, temperature, humidity)
    return flags[0] if flags else None
