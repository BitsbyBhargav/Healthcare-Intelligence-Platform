"""Export a small, reproducible Jury 2 demonstration dataset for Orange 3.

Run in the Healthcare-Intelligence-Platform repository root:
  python jury_2_dw/orange_demo/prepare_orange_data.py

This is a supplementary visual-platform experiment, NOT the benchmark used in
Streamlit. One first encounter per patient prevents repeated-patient leakage
in Orange's ordinary cross-validation. No identifiers or readmission-derived
predictors are included in the classification features.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

DEMO_DIR = Path(__file__).resolve().parent
JURY_DIR = DEMO_DIR.parent
ROOT = JURY_DIR.parent
sys.path.insert(0, str(JURY_DIR))
from jury2_features import FEATURES, NUMERIC, CATEGORICAL, build_features, diagnosis_group

MEDICATIONS = [
    "metformin", "repaglinide", "nateglinide", "chlorpropamide",
    "glimepiride", "glipizide", "glyburide", "pioglitazone",
    "rosiglitazone", "acarbose", "miglitol", "insulin",
    "glyburide-metformin", "glipizide-metformin",
]
ACTIVE = {"steady", "up", "down"}


def save_orange_tab(df: pd.DataFrame, path: Path, numeric=(), target=None) -> None:
    """Orange native 3-header .tab format specifies variable types and class."""
    names = list(df.columns)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(names)
        writer.writerow(["c" if name in numeric else "d" for name in names])
        writer.writerow(["class" if name == target else "" for name in names])
        writer.writerows(df.itertuples(index=False, name=None))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "diabetes_130_us.csv")
    parser.add_argument("--rows", type=int, default=3000,
                        help="Maximum unique patients in the sample (default 3000)")
    args = parser.parse_args()
    if args.rows < 200:
        parser.error("Use at least 200 rows for a meaningful supplementary demo")
    if not args.data.is_file():
        parser.error(f"Dataset not found: {args.data}")

    df = pd.read_csv(args.data, low_memory=False)
    required = {"patient_nbr", "readmitted", "diag_1", "diag_2"}
    missing = required - set(df.columns)
    if missing:
        parser.error("Missing required source columns: " + ", ".join(sorted(missing)))
    if "encounter_id" in df:
        df = df.sort_values("encounter_id", kind="stable")
    df = df.drop_duplicates(subset="patient_nbr", keep="first")
    df = df.loc[df["readmitted"].isin(["NO", ">30", "<30"])]
    sample = df.sample(n=min(args.rows, len(df)), random_state=42).copy()

    # Classification: the same feature definitions as the main project,
    # but a different experiment / data sample from the full benchmark.
    model_features = build_features(sample)
    for name in NUMERIC:
        vals = pd.to_numeric(model_features[name], errors="coerce")
        model_features[name] = vals.fillna(vals.median() if vals.notna().any() else 0)
    for name in CATEGORICAL:
        model_features[name] = model_features[name].fillna("Unknown").astype(str)
    classification = model_features[FEATURES].copy()
    classification["readmitted"] = sample["readmitted"].values
    save_orange_tab(classification, DEMO_DIR / "orange_classification.tab",
                    numeric=NUMERIC, target="readmitted")
    classification.to_csv(DEMO_DIR / "orange_classification.csv", index=False)

    # Association: absent medication is marked as '?' (missing), rather than
    # turning the dominant 'No' medication values into mined basket items.
    rule_data = pd.DataFrame(index=sample.index)
    for dg in ("diag_1", "diag_2", "diag_3"):
        raw_dg = sample[dg] if dg in sample else pd.Series(index=sample.index, dtype=object)
        rule_data[f"DIAG_{dg}"] = raw_dg.map(diagnosis_group).replace("Unknown", "?")
    for medication in MEDICATIONS:
        statuses = (sample[medication] if medication in sample
                    else pd.Series("No", index=sample.index))
        rule_data[f"MED_{medication}"] = statuses.astype(str).str.lower().isin(ACTIVE).map(
            {True: "Active", False: "?"})
    # There is deliberately NO class column in association baskets.
    save_orange_tab(rule_data, DEMO_DIR / "orange_associations.tab")
    rule_data.to_csv(DEMO_DIR / "orange_associations.csv", index=False)

    print(f"Exported {len(sample):,} encounters representing {sample['patient_nbr'].nunique():,} distinct patients")
    print("Classes:", sample["readmitted"].value_counts().to_dict())
    print("Orange classification File widget ->", DEMO_DIR / "orange_classification.tab")
    print("Orange association File widget     ->", DEMO_DIR / "orange_associations.tab")
    print("Note: Orange experiment scores will differ from the full Python benchmark.")


if __name__ == "__main__":
    main()
