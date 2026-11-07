"""SafeAgri sensor simulator.

Examples:
  python simulate.py --fast
  python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 0.1
  python simulate.py --sensor humidity --scenario flatline --node node-01 --fast --hours 1
  python simulate.py --scenario offline --node node-01 --fast --hours 0.1

When --node is supplied, that node receives the selected test scenario while
all other nodes continue sending normal readings.
"""
import argparse
import logging
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

LOG_PATH = Path(__file__).parent / "faults.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("simulator")

API_BASE = os.getenv("SAFEAGRI_API_URL", "http://localhost:8000").rstrip("/")
READINGS_URL = f"{API_BASE}/readings"
ALERT_SYNC_URL = f"{API_BASE}/alerts/sync"
NODE_IDS = ["node-01", "node-02", "node-03", "node-04"]
INTERVAL_MIN = 5


@dataclass
class FieldState:
    node_id: str
    moisture: float
    dry_rate: float
    temp_base: float
    humidity_base: float
    rain_chance_per_hour: float = 0.03


def make_fields():
    return [
        FieldState("node-01", 45, 1.8, 27, 58),
        FieldState("node-02", 30, 2.4, 29, 52),
        FieldState("node-03", 50, 1.5, 26, 61),
        FieldState("node-04", 22, 2.1, 28, 55),
    ]


def diurnal_temp(base, moment):
    hour = moment.hour + moment.minute / 60
    return round(base + 6 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.uniform(-0.4, 0.4), 1)


def diurnal_humidity(base, moment):
    hour = moment.hour + moment.minute / 60
    value = base - 8 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.uniform(-1.5, 1.5)
    return round(max(10, min(100, value)), 1)


def step_moisture(field, minutes):
    hours = minutes / 60
    value = field.moisture - field.dry_rate * hours * random.uniform(0.85, 1.15)
    if random.random() < field.rain_chance_per_hour * hours:
        gain = random.uniform(15, 35)
        value += gain
        log.info("RAIN on %s: +%.1f%%", field.node_id, gain)
    field.moisture = max(2, min(100, value))
    return field.moisture


def normal_reading(field, moment):
    return {
        "node_id": field.node_id,
        "soil_moisture": round(max(0, min(100, field.moisture + random.gauss(0, 0.15))), 1),
        "temperature": diurnal_temp(field.temp_base, moment),
        "humidity": diurnal_humidity(field.humidity_base, moment),
        "timestamp": moment.isoformat(),
    }


def normalize_sensor(sensor):
    return "soil_moisture" if sensor == "water" else sensor


def apply_scenario(reading, sensor, scenario, held_values):
    """Change only the requested metric; leave the other metrics untouched."""
    if scenario == "normal":
        return reading
    if scenario == "offline":
        return None

    limits = {
        "humidity": (0.0, 100.0, 8.0, 108.0),
        "temperature": (-5.0, 60.0, -10.0, 70.0),
        "soil_moisture": (0.0, 100.0, 5.0, 110.0),
    }
    if sensor not in limits:
        raise ValueError(f"Unsupported sensor: {sensor}")

    _, _, low_value, high_value = limits[sensor]
    if scenario == "low":
        reading[sensor] = low_value
    elif scenario in ("high", "spike"):
        reading[sensor] = high_value
    elif scenario == "flatline":
        key = (reading["node_id"], sensor)
        if key not in held_values:
            held_values[key] = reading[sensor]
        reading[sensor] = held_values[key]

    log.info(
        "TARGETED TEST node=%s sensor=%s scenario=%s value=%s",
        reading["node_id"], sensor, scenario, reading[sensor],
    )
    return reading


def post_reading(client, reading):
    try:
        response = client.post(READINGS_URL, json=reading, timeout=5)
        if response.status_code != 201:
            log.warning("API rejected reading: %s %s", response.status_code, response.text)
        else:
            result = response.json()
            log.info(
                "POSTED %s moisture=%s temp=%s humidity=%s valid=%s",
                reading["node_id"], reading["soil_moisture"], reading["temperature"],
                reading["humidity"], result.get("valid"),
            )
    except httpx.HTTPError as exc:
        log.error("API connection failed: %s", exc)


def sync_alerts(client):
    try:
        response = client.post(ALERT_SYNC_URL, timeout=5)
        if response.status_code != 200:
            log.warning("Alert synchronization failed: %s %s", response.status_code, response.text)
    except httpx.HTTPError as exc:
        log.error("Could not synchronize alerts: %s", exc)


def run(fast=False, hours=None, sensor=None, scenario="normal", node=None):
    # Always keep all nodes running. --node selects only which node receives
    # the injected fault; it must not silence the other fields.
    fields = make_fields()
    sensor = normalize_sensor(sensor)
    moment = datetime.now(timezone.utc)
    end = moment + timedelta(hours=hours) if hours is not None else None
    held_values = {}
    delay = 0.05 if fast else INTERVAL_MIN * 60
    offline_baseline_sent = False

    log.info(
        "Starting simulation scenario=%s sensor=%s target=%s fast=%s interval=%ss",
        scenario, sensor or "all", node or "all nodes", fast, delay,
    )

    with httpx.Client() as client:
        while end is None or moment < end:
            for field in fields:
                step_moisture(field, INTERVAL_MIN)
                reading = normal_reading(field, moment)
                is_target = node is None or field.node_id == node

                if is_target and scenario == "offline":
                    # Send one fresh baseline packet first. Subsequent cycles
                    # deliberately omit this node so the backend can age it out.
                    if not offline_baseline_sent:
                        post_reading(client, reading)
                        offline_baseline_sent = True
                        log.warning(
                            "OFFLINE TEST ARMED for %s: no more packets will be sent",
                            field.node_id,
                        )
                    else:
                        log.warning("SIMULATED NODE OFFLINE: %s (no packet sent)", field.node_id)
                    continue

                if is_target and sensor and scenario != "normal":
                    reading = apply_scenario(reading, sensor, scenario, held_values)

                if reading is not None:
                    post_reading(client, reading)

            # Let the backend update offline/dry-soil alert state during a test.
            sync_alerts(client)
            moment += timedelta(minutes=INTERVAL_MIN)
            time.sleep(delay)

    log.info("Simulation finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="Advance each five-minute step every 0.05 seconds")
    parser.add_argument("--hours", type=float, help="Stop after this many simulated hours")
    parser.add_argument("--sensor", choices=["humidity", "temperature", "soil_moisture", "water"])
    parser.add_argument("--scenario", choices=["normal", "low", "high", "spike", "flatline", "offline"], default="normal")
    parser.add_argument("--node", choices=NODE_IDS, help="Target one node; all other nodes continue normally")
    args = parser.parse_args()

    if args.hours is not None and args.hours <= 0:
        parser.error("--hours must be greater than zero")
    if args.scenario not in ("normal", "offline") and not args.sensor:
        parser.error("--sensor is required for a sensor fault scenario")
    if args.scenario == "offline" and args.sensor:
        parser.error("--sensor is not used with the offline scenario")

    run(args.fast, args.hours, args.sensor, args.scenario, args.node)
