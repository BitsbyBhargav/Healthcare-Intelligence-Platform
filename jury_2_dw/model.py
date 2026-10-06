from pathlib import Path

from imblearn.over_sampling import SMOTE
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    fbeta_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "diabetes_130_us.csv"
df = pd.read_csv(DATA_PATH, low_memory=False)

# Binary Target Formulation
df["target"] = df["readmitted"].apply(lambda x: 1 if x == "<30" else 0)
X = pd.get_dummies(df.drop(columns=["readmitted", "target"]), drop_first=True)
y = df["target"]

# Train, validation, and test splits; reserve test data for final evaluation.
X_train_validation, X_test, y_train_validation, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
X_train, X_validation, y_train, y_validation = train_test_split(
    X_train_validation, y_train_validation, test_size=0.25,
    random_state=43, stratify=y_train_validation
)

# Fit preprocessing and SMOTE on training data only.
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_validation_scaled = scaler.transform(X_validation)
X_test_scaled = scaler.transform(X_test)

smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

# Fit Random Forest Classifier
rf_model = RandomForestClassifier(
    n_estimators=100, max_depth=15, random_state=42
)
rf_model.fit(X_train_res, y_train_res)

TARGET_RECALL = 0.70
validation_probabilities = rf_model.predict_proba(X_validation_scaled)[:, 1]
_, validation_recalls, thresholds = precision_recall_curve(
    y_validation, validation_probabilities
)
eligible_thresholds = thresholds[validation_recalls[:-1] >= TARGET_RECALL]
decision_threshold = eligible_thresholds[-1]

# Evaluate once on the untouched test set using the validation-selected threshold.
test_probabilities = rf_model.predict_proba(X_test_scaled)[:, 1]
y_pred = (test_probabilities >= decision_threshold).astype(int)
roc_auc = roc_auc_score(y_test, test_probabilities)
f2_score = fbeta_score(y_test, y_pred, beta=2)
test_report = classification_report(y_test, y_pred, output_dict=True)

RESULTS_PATH = Path(__file__).resolve().parent / "model_scores.csv"
score_row = {
    "run": "Run 3",
    "strategy": "SMOTE + validation-tuned threshold",
    "decision_threshold": float(decision_threshold),
    "roc_auc": roc_auc,
    "f2_score": f2_score,
    "accuracy": test_report["accuracy"],
    "class_0_precision": test_report["0"]["precision"],
    "class_0_recall": test_report["0"]["recall"],
    "class_0_f1": test_report["0"]["f1-score"],
    "class_0_support": test_report["0"]["support"],
    "class_1_precision": test_report["1"]["precision"],
    "class_1_recall": test_report["1"]["recall"],
    "class_1_f1": test_report["1"]["f1-score"],
    "class_1_support": test_report["1"]["support"],
}
score_history = pd.read_csv(RESULTS_PATH)
score_history = score_history[score_history["run"] != score_row["run"]]
score_history = pd.concat(
    [score_history, pd.DataFrame([score_row])], ignore_index=True
)
score_history.to_csv(RESULTS_PATH, index=False)

print("Decision threshold:", round(float(decision_threshold), 4))
print("ROC-AUC:", roc_auc)
print("F2-score:", round(f2_score, 3))
print(classification_report(y_test, y_pred))
print("Score table:", RESULTS_PATH)