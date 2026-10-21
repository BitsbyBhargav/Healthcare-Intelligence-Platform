# Final completion report - 21 October 2026

## 1. Final directory structure

```text
data/                 preserved source, canonical SQLite warehouse, schema CSVs
jury_1_dw/            ETL, SQL/OLAP, exports and warehouse dashboard
jury_2_dw/            features, five-model benchmark, mining, profiles and Streamlit
  orange_demo/        typed datasets and two repaired Orange workflows
  outputs/            current model, metrics, rules, profiles, JSON and charts
tests/                pytest, installed Orange checks and genuine browser evidence
tools/                provenance recording, PDF production and final validation
docs/                 audit, inventory, validation, handover and viva preparation
deliverables/         final PDFs, genuine screenshots and execution logs
diagrams/             preserved original Jury 1 screenshots
archive/              local historical recovery copies; ignored by Git
```

The complete file-level tree is `docs/FINAL_TREE.txt`.

## 2. Files created, modified, moved, merged and deleted

`docs/file_changes.json` compares the final files with the verified initial inventory. Existing untracked user work is included in the initial state, rather than incorrectly attributed to this run.

Created: tests, provenance and PDF tools, setup/lock requirements, README, audit/validation/handover/viva documentation, current result JSON exports, final PDFs and genuine screenshot evidence. Repaired: ETL, CSV export, Streamlit app, shared diagnosis grouping, Orange workflow generator and preparation paths. Regenerated: warehouse/fact CSV, full benchmark model/results/charts, full-data mining/profiles and Orange datasets/workflows.

Moved: the nested Orange demo into `jury_2_dw/orange_demo`; seven old binary-classifier code/result files into `archive/legacy_binary`; the old root warehouse into `archive/warehouses`; two Orange session swap files into `archive/orange_session`. Removed after backup: the obsolete wrapper folder and its old launch note. No original data, model or warehouse was discarded. No duplicate implementation was silently merged. See `CLEANUP_AUDIT.md` for reasons and recovery evidence.

## 3. Orange repair and verification

Orange 3.40.0 / Associate 1.4.0 recognise 17 discrete association inputs. The `.tab` header was valid; absent saved File selection allowed default continuous data to reach the widgets. Iris reproduces the exact message. Explicit file references and regenerated workflows repair that failure mechanism. The Tree widget additionally needed bounded multiway categorical splitting to pass desktop Test & Score.

The supplementary 3,000-unique-patient sample produces 77 itemsets and 45 rule-table rows. Four configured learners pass five-fold evaluation. XML/widget channels, class roles, Rules, Itemsets, Rule Table, Confusion Matrix, ROC and Distributions are checked using installed Orange. Actual desktop Rules and Test & Score screenshots are in `deliverables/evidence`. These results are distinct from the full Python benchmark. Read `ORANGE_DEMONSTRATION.md` for launch and interpretation steps.

## 4-5. Classification results and model selection

Full data: 101,766 encounters. Patient-separated partitions contain 60,878 training, 20,400 validation and 20,488 test encounters. Validation comparison:

| Model | Accuracy | Macro F1 | Early-readmission recall | Macro AUC |
|---|---:|---:|---:|---:|
| Random Forest | 0.51412 | 0.43471 | 0.30251 | 0.64618 |
| XGBoost | 0.49230 | 0.42379 | 0.38375 | 0.64569 |
| Decision Tree | 0.43456 | 0.38333 | 0.43671 | 0.60102 |
| kNN | 0.56284 | 0.36120 | 0.01526 | 0.61108 |
| Gaussian Naive Bayes | 0.14319 | 0.12407 | 0.93582 | 0.56495 |

Random Forest wins validation macro F1. This criterion weights all outcome classes equally; kNN's higher accuracy conceals very low early-readmission recall. After refitting the winner on train plus validation, untouched-test accuracy is 0.51113, macro F1 0.43302, macro AUC 0.65031, early-readmission recall 0.30038 and precision 0.19927. The all-NO test baseline has accuracy 0.53304 but macro F1 only 0.23180. The model is limited and is not presented as clinically reliable. Full precision/recall/F1 reports, confusion matrix, ROC and exploratory permutation importance are saved.

## 6. Association mining and profiling

On all 101,766 encounters, Apriori and FP-Growth each produce 85 frequent itemsets and 23 filtered rules: support 3%, confidence 35%, lift at least 1, maximum itemset size 3. Complete outputs match. A real rule's support/confidence/lift is independently recalculated in tests. Both CSV and JSON outputs and measured charts are available. Five clinical profiles cover age, primary diagnosis, medication count, prior inpatient visits and observed stay bands. Interpretations remain observational.

## 7-8. Dashboard and testing results

29 pytest cases pass with zero final failures. They cover source preservation, diagnosis mapping, missing features, patient separation, all five learners on lightweight data, saved inference, rule metrics, profiles, warehouse sample/full integrity, six Jury 2 views, missing/corrupt results, Jury 1 rendering and execution from another working directory. Full-data runs are separately logged from those smoke tests.

