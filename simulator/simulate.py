"""
Simulated farm for SafeAgri ZM.

Posts readings to the backend for all 4 fields, on a loop, so the API,
scheduler, dashboard and ML pipeline all have data to work against before
the ESP32 hardware exists.

Each field dries down over the day, jumps back up on a simulated rain
event, and drifts a little differently per field so the 4 aren't
identical. Faults (flatline, spike, node offline) are injected on a
schedule and logged to faults.log, because the anomaly detector will
need labeled ground truth to be tested against honestly.

Usage:
    python simulate.py                 # real-time, one post every 5 min
    python simulate.py --fast          # 1 simulated reading per second
    python simulate.py --hours 48      # run for 48 simulated hours then stop
"""
import argparse
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "faults.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("simulator")

API_URL = "http://localhost:8000/readings"
NODE_IDS = ["node-01", "node-02", "node-03", "node-04"]
READING_INTERVAL_MIN = 5  # matches the proposal's 5-minute target


@dataclass
class FieldState:
    node_id: str
    moisture: float                 # percent, 0-100
    dry_rate: float                 # percent lost per hour, field-specific
    temp_base: float                # field-specific baseline temperature
    humidity_base: float
    rain_chance_per_hour: float = 0.03
    offline: bool = False
    offline_until: datetime | None = None
    fault_log: list = dc_field(default_factory=list)


def make_fields() -> list[FieldState]:
    # Slightly different per field, same as a real farm would be
    return [
        FieldState("node-01", moisture=45, dry_rate=1.8, temp_base=27, humidity_base=58),
        FieldState("node-02", moisture=30, dry_rate=2.4, temp_base=29, humidity_base=52),
        FieldState("node-03", moisture=50, dry_rate=1.5, temp_base=26, humidity_base=61),
        FieldState("node-04", moisture=22, dry_rate=2.1, temp_base=28, humidity_base=55),
    ]


def diurnal_temp(base: float, sim_time: datetime) -> float:
    """Warmer in the afternoon, cooler before dawn."""
    hour = sim_time.hour + sim_time.minute / 60
    swing = 6 * math.sin((hour - 9) / 24 * 2 * math.pi)
    return round(base + swing + random.uniform(-0.4, 0.4), 1)


def diurnal_humidity(base: float, sim_time: datetime) -> float:
    hour = sim_time.hour + sim_time.minute / 60
    swing = -8 * math.sin((hour - 9) / 24 * 2 * math.pi)  # inverse of temp
    return round(max(10, min(100, base + swing + random.uniform(-1.5, 1.5))), 1)


def step_moisture(f: FieldState, minutes: int) -> float:
    hours = minutes / 60
    loss = f.dry_rate * hours * random.uniform(0.85, 1.15)
    new_moisture = f.moisture - loss

    # Chance of rain each simulated hour, applied pro-rated per step
    if random.random() < f.rain_chance_per_hour * hours:
        rain_gain = random.uniform(15, 35)
        new_moisture += rain_gain
        log.info(f"RAIN on {f.node_id}: +{rain_gain:.1f}% moisture")

    f.moisture = max(2.0, min(100.0, new_moisture))
    return f.moisture


def maybe_inject_fault(f: FieldState, sim_time: datetime) -> str | None:
    """Small per-step chance of each fault type. Logged so it can be used
    as ground truth when testing the anomaly detector."""
    if f.offline:
        if sim_time >= f.offline_until:
            f.offline = False
            log.info(f"FAULT END offline on {f.node_id}")
        return "offline"

    roll = random.random()
    if roll < 0.0006:
        f.offline = True
        f.offline_until = sim_time + timedelta(minutes=random.choice([15, 30, 60]))
        log.info(f"FAULT START offline on {f.node_id} until {f.offline_until.isoformat()}")
        return "offline"
    if roll < 0.0010:
        log.info(f"FAULT spike on {f.node_id}")
        return "spike"
    if roll < 0.0014:
        log.info(f"FAULT flatline on {f.node_id}")
        return "flatline"
    return None


def build_reading(f: FieldState, sim_time: datetime, minutes_elapsed: int) -> dict | None:
    fault = maybe_inject_fault(f, sim_time)
    moisture = step_moisture(f, minutes_elapsed)
    temperature = diurnal_temp(f.temp_base, sim_time)
    humidity = diurnal_humidity(f.humidity_base, sim_time)

    if fault == "offline":
        return None  # node sends nothing at all
    if fault == "spike":
        moisture = random.choice([999, -50, 250])
    elif fault == "flatline":
        moisture = f.moisture  # looks normal but repeats exactly next step too
        f._flatlined_at = moisture  # noqa: SLF001 (simple sim state, fine here)

    return {
        "node_id": f.node_id,
        "soil_moisture": round(moisture, 1),
        "temperature": temperature,
        "humidity": humidity,
        "timestamp": sim_time.isoformat(),
    }


def post_reading(client: httpx.Client, reading: dict) -> None:
    try:
        r = client.post(API_URL, json=reading, timeout=5)
        if r.status_code != 201:
            log.warning(f"API rejected reading: {r.status_code} {r.text}")
    except httpx.HTTPError as e:
        log.error(f"Could not reach API at {API_URL}: {e}")


def run(fast: bool, hours: float | None, start: datetime | None = None) -> None:
    fields = make_fields()
    sim_time = start or datetime.now(timezone.utc)
    end_time = sim_time + timedelta(hours=hours) if hours else None
    sleep_seconds = 0.05 if fast else READING_INTERVAL_MIN * 60

    log.info(f"Starting simulation: fast={fast} hours={hours}")
    with httpx.Client() as client:
        while end_time is None or sim_time < end_time:
            for f in fields:
                reading = build_reading(f, sim_time, READING_INTERVAL_MIN)
                if reading is not None:
                    post_reading(client, reading)
            sim_time += timedelta(minutes=READING_INTERVAL_MIN)
            time.sleep(sleep_seconds)

    log.info("Simulation finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="advance quickly instead of real-time")
    parser.add_argument("--hours", type=float, default=None, help="stop after N simulated hours")
    args = parser.parse_args()
    run(fast=args.fast, hours=args.hours)
