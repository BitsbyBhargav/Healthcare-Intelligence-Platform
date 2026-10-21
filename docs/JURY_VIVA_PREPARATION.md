# Jury viva preparation

## Project and dataset

**1. What problem does the project address?** It combines an encounter-level healthcare warehouse with retrospective readmission classification, association mining and clinical feature profiling. Jury 1 demonstrates warehousing/OLAP; Jury 2 demonstrates data mining and model evaluation.

**2. What is complete and what is future work?** The warehouse, SQL queries, Streamlit views, five-model comparison, selected-model inference, Apriori/FP-Growth, cohort profiles and supplementary Orange workflows are implemented. Bed-capacity forecasting and length-of-stay prediction remain roadmap items.

**3. What is the dataset?** The UCI Diabetes 130-US Hospitals dataset covers historical encounters from 1999-2008. Our preserved local file has 101,766 encounters, 50 columns and 71,518 distinct patients. A patient may have several encounters.

**4. What are the target classes?** `NO`, `>30`, `<30`, encoded in that fixed order. The last class is early readmission. Explain the recorded dataset outcome; do not imply complete lifetime follow-up.

**5. Why do the UCI feature count and local column count differ?** Identifiers and the target are not counted as ordinary input features. Report the verified local shape and explicitly distinguish source columns from the 18 selected model predictors.

**6. What data-quality limitations exist?** Missing markers, empty laboratory results, broad age bands, historical coding, repeated patients, limited follow-up and no external validation. The study population is a selected historical diabetic inpatient cohort.

## Warehousing, ETL and SQL

**7. What is a data warehouse?** An organised analytical store integrating cleaned data for repeatable aggregation and reporting. Ours is a SQLite star schema built from the source encounters.

**8. Explain ETL.** Extract the local CSV, transform missing markers and construct dimension keys, then load fact and dimension tables into SQLite. The source is preserved and encounter IDs are retained.

**9. What is the grain?** One row in `Fact_Admissions` represents one hospital encounter. Patient count and admission count are different measures.

**10. What are the dimensions?** Patient demographics, admission/discharge/source combinations, and diagnosis/specialty combinations. The fact joins them through keys and stores utilisation measures and outcome.

**11. Why use surrogate keys?** Admission and diagnosis combinations need compact unique relational keys. Original patient and encounter identifiers are preserved for joins and auditing, and excluded from model predictors.

**12. What is OLAP roll-up?** Aggregating to a broader grouping, such as admission count and average hospital stay by age band. The SQL groups joined fact/patient rows by age.

**13. What is slice?** Restricting analysis to a subset, such as encounters with more than 15 medications, and comparing their readmission outcomes.

**14. How is integrity checked?** Unique indexes enforce dimension/encounter keys, SQLite integrity checks validate the file, and tests verify the full join retains all 101,766 facts.

**15. What warehouse limitation remains?** The patient dimension keeps the first demographic record. A production warehouse needs a strategy for changing demographics, constraints, incremental updates and clinical data governance.

## Preprocessing and classification

**16. Why is patient separation necessary?** Repeated encounters from the same person can make row-random tests overoptimistic. GroupShuffleSplit keeps each patient's encounters in only one partition.

**17. What are the split sizes?** 60,878 training, 20,400 validation and 20,488 test encounters in the full recorded run. Patient fractions determine these encounter counts, so they are not exact 60/20/20 row percentages.

**18. What prevents preprocessing leakage?** Median imputation, scaling and categorical encoding are inside a fitted pipeline. Each comparison fits preprocessing only on training data. Final refitting uses train plus validation before one test evaluation.

**19. How are missing and unknown inputs handled?** Numeric values use training medians; categorical missing values become `Unknown`; the encoder tolerates unseen categories. Inputs outside the training distribution still require caution.

**20. Which predictors are used?** Eight numerical utilisation/history features and ten categorical demographic/treatment/diagnosis features. Identifiers, the outcome and discharge disposition are excluded. The exact list is in `jury2_features.py`.

