"""
Labelled farm data for developing the anomaly detector.

This is a separate, offline generator. It does not post to the API. It
follows the same style as simulator/simulate.py (4 fields, readings every
5 minutes, dry-down, rain, a day and night curve) but adds two things the
live simulator does not have:

  1. Ground truth. Every row says whether it is normal or which fault it is.
  2. Faults that a range check cannot catch. A stuck (flatlined) sensor and
     a sudden implausible drop that stays inside 0 to 100 percent.

A simulated farmer also waters a field when it gets very dry, so moisture
moves up and down like a real field instead of sitting at the floor.

Faults injected (label = 1):
  spike_out_of_range   one reading outside physical limits (999, -50, 250)
  implausible_drop     one reading that falls 20 to 40 points in 5 minutes
  flatline             the sensor repeats one exact value for 30 to 120 minutes
  (offline gaps are also injected, but a silent node has no row to label,
   so it is detected by watching for missing readings, not by this model)

Usage:
    python make_dataset.py --days 60 --seed 1 --no-faults --out data/train_clean.csv
    python make_dataset.py --days 30 --seed 3 --out data/test_faulty.csv
"""
import argparse
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

STEP_MIN = 5
NODES = [
    # node_id, start moisture, dry rate (% per hour), base temp, base humidity
    ("node-01", 45, 1.8, 27, 58),
    ("node-02", 30, 2.4, 29, 52),
    ("node-03", 50, 1.5, 26, 61),
    ("node-04", 22, 2.1, 28, 55),
]
RAIN_CHANCE_PER_HOUR = 0.03
IRRIGATE_BELOW = 20.0     # the simulated farmer waters when moisture falls to this
IRRIGATE_GAIN = 25.0
SENSOR_NOISE = 0.15       # real sensors jitter a little, even in still soil

# Per reading, per field. Only used when faults are enabled.
P_SPIKE = 0.0012
P_DROP = 0.0012
P_FLATLINE_START = 0.0006
P_OFFLINE_START = 0.0005

# Extra faults, only used with extra=True. The rules in train_eval.py were NOT
# written with these in mind, which is the point of the test.
P_NOISY_START = 0.0004     # noisy_burst: readings jitter wildly around the truth
P_DRIFT_START = 0.0003     # slow_drift: the reading creeps away from the truth
P_OFFSET_START = 0.0004    # step_offset: the reading is shifted by 8 to 15 points
NOISY_SIGMA = 1.2


def diurnal(base, hour, amp, shift, rng):
    return base + amp * math.sin((hour - 9) / 24 * 2 * math.pi) * shift + rng.uniform(-0.4, 0.4)


