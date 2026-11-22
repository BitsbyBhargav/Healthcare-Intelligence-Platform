"""Make lossless browser-upload packages from the single master modelled.csv.

The packages are transport files, not another modeled dataset. Verification
reconstructs the master's exact uncompressed byte stream from all packages.
"""
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modelled.csv"
DEPLOY = ROOT / "B_snowflake_deployment"
PACKAGES = DEPLOY / "upload_packages"
ROWS_PER_FILE = 500000


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    source_manifest = json.loads((ROOT / "A_warehouse_design/data_preparation/modelled_csv_manifest.json")
                                 .read_text(encoding="utf-8"))
    expected_hash = source_manifest["sha256"]
    if sha(SOURCE) != expected_hash:
        raise ValueError("Master CSV differs from the verified dataset manifest")
    PACKAGES.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    roles = Counter()
    packages = []
    with SOURCE.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        if header != source_manifest["column_names"]:
            raise ValueError("CSV header differs from the 51-column data contract")
        source_pos, role_pos = header.index("source_key"), header.index("model_role")
        while True:
            first = next(reader, None)
            if first is None:
                break
            path = PACKAGES / f"modelled_part_{len(packages)+1:03d}.csv.gz"
            temporary = path.with_suffix(path.suffix+".tmp")
            rows = 0
            with gzip.open(temporary, "wt", encoding="utf-8", newline="", compresslevel=3) as compressed:
                writer = csv.writer(compressed, lineterminator="\n")
                writer.writerow(header)
                for row in (first,):
                    if len(row) != len(header):
                        raise ValueError("Incorrect source column count")
                    writer.writerow(row)
                    counts[row[source_pos]] += 1
                    roles[row[role_pos]] += 1
                    rows += 1
                for row in islice(reader, ROWS_PER_FILE-1):
                    if len(row) != len(header):
                        raise ValueError("Incorrect source column count")
                    writer.writerow(row)
                    counts[row[source_pos]] += 1
                    roles[row[role_pos]] += 1
                    rows += 1
            temporary.replace(path)
            if path.stat().st_size >= 240000000:
                raise ValueError("Package is too large for the browser upload margin")
            packages.append({"file":path.name,"rows":rows,"bytes":path.stat().st_size,"sha256":sha(path)})
            print(f"Packaged {path.name}: {rows:,} rows, {path.stat().st_size/1e6:.1f} MB",flush=True)
    assert dict(counts) == source_manifest["source_counts"]
    assert dict(roles) == source_manifest["model_role_counts"]
    assert sum(p["rows"] for p in packages) == source_manifest["rows"]
    expected_header = (",".join(header)+"\n").encode("utf-8")
    reconstructed = hashlib.sha256()
    reconstructed.update(expected_header)
    for record in packages:
        with gzip.open(PACKAGES/record["file"],"rb") as stream:
            if stream.readline() != expected_header:
                raise ValueError("A transport header changed")
            for block in iter(lambda:stream.read(4*1024*1024),b""):
                reconstructed.update(block)
    if reconstructed.hexdigest() != expected_hash or sha(SOURCE) != expected_hash:
        raise ValueError("Transport packages do not reconstruct the exact master CSV")
    inventory = {p.name for p in PACKAGES.glob("*.csv.gz")}
    if inventory != {p["file"] for p in packages}:
        raise ValueError("Unexpected extra package files found; do not upload a mixed inventory")
    result = {"created_at_utc":datetime.now(timezone.utc).isoformat(),"status":"verified",
              "master_file":"modelled.csv","master_sha256":expected_hash,
              "reconstructed_master_sha256":reconstructed.hexdigest(),
              "rows":source_manifest["rows"],"columns":len(header),
              "source_counts":dict(counts),"model_role_counts":dict(roles),
              "package_count":len(packages),"packages":packages,
              "verification":"Exact original uncompressed CSV bytes reconstructed; master unchanged",
              "purpose":"Temporary transport packages for manual Snowflake stage upload"}
    (DEPLOY/"upload_manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(f"VERIFIED: {len(packages)} packages, {result['rows']:,} unchanged records",flush=True)


if __name__ == "__main__":
    main()