**21. Why is this a discharge-time model?** Total hospital days, medication usage and treatment changes are known by discharge. Calling the current model an admission forecast would misrepresent the available information.

**22. What five algorithms were implemented?** Decision Tree, Gaussian Naive Bayes, kNN, Random Forest and XGBoost. Orange's four-learner example is supplementary and does not replace this comparison.

**23. How does a decision tree work?** It recursively chooses feature splits that separate class distributions. Depth and leaf-size constraints reduce overfitting; one tree can be unstable.

**24. How does Gaussian Naive Bayes work?** It combines prior class probabilities and Gaussian feature likelihoods under conditional independence. One-hot predictors are not truly Gaussian and healthcare variables are correlated; its poor observed performance is reported honestly.

**25. How does kNN work?** It finds nearby scaled examples and votes using 31 distance-weighted neighbours. Scaling matters because features have different units. Its high accuracy conceals very low early-readmission recall.

**26. How does Random Forest work?** It averages many trees trained with bootstrap sampling and random feature subsets, reducing variance relative to a single tree. The implemented candidate has 140 trees, maximum depth 18 and minimum leaf size 4.

**27. How does XGBoost differ?** Boosting adds trees sequentially to improve the objective. The candidate uses 150 rounds, depth 5 and learning rate 0.07. It had better early-readmission recall than Random Forest on validation but lower macro F1.

**28. Why choose Random Forest?** It achieved the highest validation macro F1, 0.43471, among the fixed candidate configurations. Selection used validation only. The final refit scored test macro F1 0.43302. This is the selected benchmark model, not proof of universal superiority.

**29. Why not choose the highest accuracy?** kNN validation accuracy was 0.56284 but under-30-day recall only 0.01526. Macro F1 rewards useful performance across all three classes and reduces the dominance of `NO`.

**30. How was imbalance treated?** Four models use balanced sample weights. kNN uses distance weighting and no sample-weight interface. Minority outcomes still perform poorly. No claim is made that class weighting solves imbalance.

**31. What is accuracy?** Correct predictions divided by all test examples. A majority-class model can have respectable accuracy while missing every minority-class example.

**32. What are precision and recall?** For a chosen class, precision is TP/(TP+FP), and recall is TP/(TP+FN). Random Forest's early-readmission precision is 19.93% and recall 30.04% on the held-out test set.

**33. What is F1 and macro F1?** F1 is the harmonic mean of precision and recall. Macro F1 averages the three class F1 scores equally; weighted F1 weights them by support.

**34. How do you read the confusion matrix?** Rows are true classes and columns are predicted classes, ordered `NO`, `>30`, `<30`. Of 2,367 early-readmission encounters, 711 were correctly predicted as `<30`; the remaining 1,656 were assigned to the other classes.

**35. What is ROC-AUC?** ROC varies the score threshold and plots sensitivity against false-positive rate. Multiclass evaluation uses one class versus the rest and macro averaging. Test macro AUC is 0.6503. It measures ranking, not calibration or clinical benefit.

**36. Are probabilities reliable clinical risks?** They are uncalibrated model outputs. Class weighting, historical sampling and population differences affect calibration. No prospective clinical validation has been performed.

**37. What does feature importance mean here?** Permutation importance measures the decrease in macro F1 after shuffling a predictor on a fixed 250-row test sample. Two repeats make it exploratory; correlated features and sampling noise limit interpretation.

**38. Can another run change the winner?** Yes. Different patient splits, candidate settings, feature choices or data versions can change scores. Fixed seeds and dependency locks improve reproducibility but do not establish statistical certainty.

## Association mining and profiling

**39. What is a transaction?** A hospital encounter represented by broad diagnosis groups and active medication names. Duplicate diagnosis groups are collapsed, and absent medications and identifiers are excluded.

