"""Sensor checks. Invalid readings are stored but never trusted.

Two layers:
  1. Physical limits on every metric (a value the sensor cannot produce).
  2. Trend rules on soil moisture, ported from the ml/ experiments where they
     scored about 0.91 F1 against 0.20 for range checks alone:
       - flatline: the same moisture value STUCK_RUN times in a row
       - implausible drop: moisture fell more than DROP_LIMIT points since the
         previous reading. Soil only dries slowly, so a fast fall is a fault.
     Rain and irrigation make moisture rise, which is normal and never flagged.
"""
import os
from datetime import datetime, timedelta

LIMITS = {
    "soil_moisture": (0.0, 100.0),
    "temperature": (-5.0, 60.0),
    "humidity": (0.0, 100.0),
}

FLATLINE_FLAG = "soil_moisture_flatline"
DROP_FLAG = "soil_moisture_implausible_drop"


def _stuck_run() -> int:
    return max(2, int(os.getenv("SAFEAGRI_STUCK_RUN", "4")))


def _drop_limit() -> float:
    return float(os.getenv("SAFEAGRI_DROP_LIMIT", "2.2"))


def _max_gap() -> timedelta:
    # Same window the scheduler uses to call a node offline. Across a longer
    # gap, a large fall can be real drying, so the drop rule stays quiet.
    return timedelta(minutes=float(os.getenv("SAFEAGRI_STALE_MINUTES", "15")))


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


def check_trend_flags(
    soil_moisture: float,
    recorded_at: str,
    recent_values: list[float],
    last_in_range: tuple[float, str] | None,
) -> list[str]:
    """Trend rules for one node.

    recent_values: this node's previous soil_moisture values, newest first
        (at least STUCK_RUN - 1 if that many exist).
    last_in_range: (value, recorded_at) of the node's latest earlier reading
        whose moisture was inside 0 to 100, or None.
    """
    low, high = LIMITS["soil_moisture"]
    if not low <= soil_moisture <= high:
        return []  # already caught by the range check

    flags = []
    needed = _stuck_run() - 1
    if len(recent_values) >= needed and all(v == soil_moisture for v in recent_values[:needed]):
        flags.append(FLATLINE_FLAG)

    if last_in_range is not None:
        previous_value, previous_time = last_in_range
        try:
            gap = datetime.fromisoformat(recorded_at) - datetime.fromisoformat(previous_time)
        except ValueError:
            gap = None
        if gap is not None and timedelta(0) < gap <= _max_gap() and previous_value - soil_moisture > _drop_limit():
            flags.append(DROP_FLAG)
    return flags


def describe_flag(flag: str, soil_moisture: float, temperature: float, humidity: float) -> str:
    """Plain-language alert text for one flag."""
    values = {"soil_moisture": soil_moisture, "temperature": temperature, "humidity": humidity}
    if flag == FLATLINE_FLAG:
        return f"soil moisture stuck at {soil_moisture} for {_stuck_run()} readings in a row"
    if flag == DROP_FLAG:
        return "soil moisture fell faster than soil can dry"
    metric = flag.removesuffix("_out_of_range")
    return f"{metric.replace('_', ' ')} reading {values[metric]} is out of range"