Real browser checks pass for Association Mining, Model Benchmark, Best Model, Clinical Profiling and Live Risk Studio, including controls and saved-model scoring. Overview loads initially; Streamlit's health endpoint returns 200. Browser page errors are empty. Jury 1 also renders in a real browser. Genuine screenshots are saved for all required views. Initial failures, fixes, upstream warnings and resource constraints are recorded in `VALIDATION.md` and the raw logs.

## 9-10. Required PDFs

* `deliverables/Jury2_Three_Dashboard_Evidence.pdf` - 7 pages of actual Streamlit screenshots, explanations and results; landscape A3 for readability.
* `deliverables/Jury2_Healthcare_Intelligence_Implementation_Report.pdf` - 30-page A4 academic report, all fourteen requested chapters, table of contents, measured results, code-derived diagrams, genuine screenshots and references.

Team and institution fields remain blank. Final page counts, hashes and all-page rendering/text/bounds checks are in `deliverables/logs/pdf_validation.json`. Rendered pages were visually reviewed and sparse page breaks repaired.

## 11. Team handover material

* `README.md` - overview, directory guide, dependency setup, complete run commands and troubleshooting.
* `docs/TECHNICAL_HANDOVER.md` - architecture, module purpose, data flow, warehouse, algorithms, interpretation and reproduction.
* `docs/JURY_VIVA_PREPARATION.md` - 56 technical questions/answers and demonstration sequence.
* `docs/ORANGE_DEMONSTRATION.md`, `docs/CLEANUP_AUDIT.md`, `docs/VALIDATION.md` - supplementary launch details, recovery and verification.

## 12. Exact commands to run

Run each Streamlit command in a separate terminal after the analysis scripts finish. Installation and Orange paths are documented in README.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Exact tested environment alternative: pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe jury_1_dw/etl_and_olap.py
.\.venv\Scripts\python.exe jury_1_dw/sql.py
.\.venv\Scripts\python.exe jury_1_dw/export_tables.py
.\.venv\Scripts\python.exe -m streamlit run jury_1_dw/dashboard.py --server.port 8502
.\.venv\Scripts\python.exe jury_2_dw/benchmark_models.py --train-cap 0 --val-cap 0 --test-cap 0
.\.venv\Scripts\python.exe jury_2_dw/mine_associations.py --sample-size 0
.\.venv\Scripts\python.exe jury_2_dw/clinical_profiling.py
.\.venv\Scripts\python.exe -m streamlit run jury_2_dw/app.py --server.port 8512
.\.venv\Scripts\python.exe -m pytest -q --junitxml=deliverables/logs/pytest.xml
.\.venv\Scripts\python.exe tests/browser_evidence.py
.\.venv\Scripts\python.exe tools/record_provenance.py
.\.venv\Scripts\python.exe tools/build_reports.py
.\.venv\Scripts\python.exe tools/validate_deliverables.py
.\.venv\Scripts\python.exe jury_2_dw/orange_demo/prepare_orange_data.py
& "$env:LOCALAPPDATA\Programs\Orange\python.exe" jury_2_dw/orange_demo/build_workflows.py
& "$env:LOCALAPPDATA\Programs\Orange\python.exe" tests/verify_orange.py
& "$env:LOCALAPPDATA\Programs\Orange\pythonw.exe" -m Orange.canvas --no-welcome jury_2_dw/orange_demo/jury2_association.ows
& "$env:LOCALAPPDATA\Programs\Orange\pythonw.exe" -m Orange.canvas --no-welcome jury_2_dw/orange_demo/jury2_classification.ows
```

## 13. Remaining limits and manual steps

Fill the personal/institution fields before submission. Tableau and Power BI assets are preserved but were not interactively retested. Orange automated widget checks and two desktop outputs are verified; every possible GUI selection was not exhaustively tested. Close extra analytical sessions if Orange reaches the machine's virtual-memory limit. Regenerate workflow paths after relocating the repository.

The study has no temporal/external validation, calibration, subgroup fairness study or causal analysis. Length-of-stay prediction and bed-capacity forecasting remain future work. The current model uses discharge-time variables and is an academic prototype.

## 14. Final Git and backup state

Working branch: `codex/jury2-finalization`. Publication was authorized after the user's manual demo review. The publication commit is titled `Finalize Jury 2 Healthcare Intelligence Platform` and targets this finalization branch; `main` is not modified. Exact final commit/status and remote verification are recorded after publishing in local `docs/FINAL_GIT_STATE.txt` and reported to the user. Inspect with `git log -1 --oneline` and `git status --short --branch`. See `PUBLICATION_CHECKLIST.md` for the information, artifact-size and recovery checks.

External backup: `C:\Users\offic\OneDrive\Desktop\Healthcare-Intelligence-Platform-backup-20261021`. It includes uncommitted/untracked files and Git metadata; replaceable `.venv` was excluded. Seventy non-cache project files were hash-verified. Original source SHA-256 remains `cbe830d669653c59c6ccb66c98b3c6f8084ff38da94e7c6a1660b2609ac98964`.
