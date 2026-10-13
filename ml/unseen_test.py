"""Do the detectors catch faults nobody wrote a rule for?

The first test used the three faults the simple rules were designed around.
This one adds three new fault types and asks which detector copes:

  noisy_burst   the reading jitters wildly around the truth for 30 to 90 minutes
  slow_drift    the reading creeps away from the truth, a little more each time
  step_offset   the reading is shifted by 8 to 15 points (up or down) for hours

Detectors:
  B   simple rules from train_eval.py, unchanged
  D1  Local Outlier Factor with the original 4 features, unchanged
  D2  Local Outlier Factor with 2 extra generic features (roll_std6, dev_med12)

D2 is an honest question, not a blind test: I added those features knowing
noisy and shifted sensors exist. What it tests is whether an unsupervised
model can absorb new fault families by adding features once, instead of
writing one new rule per fault.

Scoring:
  * Row level recall and precision, as before.
  * Event recall: a fault event counts as caught if any reading inside it
    raised an alarm. This matters for alerts, where one alarm per event is enough.
  * False alert episodes: a run of consecutive false alarms counts once.
  * The 6 readings after a fault ends are ignored when counting false alarms,
    because rolling features legitimately stay disturbed for a few readings.

Two extra detectors test a practical design:
  D2P  D2 but an alarm needs 3 readings in a row, to cut false alerts
  E    hybrid: the simple rules (instant, for known faults) OR D2P (for the unknown)
The 3 in a row setting was chosen after seeing seed 9 results, so seed 10 is a
fresh data set that confirms it. Judge the hybrid on seed 10.

Small samples: each new fault type has only about a dozen events. Read the
event counts, not just the percentages.

Run (after run_all.py has created the clean data):
    python unseen_test.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURES, FEATURES_V2, build_features, out_of_range
from make_dataset import generate
from train_eval import FALSE_ALARM_BUDGET, dequantize, load, stuck_run_length

HERE = Path(__file__).parent
ALL_FAULTS = ["spike_out_of_range", "implausible_drop", "flatline", "noisy_burst", "slow_drift", "step_offset"]
GRACE = 6


def lof(cols, train, val):
    pipe = make_pipeline(StandardScaler(), LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1))
    pipe.fit(dequantize(train, cols))
    thr = float(np.quantile(pipe.score_samples(val[cols]), FALSE_ALARM_BUDGET))
    return lambda df: pd.Series(pipe.score_samples(df[cols]) < thr, index=df.index)


def persist(pred, df, n=3):
    """True only where the last n readings of that node were all alarms."""
    p = pred.reindex(df.index).astype(int)
    return (p.groupby(df["node_id"]).transform(lambda x: x.rolling(n).sum()) == n).fillna(False)


def prepare(df):
    """Sort, mark events, mark the grace window after each fault."""
    df = df.sort_values(["node_id", "timestamp"]).copy()
    key = df["node_id"] + "|" + df["fault_type"]
    df["event_id"] = (key != key.shift(1)).cumsum()
    df["grace"] = (df.groupby("node_id")["label"].transform(lambda s: s.rolling(GRACE + 1, min_periods=1).max()) == 1) & (df["label"] == 0)
    return df


def score(df, pred):
    pred = pred.reindex(df.index)
    fault, normal = df["label"] == 1, (df["label"] == 0) & ~df["grace"]
    tp, fn = int((pred & fault).sum()), int((~pred & fault).sum())
    fp, tn = int((pred & normal).sum()), int((~pred & normal).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0

    flagged_normal = (pred & normal)
    episodes = int((flagged_normal & ~flagged_normal.groupby(df["node_id"]).shift(1, fill_value=False)).sum())

    per_type = {}
    ev = df[fault].assign(pred=pred[fault]).groupby(["fault_type", "event_id"])["pred"].any().reset_index()
    for ft in ALL_FAULTS:
        e = ev[ev["fault_type"] == ft]
        rows = df["fault_type"] == ft
        per_type[ft] = dict(events=int(len(e)), events_caught=int(e["pred"].sum()),
                            rows=int(rows.sum()), rows_caught=int((pred & rows).sum()))
    return dict(recall=round(rec, 3), precision=round(prec, 3), false_alarm_rows=fp,
                false_alert_episodes=episodes, by_fault_type=per_type)


def run_seed(seed, train, val, detectors_ready):
    path = HERE / "data" / f"test_unseen_seed{seed}.csv"
    generate(30, seed, faults=True, start=datetime(2026, 10, 1, tzinfo=timezone.utc), extra=True).to_csv(path, index=False)
    test = prepare(build_features(pd.read_csv(path)))
    base = {n: fn(test) for n, fn in detectors_ready.items()}
    base["D2P_LOF_6_3_in_a_row"] = persist(base["D2_LOF_6_features"], test, 3)
    base["E_hybrid_B_or_D2P"] = base["B_simple_rules"] | base["D2P_LOF_6_3_in_a_row"]
    results = {n: score(test, p) for n, p in base.items()}

    nf = int(test["label"].sum())
    print(f"\n=== seed {seed}: {len(test)} readings, {nf} faulty rows ({nf / len(test):.1%}), "
          f"{test[test.label == 1]['event_id'].nunique()} fault events ===")
    print(f"{'detector':24}{'row recall':>11}{'precision':>10}{'false alarm rows':>17}{'false alert episodes':>22}")
    for n, r in results.items():
        print(f"{n:24}{r['recall']:>11.1%}{r['precision']:>10.1%}{r['false_alarm_rows']:>17}{r['false_alert_episodes']:>22}")
    print("Events caught / events (any alarm during the event):")
    print(f"{'':24}" + "".join(f"{ft[:14]:>16}" for ft in ALL_FAULTS))
    for n, r in results.items():
        print(f"{n:24}" + "".join(f"{str(v['events_caught']) + '/' + str(v['events']):>16}" for v in r["by_fault_type"].values()))

    # Why D1 looks good on shifted and drifting sensors: check where those readings sit
    lo, hi = train["moisture"].min(), train["moisture"].max()
    inside = test["moisture"].between(lo, hi)
    print(f"Alarm rate of D1 on faulty rows, inside vs outside the clean training range ({lo:.1f} to {hi:.1f}):")
    for ft in ["noisy_burst", "slow_drift", "step_offset"]:
        m = test["fault_type"] == ft
        o, i = m & ~inside, m & inside
        print(f"  {ft:12} inside {base['D1_LOF_4_features'][i].mean():>6.1%} ({int(i.sum())} rows)   "
              f"outside {base['D1_LOF_4_features'][o].mean() if o.any() else float('nan'):>6.1%} ({int(o.sum())} rows)")
    return results


def main():
    train, val = load("train_clean.csv"), load("val_clean.csv")
    drop_rule = max(2.0, 2 * float(train["drop"].max()))
    stuck_n = stuck_run_length(val)
    ready = {
        "A_range_check_only": lambda d: out_of_range(d),
        "B_simple_rules": lambda d: out_of_range(d) | (d["drop"] > drop_rule) | (d["same_count"] >= stuck_n),
        "D1_LOF_4_features": lof(FEATURES, train, val),
        "D2_LOF_6_features": lof(FEATURES_V2, train, val),
    }
    out = {f"seed_{sd}": run_seed(sd, train, val, ready) for sd in (9, 10)}
    (HERE / "results" / "metrics_unseen.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
