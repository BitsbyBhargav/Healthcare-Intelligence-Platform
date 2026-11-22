"""Independent final-jury acquisition, harmonization, and validation.

Run from any directory. All inputs/outputs live below final jury.
No prior jury modules, model artifacts, or databases are imported.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import hashlib
import io
import json
import sqlite3
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
AUDIT = ROOT / "A_warehouse_design" / "data_preparation"
YEARS = {2023: "46xm-urtu", 2024: "sf4k-39ay"}
FIELDS = [
    ("encounter_key", pa.string()), ("source_key", pa.string()),
    ("source_row_id", pa.string()), ("patient_key", pa.string()),
    ("period", pa.string()), ("discharge_year", pa.int16()),
    ("facility_key", pa.string()), ("facility_name", pa.string()),
    ("hospital_county", pa.string()), ("service_area", pa.string()),
    ("age_band_raw", pa.string()), ("age_band_common", pa.string()),
    ("gender", pa.string()), ("race_raw", pa.string()),
    ("ethnicity_raw", pa.string()), ("admission_type_raw", pa.string()),
    ("admission_type_common", pa.string()), ("disposition_raw", pa.string()),
    ("diagnosis_system", pa.string()), ("diagnosis_code", pa.string()),
    ("diagnosis_description", pa.string()), ("los_raw", pa.string()),
    ("los_days_lower_bound", pa.int32()), ("los_top_coded", pa.bool_()),
    ("total_charges_usd", pa.float64()), ("total_costs_usd", pa.float64()),
    ("severity_code", pa.string()), ("severity_description", pa.string()),
    ("apr_drg_code", pa.string()), ("payment_type", pa.string()),
    ("readmission_label", pa.string()), ("readmission_observed", pa.bool_()),
    ("diabetes_cohort_definition", pa.string()),
]
SCHEMA = pa.schema(FIELDS)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def fetch(url, params=None):
    for attempt in range(4):
        try:
            response = requests.get(url, params=params, timeout=(20, 150),
                                    headers={"User-Agent": "Healthcare-Final-Jury-DataPreparation/1.0"})
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def remote_snapshot(year):
    ident = YEARS[year]
    meta = fetch(f"https://health.data.ny.gov/api/views/{ident}.json").json()
    count = fetch(f"https://health.data.ny.gov/resource/{ident}.json",
                  {"$select": "count(*) as n"}).json()
    fields = [(c["fieldName"], c["dataTypeName"]) for c in meta["columns"]
              if not c["fieldName"].startswith(":")]
    return {"year": year, "dataset_id": ident, "rows_updated_at": meta.get("rowsUpdatedAt"),
            "row_count": int(count[0]["n"]), "fields": fields}, meta


def download_page(year, offset, size, expected, snapshot_hash):
    folder = RAW / f"sparcs_{year}"
    path = folder / f"part_{offset:08d}.csv.gz"
    sidecar = path.with_suffix(".json")
    if path.exists() and sidecar.exists():
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        if (record.get("snapshot_hash") == snapshot_hash
                and record.get("rows") == expected and record.get("sha256") == sha(path)):
            return record
    response = fetch(f"https://health.data.ny.gov/resource/{YEARS[year]}.csv",
                     {"$select": "*,:id as source_row_id", "$order": ":id",
                      "$offset": offset, "$limit": size})
    content = response.content
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if "source_row_id" not in (reader.fieldnames or []):
        raise ValueError(f"Missing source row IDs: {year}/{offset}")
    ids = [r["source_row_id"] for r in reader]
    if len(ids) != expected or len(set(ids)) != len(ids) or any(not k for k in ids):
        raise ValueError(f"Bad page count or keys: {year}/{offset}: {len(ids)} != {expected}")
    folder.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(gzip.compress(content, compresslevel=6, mtime=0))
    temporary.replace(path)
    record = {"year": year, "offset": offset, "rows": len(ids),
              "first_id": ids[0], "last_id": ids[-1], "sha256": sha(path),
              "snapshot_hash": snapshot_hash, "downloaded_at_utc": now(),
              "file": str(path.relative_to(ROOT))}
    save_json(sidecar, record)
    return record


def ensure_uci():
    url = "https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip"
    folder = RAW / "uci_diabetes"
    folder.mkdir(parents=True, exist_ok=True)
    files = [folder / name for name in ["diabetic_data.csv", "IDS_mapping.csv"]]
    if not all(path.exists() for path in files):
        archive = zipfile.ZipFile(io.BytesIO(fetch(url).content))
        for path in files:
            entry = next(name for name in archive.namelist() if name.split("/")[-1] == path.name)
            path.write_bytes(archive.read(entry))
    expected = "0689e7ec031237dc63031b938805c48377748761a3b26acab621567afa24df97"
    if sha(files[0]) != expected:
        raise ValueError("UCI official raw hash differs from reviewed source snapshot")
    save_json(folder / "manifest.json", {"source": url, "checked_at_utc": now(),
              "files": [{"name": path.name, "sha256": sha(path), "bytes": path.stat().st_size} for path in files]})


def download(args):
    AUDIT.mkdir(parents=True, exist_ok=True)
    ensure_uci()
    for year in args.years:
        snapshot, meta = remote_snapshot(year)
        folder = RAW / f"sparcs_{year}"
        folder.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        existing = folder / "manifest.json"
        if existing.exists():
            old = json.loads(existing.read_text(encoding="utf-8"))
            if old["snapshot_hash"] != fingerprint or old["page_size"] != args.page_size:
                raise ValueError(f"Snapshot/page size changed for {year}; use a new raw snapshot folder.")
        manifest = {"snapshot": snapshot, "snapshot_hash": fingerprint,
                    "page_size": args.page_size, "status": "downloading", "started_at_utc": now()}
        save_json(existing, manifest)
        save_json(folder / "metadata.json", meta)
        # Preserve the publisher's dictionary/overview alongside the raw source.
        for attachment in meta.get("metadata", {}).get("attachments", []):
            if not attachment.get("filename", "").endswith(".pdf"):
                continue
            path = folder / attachment["filename"]
            if not path.exists():
                url = (f"https://health.data.ny.gov/api/views/{YEARS[year]}/files/"
                       f"{attachment['assetId']}?download=true")
                path.write_bytes(fetch(url).content)
        tasks = [(offset, min(args.page_size, snapshot["row_count"] - offset))
                 for offset in range(0, snapshot["row_count"], args.page_size)]
        records = []
        print(f"Downloading {year}: {snapshot['row_count']:,} rows in {len(tasks)} pages", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(download_page, year, offset, args.page_size, expected, fingerprint): offset
                       for offset, expected in tasks}
            for future in concurrent.futures.as_completed(pending):
                records.append(future.result())
                print(f"{year}: {len(records)}/{len(tasks)} pages verified; "
                      f"{sum(r['rows'] for r in records):,} rows", flush=True)
        after, _ = remote_snapshot(year)
        if after != snapshot:
            raise ValueError(f"Source changed during {year} download. Do not prepare a mixed snapshot.")
        manifest.update(status="complete", completed_at_utc=now(),
                        pages=sorted(records, key=lambda r: r["offset"]))
        save_json(existing, manifest)


def text(frame, field):
    if field not in frame:
        return pd.Series(pd.NA, index=frame.index, dtype="string")
    return frame[field].astype("string").str.strip().replace({"": pd.NA, "?": pd.NA})


def age_common(series):
    mapping = {"[0-10)": "0-29", "[10-20)": "0-29", "[20-30)": "0-29",
               "[30-40)": "30-49", "[40-50)": "30-49", "[50-60)": "50-69",
               "[60-70)": "50-69", "[70-80)": "70+", "[80-90)": "70+",
               "[90-100)": "70+", "0 to 17": "0-29", "18 to 29": "0-29",
               "30 to 49": "30-49", "50 to 69": "50-69", "70 or Older": "70+",
               "0-17": "0-29", "18-29": "0-29", "30-49": "30-49", "50-69": "50-69"}
    return series.map(mapping).astype("string")


def parse_los(series):
    value = series.astype("string").str.strip().str.replace(r"\s*\+$", "+", regex=True)
    top = value.str.fullmatch(r"\d+\+", na=False)
    number = pd.to_numeric(value.str.replace(r"\+$", "", regex=True), errors="coerce")
    valid = number.notna() & number.ge(0) & number.le(100000) & number.mod(1).eq(0)
    return number.where(valid).astype("Int32"), top


def parse_money(series):
    cleaned = series.astype("string").str.replace(r"[$,]", "", regex=True)
    number = pd.to_numeric(cleaned, errors="coerce")
    return number.where(np.isfinite(number)).astype("Float64")


def mappings():
    result = {}
    current = None
    with (RAW / "uci_diabetes" / "IDS_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            if row[0].endswith("_id"):
                current = row[0]
                result[current] = {}
            else:
                result[current][row[0].strip()] = row[1].strip()
    return result


def normalize(frame, source, year=None):
    uci = source == "UCI_DIABETES"
    out = pd.DataFrame(index=frame.index)
    out["source_key"] = source
    out["source_row_id"] = text(frame, "encounter_id" if uci else "source_row_id")
    out["encounter_key"] = source + ":" + out["source_row_id"]
    out["patient_key"] = "UCI_DIABETES:" + text(frame, "patient_nbr") if uci else pd.NA
    out["period"] = "1999-2008" if uci else str(year)
    out["discharge_year"] = pd.NA if uci else year
    facility_id = text(frame, "permanent_facility_id")
    out["facility_key"] = source + ":" + facility_id if not uci else pd.NA
    out["facility_name"] = text(frame, "facility_name")
    out["hospital_county"] = text(frame, "hospital_county")
    out["service_area"] = text(frame, "hospital_service_area" if year == 2023 else "health_service_area")
    out["age_band_raw"] = text(frame, "age" if uci else "age_group")
    out["age_band_common"] = age_common(out["age_band_raw"])
    out["gender"] = text(frame, "gender").replace({"F": "Female", "M": "Male",
                                                   "U": "Unknown", "Unknown/Invalid": "Unknown"})
    out["race_raw"] = text(frame, "race")
    out["ethnicity_raw"] = text(frame, "ethnicity")
    if uci:
        maps = mappings()
        out["admission_type_raw"] = text(frame, "admission_type_id").map(maps["admission_type_id"])
        out["disposition_raw"] = text(frame, "discharge_disposition_id").map(maps["discharge_disposition_id"])
    else:
        out["admission_type_raw"] = text(frame, "type_of_admission")
        out["disposition_raw"] = text(frame, "patient_disposition")
    admission = out["admission_type_raw"].astype("string").str.strip().str.lower()
    out["admission_type_common"] = admission.map({
        "emergency": "Emergency", "urgent": "Urgent", "elective": "Elective",
        "newborn": "Newborn", "trauma": "Trauma", "trauma center": "Trauma",
        "not available": "Unknown", "not mapped": "Unknown", "null": "Unknown",
        "unknown": "Unknown", "other": "Other"}).fillna("Unknown")
    out["diagnosis_system"] = "ICD9_CM" if uci else "CCSR_ICD10_CM"
    out["diagnosis_code"] = text(frame, "diag_1" if uci else "ccsr_diagnosis_code")
    out["diagnosis_description"] = text(frame, "ccsr_diagnosis_description")
    out["los_raw"] = text(frame, "time_in_hospital" if uci else "length_of_stay")
    out["los_days_lower_bound"], out["los_top_coded"] = parse_los(out["los_raw"])
    out["total_charges_usd"] = parse_money(text(frame, "total_charges"))
    out["total_costs_usd"] = parse_money(text(frame, "total_costs"))
    out["severity_code"] = text(frame, "apr_severity_of_illness_code")
    out["severity_description"] = text(frame, "apr_severity_of_illness")
    out["apr_drg_code"] = text(frame, "apr_drg_code")
    out["payment_type"] = text(frame, "payer_code" if uci else "payment_typology_1")
    out["readmission_label"] = text(frame, "readmitted") if uci else pd.NA
    out["readmission_observed"] = out["readmission_label"].notna()
    out["diabetes_cohort_definition"] = "Any recorded diabetes diagnosis (UCI inclusion)" if uci else "All inpatient discharges; primary CCSR only"
    return out


def as_table(frame):
    # Explicit types keep all-null fields consistent across source partitions.
    arrays = [pa.array(frame[name], type=kind, from_pandas=True) for name, kind in FIELDS]
    return pa.Table.from_arrays(arrays, schema=SCHEMA)


def prepare(args):
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    save_json(AUDIT / "preparation_report.json", {"status": "in_progress", "started_at_utc": now()})
    save_json(AUDIT / "verification_report.json", {"status": "pending", "reason": "Preparation running"})
    conn = sqlite3.connect(OUT / "validation_keys.sqlite")
    conn.execute("DROP TABLE IF EXISTS encounter_keys")
    conn.execute("CREATE TABLE encounter_keys (key TEXT PRIMARY KEY) WITHOUT ROWID")
    source_stats = []
    outputs = []
    previews = {}
    def write(frame, source, name, year=None):
        normalized = normalize(frame, source, year)
        if source not in previews:
            previews[source] = normalized.head(10).copy()
        if normalized["source_row_id"].isna().any():
            raise ValueError("A source record is missing its row identifier")
        try:
            conn.executemany("INSERT INTO encounter_keys VALUES (?)",
                             ((key,) for key in normalized["encounter_key"]))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Duplicate source encounter identifiers; refusing inflated volume") from exc
        folder = OUT / "encounters" / f"source={source}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.parquet"
        pq.write_table(as_table(normalized), path, compression="zstd")
        outputs.append({"file": str(path.relative_to(ROOT)), "rows": len(frame), "sha256": sha(path)})
        stats = {"rows": len(frame), "labels": int(normalized["readmission_observed"].sum()),
                 "missing_los": int(normalized["los_days_lower_bound"].isna().sum()),
                 "top_coded_los": int(normalized["los_top_coded"].sum()),
                 "unknown_age": int(normalized["age_band_common"].isna().sum()),
                 "missing_facility": int(normalized["facility_key"].isna().sum()),
                 "negative_costs": int(normalized["total_costs_usd"].lt(0).fillna(False).sum()),
                 "negative_charges": int(normalized["total_charges_usd"].lt(0).fillna(False).sum()),
                 "zero_los": int(normalized["los_days_lower_bound"].eq(0).fillna(False).sum()),
                 "invalid_los_tokens": int((normalized["los_raw"].notna() & normalized["los_days_lower_bound"].isna()).sum()),
                 "invalid_cost_tokens": int((text(frame, "total_costs").notna() & normalized["total_costs_usd"].isna()).sum()),
                 "invalid_charge_tokens": int((text(frame, "total_charges").notna() & normalized["total_charges_usd"].isna()).sum())}
        return normalized, stats
    uci_path = RAW / "uci_diabetes" / "diabetic_data.csv"
    uci = pd.read_csv(uci_path, dtype="string", keep_default_na=False)
    if not set(uci["readmitted"]) <= {"NO", ">30", "<30"}:
        raise ValueError("Unexpected UCI readmission label")
    _, stats = write(uci, "UCI_DIABETES", "part_00000000")
    stats.update(source="UCI_DIABETES", unique_patients=int(uci["patient_nbr"].nunique()),
                 original_columns=len(uci.columns), raw_sha256=sha(uci_path),
                 class_counts=uci["readmitted"].value_counts().astype(int).to_dict())
    source_stats.append(stats)
    clean_uci = uci.replace("?", pd.NA)
    # Literal 'None' in A1Cresult/max_glu_serum means a test was not performed;
    # pandas default missing-value conversion would incorrectly erase it.
    clean_uci.to_parquet(OUT / "uci_supervised.parquet", index=False, compression="zstd")
    missing = (clean_uci.isna().sum().rename("missing_count").to_frame()
               .assign(missing_fraction=lambda x: x.missing_count / len(clean_uci)))
    missing.to_csv(AUDIT / "uci_missingness.csv", index_label="field")
    print(f"Prepared UCI: {len(uci):,} rows; labels retained", flush=True)
    for year in args.years:
        folder = RAW / f"sparcs_{year}"
        manifest_path = folder / "manifest.json"
        deadline = time.monotonic() + 1800
        announced = False
        while args.wait_download:
            state = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            if state.get("status") == "complete":
                break
            if not announced:
                print(f"Waiting for verified {year} download before preparation", flush=True)
                announced = True
            if time.monotonic() > deadline:
                raise TimeoutError(f"Download for {year} did not complete in 30 minutes")
            time.sleep(10)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["status"] != "complete":
            raise ValueError(f"Incomplete source download: {year}")
        total = Counter()
        categories = {field: Counter() for field in ["age_band_raw", "gender", "admission_type_raw", "los_raw", "diagnosis_description"]}
        for i, record in enumerate(manifest["pages"], 1):
            path = ROOT / record["file"]
            if sha(path) != record["sha256"]:
                raise ValueError(f"Raw checksum mismatch: {path.name}")
            frame = pd.read_csv(path, dtype="string", keep_default_na=False)
            if len(frame) != record["rows"]:
                raise ValueError("Page row count mismatch")
            years = pd.to_numeric(frame["discharge_year"], errors="coerce")
            if not years.eq(year).all():
                raise ValueError(f"Unexpected discharge year in {path.name}")
            normalized, stats = write(frame, f"SPARCS_{year}", f"part_{record['offset']:08d}", year)
            total.update(stats)
            for field in categories:
                categories[field].update(normalized[field].dropna().value_counts().astype(int).to_dict())
            print(f"Prepared {year}: {i}/{len(manifest['pages'])} pages; {total['rows']:,} rows", flush=True)
        if total["rows"] != manifest["snapshot"]["row_count"] or total["labels"]:
            raise ValueError("Source count/label reconciliation failed")
        source_stats.append(dict(source=f"SPARCS_{year}", **total))
        save_json(AUDIT / f"sparcs_{year}_categories.json", categories)
    unique = conn.execute("SELECT COUNT(*) FROM encounter_keys").fetchone()[0]
    conn.close()
    total = sum(s["rows"] for s in source_stats)
    if total != unique:
        raise ValueError("Duplicate encounter inflation detected")
    report = {"prepared_at_utc": now(), "status": "complete", "total_encounters": total,
              "unique_source_encounter_keys": unique, "source_statistics": source_stats,
              "volume_factor_vs_original": total / len(uci), "synthetic_records": 0,
              "readmission_labeled_rows": sum(s["labels"] for s in source_stats),
              "outputs": outputs, "schema": str(SCHEMA),
              "notes": ["No cross-source patient matching.", "SPARCS has no readmission labels.",
                        "No model fitting or measured performance improvement is claimed.",
                        "Top-coded stays are lower bounds, never exact totals.",
                        "Cross-source populations and time periods differ; filter analyses by source."]}
    save_json(AUDIT / "preparation_report.json", report)
    with (AUDIT / "encounter_preview.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SCHEMA.names)
        writer.writeheader()
        for preview in previews.values():
            writer.writerows(preview.astype(object).where(preview.notna(), None).to_dict("records"))
    save_json(AUDIT / "data_contract.json", {
        "grain": "One published encounter/discharge record from a frozen source snapshot",
        "primary_key": "encounter_key = source_key + ':' + source_row_id",
        "fields": [{"name": field.name, "arrow_type": str(field.type), "nullable": field.nullable}
                   for field in SCHEMA],
        "age_band_common": ["0-29", "30-49", "50-69", "70+"],
        "original_target_classes": ["NO", ">30", "<30"],
        "readmission_training_source": "UCI_DIABETES",
        "unavailable_target_policy": "Null with readmission_observed=false; never recode to NO",
        "dates_policy": "No invented encounter dates or UCI discharge years",
        "identifier_policy": "Source-qualified row IDs; no cross-source patient linkage",
        "cost_policy": "SPARCS estimated costs and charges, not insurer payments",
        "los_policy": "Source-specific definition; capped SPARCS LOS stored as a lower bound with flag",
        "preview_policy": "Ten convenience rows per source, not a representative analytical sample"})
    pq.write_metadata(SCHEMA, OUT / "encounters" / "_common_metadata")
    print(f"COMPLETE: {total:,} unique source encounters; {report['readmission_labeled_rows']:,} labeled", flush=True)


def verify(args):
    report = json.loads((AUDIT / "preparation_report.json").read_text(encoding="utf-8"))
    if report.get("status") != "complete":
        raise ValueError("Preparation has not completed")
    expected_files = {str(ROOT / record["file"]) for record in report["outputs"]}
    actual_files = {str(path) for path in (OUT / "encounters").rglob("*.parquet")}
    if expected_files != actual_files:
        raise ValueError("Processed partition inventory differs from the completed manifest")
    counts = Counter()
    checks = Counter()
    for record in report["outputs"]:
        path = ROOT / record["file"]
        if sha(path) != record["sha256"]:
            raise ValueError(f"Processed checksum mismatch: {path}")
        table = pq.read_table(path, schema=SCHEMA)
        frame = table.to_pandas()
        if len(frame) != record["rows"]:
            raise ValueError("Processed row-count mismatch")
        for source, group in frame.groupby("source_key"):
            counts[source] += len(group)
            if source.startswith("SPARCS"):
                assert group["readmission_label"].isna().all()
                assert not group["readmission_observed"].any()
                assert group["patient_key"].isna().all()
                expected_caps = group["los_raw"].isin(["120 +", "120+"])
                assert group["los_top_coded"].eq(expected_caps).all()
                assert group.loc[expected_caps, "los_days_lower_bound"].eq(120).all()
            else:
                assert group["readmission_label"].isin(["NO", ">30", "<30"]).all()
                assert group["facility_key"].isna().all()
                assert group["discharge_year"].isna().all()
                assert group["total_costs_usd"].isna().all()
                assert group["los_days_lower_bound"].between(1, 14).all()
        assert frame["encounter_key"].notna().all()
        assert frame["age_band_common"].dropna().isin(["0-29", "30-49", "50-69", "70+"]).all()
        assert frame.loc[frame["age_band_raw"].notna(), "age_band_common"].notna().all()
        checks["files_checked"] += 1
    assert sum(counts.values()) == report["total_encounters"]
    for source in report["source_statistics"]:
        assert counts[source["source"]] == source["rows"]
    for year in args.years:
        manifest = json.loads((RAW / f"sparcs_{year}" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "complete"
        for record in manifest["pages"]:
            assert sha(ROOT / record["file"]) == record["sha256"]
    clean = pd.read_parquet(OUT / "uci_supervised.parquet")
    assert len(clean) == counts["UCI_DIABETES"]
    assert int(clean["A1Cresult"].eq("None").sum()) == 84748
    assert int(clean["max_glu_serum"].eq("None").sum()) == 96420
    result = {"verified_at_utc": now(), "status": "passed", "counts": counts, **checks,
              "checks": ["raw/processed reconciliation", "processed SHA-256 integrity", "explicit Parquet schema",
                         "no fabricated SPARCS readmission labels/patient IDs", "no invented UCI dates/costs/facilities",
                         "valid common age bands with no unmapped published categories", "all original UCI target classes retained",
                         "publisher 120 + caps preserved as 120-day lower bounds",
                         "original UCI test-not-performed tokens preserved", "raw page SHA-256 integrity"]}
    save_json(AUDIT / "verification_report.json", result)
    lines = ["FINAL JURY - VERIFIED DATA PREPARATION", "", "Status: Complete", "",
             f"Total source encounter records: {report['total_encounters']:,}",
             f"Unique source-qualified encounter keys: {report['unique_source_encounter_keys']:,}",
             f"Volume relative to original UCI source: {report['volume_factor_vs_original']:.2f}x",
             f"Encounters with observed readmission labels: {report['readmission_labeled_rows']:,}",
             "Synthetic records: 0", "", "SOURCE COUNTS"]
    for row in report["source_statistics"]:
        lines.append(f"{row['source']}: {row['rows']:,} records; {row['labels']:,} readmission labels")
    lines.extend(["", "QUALITY FINDINGS"])
    for row in report["source_statistics"]:
        lines.append(row["source"] + ": " + "; ".join(f"{key}={row[key]:,}" for key in [
            "missing_los", "top_coded_los", "unknown_age", "missing_facility",
            "negative_costs", "negative_charges", "zero_los", "invalid_los_tokens",
            "invalid_cost_tokens", "invalid_charge_tokens"]))
    lines.extend(["", "VERIFICATION", *result["checks"], "",
                  "No classifiers or clusterers were trained in this preparation step.",
                  "The expansion increases warehouse/operational data volume; it does not",
                  "increase labeled readmission training examples. Sources have different",
                  "cohorts, years, diagnosis systems, and LOS definitions; retain source filters.",
                  "", "DELIVERABLES",
                  "data/processed/encounters: typed common Parquet partitions",
                  "data/processed/uci_supervised.parquet: clean original-column dataset",
                  "data/processed/validation_keys.sqlite: uniqueness validation index only",
                  "data_preparation/preparation_report.json: counts and hashes",
                  "data_preparation/verification_report.json: completed integrity checks",
                  "data_preparation/data_contract.json: field types and null/outcome policies",
                  "data_preparation/encounter_preview.csv: 10 convenience rows per source",
                  "", "Snowflake loading and analytical warehouse demonstration remain next steps."])
    (AUDIT / "DATA_PREPARATION_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["download", "prepare", "verify"])
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2024], choices=YEARS)
    parser.add_argument("--page-size", type=int, default=100000)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--wait-download", action="store_true",
                        help="Wait for completed raw manifests while another download process runs")
    args = parser.parse_args()
    if args.page_size < 1 or args.workers < 1:
        parser.error("page size and workers must be positive")
    globals()[args.action](args)


if __name__ == "__main__":
    main()
