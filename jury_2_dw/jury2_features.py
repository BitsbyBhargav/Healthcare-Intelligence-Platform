"""Shared, reproducible feature definitions for discharge-time readmission risk.

Only use fields available by discharge; never use identifiers or target fields as inputs.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

LABELS = ["NO", ">30", "<30"]  # fixed class order for reports and Streamlit
NUMERIC = [
    "time_in_hospital", "num_lab_procedures", "num_procedures",
    "num_medications", "number_outpatient", "number_emergency",
    "number_inpatient", "number_diagnoses",
]
CATEGORICAL = [
    "age", "gender", "race", "admission_type_id", "insulin",
    "change", "diabetesMed", "A1Cresult", "diag_1_group", "diag_2_group",
]
FEATURES = NUMERIC + CATEGORICAL


def diagnosis_group(code: object) -> str:
    """Map detailed ICD-9 diagnosis strings into defensible broad categories."""
    if pd.isna(code) or str(code).strip() in ("", "?"):
        return "Unknown"
    value = str(code).strip().upper()
    if value.startswith("V"):
        return "Supplementary_V"
    if value.startswith("E"):
        return "External_Cause_E"
    match = re.match(r"^(\d{1,3})(?:\.\d+)?$", value)
    if not match:
        return "Other"
    n = int(match.group(1))
    if n == 250: return "Diabetes"
    for lo, hi, label in [
        (1,139,"Infectious"), (140,239,"Neoplasms"),
        (240,279,"Endocrine"), (280,289,"Blood"),
        (290,319,"Mental"), (320,389,"Nervous"),
        (390,459,"Circulatory"), (460,519,"Respiratory"),
        (520,579,"Digestive"), (580,629,"Genitourinary"),
        (630,679,"Pregnancy"), (680,709,"Skin"),
        (710,739,"Musculoskeletal"), (740,759,"Congenital"),
        (760,779,"Perinatal"), (780,799,"Symptoms"),
        (800,999,"Injury")
    ]:
        if lo <= n <= hi:
            return label
    return "Other"


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Construct identical columns for model training and future UI inference."""
    df = raw.mask(raw.eq("?")).copy()
    df["diag_1_group"] = df.get("diag_1", pd.Series(index=df.index, dtype=object)).map(diagnosis_group)
    df["diag_2_group"] = df.get("diag_2", pd.Series(index=df.index, dtype=object)).map(diagnosis_group)
    for col in FEATURES:
        if col not in df.columns:
            df[col] = np.nan
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in CATEGORICAL:
        df[col] = df[col].astype("string").fillna("Unknown").astype(str)
    return df[FEATURES].copy()
