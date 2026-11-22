# HealthLine 2.0 | Hospital Intelligence Platform

A working, local Streamlit application connecting historical hospital data, a star-schema warehouse, incremental ETL, readmission modeling, encounter clustering, and hypothetical capacity scenarios. Built for internal technical and external hackathon demonstrations.

**Research demonstration, not a clinical diagnostic system.** Historical replay is not live admission data. Capacity outputs are explicitly hypothetical. No deployment validation is claimed.

## Launch

From the repository root in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8530
```

Open http://127.0.0.1:8530. The existing environment is already installed. For the exact dependency versions use `requirements-lock.txt`; the tested runtime is Python 3.14. No network access is needed for the core demonstration after installation. Telemetry is disabled; the server binds to localhost.

The supplied model and clustering artifacts support immediate use. If cluster artifacts are missing, regenerate with `python -m healthline.intelligence` before launching. Load only trusted local joblib artifacts.

## Separate analytics and simulation workspaces

Use the **Workspace** selector in the sidebar:

- **Jury 2 · Analytics**: the previous evaluation, model inference, mining and profiling pages, plus **Patient Clustering**. Also includes the full historical executive view, warehouse explorer and evidence.
- **Simulation · Replay**: historical batch replay, a replay-only executive view and warehouse explorer, and hypothetical operational scenarios.

The standalone `jury_2_dw/app.py` dashboard also includes Patient Clustering.

### Available features

| Workspace | What actually runs |
|---|---|
| Executive Command Center | SQL counts, outcome distribution, historical stays and complexity; historical or replay warehouse selector |
| Live Pipeline Studio | Real 50–500-row CSV batches, validation, transformation, transactional inserts, saved-model inference, cluster assignments, measured logs |
| Data Warehouse Explorer | Read-only SQL queries, schema, fact/dimension previews, counts, ingestion history |
| Jury 2 analytics pages | Patient Clustering (K-Means/PCA), preserved three-class Random Forest inference, five-model comparison, feature importance, Apriori/FP-Growth, clinical profiles |
| Operational Scenario Lab | Clearly hypothetical daily demand model and saved scenario comparison |
| Architecture & Evidence | Provenance, methodology, actual model and test evidence, limitations |

Choose **Simulation · Replay** in the sidebar to see the demo warehouse change after ingestion. The full historical warehouse remains read-only and contains 101,766 encounters. The simulation workspace always writes only to the isolated replay warehouse. Segmentation charts use the complete historical source; replay segment results are available through SQL.

## Architecture and files

```text
app.py                         unified Streamlit entry point
healthline/
  warehouse.py                 schema, validation, atomic replay, reset protection, SQL
  intelligence.py              K-Means/PCA training and validated model inference
  scenarios.py                 hypothetical stock-and-flow calculations
  ui.py                        six integrated pages; reuses original Jury 2 views
  artifacts/                   fitted clustering pipeline, full assignments, profiles, report
.streamlit/config.toml         light theme, localhost binding, telemetry disabled
runtime/replay.db              auto-created local demo warehouse; ignored by Git
data/                         preserved source and original warehouse/CSV exports
jury_1_dw/                    original warehouse tools and dashboard
jury_2_dw/                    preserved classification, mining, profiling and Orange work
  outputs/best_model.joblib     unchanged fitted classifier with preprocessing
  app.py                       original six-view dashboard; also reusable by HealthLine
 tests/                       regression, acceptance and actual-browser checks
 docs/HEALTHLINE_DEMO.md        three-minute walkthrough
 docs/HEALTHLINE_REVIEW.md      implementation evidence, audit, changes, publication gate
 docs/JURY2_README.md           preserved previous project instructions
 deliverables/healthline_evidence/ actual browser screenshots and interaction log
