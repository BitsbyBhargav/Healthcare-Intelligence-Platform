# Audit and cleanup record - 21 October 2026

## Recovery and initial state

Initial branch was `main` at `c7ef944` (`Add readmission modeling dashboard`), with a modified Streamlit app and untracked Jury 2 scripts, outputs, RUN_FIRST and the nested Orange demo. No pre-existing user changes were discarded.

A complete project-file copy, including `.git`, uncommitted and untracked files, was made at `C:\Users\offic\OneDrive\Desktop\Healthcare-Intelligence-Platform-backup-20261021` before restructuring. The replaceable `.venv` runtime was excluded. All 70 non-cache project files were verified against the backup using SHA-256. `initial_inventory.json` records paths, sizes and hashes; `INITIAL_TREE.txt` records the original tree. The working branch is `codex/jury2-finalization`.

## Dependency findings

The current Streamlit application imports shared feature definitions and reads `jury_2_dw/outputs`. It does not use the old binary Random Forest files. The legacy `import.py` imports `model.py`, which trains as a module side effect and uses encounter/patient identifiers and row-level random splits. Those historical artifacts are not suitable substitutes for the current multiclass, patient-separated benchmark. References were searched before archiving.

Jury 1's SQL and dashboard read `data/healthcare_dw.db`, while ETL/export previously used the root database. Both existing warehouse files contained 101,766 facts but had different hashes. They were preserved in the backup before the active warehouse was regenerated from the unchanged source.

## File disposition

| Disposition | Files / reason |
|---|---|
| Kept | Primary source CSV, Tableau workbook, Power BI file, original Jury 1 screenshots, SQL and warehouse dashboard |
| Moved | Nested `Jury2_Orange_QuickDemo/jury_2_dw/orange_demo` to `jury_2_dw/orange_demo` so exporters resolve the real repository root |
| Archived locally | `model.py`, `import.py`, `extract_record.py`, old binary scores and three `.pkl` files under `archive/legacy_binary`; old root database under `archive/warehouses` |
| Archived locally | Two Orange `.swp.p` session files under `archive/orange_session` |
| Removed after backup | Remaining obsolete wrapper folder `Jury2_Orange_QuickDemo`, including its old launch note; no source data or trained artifact was discarded |
| Repaired | ETL, table exporter, Streamlit faculty views, diagnosis grouping and Orange workflow generation |
| Regenerated | Canonical warehouse and fact CSV, Orange datasets/workflows, benchmark model/results/charts, full-data mining and profiles |
| Added | Practical tests, provenance, dependency lock, setup/run documentation, audit, handover, viva material, genuine screenshot evidence and two PDF reports |
| Merged | No independent implementations silently merged; active Jury 2 modules remain authoritative |

`archive/` is a local recovery aid and ignored by Git. Its contents also remain in the external pre-edit backup, with the tracked originals recoverable from Git history. Generated current outputs are retained for an immediate jury demonstration; virtual environments, caches and Orange swap files are ignored.

## Path and data repairs

* ETL reads local data and preserves source encounter IDs rather than fetching/overwriting source data and generating replacement IDs.
* All active warehouse consumers use `data/healthcare_dw.db`.
* Orange workflow File widgets explicitly reference the regenerated `.tab` files. The existing three-header discrete format was valid; the missing File settings were the workflow defect.
* Orange Tree settings are explicit and bounded, with multiway categorical splitting. The original binary split default failed in desktop Test & Score.
* Diagnosis mapping supports one- and two-digit numeric ICD-9 categories as well as three-digit/decimal codes.
* The application exposes frequent itemsets, selection rationale and length-of-stay profiling; A1C missing values are represented consistently as Unknown in the inference form.
* `.gitattributes` prevents Windows line-ending conversion of PDFs, serialized artifacts, raw evidence logs and CSV/TAB data. Staged PDF and source-data bytes were checked against the actual files. The source CSV was not edited; Git now preserves its original on-disk bytes instead of normalizing its line endings.

## Final structure

The final tree is recorded in `FINAL_TREE.txt` and summarised in README. Jury 1 and Jury 2 retain their simple phase folders, with shared Jury 2 feature definitions, central source/warehouse data, reproducible outputs, tests, docs and deliverables. No complex framework or deployment infrastructure was introduced.

## GitHub publication preparation

After the user's manual demonstration review and publication approval, runtime startup logs containing network addresses and installation diagnostics were removed from the publication index and retained locally through `.gitignore`. Credential, environment, cache and temporary-artifact exclusions were expanded. The selected model was losslessly compressed from 71,691,825 to 19,651,316 bytes; 500 encounter predictions/probabilities and every tree's stored arrays match the original. All reported evaluation results remain unchanged.

The unpublished local commit `c23de28` was preserved in `prepublication-finalization.bundle` inside the external backup directory. The publication commit is consolidated on the unchanged remote-main base so excluded runtime logs and the larger intermediate model do not enter the branch's published history. This changes only unpublished local history; no remote branch is rewritten and the backup bundle is not pushed.
