"""Stream the actual UCI + SPARCS integration into the single modelled.csv.

Source-only clinical fields remain unavailable in other sources. No patient
matching, readmission pseudo-labeling, or synthetic generation takes place.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "modelled.csv"
OLD_NAME = ROOT / "Modelled data.csv"
AUDIT = ROOT / "A_warehouse_design/data_preparation"
CLINICAL = ["num_lab_procedures", "num_procedures", "num_medications", "number_outpatient",
            "number_emergency", "number_inpatient", "number_diagnoses", "insulin", "change",
            "diabetesMed", "A1Cresult", "max_glu_serum", "diag_2", "diag_3", "admission_source_id"]


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    preparation = json.loads((AUDIT / "preparation_report.json").read_text(encoding="utf-8"))
    verification = json.loads((AUDIT / "verification_report.json").read_text(encoding="utf-8"))
    if preparation.get("status") != "complete" or verification.get("status") != "passed":
        raise ValueError("Common-source preparation must be complete and verified")
    if OLD_NAME.exists():
        if OUTPUT.exists():
            raise ValueError("Both final CSV names exist; preserve and reconcile them before overwriting")
        OLD_NAME.replace(OUTPUT)
    temporary = OUTPUT.with_suffix(".csv.tmp")
    uci = pd.read_parquet(ROOT / "data/processed/uci_supervised.parquet")
    clinical = uci.set_index("encounter_id")[CLINICAL]
    splits = pd.read_parquet(ROOT / "data/processed/augmentation_pilot/real_patient_splits.parquet")
    split_lookup = splits.set_index("encounter_id")["split"].to_dict()
    expected_counts = {r["source"]:r["rows"] for r in preparation["source_statistics"]}
    counts = Counter()
    columns = None
    print("Writing the single integrated modelled.csv", flush=True)
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        for number, record in enumerate(preparation["outputs"],1):
            path = ROOT / record["file"]
            if file_hash(path) != record["sha256"]:
                raise ValueError(f"Prepared input changed: {path}")
            frame = pq.ParquetFile(path).read().to_pandas()
            frame.rename(columns={"readmission_observed":"readmission_label_available"}, inplace=True)
            source = str(frame["source_key"].iloc[0])
            frame["is_synthetic"] = False
            if source == "UCI_DIABETES":
                extra = clinical.reindex(frame["source_row_id"].tolist()).reset_index(drop=True)
                for field in CLINICAL:
                    frame["uci_"+field] = extra[field].to_numpy()
                frame["model_role"] = frame["source_row_id"].map(split_lookup).map({
                    "train":"TRAIN_LABELED", "validation":"VALIDATION_LABELED", "test":"TEST_LABELED"
                }).fillna("EXCLUDED_READMISSION_COHORT")
                frame["label_origin"] = "PUBLISHED_UCI_OUTCOME"
            else:
                for field in CLINICAL:
                    frame["uci_"+field] = pd.NA
                frame["model_role"] = ("UNLABELED_TRAIN_CANDIDATE" if source == "SPARCS_2023"
                                       else "UNLABELED_HOLDOUT_CANDIDATE")
                frame["label_origin"] = "UNAVAILABLE_IN_SOURCE"
                assert frame["readmission_label"].isna().all()
                assert not frame["readmission_label_available"].any()
            if columns is None:
                columns = list(frame.columns)
            assert list(frame.columns) == columns
            frame.to_csv(stream, index=False, header=number==1, lineterminator="\n")
            counts[source] += len(frame)
            print(f"Written {number}/{len(preparation['outputs'])} partitions; {sum(counts.values()):,} records", flush=True)
    if dict(counts) != expected_counts:
        raise ValueError("Export source counts differ from the verified source manifest")
    # Independent streaming CSV check. Missing strings and the literal 'None'
    # remain distinct; readmission outcomes are never filled from another cohort.
    check_counts = Counter()
    roles = Counter()
    classes = Counter()
    read_rows = 0
    for chunk in pd.read_csv(temporary, dtype="string", keep_default_na=False, chunksize=100000):
        assert list(chunk.columns) == columns
        assert chunk["is_synthetic"].eq("False").all()
        assert chunk["age_band_common"].isin(["0-29","30-49","50-69","70+"]).all()
        assert chunk["encounter_key"].eq(chunk["source_key"]+":"+chunk["source_row_id"]).all()
        external = chunk["source_key"].str.startswith("SPARCS")
        assert chunk.loc[external,"readmission_label"].eq("").all()
        assert chunk.loc[external,"readmission_label_available"].eq("False").all()
        assert chunk.loc[external,"patient_key"].eq("").all()
        assert chunk.loc[external,["uci_"+f for f in CLINICAL]].eq("").all().all()
        observed = chunk.loc[~external]
        assert observed["readmission_label"].isin(["NO",">30","<30"]).all()
        assert observed["readmission_label_available"].eq("True").all()
        assert observed["discharge_year"].eq("").all()
        check_counts.update(chunk["source_key"].value_counts().astype(int).to_dict())
        roles.update(chunk["model_role"].value_counts().astype(int).to_dict())
        classes.update(observed["readmission_label"].value_counts().astype(int).to_dict())
        read_rows += len(chunk)
    assert dict(check_counts) == expected_counts
    assert read_rows == preparation["total_encounters"]
    assert roles["TRAIN_LABELED"] == 59565
    assert roles["VALIDATION_LABELED"] == 19917
    assert roles["TEST_LABELED"] == 19861
    assert roles["EXCLUDED_READMISSION_COHORT"] == 2423
    assert sum(classes.values()) == 101766
    temporary.replace(OUTPUT)
    manifest = {"created_at_utc":datetime.now(timezone.utc).isoformat(),"file":OUTPUT.name,
                "status":"verified", "rows":read_rows,"columns":len(columns),
                "source_counts":dict(check_counts),"model_role_counts":dict(roles),
                "observed_label_counts":dict(classes),"observed_readmission_labels":sum(classes.values()),
                "synthetic_rows":0,"generated_readmission_labels":0,"sha256":file_hash(OUTPUT),
                "bytes":OUTPUT.stat().st_size,"column_names":columns,
                "integration":"Schema-aligned union; no cross-source patient matching",
                "training_scope":"SPARCS candidates are unlabeled; no semi-supervised model has been fitted",
                "test_scope":"Only TEST_LABELED has scored readmission ground truth; SPARCS holdout is for distribution checks",
                "prior_augmentation":"94,380-row UCI+SMOTENC training dataset remains separately in its existing Parquet file",
                "verification":"Complete CSV scan, source/role/class count reconciliation, provenance and null rules"}
    (AUDIT / "modelled_csv_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k!='column_names'},indent=2),flush=True)


if __name__ == "__main__":
    main()