def generate(days: int, seed: int, faults: bool, start: datetime, extra: bool = False) -> pd.DataFrame:
    rng = random.Random(seed)
    steps = int(days * 24 * 60 / STEP_MIN)
    state = {
        n: dict(moisture=m, dry=d, tbase=t, hbase=h, stuck_left=0, stuck_val=None, offline_left=0, last_posted=m,
             noisy_left=0, drift_left=0, drift_offset=0.0, drift_step=0.0, offset_left=0, offset_val=0.0)
        for n, m, d, t, h in NODES
    }
    rows = []
    for i in range(steps):
        ts = start + timedelta(minutes=STEP_MIN * i)
        hour = ts.hour + ts.minute / 60
        for node_id, _, _, _, _ in NODES:
            s = state[node_id]

            # true soil moisture evolves whether or not the sensor is healthy
            hours = STEP_MIN / 60
            s["moisture"] -= s["dry"] * hours * rng.uniform(0.85, 1.15)
            if rng.random() < RAIN_CHANCE_PER_HOUR * hours:
                s["moisture"] += rng.uniform(15, 35)
            if s["moisture"] <= IRRIGATE_BELOW:
                s["moisture"] += IRRIGATE_GAIN
            s["moisture"] = max(2.0, min(100.0, s["moisture"]))

            posted = max(0.0, min(100.0, s["moisture"] + rng.gauss(0, SENSOR_NOISE)))  # firmware clamps to 0 to 100
            temp = round(diurnal(s["tbase"], hour, 6, 1, rng), 1)
            hum = round(max(10, min(100, diurnal(s["hbase"], hour, 8, -1, rng))), 1)
            label, fault = 0, "none"

            if faults:
                if s["offline_left"] > 0:
                    s["offline_left"] -= 1
                    continue                      # silent node, no row at all
                if s["stuck_left"] > 0:
                    s["stuck_left"] -= 1
                    posted, label, fault = s["stuck_val"], 1, "flatline"
                else:
                    r = rng.random()
                    if r < P_OFFLINE_START:
                        s["offline_left"] = rng.choice([3, 6, 12])
                        continue
                    elif r < P_OFFLINE_START + P_FLATLINE_START:
                        s["stuck_left"] = rng.randint(6, 24) - 1
                        s["stuck_val"] = s["last_posted"]
                        posted, label, fault = s["stuck_val"], 1, "flatline"
                    elif r < P_OFFLINE_START + P_FLATLINE_START + P_SPIKE:
                        posted, label, fault = rng.choice([999.0, -50.0, 250.0]), 1, "spike_out_of_range"
                    elif r < P_OFFLINE_START + P_FLATLINE_START + P_SPIKE + P_DROP and s["moisture"] >= 35:
                        posted, label, fault = s["moisture"] - rng.uniform(20, 40), 1, "implausible_drop"

            if extra and faults and fault == "none":
                clamp = lambda v: max(0.0, min(100.0, v))
                if s["noisy_left"] > 0:
                    s["noisy_left"] -= 1
                    posted, label, fault = clamp(s["moisture"] + rng.gauss(0, NOISY_SIGMA)), 1, "noisy_burst"
                elif s["drift_left"] > 0:
                    s["drift_left"] -= 1
                    s["drift_offset"] += s["drift_step"]
                    posted, label, fault = clamp(s["moisture"] + s["drift_offset"]), 1, "slow_drift"
                elif s["offset_left"] > 0:
                    s["offset_left"] -= 1
                    posted, label, fault = clamp(s["moisture"] + s["offset_val"]), 1, "step_offset"
                else:
                    r2 = rng.random()
                    if r2 < P_NOISY_START:
                        s["noisy_left"] = rng.randint(6, 18) - 1
                        posted, label, fault = clamp(s["moisture"] + rng.gauss(0, NOISY_SIGMA)), 1, "noisy_burst"
                    elif r2 < P_NOISY_START + P_DRIFT_START:
                        s["drift_left"] = rng.randint(24, 48) - 1
                        s["drift_step"] = rng.choice([-1, 1]) * rng.uniform(0.4, 0.8)
                        s["drift_offset"] = s["drift_step"]
                        posted, label, fault = clamp(s["moisture"] + s["drift_offset"]), 1, "slow_drift"
                    elif r2 < P_NOISY_START + P_DRIFT_START + P_OFFSET_START:
                        s["offset_left"] = rng.randint(12, 48) - 1
                        s["offset_val"] = rng.choice([-1, 1]) * rng.uniform(8, 15)
                        posted, label, fault = clamp(s["moisture"] + s["offset_val"]), 1, "step_offset"

            posted = round(posted, 1)
            if fault in ("none", "implausible_drop"):
                s["last_posted"] = posted
            rows.append((ts.isoformat(), node_id, posted, temp, hum, label, fault))

    return pd.DataFrame(rows, columns=["timestamp", "node_id", "soil_moisture", "temperature", "humidity", "label", "fault_type"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-faults", action="store_true", help="clean data, no injected faults")
    ap.add_argument("--extra-faults", action="store_true", help="also inject noisy_burst, slow_drift and step_offset")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    df = generate(args.days, args.seed, faults=not args.no_faults, start=start, extra=args.extra_faults)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"wrote {len(df)} rows to {args.out}")
    print(df["fault_type"].value_counts().to_string())
