# Technical handover

## Architecture and scope

The common source is `data/diabetes_130_us.csv`. Jury 1 transforms it into a SQLite star schema. Jury 2 reads the original encounter-level source directly so prior visits, medication information and diagnosis codes remain available. The analyses share feature definitions but have separate purposes: supervised classification predicts recorded readmission outcome; association mining describes diagnosis/medication co-occurrence; profiling summarises observed cohorts. Streamlit reads precomputed results and loads a fitted pipeline only for inference. Orange is a supplementary visual experiment.

There is no hospital connection, live hospital feed, deployed clinical service, bed-capacity model or length-of-stay prediction model. Hospital days are an observed discharge-time predictor and a descriptive profile. The project title describes the broader roadmap.

## Important modules

| Module | Responsibility |
|---|---|
| `jury_1_dw/etl_and_olap.py` | Read local source, validate encounter keys, construct fact/dimension tables, create unique indexes and check SQLite integrity |
| `jury_1_dw/sql.py` | Demonstrate roll-up by age and slice for medication count greater than 15 |
| `jury_1_dw/export_tables.py` | Export the canonical warehouse to four CSV tables |
| `jury_1_dw/dashboard.py` | Historical warehouse KPIs and SQL-derived charts |
| `jury_2_dw/jury2_features.py` | Define 18 predictors, three class labels and broad ICD-9 diagnosis categories |
| `jury_2_dw/benchmark_models.py` | Group splits, training-only preprocessing, five comparable learners, validation selection, holdout test, model/plot export |
| `jury_2_dw/mine_associations.py` | Encounter baskets, Boolean encoding, Apriori/FP-Growth, rule filtering and chart export |
| `jury_2_dw/clinical_profiling.py` | Encounter counts and observed under-30-day rates by five grouping dimensions |
| `jury_2_dw/app.py` | Six application views with precomputed data and saved-model scoring |
| `jury_2_dw/orange_demo/prepare_orange_data.py` | Deterministic unique-patient sample and Orange three-header `.tab` export |
| `jury_2_dw/orange_demo/build_workflows.py` | Generate XML workflows with data references and explicit widget settings |
| `tests/verify_orange.py` | Run installed Orange widgets and supplementary cross-validation |
| `tests/browser_evidence.py` | Exercise the actual Streamlit browser UI and save viewport screenshots |
| `tools/build_reports.py` | Assemble academic PDFs from measured results and actual evidence |

## Data warehouse operation

The fact grain is one source encounter. `Fact_Admissions` holds source encounter ID, patient key, generated admission and diagnosis keys, utilisation measures and readmission outcome. `Dim_Patient` has one record per patient; `Dim_Admission` has one record per admission/discharge/source combination; `Dim_Diagnosis` has one record per primary/secondary diagnosis and specialty combination. Pandas merges use many-to-one validation. Unique indexes detect duplicate keys; the validation suite checks the full fact-to-dimension join count.

The ETL previously fetched data and overwrote the local CSV, replaced original encounter IDs, and wrote a root-level database while the dashboard opened the `data/` database. It now reads the preserved local CSV and all active scripts agree on `data/healthcare_dw.db`. The historical root warehouse is in the local archive and external backup. The dimension design does not preserve changes to patient demographics over encounters. Explain this as a warehouse limitation rather than claiming a full clinical enterprise warehouse.

## Features, missingness and prediction point

Eight numeric features: hospital days, laboratory procedures, procedures, medication count, prior outpatient, emergency and inpatient visits, and diagnosis count. Ten categorical features: age band, gender, race, admission type, insulin status, medication change, diabetes medication flag, A1C result, and two diagnosis groups. Identifiers, readmitted outcome and discharge disposition are excluded from predictors. The patient ID is used only to separate groups.

Question marks and missing values become missing numeric values or categorical `Unknown`. Numeric medians and scaling are fitted inside the training pipeline; categorical values are one-hot encoded with unseen-category handling and minimum frequency 50. The source has empty A1C entries, so the inference UI uses `Unknown` for those observations. Detailed ICD-9 codes are mapped to broad categories; leading-zero numeric diagnoses and decimal diagnoses are supported. This grouping is a technical feature mapping, not a diagnostic service.

Because medication usage and total hospital days are known by discharge, predictions are discharge-time research estimates. There is no admission-time forecasting claim. Dataset outcome `NO` means no recorded readmission in the source definition, rather than a guarantee that a patient was never subsequently hospitalised elsewhere.

## Training, comparison and evaluation

GroupShuffleSplit reserves approximately 20% of patients for test using seed 42, then reserves approximately 25% of the remaining patients for validation using seed 43. Resulting encounter counts are 60,878 / 20,400 / 20,488. Groups are disjoint across partitions. Preprocessing is fit only on training data for comparisons. The same samples and feature definitions are used for all five models. Four algorithms receive balanced sample weights; kNN uses its distance-weighted neighbourhood and has no equivalent sample-weight interface. This difference is explicit.

