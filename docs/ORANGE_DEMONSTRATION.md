# Orange demonstration

Use the Orange commands in README. Tested installation: Orange 3.40.0, Orange3-Associate 1.4.0 in its separate Python 3.12 environment.

## Repair evidence

The original association `.tab` already contained 17 correctly marked discrete features. Installed Orange loaded all 3,000 rows and recognised all 17 inputs as discrete. The workflow XML had no saved File settings, permitting default Iris data to enter the mining widgets. Loading Iris reproduces the exact reported error. This confirms the failure mechanism; no screenshot of the original user's pre-edit File selection was available.

The repaired generator saves `RecentPath` settings with an absolute local path and a workflow-relative fallback. Regenerate workflows after moving the repository. Association inputs contain grouped diagnosis categories and active medication exposure. `?` means an absent item/missing value, so dominant non-use states are not mined. Patient and encounter IDs are excluded. Classification has 18 predictors and `readmitted` explicitly marked as its discrete class.

## Association workflow

1. Open `jury_2_dw/orange_demo/jury2_association.ows` in Orange.
2. Double-click Association data and confirm `orange_associations.tab`, 3,000 rows, 17 categorical inputs and no class.
3. Open Frequent Itemsets: support 3%, maximum displayed size 3. The verified sample gives 77 itemsets.
4. Open FP-Growth Rules: support 3%, confidence 35%, maximum two items on each rule side. The verified sample gives 45 rules, sent to Rule table as a genuine Orange Table.
5. Explain support, confidence and lift, and inspect both rule sides. Orange includes rules below lift 1; the primary Python output filters lift at least 1 and diagnosis/medication combinations.

The sample uses one first encounter per patient (ordered by encounter ID as a practical proxy), then samples 3,000 with seed 42. It does not represent an independently validated clinical cohort. Orange preserves primary/secondary/tertiary diagnosis positions, whereas the Python mining pipeline deduplicates diagnosis groups across positions. Rule counts therefore differ by design.

## Classification workflow

1. Open `jury_2_dw/orange_demo/jury2_classification.ows`.
2. Confirm `orange_classification.tab` in Classification data and `readmitted` as target.
3. Open Test & Score: five-fold stratified cross-validation with Decision Tree, Naive Bayes, kNN and Random Forest. Its four learners are supplementary; the primary benchmark has five.
4. Select a learner, then open Confusion Matrix and ROC Analysis. Switch the target class to `<30` for early readmission. Use Distributions to inspect cohort and class distributions.
5. Explain why these sample-based cross-validation scores differ from the full patient-group holdout benchmark.

The workflow explicitly disables the Tree widget's exhaustive binary categorical splits, which failed in the original desktop Test & Score check. It uses a maximum depth of 8, minimum leaf 10 and minimum internal size 20. kNN uses 15 neighbours; Random Forest uses 100 trees with repeatable training. Settings are loaded from the generated workflow in the automated Orange test so it exercises the demonstration configuration.

## Verification boundaries

`tests/verify_orange.py` checks workflow XML, imported widget classes, input/output channel names, data domains, real itemset/rule computation, the rule-table output, four-learner cross-validation, and Confusion Matrix/ROC/Distributions widget inputs. Counts, metrics and versions are saved to `deliverables/logs/orange_validation.json`. Desktop evidence is stored in `deliverables/evidence`. Read the final validation record for exactly which desktop outputs were inspected. An upstream Orange3-Associate warning about deprecated deferred commit decoration is recorded; it does not prevent the verified rule output.
