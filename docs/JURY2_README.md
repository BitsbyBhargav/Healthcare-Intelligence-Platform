# Healthcare Intelligence Platform

Integrated Clinical & Operational Healthcare Intelligence Platform: Data Warehouse with AI-Driven Patient Readmission & Bed Capacity Prediction.

Jury 2 working scope: **Predictive Patient Risk Mining and Clinical Feature Profiling using Healthcare Data**. Bed-capacity and length-of-stay forecasting remain future work. This is a retrospective academic prototype; readmission inference uses discharge-time variables.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run jury_2_dw/app.py
```

The supplied outputs are ready for demonstration. For the exact tested environment, use `requirements-lock.txt` instead of `requirements.txt`. The tested project runtime is Python 3.14; Orange uses its separate installed Python 3.12 environment. Do not install Orange into the project environment.

## Directory guide

```text
data/                         preserved source, canonical SQLite warehouse, star-schema CSVs
jury_1_dw/                    local ETL, SQL OLAP queries, warehouse dashboard, CSV export
jury_2_dw/
  jury2_features.py           shared discharge-time feature definitions
  benchmark_models.py         five models and patient-separated evaluation
  mine_associations.py        Apriori / FP-Growth and diagnosis-medication rules
  clinical_profiling.py       observational cohort analysis
  app.py                     six Streamlit views, including three faculty-required views
  orange_demo/               typed .tab datasets, exporters, two .ows workflows
  outputs/                   current fitted model, scores, rules, profiles, charts
tests/                       pytest, Orange widget checks, browser evidence capture
tools/                       evidence, provenance and PDF production utilities
docs/                        audit, initial inventory, handover, viva and validation
deliverables/                final PDFs, genuine screenshots, execution logs
diagrams/                    original Jury 1 screenshots
archive/                     local historical code/models/database; ignored by Git
DWDM Jury 1.twb               preserved Tableau workbook
HEALTHCARE DASHBOARD.pbix    preserved Power BI asset
```

## Reproduce Jury 1

```powershell
.\.venv\Scripts\python.exe jury_1_dw/etl_and_olap.py
.\.venv\Scripts\python.exe jury_1_dw/sql.py
.\.venv\Scripts\python.exe jury_1_dw/export_tables.py
.\.venv\Scripts\python.exe -m streamlit run jury_1_dw/dashboard.py --server.port 8502
```

ETL reads `data/diabetes_130_us.csv` without modifying it, preserves source encounter identifiers, and writes `data/healthcare_dw.db`. Use `--output PATH` for an isolated warehouse copy. The fact grain is one encounter. Patient, admission-combination and diagnosis-combination dimensions support roll-up and slice queries. The patient dimension uses the first observed demographic record for each patient; it is not a slowly changing dimension.

## Reproduce Jury 2

```powershell
.\.venv\Scripts\python.exe jury_2_dw/benchmark_models.py --train-cap 0 --val-cap 0 --test-cap 0
.\.venv\Scripts\python.exe jury_2_dw/mine_associations.py --sample-size 0
.\.venv\Scripts\python.exe jury_2_dw/clinical_profiling.py
.\.venv\Scripts\python.exe -m streamlit run jury_2_dw/app.py --server.port 8512
```

The first command fits Decision Tree, Gaussian Naive Bayes, kNN, Random Forest and XGBoost. It selects by validation macro F1, using under-30-day recall to break a tie, then refits the selected pipeline on training plus validation and evaluates it on the untouched test patients. Omitting caps uses the script's faster sampled defaults; label those runs as sampled. The recorded full run used 60,878 training, 20,400 validation and 20,488 test encounters.

The current selected model is Random Forest: test accuracy 0.5111, macro F1 0.4330, macro one-vs-rest ROC-AUC 0.6503, under-30-day recall 0.3004. The majority-class baseline has higher accuracy; macro F1 exposes its inability to recognise minority classes. Outputs and the report discuss this limitation.

Mining uses all 101,766 encounters, 3% minimum support, 35% minimum confidence, lift at least 1 and itemsets of at most three items. Both algorithms produce 85 itemsets and 23 filtered rules. Clinical profiles cover age, primary diagnosis, medication count, prior inpatient visits and length of stay.

## Orange preparation and demonstration

```powershell
.\.venv\Scripts\python.exe jury_2_dw/orange_demo/prepare_orange_data.py
& "$env:LOCALAPPDATA\Programs\Orange\python.exe" jury_2_dw/orange_demo/build_workflows.py
& "$env:LOCALAPPDATA\Programs\Orange\python.exe" tests/verify_orange.py
& "$env:LOCALAPPDATA\Programs\Orange\pythonw.exe" -m Orange.canvas --no-welcome jury_2_dw/orange_demo/jury2_association.ows
& "$env:LOCALAPPDATA\Programs\Orange\pythonw.exe" -m Orange.canvas --no-welcome jury_2_dw/orange_demo/jury2_classification.ows
```

Installed and tested: Orange 3.40.0 and Orange3-Associate 1.4.0. Adjust the Orange installation path if necessary. Rebuild `.ows` files after moving the repository; they include a local path and a workflow-relative fallback. Only open workflow files from trusted sources because Orange settings use pickle serialization.

See `docs/ORANGE_DEMONSTRATION.md` for the widget sequence, thresholds, interpretation and diagnostic details. Orange uses 3,000 distinct patients and four learners, as a supplementary experiment. The five-model faculty comparison is the Python/Streamlit benchmark.

## Validation and evidence

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q --junitxml=deliverables/logs/pytest.xml
# With Streamlit running at 127.0.0.1:8512 and Google Chrome installed:
.\.venv\Scripts\python.exe tests/browser_evidence.py
.\.venv\Scripts\python.exe tools/record_provenance.py
.\.venv\Scripts\python.exe tools/build_reports.py
.\.venv\Scripts\python.exe tools/validate_deliverables.py
```

