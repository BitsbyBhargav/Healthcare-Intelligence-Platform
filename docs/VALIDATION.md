# Execution and validation record

## Executed pipeline commands

Commands below ran in PowerShell from the repository root on 21 October 2026. `$orange` represents `C:\Users\offic\AppData\Local\Programs\Orange\python.exe`.

```powershell
.\.venv\Scripts\python.exe jury_2_dw/orange_demo/prepare_orange_data.py
& $orange jury_2_dw/orange_demo/build_workflows.py
& $orange tests/verify_orange.py
.\.venv\Scripts\python.exe jury_2_dw/benchmark_models.py --train-cap 0 --val-cap 0 --test-cap 0
.\.venv\Scripts\python.exe jury_2_dw/mine_associations.py --sample-size 0
.\.venv\Scripts\python.exe jury_2_dw/clinical_profiling.py
.\.venv\Scripts\python.exe jury_1_dw/etl_and_olap.py
.\.venv\Scripts\python.exe jury_1_dw/sql.py
.\.venv\Scripts\python.exe jury_1_dw/export_tables.py
.\.venv\Scripts\python.exe -m pytest -q --junitxml=deliverables/logs/pytest.xml
.\.venv\Scripts\python.exe -m streamlit run jury_2_dw/app.py --server.headless true --server.address 127.0.0.1 --server.port 8512 --browser.gatherUsageStats false
.\.venv\Scripts\python.exe tests/browser_evidence.py
.\.venv\Scripts\python.exe tools/record_provenance.py
```

## Results

* Backup: 70 non-cache project files verified with SHA-256 against the external pre-edit backup. The dataset remains byte-identical.
* Full-data benchmark: completed, five candidates, 101,766 encounters, patient-separated train/validation/test. Random Forest selected on validation macro F1. Its holdout scores are in `best_model_report.json` and full execution output in `deliverables/logs/benchmark.log`.
* Mining: completed on all encounters, both algorithms yield 85 itemsets and 23 filtered rules. Complete outputs agree; an independent metric calculation is covered by tests.
* Profiling: completed on all encounters, covering five grouping dimensions. Group counts and early-readmission totals are verified for complete-cohort profiles.
* Warehouse: rebuilt from the preserved local CSV; 101,766 joined fact rows, unique keys and SQLite integrity pass. Roll-up, slice and table export commands completed.
* Pytest: **29 passed**, zero final failures. Includes seven diagnosis cases, feature/missing handling, patient separation, all five algorithms on lightweight data, saved artifact inference, mining metrics, profiles, warehouse sample/full integrity, all six Jury 2 views, missing/corrupt result handling, Jury 1 dashboard, and execution from another working directory. The small-data training tests are smoke tests; the separately logged benchmark is the full-data run.
* Streamlit: startup health endpoint returned HTTP 200. Browser checks passed for Association Mining, Model Benchmark, Best Model, Clinical Profiling and Live Risk Studio, including algorithm switching, a lift-slider input, metric selection, stay-profile selection and a saved-model prediction. Overview is tested by AppTest and initial browser loading. Browser page-error list is empty.
* Screenshots: genuine Chrome viewport captures, inspected visually, in `deliverables/evidence`. They show actual generated results and working controls.
* Orange: XML/classes/channels/domains checked; 17 discrete association inputs, 77 itemsets, 45 output rules. Four configured learners pass supplementary five-fold evaluation; Confusion Matrix, ROC, Distributions and Rule Table receive real inputs. Desktop rule output and final Test & Score are inspected separately. Results use 3,000 unique patients and are not the Python benchmark scores.

## Failures encountered and corrections

1. Initial Orange workflows had no saved dataset selection. Correct `.tab` files loaded as discrete, while default Iris reproduced the reported message. Explicit File settings repair the workflow. This is a verified failure mechanism; the original user's pre-edit File selection could not be recovered from an unsaved session.
2. Orange desktop classification exposed a failed Tree learner with its default binary categorical splitting. The generator now disables exhaustive binary splitting and sets bounded depth/minimum sample settings. The verification harness now reads the saved workflow settings, and the revised real-widget/CV checks pass.
3. The first pytest run had 27 passes and two failures: a test wrongly assumed SQL row order, and a subprocess ran out of memory while application test caches accumulated. The key comparison now uses a set and test caches are released between tests. The subsequent run passed all 29 cases. Initial failure output is retained as `pytest_initial.log`.
4. A pandas downcasting warning was removed by replacing marker conversion with a mask. The subsequent suite emitted no warning summary.
5. Port 8501 was occupied. A separate verification app used 8512; the existing process was left alone.
6. Playwright's browser download failed. The browser test uses installed Google Chrome instead. Download output remains in `browser_install.log`.
7. The initial browser radio action targeted a hidden native input intercepted by Streamlit's visual label. The test now clicks the visible label, and the full interaction run passes. The failure is retained in `browser_radio_failure.log`.
8. The app closure stopped the verification server and in-progress browser work. The server was restarted, its health checked, and browser evidence recaptured. A startup race produced one connection-refused attempt before the server was ready; the completed later run is recorded in `browser.json`.
9. An initial provenance serialization rejected XGBoost's NaN missing-value parameter; the recorder explicitly serializes that configuration as the string `NaN`. It does not alter the model or its predictions.
10. Running a second Orange Python process alongside the desktop instance reached the machine's virtual-memory limit and caused import/paging-file failures. The temporary desktop instance opened for verification was closed after capturing evidence, then Orange validation was rerun on its own. No operating-system memory settings were changed. Avoid running several Orange and model sessions simultaneously on this machine.

## Warnings and limits

Orange widgets emit upstream deferred-method decoration warnings (Associate commit and learner apply methods), recorded in `orange.log`. Rule output, learner evaluation and table rendering pass despite these warnings. Do not suppress them and claim a warning-free Orange runtime.

The PDFs and their render/text/layout validation are recorded by `tools/validate_deliverables.py` in `deliverables/logs/pdf_validation.json`. The final Git state and complete file list are recorded in `FINAL_COMPLETION_REPORT.md` and `FINAL_TREE.txt`.

Publication preparation: the selected model is losslessly compressed, with identical predictions/probabilities on 500 encounters and identical arrays in all trees. The main pytest suite is rerun for the publication artifact. Startup and package-install logs are local-only and ignored; retained test, benchmark, mining, profiling, Orange and PDF evidence remains published. The separate publication audit records credential-pattern checks, ignore-rule probes and GitHub file-size checks. Historical test results and the two PDFs retain their verified analytical findings.

No external/temporal clinical validation, calibration, subgroup fairness testing or causal analysis was performed. The Tableau and Power BI assets and historical Jury 1 screenshots are preserved, but desktop interaction in those BI applications has not been retested. Orange widget inputs are automated; desktop clicks through every ROC target and confusion-matrix cell are not exhaustively tested. These limits are explicit, rather than marked as passed.
