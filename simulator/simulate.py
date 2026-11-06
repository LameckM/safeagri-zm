"""
SafeAgri simulated farm.

Normal mode posts all four fields every five simulated minutes.
Targeted mode changes only one selected sensor on one node while the other
two measurements continue to report normal simulated values.

Examples:
    python simulate.py --fast
    python simulate.py --sensor humidity --scenario high --node node-01 --fast
    python simulate.py --sensor temperature --scenario spike --node node-02 --fast
    python simulate.py --sensor soil_moisture --scenario low --node node-03 --hours 1
    python simulate.py --sensor humidity --scenario flatline --node node-01
    python simulate.py --sensor temperature --scenario offline --node node-01
"""
import argparse
import logging
import math
import random
import time
from dataclasses import dataclass
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
READING_INTERVAL_MIN = 5
IRRIGATE_BELOW = 20.0
IRRIGATE_GAIN = 25.0
SENSOR_NOISE = 0.15

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


def diurnal_temp(base, sim_time):
    hour = sim_time.hour + sim_time.minute / 60
    swing = 6 * math.sin((hour - 9) / 24 * 2 * math.pi)
    return round(base + swing + random.uniform(-0.4, 0.4), 1)


def diurnal_humidity(base, sim_time):
    hour = sim_time.hour + sim_time.minute / 60
    swing = -8 * math.sin((hour - 9) / 24 * 2 * math.pi)
    return round(max(10, min(100, base + swing + random.uniform(-1.5, 1.5))), 1)


def step_moisture(field, minutes):
    hours = minutes / 60
    moisture = field.moisture - field.dry_rate * hours * random.uniform(0.85, 1.15)
    if random.random() < field.rain_chance_per_hour * hours:
        moisture += random.uniform(15, 35)
        log.info("RAIN on %s", field.node_id)
    if moisture <= IRRIGATE_BELOW:
        moisture += IRRIGATE_GAIN
        log.info("BACKGROUND WATERING on %s", field.node_id)
    field.moisture = max(2.0, min(100.0, moisture))
    return field.moisture


def normal_reading(field, sim_time, minutes):
    moisture = step_moisture(field, minutes)
    return {
        "node_id": field.node_id,
        "soil_moisture": round(max(0, min(100, moisture + random.gauss(0, SENSOR_NOISE))), 1),
        "temperature": diurnal_temp(field.temp_base, sim_time),
        "humidity": diurnal_humidity(field.humidity_base, sim_time),
        "timestamp": sim_time.isoformat(),
    }


def apply_sensor_scenario(reading, sensor, scenario, flatline_values):
    """Override exactly one metric; the other sensor values stay untouched."""
    if scenario == "normal":
        return reading
    if scenario == "offline":
        return None

    ranges = {
        "humidity": (0.0, 100.0, 8.0, 108.0),
        "temperature": (-5.0, 60.0, -10.0, 70.0),
        "soil_moisture": (0.0, 100.0, 5.0, 110.0),
    }
    low, high, low_fault, high_fault = ranges[sensor]
    current = reading[sensor]

    if scenario == "low":
        reading[sensor] = low_fault
    elif scenario == "high":
        reading[sensor] = high_fault
    elif scenario == "spike":
        reading[sensor] = high_fault
    elif scenario == "flatline":
        key = (reading["node_id"], sensor)
        flatline_values.setdefault(key, current)
        reading[sensor] = flatline_values[key]

    log.info(
        "TARGETED SENSOR TEST node=%s sensor=%s scenario=%s value=%s",
        reading["node_id"], sensor, scenario, reading[sensor],
    )
    return reading


def post_reading(client, reading):
    try:
        response = client.post(API_URL, json=reading, timeout=5)
        if response.status_code != 201:
            log.warning("API rejected reading: %s %s", response.status_code, response.text)
        else:
            log.info(
                "POSTED %s moisture=%s temperature=%s humidity=%s valid=%s",
                reading["node_id"], reading["soil_moisture"],
                reading["temperature"], reading["humidity"],
                response.json().get("valid"),
            )
    except httpx.HTTPError as exc:
        log.error("Could not reach API at %s: %s", API_URL, exc)


def run(fast=False, hours=None, sensor=None, scenario="normal", node=None, start=None):
    fields = make_fields()
    if node:
        fields = [field for field in fields if field.node_id == node]
    sim_time = start or datetime.now(timezone.utc)
    end_time = sim_time + timedelta(hours=hours) if hours else None
    sleep_seconds = 0.05 if fast else READING_INTERVAL_MIN * 60
    flatline_values = {}

    mode = f"{sensor}/{scenario} on {node}" if sensor else "all sensors / natural variation"
    log.info("Starting simulation: mode=%s fast=%s hours=%s", mode, fast, hours)

    with httpx.Client() as client:
        while end_time is None or sim_time < end_time:
            for field in fields:
                reading = normal_reading(field, sim_time, READING_INTERVAL_MIN)
                if sensor:
                    reading = apply_sensor_scenario(reading, sensor, scenario, flatline_values)
                if reading is not None:
                    post_reading(client, reading)
                else:
                    log.warning("SIMULATED NODE OFFLINE: %s", field.node_id)
            sim_time += timedelta(minutes=READING_INTERVAL_MIN)
            time.sleep(sleep_seconds)

    log.info("Simulation finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="advance simulated time quickly")
    parser.add_argument("--hours", type=float, default=None, help="stop after N simulated hours")
    parser.add_argument("--sensor", choices=["humidity", "temperature", "soil_moisture", "water"],
                        help="test one sensor independently; omit for normal farm simulation")
    parser.add_argument("--scenario", choices=["normal", "low", "high", "spike", "flatline", "offline"],
                        default="normal", help="target sensor behaviour")
    parser.add_argument("--node", choices=NODE_IDS, help="limit the simulation to one field node")
    args = parser.parse_args()
    if args.scenario != "normal" and not args.sensor:
        parser.error("--sensor is required when using a non-normal --scenario")
    if args.scenario == "offline" and not args.sensor:
        parser.error("--sensor is required for an offline test")
    selected_sensor = "soil_moisture" if args.sensor == "water" else args.sensor
    run(args.fast, args.hours, selected_sensor, args.scenario, args.node)