```

The original dashboards remain available:

```powershell
.\.venv\Scripts\python.exe -m streamlit run jury_1_dw/dashboard.py --server.port 8502
.\.venv\Scripts\python.exe -m streamlit run jury_2_dw/app.py --server.port 8512
```

## Data and ETL contracts

Source: [UCI Diabetes 130-US Hospitals, 1999–2008](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008), preserved locally with 101,766 rows and 71,518 distinct patient linkage numbers. No synthetic patient records or invented encounter dates are used. System ingestion timestamps are recorded in UTC.

Replay creates the existing four-table star-schema pattern with actual primary and foreign keys, plus `pipeline_runs`, `ingestion_batches`, `rejected_records`, `patient_clusters`, `model_predictions`, `operational_scenarios`, and demo metadata. The original warehouse is never migrated or overwritten. Demographics use first observation per patient, matching the original warehouse; this is not a slowly changing dimension.

Required identifiers and numeric fields are checked for missing, nonnumeric, noninteger and out-of-range values. Age groups and readmission labels are validated. Missing categorical dimensions normalize to `Unknown`. Classifier preprocessing receives original valid rows, preserving training-time missing-diagnosis behavior. Duplicate encounter keys are counted and skipped. Accepted rows include valid duplicates; `input = accepted + rejected`, and on successful runs `accepted = loaded + duplicates`.

`BEGIN IMMEDIATE` serializes writes. Dimensions, facts, predictions, clusters, source cursor, rejected rows and success logs commit together. Failure rolls back the load and cursor, then records a failure log. A repeat batch loads zero new encounters. Independent concurrent next-batch requests safely advance distinct source ranges. Source cursor is global to the local demo, not per browser tab.

A reset clears only a marked replay database's clinical replay data and run history. It preserves the source, original warehouse, fitted models and separately stored hypothetical scenarios. Original data/model/archive directories are blocked as write targets. The original Jury 1 rebuild script remains available for reproducibility but is not invoked by the new app.

## Machine learning evidence

The existing classifier is a **three-class discharge-stage Random Forest**, not the archived binary formula. Classes are `NO`, `>30`, `<30`; the decision selects maximum predicted probability. There is no binary decision threshold in this pipeline. Features include treatment and length-of-stay information and must not be described as admission-time predictions. Saved feature order and output class order are checked before inference.

Preserved patient-disjoint evaluation: 60,878 training, 20,400 validation, 20,488 test encounters. Test accuracy **0.5111**, macro F1 **0.4330**, macro OVR ROC AUC **0.6503**, <30-day recall **0.3004**. Accuracy is below the majority-class baseline; probabilities are not calibrated clinical confidence. No retraining or new performance claim was made for this classifier.

K-Means fits all 101,766 encounters using median imputation, StandardScaler, age-bin midpoints, medication/diagnosis/lab/procedure counts, prior utilization and retrospective stay. It compares K=2–6 with 10 initializations and seed 42; silhouette is evaluated on the same 2,000-row sample. **K=2, silhouette 0.1743**, with sizes **64,743 / 37,023**. Two PCA dimensions explain **38.09%** of scaled variance. Separation is modest; these are descriptive encounter segments, not medically validated patient types. Readmission outcomes and IDs are excluded from clustering inputs.

The newer local mining outputs are preserved: a reproducible 15,000-encounter sample, 86 itemsets and 25 cross-domain rules for each algorithm. The previous report assets describe a separate full-data run; they remain unchanged historical deliverables. All UI mining counts come from current artifact metadata.

## Hypothetical scenarios

The 14-day scenario uses `discharges = min(demand, demand / assumed_stay * discharge_realization)` and `next_demand = demand + daily_admissions - discharges`. Demand may exceed available beds; it is not measured occupancy. Assumptions are independent from historical training data. There is no temporal forecasting, staffing, queue, seasonality or uncertainty model.

## Verification and demonstration

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=deliverables/logs/healthline_all_tests.xml
# With HealthLine running on port 8530 and Chrome installed:
.\.venv\Scripts\python.exe tests/healthline_browser.py
.\.venv\Scripts\python.exe tools/verify_healthline.py
```

Automated tests use temporary databases and exercise real records, idempotency, rejection, rollback, concurrent replay, protected resets, SQL, fitted model equivalence, clustering/PCA, both old dashboards and all new pages. Browser checks exercise a real replay, SQL explorer, saved-model inference and scenario save, and capture actual screenshots. See [review evidence](docs/HEALTHLINE_REVIEW.md) and the [three-minute demo](docs/HEALTHLINE_DEMO.md).

## Preservation and publication

Work is on `codex/healthline-2`. Existing uncommitted report/mining work was backed up under ignored `archive/healthline2_before/` before implementation. The original CSV, SQLite warehouse and trained classifier are hash-verified unchanged. Runtime DBs, caches, environment files, private keys and credentials are excluded. New assignments contain only existing public dataset encounter linkage numbers, cluster labels, PCA coordinates and historical outcomes.

**No commit, push, publish, or merge is authorized until the user reviews and explicitly approves the implementation.** Publication review must distinguish the user's pre-existing modifications from this upgrade. The repository remote remains the existing BitsbyBhargav/Healthcare-Intelligence-Platform remote.
