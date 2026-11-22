"""Export the approved augmentation pilot's training dataset as plain CSV.

The spreadsheet authoring API has no documented CSV export. This direct
data export preserves values and provenance without workbook formatting.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/augmentation_pilot/training_real_plus_synthetic.parquet"
OUTPUT = ROOT / "data/processed/augmentation_pilot/uci_synthetic_training.csv"
NUMERIC = ["time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
           "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses"]


def main():
    frame = pd.read_parquet(SOURCE)
    for column in NUMERIC:
        if not frame[column].notna().all() or not frame[column].mod(1).eq(0).all():
            raise ValueError(f"Expected integral count/duration values: {column}")
        frame[column] = frame[column].astype("int64")
    assert frame.record_key.is_unique
    temporary = OUTPUT.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8", lineterminator="\n")
    check = pd.read_csv(temporary, keep_default_na=False,
                        dtype={c: "string" for c in frame if c not in NUMERIC + ["is_synthetic"]})
    pd.testing.assert_frame_equal(check, frame, check_dtype=False)
    assert check.is_synthetic.sum() == 34815
    assert len(check) == 94380
    assert check.readmitted.value_counts().to_dict() == {"NO":31460, ">30":31460, "<30":31460}
    temporary.replace(OUTPUT)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": OUTPUT.name, "rows": len(frame), "columns": len(frame.columns),
        "real_training_rows": int((~frame.is_synthetic).sum()),
        "synthetic_training_rows": int(frame.is_synthetic.sum()),
        "target_counts": check.readmitted.value_counts().to_dict(),
        "source": str(SOURCE.relative_to(ROOT)), "purpose": "Modelled training data for warehouse work",
        "holdout_policy": "Real validation/test datasets remain separate and are not included",
        "synthetic_policy": "Generated labels are method-assigned, not observed outcomes",
        "provenance_columns": ["is_synthetic", "label_origin", "generator", "record_key"],
        "csv_encoding": "UTF-8", "header": True, "index_column": False,
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "verification": "Full CSV round trip matches the selected source; unique keys and counts passed",
    }
    report = ROOT / "A_warehouse_design/data_preparation/modelled_csv_manifest.json"
    report.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
