"""Jury 2: descriptive clinical profiling using actual historical encounters.

All rates are observational. No claim that the features cause readmission.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from jury2_features import diagnosis_group, LABELS

ROOT = Path(__file__).resolve().parents[1]


def cohort_table(df: pd.DataFrame, column: str, min_count: int = 0) -> pd.DataFrame:
    result = df.groupby(column, observed=True).agg(
        encounters=("readmitted", "size"),
        readmitted_within_30=("is_readmitted_30", "sum"),
        readmission_rate_30=("is_readmitted_30", "mean"),
        avg_length_of_stay=("time_in_hospital", "mean"),
        avg_medications=("num_medications", "mean"),
    ).reset_index()
    result = result[result["encounters"] >= min_count]
    result["readmission_rate_30_pct"] = (100 * result.pop("readmission_rate_30")).round(2)
    return result.sort_values("encounters", ascending=False)


def chart(df: pd.DataFrame, field: str, out: Path, title: str):
    ordered = df.sort_values("readmission_rate_30_pct")
    fig, ax = plt.subplots(figsize=(10, max(4, 0.38 * len(ordered) + 1)))
    ax.barh(ordered[field].astype(str), ordered["readmission_rate_30_pct"])
    ax.set_xlabel("Historical readmission within 30 days (%)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "diabetes_130_us.csv")
    ap.add_argument("--output", type=Path, default=ROOT / "jury_2_dw" / "outputs")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.data, low_memory=False).replace("?", np.nan)
    df = df[df["readmitted"].isin(LABELS)].copy()
    df["is_readmitted_30"] = df["readmitted"].eq("<30").astype(int)
    for col in ["time_in_hospital", "num_medications", "number_inpatient"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["diagnosis_group"] = df["diag_1"].map(diagnosis_group)
    df["medication_load"] = pd.cut(df["num_medications"],
        bins=[-np.inf, 5, 10, 20, np.inf], labels=["0–5", "6–10", "11–20", "21+"])
    df["prior_inpatient_visits"] = pd.cut(df["number_inpatient"],
        bins=[-np.inf, 0, 1, np.inf], labels=["0", "1", "2+"])
    df["stay_group"] = pd.cut(df["time_in_hospital"], bins=[0,3,7,14], labels=["1-3 days", "4-7 days", "8-14 days"])
    summary = {
        "dataset_encounters": int(len(df)),
        "unique_patients": int(df["patient_nbr"].nunique()),
        "readmission_counts": {str(k):int(v) for k,v in df["readmitted"].value_counts().items()},
        "readmission_under_30_pct": round(float(df["is_readmitted_30"].mean() * 100), 2),
        "mean_length_of_stay_days": round(float(df["time_in_hospital"].mean()), 2),
        "mean_medications": round(float(df["num_medications"].mean()), 2),
        "scope": "Retrospective, observational analysis of historic diabetes hospital encounters",
    }
    (args.output / "clinical_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    specs = [
        ("stay_group", "profile_stay.csv", "profile_stay.png", 0, "Readmission rates by length of stay"),
        ("age", "profile_age.csv", "profile_age.png", 0, "Readmission rates by age group"),
        ("diagnosis_group", "profile_diagnosis.csv", "profile_diagnosis.png", 500, "Readmission rates by primary diagnosis"),
        ("medication_load", "profile_medications.csv", "profile_medications.png", 0, "Readmission rates by medication count"),
        ("prior_inpatient_visits", "profile_prior_inpatient.csv", "profile_prior_inpatient.png", 0,
         "Readmission rates by previous inpatient visits"),
    ]
    for col, csv, png, min_count, title in specs:
        table = cohort_table(df, col, min_count=min_count)
        table.to_csv(args.output / csv, index=False)
        chart(table, col, args.output / png, title)
    print("CLINICAL DATA SUMMARY\n", json.dumps(summary, indent=2), flush=True)
    print("Saved historical profiles to", args.output.resolve(), flush=True)


if __name__ == "__main__":
    main()
