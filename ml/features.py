"""Turn raw readings into the numbers the anomaly model looks at.

Works on any table with node_id, timestamp and soil_moisture, so it will
work the same on simulated data now and on readings from the real database
later.

Four features per reading, calculated separately for each node:
  moisture     the reading itself
  rise         how far it went UP since the last valid reading (valid = inside 0 to 100)
  drop         how far it went DOWN since the last valid reading
  same_count   how many readings in a row have had exactly this value

Why these: an impossible value shows up in moisture, a sudden fall that
stays in range shows up in drop, and a stuck sensor shows up in same_count.
Rain and watering make rise jump, which is normal. Soil only dries slowly,
so a big drop is never normal. Splitting the change into rise and drop lets
the model learn that difference. With one signed change column, an
IsolationForest scored sudden drops as ordinary.
"""
import numpy as np
import pandas as pd

FEATURES = ["moisture", "rise", "drop", "same_count"]
FEATURES_V2 = FEATURES + ["roll_std6", "dev_med12"]   # generic extras, see build_features

LIMITS = {  # same physical limits the backend already uses (backend/app/validation.py)
    "soil_moisture": (0.0, 100.0),
    "temperature": (-5.0, 60.0),
    "humidity": (0.0, 100.0),
}


def out_of_range(df: pd.DataFrame) -> pd.Series:
    """What the backend's validation catches today."""
    bad = pd.Series(False, index=df.index)
    for col, (low, high) in LIMITS.items():
        if col in df.columns:
            bad |= (df[col] < low) | (df[col] > high)
    return bad


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["node_id", "timestamp"]).copy()
    lo, hi = LIMITS["soil_moisture"]
    parts = []
    for _, g in df.groupby("node_id", sort=False):
        g = g.copy()
        m = g["soil_moisture"]
        valid_m = m.where((m >= lo) & (m <= hi))
        prev_valid = valid_m.ffill().shift(1)
        g["moisture"] = m
        d1 = (m - prev_valid).fillna(0.0)
        g["rise"] = d1.clip(lower=0.0)
        g["drop"] = (-d1).clip(lower=0.0)
        run_id = (m != m.shift(1)).cumsum()
        g["same_count"] = g.groupby(run_id).cumcount() + 1
        # Generic extras that look for several families of fault at once, not one rule per fault:
        #   roll_std6   how jumpy the last 6 valid readings are (a noisy sensor)
        #   dev_med12   distance from the median of the previous 12 valid readings (shifts and drift)
        g["roll_std6"] = valid_m.rolling(6, min_periods=3).std().ffill().fillna(0.0)
        g["dev_med12"] = (m - valid_m.shift(1).rolling(12, min_periods=3).median()).fillna(0.0)
        parts.append(g)
    out = pd.concat(parts).sort_index()
    return out