Decision Tree uses depth 12 and minimum leaf size 30. Gaussian Naive Bayes models class-conditional independent Gaussian features. kNN uses 31 distance-weighted neighbours after scaling. Random Forest uses 140 trees, depth 18 and minimum leaf size 4. XGBoost uses 150 boosting rounds, depth 5, learning rate 0.07, subsampling and histogram trees. There was no broad hyperparameter search; selection is among these fixed candidate configurations.

Validation macro F1 determines the winner, with under-30-day recall as tie-breaker. Macro F1 weights each class equally despite imbalance. Refit the winner on train plus validation; use the untouched test patients once to estimate final performance. The saved joblib bundle contains the complete pipeline, feature names, labels and prediction point. Class order is `NO`, `>30`, `<30`.

The verified winner is Random Forest. Test accuracy is 0.5111, macro F1 0.4330 and macro one-vs-rest AUC 0.6503. Under-30-day precision is 0.1993 and recall 0.3004. An all-`NO` predictor scores about 53.3% test accuracy, illustrating why accuracy alone is unsuitable. The minority class remains poorly predicted. Outputs are uncalibrated research probabilities, and balanced training can alter their relationship to real-world prevalence.

Permutation importance measures the fall in macro F1 when a feature is shuffled on a fixed 250-row test sample with two repeats. It is exploratory and noisy. Correlated predictors and small samples limit interpretation; negative importance can occur. It cannot establish causality or a clinical ranking of risk factors.

## Association mining

Each basket represents one encounter. Broad categories from all three diagnosis columns are deduplicated into `DIAG:category` items. Medications with `Steady`, `Up` or `Down` status become `MED:name` items. Absent medications and identifiers are excluded. The Boolean transaction matrix has 33 observed items.

Both algorithms use support 0.03 and maximum itemset size 3. Rules require confidence at least 0.35 and lift at least 1, and their combined sides must contain both a diagnosis and a medication. This filter allows a mixture of item types on either side; it is not restricted to one diagnosis implying one medication. Each algorithm produces 85 itemsets and 23 filtered rules. The test suite compares complete sorted itemset/rule tables and independently recomputes support, confidence and lift from the original baskets.

Support is P(A and B); confidence is P(B|A); lift is P(B|A)/P(B). A high confidence rule can simply reflect a very common consequent. Lift slightly above 1 is weak enrichment, not a strong medical discovery. The top retained rule has support 4.34%, confidence 65.67% and lift 1.229 for Diabetes plus Endocrine diagnoses implying insulin exposure. Disease severity, prescribing practice and repeated encounters can confound these associations. Neither medication efficacy nor treatment recommendations follow from them.

Apriori enumerates candidate itemsets using downward closure. FP-Growth compresses transactions and recursively grows frequent patterns. On this small item universe, Apriori was faster in this run; FP-Growth is not guaranteed to be faster. Compare outputs and disclose the measured workload rather than claiming universal speed.

## Clinical profiling and application

Profiles aggregate age, primary diagnosis, medication-load bands, prior inpatient visits and observed hospital stay. Each CSV includes cohort size, under-30-day count/rate, mean stay and mean medication count. Diagnosis charts suppress groups with fewer than 500 encounters. Other profile group counts sum to the source count. Rates are encounter-weighted, and repeated patients mean observations are not independent.

The application has Overview, Association Mining, Model Benchmark, Best Model, Clinical Profiling and Live Risk Studio. The three middle faculty views expose the actual rules, five model scores and selected-model test evidence. The risk form uses bounded synthetic example inputs, sends no patient identifiers and calls the saved pipeline without retraining. Missing CSV/JSON files yield explicit messages; class-order validation protects against an incompatible bundle.

## Reproduction and demonstration

Use the ordered commands in README. For the jury: begin with source counts and scope, open Association Mining and explain one rule, compare validation macro F1 across five models, then show Random Forest test confusion matrix and ROC. Use the <30-day row to explain false negatives and precision. Demonstrate one hypothetical discharge-time encounter, then show a profile and the separate Orange workflow. Keep full training outside the live presentation.

Read `docs/VALIDATION.md` for test commands and the actual failures encountered and repaired. The reports are generated from current artifacts; rerun screenshot capture and report generation after changing results. The external backup and `docs/initial_inventory.json` record the pre-edit state. Historical binary models are in `archive/legacy_binary` locally and are not active benchmark outputs.

## Common errors and operational limits

* Run scripts by absolute path or from the repository root; paths derive from each module's location.
* Keep Orange and project dependency environments separate. Workflow generation imports Orange's `RecentPath` type.
* If the Orange workflow moves, regenerate it and confirm the File widget names the correct `.tab` file.
* Use an available Streamlit port. Tests intentionally use 8512 and an isolated browser session.
* If model loading fails after a dependency upgrade, restore the locked environment or retrain and regenerate all outputs.
* There is no external hospital validation, temporal test, calibration study, subgroup fairness analysis or operational simulation. These are future validation tasks, not completed deliverables.
