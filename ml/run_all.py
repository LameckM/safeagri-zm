"""One command to rebuild the data and run the whole evaluation.

    python run_all.py

It creates four simulated data sets (same seeds every time, so you get the
same numbers), trains the models and prints the comparison, then runs the
unseen fault test (faults the simple rules were not written for).
"""
from datetime import datetime, timezone
from pathlib import Path

from make_dataset import generate
import train_eval
import unseen_test

DATA = Path(__file__).parent / "data"
START = datetime(2026, 10, 1, tzinfo=timezone.utc)

SETS = [
    # file name, days, seed, faults
    ("train_clean.csv", 60, 1, False),
    ("val_clean.csv", 14, 2, False),
    ("val_faulty.csv", 30, 4, True),
    ("test_faulty.csv", 30, 6, True),
]

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    for name, days, seed, faults in SETS:
        df = generate(days, seed, faults=faults, start=START)
        df.to_csv(DATA / name, index=False)
        print(f"wrote data/{name}: {len(df)} rows")
    train_eval.main()
    print("\n" + "=" * 70 + "\nUNSEEN FAULT TEST")
    unseen_test.main()
