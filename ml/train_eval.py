"""Train the anomaly detector and measure it honestly.

Detectors compared:

  A. Range check only. This is what the backend does today.
  B. Simple rules on the features: range check, a drop rule and a stuck
     sensor rule. This is the fair baseline. If the ML cannot beat simple
     rules it has not earned a place in the project.
  C. IsolationForest, trained on normal data only.
  D. Local Outlier Factor (novelty mode), trained on normal data only.

C and D are unsupervised because in a real deployment you will not have many
labelled faults to learn from.

Four separate data sets, so nothing is judged on data it was tuned on:
  train_clean   fit the models                     (normal data only)
  val_clean     set each alarm threshold           (normal data only)
  val_faulty    choose between the ML models       (has labelled faults)
  test_faulty   final report, used once            (has labelled faults)

Assumption, stated plainly: the model learns from a period of normal data.
In the field that means the first weeks after install, checked by a person.
Each alarm threshold is set so that at most FALSE_ALARM_BUDGET of normal
readings raise an alarm.

Everything here uses SIMULATED faults. Passing this test shows the pipeline
works. It does NOT prove the real-world 85 percent target. That needs real
sensors with faults created on purpose.

Run:
    python make_dataset.py --days 60 --seed 1 --no-faults --out data/train_clean.csv
    python make_dataset.py --days 14 --seed 2 --no-faults --out data/val_clean.csv
    python make_dataset.py --days 30 --seed 4 --out data/val_faulty.csv
    python make_dataset.py --days 30 --seed 6 --out data/test_faulty.csv
    python train_eval.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURES, build_features, out_of_range

HERE = Path(__file__).parent
FALSE_ALARM_BUDGET = 0.005
FAULTS = ["spike_out_of_range", "implausible_drop", "flatline"]


def load(name):
    return build_features(pd.read_csv(HERE / "data" / name))


def dequantize(train, cols=None):
    """Readings are rounded to 0.1, so normal training rows repeat exactly. Distance based
    models such as LOF divide by neighbour distances, and exact duplicates make those blow
    up (scores of minus hundreds of millions for normal rows). Adding noise smaller than
    the rounding step removes the fake duplicates without changing what the data means."""
    rng = np.random.default_rng(0)
    cols = cols or FEATURES
    out = train[cols].copy()
    for col in ["moisture", "rise", "drop", "roll_std6", "dev_med12"]:
        if col in out.columns:
            out[col] = out[col] + rng.uniform(-0.05, 0.05, len(out))
    return out


def metrics(y, pred):
    y, pred = np.asarray(y).astype(bool), np.asarray(pred).astype(bool)
    tp, fp = int((y & pred).sum()), int((~y & pred).sum())
    fn, tn = int((y & ~pred).sum()), int((~y & ~pred).sum())
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, accuracy=round((tp + tn) / n, 4), precision=round(prec, 4),
                recall=round(rec, 4), f1=round(f1, 4), false_alarm_rate=round(fp / (fp + tn), 4))


def stuck_run_length(val_clean):
    for n in range(2, 30):
        if (val_clean["same_count"] >= n).mean() <= FALSE_ALARM_BUDGET:
            return n
    return 30


def evaluate(df, preds):
    y = df["label"]
    out = {}
    for name, p in preds.items():
        m = metrics(y, p)
        m["by_fault_type"] = {
            ft: dict(rows=int((df["fault_type"] == ft).sum()), caught=int(p[df["fault_type"] == ft].sum()),
                     recall=round(float(p[df["fault_type"] == ft].mean()), 3)) for ft in FAULTS}
        out[name] = m
    return out


def show(title, df, res):
    y = df["label"]
    print(f"\n{title}: {len(df)} readings, {int(y.sum())} anomalous ({y.mean():.1%}). "
          f"Never alarming would score {1 - y.mean():.1%} accuracy.")
    print(f"{'detector':24}{'accuracy':>9}{'precision':>10}{'recall':>8}{'F1':>6}{'false alarms':>13}")
    for name, m in res.items():
        print(f"{name:24}{m['accuracy']:>9.1%}{m['precision']:>10.1%}{m['recall']:>8.1%}{m['f1']:>6.2f}{m['fp']:>13}")
    print("Caught / total by fault type:")
    for name, m in res.items():
        print(f"  {name:24}" + ",  ".join(f"{ft} {v['caught']}/{v['rows']}" for ft, v in m["by_fault_type"].items()))


def main():
    train, val_clean = load("train_clean.csv"), load("val_clean.csv")
    val_f, test_f = load("val_faulty.csv"), load("test_faulty.csv")

    # Thresholds for the rules come from normal data only
    drop_rule = max(2.0, 2 * float(train["drop"].max()))
    stuck_n = stuck_run_length(val_clean)

    # ML candidates, fitted on normal data only, thresholds set on normal validation data
    candidates = {
        "C_isolation_forest": make_pipeline(StandardScaler(), IsolationForest(n_estimators=300, random_state=0, n_jobs=-1)),
        "D_local_outlier_factor": make_pipeline(StandardScaler(), LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1)),
    }
    thresholds = {}
    for name, pipe in candidates.items():
        pipe.fit(dequantize(train))
        thresholds[name] = float(np.quantile(pipe.score_samples(val_clean[FEATURES]), FALSE_ALARM_BUDGET))

    def predict_all(df):
        preds = {
            "A_range_check_only": out_of_range(df),
            "B_simple_rules": out_of_range(df) | (df["drop"] > drop_rule) | (df["same_count"] >= stuck_n),
        }
        for name, pipe in candidates.items():
            preds[name] = pd.Series(pipe.score_samples(df[FEATURES]) < thresholds[name], index=df.index)
        return preds

    # Choose the ML model on the validation set with faults. The test set is not touched here.
    val_res = evaluate(val_f, predict_all(val_f))
    best = max(candidates, key=lambda n: val_res[n]["f1"])
    show("MODEL SELECTION on val_faulty", val_f, val_res)
    print(f"\nChosen ML model (highest F1 on validation): {best}")

    # Final report on the unseen test set
    test_res = evaluate(test_f, predict_all(test_f))
    show("FINAL TEST on test_faulty (unseen)", test_f, test_res)

    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "metrics.json").write_text(json.dumps({
        "chosen_ml_model": best, "drop_rule": round(drop_rule, 2), "stuck_rule_run_length": stuck_n,
        "false_alarm_budget": FALSE_ALARM_BUDGET, "validation": val_res, "test": test_res}, indent=2))
    (HERE / "models").mkdir(exist_ok=True)
    joblib.dump({"model": candidates[best], "threshold": thresholds[best], "features": FEATURES, "name": best},
                HERE / "models" / "anomaly_model.joblib")
    print(f"\nSaved models/anomaly_model.joblib and results/metrics.json. Drop rule {drop_rule:.2f}, stuck rule {stuck_n} in a row.")


if __name__ == "__main__":
    main()