**40. What does support mean?** The proportion of all encounters containing both rule sides. At minimum support 3%, a retained itemset appears in at least about 3,053 encounters.

**41. What is confidence?** P(consequent | antecedent). It is directional and can be high merely because the consequent is common.

**42. What is lift?** Confidence divided by consequent prevalence. A value above 1 indicates positive co-occurrence relative to independence. Lift 1.229 is modest enrichment and does not prove treatment efficacy.

**43. How does Apriori work?** It uses downward closure: every subset of a frequent itemset must be frequent. It generates and prunes candidates by increasing itemset length.

**44. How does FP-Growth work?** It compresses common transaction prefixes and recursively mines conditional patterns without Apriori's explicit candidate generation. Actual runtime depends on data density, item universe and implementation.

**45. What did the algorithms produce?** Both produced 85 frequent itemsets and 23 filtered diagnosis/medication rules on all 101,766 encounters. The tests verify matching complete outputs and independently recompute a rule's metrics.

**46. Explain a real rule.** Diabetes plus Endocrine diagnosis groups imply insulin exposure with support 4.34%, confidence 65.67% and lift 1.229. This describes observed prescribing co-occurrence, with potential confounding.

**47. Do these rules prove causation?** No. Disease severity, clinical protocols, repeated visits and other factors may explain patterns. The analysis cannot recommend medicines or prove that a medication causes or prevents readmission.

**48. What is clinical profiling?** Descriptive aggregation by age, diagnosis, medication count, prior inpatient visits and stay bands. Prior inpatient groups 0, 1 and 2+ have observed early-readmission rates 8.44%, 12.92% and 21.40%. These are encounter-weighted associations.

## Streamlit, Orange and validation

**49. What are the three faculty dashboards?** Association Mining, Model Benchmark and Best Model. They show rules/itemsets, five validation score comparisons, and selected-model holdout metrics, confusion matrix, ROC, report and importance.

**50. Does the application retrain on each click?** No. It reads cached output tables and loads the fitted joblib bundle for the example risk form. This keeps the demonstration responsive and separates evaluation from display.

**51. Why did Orange report no discrete features?** The original workflows had no saved File selection and could load default continuous Iris data. The exported `.tab` file already had discrete headers. The repaired workflows bind the intended files, which Orange verifies as 17 discrete inputs.

**52. What is Orange's native tab format?** Three header rows: variable names, variable types and optional roles such as `class`. Association data uses discrete attributes and no class; classification explicitly marks `readmitted` as class.

**53. Why do Orange scores and rule counts differ?** Orange uses a separate 3,000-unique-patient sample, four learners, different feature representation and its own cross-validation. Its diagnosis columns retain diagnosis position; Python baskets deduplicate across positions. The experiments must not be conflated.

**54. How is the work tested?** A 29-test pytest suite, full-data pipeline runs, installed Orange widget execution, real browser interactions, genuine screenshots and PDF rendering checks. Failure logs and repairs are retained for transparency.

**55. What should improve before clinical use?** External and temporal validation, calibration, subgroup evaluation, bias assessment, richer clinical context, prospective workflow study and appropriate clinical oversight. A better academic next step is a carefully evaluated modelling improvement, not an unsupported deployment claim.

**56. What is the roadmap for bed capacity?** Add time-stamped admission/discharge data, validated length-of-stay or occupancy forecasting, capacity constraints and operational evaluation. The current dataset and implementation do not provide a validated live capacity forecast.

## Five-minute demonstration sequence

1. Show the Overview and identify the historical cohort and discharge-time scope.
2. Open Association Mining, switch algorithm and explain support, confidence and lift for one real rule.
3. Open Model Benchmark and explain why macro F1 selects Random Forest despite kNN accuracy.
4. Open Best Model, read the <30-day confusion-matrix row and acknowledge low recall/precision.
5. Run a hypothetical risk-form input, then show a clinical profile and the separate Orange workflows.
6. Close with reproducibility, tested evidence and the future operational roadmap.
