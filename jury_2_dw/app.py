"""Jury 2 | Clinical Risk Intelligence Studio.

Run from the repository root:
    streamlit run jury_2_dw/app.py

Input artifacts from the precomputed Jury 2 benchmark, mining, and profiling
scripts must be placed in jury_2_dw/outputs/. The model is never retrained in
this application. It performs live inference from the saved fitted pipeline.

For academic demonstration only; not a clinical decision support device.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

from jury2_features import FEATURES, LABELS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "jury_2_dw" / "outputs"
DATA = ROOT / "data" / "diabetes_130_us.csv"
COLOR = {"NO": "#376A9A", ">30": "#E8AB54", "<30": "#D96264"}
MODEL_PATH = OUT / "best_model.joblib"
PAGES = [
    "Overview", "Model Benchmark", "Best Model", "Association Mining",
    "Clinical Profiling", "Live Risk Studio",
]

st.set_page_config(
    page_title="Clinical Risk Intelligence | DWDM Jury 2",
    page_icon="🏥", layout="wide", initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1450px;}
h1,h2,h3 {letter-spacing: -.025em;}
.hero {padding: 22px 25px; border-radius: 16px; background:
 linear-gradient(105deg, #143550, #175B70); color:#fff; margin-bottom:19px;}
.hero .eyebrow {text-transform:uppercase; letter-spacing:.14em; font-size:12px; opacity:.82;}
.hero h1 {color:#fff; font-size:29px; margin:6px 0;}
.hero p {color:#D8EBF1; margin:3px 0; font-size:14px;}
.subtext {color:#5F7284; font-size:13px;}
.tag {display:inline-block; border:1px solid #BED3DF; padding:3px 10px;
 border-radius:30px; font-size:12px; margin-right:8px;}
[data-testid="stMetric"] {border:1px solid rgba(121,143,164,.24); border-radius:12px; padding:13px;}
[data-testid="stSidebar"] {border-right: 1px solid rgba(130,152,170,.2);}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Loading trained classifier…")
def load_classifier(path: str):
    """Load only the local trained artifact you created; joblib files can execute code."""
    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or "pipeline" not in artifact or "labels" not in artifact:
        raise ValueError("Model artifact is not the expected Jury 2 pipeline bundle.")
    labels = list(artifact["labels"])
    if labels != LABELS:
        raise ValueError(f"Class order mismatch: model {labels}, expected {LABELS}.")
    return artifact


def from_output(filename: str) -> Path:
    return OUT / filename


def needed(filename: str) -> bool:
    return from_output(filename).is_file()


def require_csv(filename: str) -> pd.DataFrame | None:
    if not needed(filename):
        st.error(f"Missing result: `jury_2_dw/outputs/{filename}`. Run the corresponding Jury 2 analysis script.")
        return None
    try:
        return read_csv(str(from_output(filename)))
    except Exception as exc:
        st.error(f"Cannot read {filename}: {exc}")
        return None


def require_json(filename: str) -> dict | None:
    if not needed(filename):
        st.error(f"Missing result: `jury_2_dw/outputs/{filename}`. Run the corresponding Jury 2 analysis script.")
        return None
    try:
        return read_json(str(from_output(filename)))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Cannot read {filename}: {exc}")
        return None


def hero(title: str, description: str, eyebrow: str = "Jury 2 • Healthcare Intelligence") -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1><p>{description}</p></div>",
        unsafe_allow_html=True,
    )


def show_image(filename: str, caption: str) -> None:
    path = from_output(filename)
    if path.is_file():
        st.image(str(path), caption=caption, width="stretch")
    else:
        st.info(f"Chart not generated yet: `{path.relative_to(ROOT)}`.")


def show_overview() -> None:
    hero("Clinical Risk Intelligence Studio", "Readmission analysis, model evaluation, and an interactive research demo.")
    summary = require_json("clinical_summary.json")
    report = require_json("best_model_report.json")
    if summary is None or report is None:
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Hospital encounters", f"{summary['dataset_encounters']:,}")
    metric_cols[1].metric("Unique patients", f"{summary['unique_patients']:,}")
    metric_cols[2].metric("Readmitted within 30 days", f"{summary['readmission_under_30_pct']:.2f}%")
    metric_cols[3].metric("Selected model", report["selected_model"])

    st.markdown("### At a glance")
    left, right = st.columns([1.15, 0.85])
    with left:
        show_image("model_comparison.png", "Validation performance across benchmark models")
    with right:
        show_image("profile_age.png", "Historical readmission rates by age group")
    st.info(
        "Research demonstration only. These retrospective model scores and associations are not "
        "clinical advice and should not guide patient care."
    )


def show_benchmark() -> None:
    hero("Model Benchmark", "Compare the candidate classifiers on the validation set.")
    report = require_json("best_model_report.json")
    if report:
        st.info(f"Selected: {report['selected_model']} by validation macro F1 (equal weight per class); "
                "ties use <30-day recall. The test set is reserved for the selected model.")
        st.caption(f"Patient-disjoint samples: train {report['train_rows_used']:,}, "
                   f"validation {report['validation_rows_used']:,}, test {report['holdout_test_rows_used']:,}. "
                   "Discharge-time prediction; bed-capacity forecasting is future work.")
    comparison = require_csv("model_comparison.csv")
    if comparison is None:
        return
    metric = st.selectbox(
        "Compare by metric",
        ["f1_macro", "accuracy", "recall_under_30", "precision_under_30", "roc_auc_ovr_macro"],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    chart = px.bar(
        comparison.sort_values(metric, ascending=False),
        x="model", y=metric, color="model", text=metric,
        title=f"Validation {metric.replace('_', ' ').title()}",
        range_y=[0, 1],
    )
    chart.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    chart.update_layout(showlegend=False, xaxis_title="", yaxis_title="Score")
    st.plotly_chart(chart, width="stretch")
    st.dataframe(comparison, hide_index=True, width="stretch")


def show_best_model() -> None:
    hero("Best Model", "Held-out test results for the model selected using validation macro F1.")
    report = require_json("best_model_report.json")
    if report is None:
        return
    metrics = report["test_metrics"]
    cols = st.columns(4)
    cols[0].metric("Accuracy", f"{metrics['accuracy']:.1%}")
    cols[1].metric("Macro F1", f"{metrics['f1_macro']:.3f}")
    cols[2].metric("<30 day recall", f"{metrics['recall_under_30']:.1%}")
    cols[3].metric("Macro ROC AUC", f"{metrics['roc_auc_ovr_macro']:.3f}")
    st.caption(
        f"{report['selected_model']} • {report['holdout_test_rows_used']:,} held-out encounters • "
        f"{report['prediction_point'].capitalize()} prediction"
    )

    class_report = pd.DataFrame(report["per_class_test_report"]).T
    class_report = class_report.loc[[label for label in LABELS if label in class_report.index]]
    left, right = st.columns(2)
    with left:
        show_image("best_confusion_matrix.png", "Confusion matrix on the held-out test set")
    with right:
        show_image("best_roc.png", "One-vs-rest ROC curves on the held-out test set")
    st.subheader("Per-class test performance")
    st.dataframe(class_report, width="stretch")

    importance = require_csv("best_feature_importance.csv")
    if importance is not None:
        importance = importance.sort_values("importance_mean", ascending=True).tail(12)
        chart = px.bar(
            importance, x="importance_mean", y="feature", orientation="h",
            error_x="importance_std", title="Permutation importance (held-out sample)",
        )
        st.plotly_chart(chart, width="stretch")


def show_associations() -> None:
    hero("Association Mining", "Explore co-occurrence rules discovered with Apriori and FP-Growth.")
    st.caption("Support = fraction of encounters containing both sides; confidence = P(consequent | antecedent); "
               "lift = confidence / P(consequent). These are associations, not treatment effects.")
    algorithm = st.radio("Mining algorithm", ["Apriori", "FP-Growth"], horizontal=True)
    prefix = "apriori" if algorithm == "Apriori" else "fp_growth"
    summary = require_json("mining_summary.json")
    if summary:
        cols = st.columns(3)
        cols[0].metric("Encounters mined", f"{summary['settings']['sampled_encounters']:,}")
        cols[1].metric("Frequent itemsets", summary[algorithm]['frequent_itemsets'])
        cols[2].metric("Diagnosis / medication rules", summary[algorithm]['cross_domain_rules'])
    with st.expander("Frequent patterns"):
        itemsets = require_csv(f"{prefix}_itemsets.csv")
        if itemsets is not None:
            st.dataframe(itemsets.sort_values('support', ascending=False), hide_index=True)
    rules = require_csv(f"{prefix}_rules.csv")
    if rules is None:
        return
    if rules.empty:
        st.info("No association rules were generated.")
        return
    min_lift = st.slider("Minimum lift", 1.0, max(2.0, float(rules["lift"].max())), 1.0, 0.05)
    filtered = rules.loc[rules["lift"] >= min_lift].sort_values("lift", ascending=False)
    st.caption(f"{len(filtered):,} rules match the selected lift threshold.")
    st.dataframe(filtered, hide_index=True, width="stretch")
    if not filtered.empty:
        chart_data = filtered.head(12).copy()
        chart_data["rule"] = chart_data["antecedents"] + " → " + chart_data["consequents"]
        chart = px.bar(
            chart_data.sort_values("lift"), x="lift", y="rule", orientation="h",
            color="confidence", hover_data=["support", "confidence"],
            title="Highest-lift rules",
        )
        st.plotly_chart(chart, width="stretch")


def show_profiling() -> None:
    hero("Clinical Profiling", "Descriptive, observational patterns in historical hospital encounters.")
    profile_files = {
        "Age group": ("profile_age.csv", "age"),
        "Primary diagnosis": ("profile_diagnosis.csv", "diagnosis_group"),
        "Medication load": ("profile_medications.csv", "medication_load"),
        "Prior inpatient visits": ("profile_prior_inpatient.csv", "prior_inpatient_visits"),
        "Length of stay": ("profile_stay.csv", "stay_group"),
    }
    label = st.selectbox("Profile by", list(profile_files))
    filename, category = profile_files[label]
    profile = require_csv(filename)
    if profile is None:
        return
    if profile.empty:
        st.info("No profile rows are available.")
        return
    profile = profile.sort_values("readmission_rate_30_pct", ascending=False)
    chart = px.bar(
        profile, x="readmission_rate_30_pct", y=category, orientation="h",
        color="encounters", hover_data=["encounters", "readmitted_within_30"],
        title="Historical readmission within 30 days",
        labels={"readmission_rate_30_pct": "Readmission rate (%)", category: label},
    )
    st.plotly_chart(chart, width="stretch")
    st.dataframe(profile, hide_index=True, width="stretch")
    st.caption("Rates are descriptive historical observations; they do not establish causation.")


def show_risk_studio() -> None:
    hero("Live Risk Studio", "Enter discharge-time encounter details to explore the saved model's predictions.")
    st.warning(
        "Academic demonstration only—not a validated clinical decision support device. "
        "Do not enter identifiable patient information or use predictions for care decisions."
    )
    with st.form("risk_inputs"):
        st.subheader("Encounter")
        cols = st.columns(4)
        time_in_hospital = cols[0].number_input("Hospital days", 1, 14, 4)
        num_lab_procedures = cols[1].number_input("Lab procedures", 0, 132, 40)
        num_procedures = cols[2].number_input("Procedures", 0, 6, 1)
        num_medications = cols[3].number_input("Medications", 0, 81, 16)
        number_outpatient = cols[0].number_input("Prior outpatient visits", 0, 42, 0)
        number_emergency = cols[1].number_input("Prior emergency visits", 0, 76, 0)
        number_inpatient = cols[2].number_input("Prior inpatient visits", 0, 21, 0)
        number_diagnoses = cols[3].number_input("Diagnoses", 1, 16, 6)

        st.subheader("Patient and treatment")
        cols = st.columns(4)
        age = cols[0].selectbox("Age group", [
            "[0-10)", "[10-20)", "[20-30)", "[30-40)", "[40-50)", "[50-60)",
            "[60-70)", "[70-80)", "[80-90)", "[90-100)",
        ], index=7)
        gender = cols[1].selectbox("Gender", ["Female", "Male", "Unknown/Invalid"])
        race = cols[2].selectbox(
            "Race", ["Caucasian", "AfricanAmerican", "Hispanic", "Asian", "Other", "Unknown"]
        )
        admission_type_id = cols[3].selectbox("Admission type", [str(value) for value in range(1, 9)])
        insulin = cols[0].selectbox("Insulin", ["No", "Steady", "Up", "Down"])
        change = cols[1].selectbox("Medication change", ["No", "Ch"])
        diabetes_med = cols[2].selectbox("Diabetes medication", ["Yes", "No"])
        a1c_result = cols[3].selectbox("A1C result", ["Unknown", "Norm", ">7", ">8"])
        diagnosis_options = [
            "Diabetes", "Circulatory", "Respiratory", "Digestive", "Infectious",
            "Endocrine", "Genitourinary", "Neoplasms", "Musculoskeletal",
            "Symptoms", "Injury", "Other", "Unknown",
        ]
        diag_1_group = st.selectbox("Primary diagnosis group", diagnosis_options, index=0)
        diag_2_group = st.selectbox("Secondary diagnosis group", diagnosis_options, index=1)
        submitted = st.form_submit_button("Estimate readmission probabilities", type="primary")

    if not submitted:
        return
    if not MODEL_PATH.is_file():
        st.error(f"Model artifact not found: `{MODEL_PATH}`. Run the benchmark script first.")
        return
    try:
        artifact = load_classifier(str(MODEL_PATH))
        encounter = pd.DataFrame([{
            "time_in_hospital": time_in_hospital,
            "num_lab_procedures": num_lab_procedures,
            "num_procedures": num_procedures,
            "num_medications": num_medications,
            "number_outpatient": number_outpatient,
            "number_emergency": number_emergency,
            "number_inpatient": number_inpatient,
            "number_diagnoses": number_diagnoses,
            "age": age,
            "gender": gender,
            "race": race,
            "admission_type_id": admission_type_id,
            "insulin": insulin,
            "change": change,
            "diabetesMed": diabetes_med,
            "A1Cresult": a1c_result,
            "diag_1_group": diag_1_group,
            "diag_2_group": diag_2_group,
        }], columns=FEATURES)
        probabilities = artifact["pipeline"].predict_proba(encounter)[0]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Could not score this encounter: {exc}")
        return
    result = pd.DataFrame({"Outcome": artifact["labels"], "Probability": probabilities})
    prediction = result.loc[result["Probability"].idxmax()]
    st.subheader(f"Most likely outcome: {prediction['Outcome']}")
    cols = st.columns(3)
    for col, row in zip(cols, result.itertuples(index=False)):
        col.metric(row.Outcome, f"{row.Probability:.1%}")
    chart = px.bar(
        result, x="Outcome", y="Probability", color="Outcome", text="Probability",
        color_discrete_map=COLOR, range_y=[0, 1], title="Model output (not a clinical risk score)",
    )
    chart.update_traces(texttemplate="%{text:.1%}", textposition="outside")
    chart.update_layout(showlegend=False, yaxis_title="Predicted probability")
    st.plotly_chart(chart, width="stretch")


with st.sidebar:
    st.markdown("## 🏥 Clinical Risk Intelligence")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Jury 2 · Diabetes readmission research")
    st.caption("For academic demonstration only.")

if page == "Overview":
    show_overview()
elif page == "Model Benchmark":
    show_benchmark()
elif page == "Best Model":
    show_best_model()
elif page == "Association Mining":
    show_associations()
elif page == "Clinical Profiling":
    show_profiling()
elif page == "Live Risk Studio":
    show_risk_studio()
