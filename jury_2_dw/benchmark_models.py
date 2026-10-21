"""Jury 2: comparable 5-model benchmark with patient-disjoint splits.

Run from repository root:
    python jury_2_dw/benchmark_models.py
    python jury_2_dw/benchmark_models.py --train-cap 40000 --val-cap 8000

Model-selection scores are from validation; the selected model is evaluated
on a separate patient-disjoint holdout test set. Row caps speed up live demos.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay,
    f1_score, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from jury2_features import CATEGORICAL, FEATURES, LABELS, NUMERIC, build_features

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "diabetes_130_us.csv"
DEFAULT_OUTPUT = ROOT / "jury_2_dw" / "outputs"
SEED = 42


def sampled_indices(y: pd.Series, cap: int, seed: int) -> np.ndarray:
    """Stratified subset; return all rows if cap is zero or already small."""
    if cap <= 0 or len(y) <= cap:
        return np.arange(len(y))
    chosen, _ = train_test_split(
        np.arange(len(y)), train_size=cap, stratify=y, random_state=seed
    )
    return np.sort(chosen)


def prepare(raw: pd.DataFrame):
    """Keep original three outcomes; split by patient to avoid identity leakage."""
    needed = {"patient_nbr", "readmitted"}
    if not needed.issubset(raw.columns):
        raise ValueError(f"Missing required source columns: {sorted(needed - set(raw.columns))}")
    labels = raw["readmitted"].astype(str).str.strip()
    keep = labels.isin(LABELS) & raw["patient_nbr"].notna()
    raw = raw.loc[keep].reset_index(drop=True)
    y = raw["readmitted"].astype(str).str.strip().map({x:i for i,x in enumerate(LABELS)})
    groups = raw["patient_nbr"].astype(str)
    X = build_features(raw)
    split = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    develop_i, test_i = next(split.split(X, y, groups=groups))
    split_val = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED+1)
    train_sub, val_sub = next(split_val.split(
        X.iloc[develop_i], y.iloc[develop_i], groups=groups.iloc[develop_i]
    ))
    train_i, val_i = develop_i[train_sub], develop_i[val_sub]
    assert not (set(groups.iloc[train_i]) & set(groups.iloc[val_i]))
    assert not (set(groups.iloc[train_i]) & set(groups.iloc[test_i]))
    assert not (set(groups.iloc[val_i]) & set(groups.iloc[test_i]))
    return X, y, train_i, val_i, test_i


def preprocessing():
    """Impute, scale numeric features and one-hot encode categorical features."""
    num = Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scale", StandardScaler())])
    cat = Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                    ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=50,
                                             sparse_output=False))])
    return ColumnTransformer([("num", num, NUMERIC), ("cat", cat, CATEGORICAL)],
                             sparse_threshold=0)


def classifiers():
    return {
        "Decision Tree": DecisionTreeClassifier(
            max_depth=12, min_samples_leaf=30, random_state=SEED),
        "Naive Bayes": GaussianNB(),
        "KNN": KNeighborsClassifier(n_neighbors=31, weights="distance", n_jobs=2),
        "Random Forest": RandomForestClassifier(
            n_estimators=140, max_depth=18, min_samples_leaf=4,
            n_jobs=4, random_state=SEED),
        "XGBoost": XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.07,
            subsample=0.85, colsample_bytree=0.85, tree_method="hist",
            objective="multi:softprob", eval_metric="mlogloss", n_jobs=4,
            random_state=SEED),
    }


def fit_model(name, estimator, X, y):
    """Fit full preprocessing and use class weights for capable algorithms."""
    pipe = Pipeline([("preprocess", preprocessing()), ("classifier", clone(estimator))])
    kwargs = {}
    if name != "KNN":
        kwargs["classifier__sample_weight"] = compute_sample_weight("balanced", y)
    pipe.fit(X, y, **kwargs)
    return pipe


def metrics(pipe, X, y) -> dict:
    pred = pipe.predict(X)
    probs = pipe.predict_proba(X)
    result = {
        "accuracy": accuracy_score(y, pred),
        "precision_macro": precision_score(y, pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y, pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y, pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y, pred, average="weighted", zero_division=0),
        "recall_under_30": recall_score(y, pred, labels=[2], average="macro", zero_division=0),
        "precision_under_30": precision_score(y, pred, labels=[2], average="macro", zero_division=0),
    }
    try:
        result["roc_auc_ovr_macro"] = roc_auc_score(
            y, probs, multi_class="ovr", average="macro", labels=[0,1,2])
    except ValueError:
        result["roc_auc_ovr_macro"] = float("nan")
    return result


def save_plots(out: Path, comparison: pd.DataFrame, best, X_test, y_test):
    plt.style.use("seaborn-v0_8-whitegrid")
    a = comparison.set_index("model")[["accuracy", "f1_macro", "recall_under_30"]]
    ax = a.plot.bar(figsize=(11, 5), width=0.8)
    ax.set_title("Validation comparison: 5 classification algorithms")
    ax.set_ylabel("Score (0–1)")
    ax.set_ylim(0, 1)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out / "model_comparison.png", dpi=180)
    plt.close()

    pred = best.predict(X_test)
    cm = confusion_matrix(y_test, pred, labels=[0, 1, 2])
    fig, ax = plt.subplots(figsize=(6.5, 5.4))
    ConfusionMatrixDisplay(cm, display_labels=LABELS).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Selected model — unseen test set")
    fig.tight_layout()
    fig.savefig(out / "best_confusion_matrix.png", dpi=180)
    plt.close(fig)

    prob = best.predict_proba(X_test)
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, label in enumerate(LABELS):
        binary = (np.asarray(y_test) == i).astype(int)
        if binary.min() == binary.max():
            continue
        fpr, tpr, _ = roc_curve(binary, prob[:, i])
        ax.plot(fpr, tpr, label=f"{label} vs rest")
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Chance")
    ax.set(xlabel="False positive rate", ylabel="True positive rate", title="Selected model — one-vs-rest ROC")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "best_roc.png", dpi=180)
    plt.close(fig)


def save_importance(out, best, X_test, y_test):
    """Model-independent permutation importance on held-out test subset."""
    rng = np.random.default_rng(SEED)
    inds = rng.choice(len(X_test), size=min(250, len(X_test)), replace=False)
    p = permutation_importance(best, X_test.iloc[inds], y_test.iloc[inds],
                               n_repeats=2, scoring="f1_macro", random_state=SEED,
                               n_jobs=1)
    importance = pd.DataFrame({"feature": FEATURES, "importance_mean": p.importances_mean,
                               "importance_std": p.importances_std})
    importance = importance.sort_values("importance_mean", ascending=False)
    importance.to_csv(out / "best_feature_importance.csv", index=False)
    top = importance.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(top["feature"], top["importance_mean"])
    ax.set_title("Permutation importance (held-out sample)")
    ax.set_xlabel("Decrease in macro F1 when feature is shuffled")
    fig.tight_layout()
    fig.savefig(out / "best_feature_importance.png", dpi=180)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--train-cap", type=int, default=25000,
                    help="Max training rows for quick benchmark; 0 means use all")
    ap.add_argument("--val-cap", type=int, default=5000,
                    help="Max validation rows for quick benchmark; 0 means use all")
    ap.add_argument("--test-cap", type=int, default=5000,
                    help="Max final test rows; 0 means all")
    ap.add_argument("--skip-importance", action="store_true")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.data.exists():
        raise FileNotFoundError(f"Dataset not found: {args.data}. Run from repo root or pass --data PATH")

    raw = pd.read_csv(args.data, low_memory=False)
    X, y, ti, vi, ei = prepare(raw)
    X_train, y_train = X.iloc[ti].reset_index(drop=True), y.iloc[ti].reset_index(drop=True)
    X_val, y_val = X.iloc[vi].reset_index(drop=True), y.iloc[vi].reset_index(drop=True)
    X_test, y_test = X.iloc[ei].reset_index(drop=True), y.iloc[ei].reset_index(drop=True)
    a = sampled_indices(y_train, args.train_cap, SEED)
    b = sampled_indices(y_val, args.val_cap, SEED+1)
    c = sampled_indices(y_test, args.test_cap, SEED+2)
    X_train, y_train = X_train.iloc[a], y_train.iloc[a]
    X_val, y_val = X_val.iloc[b], y_val.iloc[b]
    X_test, y_test = X_test.iloc[c], y_test.iloc[c]

    print(f"Dataset={len(X):,} rows | train={len(X_train):,} | validation={len(X_val):,} | holdout test={len(X_test):,}", flush=True)
    print("Labels:", LABELS, "| Prediction point: discharge", flush=True)
    rows = []
    for name, estimator in classifiers().items():
        start = time.perf_counter()
        print(f"Training {name}...", flush=True)
        pipe = fit_model(name, estimator, X_train, y_train)
        row = {"model": name, **metrics(pipe, X_val, y_val),
               "training_seconds": round(time.perf_counter()-start, 2)}
        rows.append(row)
        print(f"  macro F1={row['f1_macro']:.4f} | <30 recall={row['recall_under_30']:.4f} | AUC={row['roc_auc_ovr_macro']:.4f}", flush=True)
    comparison = pd.DataFrame(rows).sort_values(
        ["f1_macro", "recall_under_30"], ascending=False).reset_index(drop=True)
    comparison.round(5).to_csv(args.output / "model_comparison.csv", index=False)
    print("\nVALIDATION MODEL COMPARISON\n", comparison.to_string(index=False), flush=True)

    winner = str(comparison.loc[0, "model"])
    print(f"\nSelected from validation: {winner}. Refit on train+validation subset...", flush=True)
    best = fit_model(winner, classifiers()[winner],
                     pd.concat([X_train, X_val], ignore_index=True),
                     pd.concat([y_train, y_val], ignore_index=True))
    heldout = metrics(best, X_test, y_test)
    report = classification_report(y_test, best.predict(X_test),
                                   labels=[0,1,2], target_names=LABELS,
                                   output_dict=True, zero_division=0)
    summary = {
        "selected_model": winner, "selection_metric": "validation macro F1",
        "prediction_point": "discharge", "class_order": LABELS,
        "dataset_rows": int(len(X)), "train_rows_used": int(len(X_train)),
        "validation_rows_used": int(len(X_val)), "holdout_test_rows_used": int(len(X_test)),
        "patient_disjoint_splits": True,
        "test_metrics": {k:float(v) for k,v in heldout.items()},
        "per_class_test_report": report,
    }
    (args.output / "best_model_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    joblib.dump({"pipeline": best, "labels": LABELS, "features": FEATURES,
                 "model_name": winner, "prediction_point": "discharge"},
                args.output / "best_model.joblib", compress=3)
    save_plots(args.output, comparison, best, X_test, y_test)
    if not args.skip_importance:
        print("Calculating permutation importance...", flush=True)
        save_importance(args.output, best, X_test, y_test)
    print("\nFINAL HOLDOUT TEST METRICS", heldout, flush=True)
    print("Saved artifacts to", args.output.resolve(), flush=True)


if __name__ == "__main__":
    main()
