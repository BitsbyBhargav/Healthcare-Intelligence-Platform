"""Jury 2 Unit III: Apriori vs FP-Growth on diagnosis-medication transactions.

Each transaction represents one hospital encounter. Rules express associations,
not medication efficacy, diagnosis certainty, or causal medical relationships.
"""
from __future__ import annotations

import argparse
import json
import inspect
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder

from jury2_features import diagnosis_group

ROOT = Path(__file__).resolve().parents[1]
MEDICATIONS = [
    "metformin", "repaglinide", "nateglinide", "chlorpropamide",
    "glimepiride", "glipizide", "glyburide", "pioglitazone",
    "rosiglitazone", "acarbose", "miglitol", "insulin",
    "glyburide-metformin", "glipizide-metformin",
]
ACTIVE = {"steady", "up", "down"}


def build_transactions(df: pd.DataFrame) -> list[list[str]]:
    """Use grouped diagnoses and medication exposure as basket items."""
    transactions = []
    for record in df.to_dict(orient="records"):
        items = set()
        for diag_col in ("diag_1", "diag_2", "diag_3"):
            group = diagnosis_group(record.get(diag_col))
            if group != "Unknown":
                items.add("DIAG:" + group)
        for med in MEDICATIONS:
            if str(record.get(med, "No")).strip().lower() in ACTIVE:
                items.add("MED:" + med)
        transactions.append(sorted(items))
    return transactions


def show_items(value) -> str:
    return " | ".join(sorted(value))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "diabetes_130_us.csv")
    ap.add_argument("--output", type=Path, default=ROOT / "jury_2_dw" / "outputs")
    ap.add_argument("--sample-size", type=int, default=15000,
                    help="Rows sampled with fixed seed; 0 = all rows")
    ap.add_argument("--min-support", type=float, default=0.03)
    ap.add_argument("--min-confidence", type=float, default=0.35)
    ap.add_argument("--min-lift", type=float, default=1.0)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not 0 < args.min_support <= 1 or not 0 <= args.min_confidence <= 1:
        raise ValueError("Support must be in (0,1], confidence in [0,1].")
    df = pd.read_csv(args.data, low_memory=False)
    if args.sample_size > 0 and len(df) > args.sample_size:
        df = df.sample(n=args.sample_size, random_state=42)
    print(f"Mining {len(df):,} hospital encounters...", flush=True)

    transactions = build_transactions(df)
    te = TransactionEncoder()
    basket = pd.DataFrame(te.fit(transactions).transform(transactions), columns=te.columns_)
    print(f"Unique clinical items: {basket.shape[1]}", flush=True)
    methods = {"Apriori": apriori, "FP-Growth": fpgrowth}
    summary = {}
    all_rules = {}
    for name, algorithm in methods.items():
        start = time.perf_counter()
        freq = algorithm(basket, min_support=args.min_support, use_colnames=True, max_len=3)
        seconds = time.perf_counter() - start
        rule_kwargs = {"metric": "confidence", "min_threshold": args.min_confidence}
        # mlxtend 0.23.x releases differ in whether num_itemsets is required.
        if "num_itemsets" in inspect.signature(association_rules).parameters:
            rule_kwargs["num_itemsets"] = len(basket)
        rules = association_rules(freq, **rule_kwargs) if not freq.empty else pd.DataFrame()
        if not rules.empty:
            # Only clinically relevant rules with one diagnosis and one medication
            def cross_domain(row):
                both = row["antecedents"] | row["consequents"]
                return any(x.startswith("DIAG:") for x in both) and any(x.startswith("MED:") for x in both)
            rules = rules[rules.apply(cross_domain, axis=1)]
            rules = rules[rules["lift"] >= args.min_lift].copy()
            rules = rules.sort_values(["lift", "confidence", "support"], ascending=False)
        freq_out = freq.copy()
        freq_out["itemsets"] = freq_out["itemsets"].apply(show_items)
        freq_out.to_csv(args.output / f"{name.lower().replace('-', '_')}_itemsets.csv", index=False)

        if not rules.empty:
            out = rules[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
            out["antecedents"] = out["antecedents"].map(show_items)
            out["consequents"] = out["consequents"].map(show_items)
            out.insert(0, "algorithm", name)
        else:
            out = pd.DataFrame(columns=["algorithm", "antecedents", "consequents", "support", "confidence", "lift"])
        out.to_csv(args.output / f"{name.lower().replace('-', '_')}_rules.csv", index=False)
        all_rules[name] = out
        summary[name] = {"seconds": round(seconds, 3), "frequent_itemsets": int(len(freq)),
                         "cross_domain_rules": int(len(out))}
        print(f"{name}: {len(freq)} frequent itemsets, {len(out)} cross-domain rules, {seconds:.2f} s", flush=True)

    # Results should agree when min-support/max-len and transaction set match.
    summary["settings"] = {"sampled_encounters": int(len(df)), "unique_items": int(basket.shape[1]),
                           "min_support": args.min_support, "min_confidence": args.min_confidence,
                           "min_lift": args.min_lift, "max_itemset_len": 3}
    (args.output / "mining_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    top = all_rules["FP-Growth"].head(12)
    fig, ax = plt.subplots(figsize=(11, 6))
    if len(top):
        labels = [f"{a[:31]} → {b[:31]}" for a, b in zip(top["antecedents"], top["consequents"])]
        ax.barh(range(len(top)), top["lift"][::-1])
        ax.set_yticks(range(len(top)), labels[::-1], fontsize=8)
        ax.set_xlabel("Lift")
        ax.set_title("Diagnosis–medication association patterns (FP-Growth)")
    else:
        ax.text(0.5, 0.5, "No qualifying cross-domain rules. Try --min-support 0.01", ha="center", va="center")
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(args.output / "top_association_rules.png", dpi=180)
    plt.close(fig)
    print("Saved mining outputs to", args.output.resolve(), flush=True)


if __name__ == "__main__":
    main()
