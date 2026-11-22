> Navigation update: analytics and simulation now have separate workspaces. Patient Clustering is part of Jury 2 (including its standalone dashboard). Select Simulation · Replay for pipeline, replay warehouse, and hypothetical scenarios. Changing batch size does not retrain models; only replay cohort summaries and processing time change.

# HealthLine 2.0 — three-minute demonstration

Before judging: launch `python -m streamlit run app.py --server.port 8530`, open the local URL, and check the six-page navigation. No internet is required. Use the existing `.venv` Python on Windows. Close other heavy analytic sessions if memory is constrained.

For a clean replay, open Live Pipeline Studio → Start a fresh demo session → check Reset the isolated replay session → Reset demo session. This intentionally clears only the replay records and logs. Keep a 100-row batch selected. Original data and fitted models remain unchanged.

## 0:00–0:25 · Problem and executive overview

“Hospitals need to connect fragmented encounter data with readmission analysis and resource planning. HealthLine demonstrates that chain using real historical UCI hospital encounters.”

Show the full historical warehouse: 101,766 encounters, SQL-derived stays, complexity and observed readmission distribution. Explain that these are historical records, not current hospital occupancy.

## 0:25–1:05 · Actual ingestion

Open Live Pipeline Studio. Click **Run Hospital Data Replay**. Stages track actual work; no artificial delays are inserted, so small batches finish quickly. Show before/after counts, duration, accepted/rejected/duplicate counts and the completed run history. Open Full execution record to expose the run ID and timestamps.

“This is a replay of actual source rows into an isolated warehouse. The source has no encounter dates for a live time series. The timestamps here record ingestion now.”

## 1:05–1:30 · Warehouse evidence

Open Data Warehouse Explorer and select **Simulation · Replay** in the sidebar. Show fact, dimension, prediction and cluster counts. Select Readmission distribution or Readmission by cluster and show the actual SQL and results. Mention primary keys, foreign keys, duplicate detection and rollback. A second click ingests the next range; the automated repeat-batch test proves identical rows cannot double-count.

## 1:30–2:15 · Patient intelligence

Open Jury 2 · Analytics → Patient Clustering. Show K=2, sampled silhouette 0.174, PCA and measured cluster profiles. “These are modestly separated retrospective encounter segments, not validated clinical phenotypes.”

Choose Live Risk Studio. Submit the default form to run the preserved trained pipeline. “This is a three-class discharge-stage model. It uses treatments and length of stay, so it is not admission-time risk. Its held-out macro F1 is 0.433, and its outputs are not calibrated clinical confidence.”

If asked, Best Model shows the actual confusion matrix, metrics and feature importance; Association Mining retains the existing Apriori and FP-Growth results.

## 2:15–2:45 · Decision support

Return briefly to Executive Command Center with the replay warehouse selected: the count now reflects the replay. Open Operational Scenario Lab. Change daily admissions or available beds and show hypothetical pressure. Save a scenario to compare assumptions.

“These are explicit stock-and-flow assumptions, not a learned occupancy forecast or synthetic training data.”

## 2:45–3:00 · Evidence and boundaries

Show Architecture & Evidence and test results. End with: “Implemented: incremental ETL, SQL warehouse analytics, trained-model inference, clustering, and scenario exploration. Simulated: historical arrival replay and capacity assumptions. Real deployment would need governance, secure clinical integration, external and prospective validation, calibration, and monitoring.”

## Recovery

- Empty replay: run one batch; historical data remains available independently.
- Port occupied: choose another `--server.port`; browser evidence script expects 8530.
- Missing cluster files: run `python -m healthline.intelligence` once, then restart.
- Incompatible fitted models: use the pinned dependencies. Do not silently substitute a formula.
- Replay failure: inspect the error in run history. Fact writes and cursor roll back together; retry after resolving the cause.
- Original Jury dashboards remain available through their documented launch commands.
