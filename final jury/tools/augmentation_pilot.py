"""Training-only synthetic augmentation pilot; no SPARCS inputs or inferred labels.

Use the existing environment plus the locally installed .vendor imbalanced-learn.
This experiment does not mark the later classification jury blocks complete.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vendor"))

import hashlib
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTENC
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from scipy.sparse import csr_matrix, hstack

DATA = ROOT / "data" / "processed" / "augmentation_pilot"
REPORT = ROOT / "A_warehouse_design" / "augmentation_pilot"
NUM = ["time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
       "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses"]
CAT = ["age", "gender", "race", "admission_type_id", "admission_source_id", "insulin",
       "change", "diabetesMed", "A1Cresult", "max_glu_serum", "primary_diagnosis_group"]
LABELS = ["NO", ">30", "<30"]


def save(name, value):
    (REPORT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def diagnosis_group(series):
    number = pd.to_numeric(series, errors="coerce")
    result = pd.Series("Other", index=series.index, dtype="string")
    for lo, hi, name in [(1,139,"Infectious"),(140,239,"Neoplasms"),(240,279,"Endocrine"),
                         (280,289,"Blood"),(290,319,"Mental"),(320,389,"Nervous"),
                         (390,459,"Circulatory"),(460,519,"Respiratory"),(520,579,"Digestive"),
                         (580,629,"Genitourinary"),(630,679,"Pregnancy"),(680,709,"Skin"),
                         (710,739,"Musculoskeletal"),(740,759,"Congenital"),
                         (760,779,"Perinatal"),(780,799,"Symptoms"),(800,999,"Injury")]:
        result.loc[number.ge(lo) & number.lt(hi + 1)] = name
    result.loc[number.ge(250) & number.lt(251)] = "Diabetes"
    result.loc[series.isna()] = "Missing"
    return result


def metrics(truth, predicted):
    return {"accuracy": float(accuracy_score(truth, predicted)),
            "macro_f1": float(f1_score(truth, predicted, average="macro", zero_division=0)),
            "per_class": classification_report(truth, predicted, labels=LABELS,
                                                output_dict=True, zero_division=0),
            "confusion_matrix_order": LABELS,
            "confusion_matrix": confusion_matrix(truth, predicted, labels=LABELS).tolist()}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    source = ROOT / "data" / "processed" / "uci_supervised.parquet"
    frame = pd.read_parquet(source)
    initial = len(frame)
    # No new follow-up is possible after death; hospice is excluded by this
    # prespecified pilot eligibility rule, uniformly for every comparison.
    excluded = frame["discharge_disposition_id"].isin(["11", "13", "14", "19", "20", "21"])
    frame = frame.loc[~excluded].reset_index(drop=True)
    frame["primary_diagnosis_group"] = diagnosis_group(frame["diag_1"])
    features = frame[NUM + CAT].copy()
    for field in NUM:
        features[field] = pd.to_numeric(features[field], errors="coerce")
    for field in CAT:
        features[field] = features[field].fillna("Missing").astype(str)
    target = frame["readmitted"].astype(str)
    train, other = next(GroupShuffleSplit(n_splits=1, train_size=.6, random_state=42)
                        .split(frame, target, groups=frame["patient_nbr"]))
    val_local, test_local = next(GroupShuffleSplit(n_splits=1, train_size=.5, random_state=43)
                                .split(frame.iloc[other], target.iloc[other],
                                       groups=frame.iloc[other]["patient_nbr"]))
    validation, test = other[val_local], other[test_local]
    indices = {"train": train, "validation": validation, "test": test}
    patient_sets = {key: set(frame.iloc[ix]["patient_nbr"]) for key, ix in indices.items()}
    assert not (patient_sets["train"] & patient_sets["validation"])
    assert not (patient_sets["train"] & patient_sets["test"])
    assert not (patient_sets["validation"] & patient_sets["test"])
    manifest = frame[["encounter_id", "patient_nbr", "readmitted"]].copy()
    manifest["split"] = ""
    for key, ix in indices.items():
        manifest.loc[ix, "split"] = key
    manifest.to_parquet(DATA / "real_patient_splits.parquet", index=False)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    real_train = features.iloc[train].reset_index(drop=True).copy()
    real_train[NUM] = imputer.fit_transform(real_train[NUM])
    scaler.fit(real_train[NUM])
    transformed = {}
    for key, ix in indices.items():
        x = features.iloc[ix].reset_index(drop=True).copy()
        x[NUM] = imputer.transform(x[NUM])
        transformed[key] = x
    # The sampler learns only from real training patients, after real-only
    # imputation/scaling. Validation and test records never enter this step.
    sampler_input = real_train.copy()
    sampler_input[NUM] = scaler.transform(sampler_input[NUM])
    sampler = SMOTENC(categorical_features=list(range(len(NUM), len(NUM + CAT))),
                      sampling_strategy="not majority", k_neighbors=5, random_state=42)
    print(f"Real split sizes: { {key: len(ix) for key, ix in indices.items()} }", flush=True)
    print("Generating SMOTENC training examples", flush=True)
    start = time.perf_counter()
    resampled, labels = sampler.fit_resample(sampler_input, target.iloc[train].reset_index(drop=True))
    synthetic = resampled.iloc[len(real_train):].reset_index(drop=True).copy()
    synthetic[NUM] = np.rint(scaler.inverse_transform(synthetic[NUM]))
    synthetic_target = labels.iloc[len(real_train):].reset_index(drop=True)
    for field in NUM:
        assert synthetic[field].between(real_train[field].min(), real_train[field].max()).all()
        assert synthetic[field].mod(1).eq(0).all()
    assert synthetic["time_in_hospital"].between(1,14).all()
    for field in CAT:
        assert synthetic[field].isin(real_train[field].unique()).all()
    generated_seconds = time.perf_counter() - start
    synthetic_export = synthetic.assign(readmitted=synthetic_target, is_synthetic=True,
                                        label_origin="SMOTENC-assigned; not observed",
                                        generator="SMOTENC_seed42")
    synthetic_export["record_key"] = [f"SYN_SMOTENC42:{i}" for i in range(len(synthetic_export))]
    synthetic_export.to_parquet(DATA / "synthetic_training_only.parquet", index=False)
    real_export = real_train.assign(readmitted=target.iloc[train].to_numpy(), is_synthetic=False,
                                    label_origin="Published UCI outcome", generator="Not applicable",
                                    record_key="UCI:" + frame.iloc[train]["encounter_id"].to_numpy())
    pd.concat([real_export, synthetic_export], ignore_index=True).to_parquet(
        DATA / "training_real_plus_synthetic.parquet", index=False)
    combined_x = pd.concat([real_train, synthetic], ignore_index=True)
    combined_y = pd.concat([target.iloc[train].reset_index(drop=True), synthetic_target], ignore_index=True)
    assert len(combined_x) == len(real_train) + len(synthetic)
    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    encoder.fit(real_train[CAT])
    def encode(x):
        return hstack([csr_matrix(scaler.transform(x[NUM])), encoder.transform(x[CAT])], format="csr")
    encoded = {key: encode(x) for key, x in transformed.items()}
    augmented = encode(combined_x)
    variants = {"Real_only": (encoded["train"], target.iloc[train], None),
                "Real_class_weighted": (encoded["train"], target.iloc[train], "balanced_subsample"),
                "Real_plus_SMOTENC": (augmented, combined_y, None)}
    models = {}
    validation_scores = {}
    fit_seconds = {}
    params = dict(n_estimators=120, max_depth=14, min_samples_leaf=8, n_jobs=4, random_state=42)
    for name, (x, y, weight) in variants.items():
        start = time.perf_counter()
        model = RandomForestClassifier(**params, class_weight=weight)
        model.fit(x, y)
        validation_scores[name] = metrics(target.iloc[validation], model.predict(encoded["validation"]))
        models[name] = model
        fit_seconds[name] = time.perf_counter()-start
        print(name, "validation macro F1:", round(validation_scores[name]["macro_f1"],4), flush=True)
    # Choose without looking at test outcomes. Dict order prefers the simpler
    # real-only model in an exact tie.
    chosen = max(variants, key=lambda key: validation_scores[key]["macro_f1"])
    selected_names = list(dict.fromkeys(["Real_only", chosen]))
    test_predictions = {key: models[key].predict(encoded["test"]) for key in selected_names}
    test_scores = {key: metrics(target.iloc[test], value) for key, value in test_predictions.items()}
    predictions = frame.iloc[test][["encounter_id", "patient_nbr", "readmitted"]].reset_index(drop=True)
    for key, value in test_predictions.items():
        predictions[key] = value
    predictions.to_parquet(DATA / "real_test_predictions.parquet", index=False)
    # Quality diagnostics describe resemblance, not clinical validity.
    quality = {"numeric_KS_statistic": {key: float(ks_2samp(real_train[key],synthetic[key]).statistic) for key in NUM}}
    train_hashes = set(pd.util.hash_pandas_object(real_export[NUM+CAT+["readmitted"]], index=False))
    synth_hashes = pd.util.hash_pandas_object(synthetic_export[NUM+CAT+["readmitted"]], index=False)
    quality["exact_feature_and_label_matches_to_training"] = int(synth_hashes.isin(train_hashes).sum())
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "complete",
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "original_real_rows": initial, "excluded_death_hospice_rows": int(excluded.sum()),
              "eligible_real_rows": len(frame), "split_counts": {key: len(ix) for key, ix in indices.items()},
              "patient_counts": {key: len(value) for key, value in patient_sets.items()},
              "patient_overlap": 0, "real_training_classes": target.iloc[train].value_counts().to_dict(),
              "synthetic_training_rows": len(synthetic), "synthetic_classes": synthetic_target.value_counts().to_dict(),
              "augmented_training_rows": len(combined_x), "synthetic_validation_rows": 0, "synthetic_test_rows": 0,
              "selection_rule": "Highest validation macro F1; test untouched until selection fixed",
              "chosen_variant": chosen, "validation_results": validation_scores,
              "test_results": test_scores, "generation_seconds": generated_seconds,
              "fit_seconds": fit_seconds, "model_parameters": params, "quality": quality,
              "features": {"numeric": NUM, "categorical": CAT},
              "limits": ["One prespecified split and one model family; exploratory, not clinical validation.",
                         "Synthetic labels are method-assigned, not additional observed outcomes.",
                         "No SPARCS data or predicted SPARCS readmission labels were used.",
                         "Published NO means no recorded readmission; complete follow-up is not established.",
                         "Discharge-stage features; not an admission-time prediction experiment.",
                         "No test-set tuning; no guaranteed improvement or new real patients."]}
    save("results.json", report)
    table = []
    for name, score in validation_scores.items():
        table.append({"variant": name, "validation_macro_f1": score["macro_f1"],
                      "validation_early_readmission_recall": score["per_class"]["<30"]["recall"],
                      "validation_accuracy": score["accuracy"], "selected_on_validation": name == chosen})
    pd.DataFrame(table).to_csv(REPORT / "validation_comparison.csv", index=False)
    lines = ["SYNTHETIC AUGMENTATION PILOT - ACTUAL RESULTS", "",
             f"Eligible real encounters: {len(frame):,}; excluded death/hospice: {int(excluded.sum()):,}",
             f"Real split counts: {report['split_counts']}", "Patient overlap across splits: 0",
             f"Generated training-only rows: {len(synthetic):,}",
             f"Training after augmentation: {len(combined_x):,}",
             "Synthetic validation/test records: 0", "", "VALIDATION RESULTS"]
    for row in table:
        lines.append(f"{row['variant']}: macro F1={row['validation_macro_f1']:.4f}; "
                     f"early-readmission recall={row['validation_early_readmission_recall']:.4f}")
    lines.extend(["", f"Selected using validation only: {chosen}", "", "REAL TEST RESULTS"])
    for key, value in test_scores.items():
        lines.append(f"{key}: macro F1={value['macro_f1']:.4f}; accuracy={value['accuracy']:.4f}; "
                     f"early-readmission recall={value['per_class']['<30']['recall']:.4f}")
    lines.extend(["", "LIMITATIONS", *report["limits"], "",
                  "This pilot does not complete the later classification jury blocks.",
                  "Retain generated data with explicit synthetic provenance; do not present",
                  "the augmented training count as additional real clinical encounters."])
    (REPORT / "PILOT_SUMMARY.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("COMPLETE; validation-selected variant:", chosen, flush=True)
    print(json.dumps(test_scores, indent=2), flush=True)


if __name__ == "__main__":
    main()