The browser evidence script uses an isolated headless Chrome session and saves genuine application screenshots. The reports require those screenshots and the actual output files. The original dataset is available from [UCI](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008); its historical coverage is 1999-2008. The local source contains 101,766 rows and 71,518 patients.

## Publication assets

The published project retains the source dataset, canonical Jury 1 warehouse, original BI assets, the selected fitted model, measured results, Orange files, testing evidence and both Jury 2 PDFs. The fitted joblib pipeline uses lossless compression; its predictions, probabilities and all tree arrays were checked against the uncompressed artifact on 500 source encounters. Model selection and reported metrics are unchanged.

Virtual environments, caches, local credentials, temporary exports, experimental model dumps and runtime/install logs are ignored. The selected inference pipeline is explicitly retained so Live Risk Studio works after installation without retraining. See `docs/PUBLICATION_CHECKLIST.md` for the publishing checks and recovery record.

## Troubleshooting

* Port occupied: choose `--server.port 8512` or another free port. The verification run used 8512.
* Missing results: run the corresponding benchmark, mining or profiling command. The dashboard gives an explicit error for absent CSV/JSON outputs.
* Incompatible model: install the locked dependencies and regenerate the benchmark. Load only locally produced, trusted joblib artifacts.
* Orange says there are no discrete features: open File and select `orange_associations.tab`, not Iris or a numeric CSV. Rebuild and reopen the workflow after relocating the project.
* Orange Tree fails: use the bounded settings saved by the workflow generator; learner defaults are not the supplementary experiment specification.
* Orange import says the paging file is too small: close extra Orange/analytical sessions and run one Orange process at a time. The verification does not require changing Windows settings.
* Original data: do not replace it with a sample. `--data` and `--output` allow isolated experiments.

See `docs/TECHNICAL_HANDOVER.md`, `docs/JURY_VIVA_PREPARATION.md`, `docs/CLEANUP_AUDIT.md` and `docs/VALIDATION.md` for detailed handover and evidence.
