# GitHub publication checklist

The user approved publication after manually reviewing the Streamlit and Orange demos.

* Repository: `https://github.com/BitsbyBhargav/Healthcare-Intelligence-Platform`
* Publication branch: `codex/jury2-finalization`
* Requested commit title: `Finalize Jury 2 Healthcare Intelligence Platform`
* Remote main at preparation: `c7ef944408a9712431a809160427e8eed8afe6b0`
* The finalization branch was absent remotely at the initial check; no existing branch requires replacement.

## Structure and included assets

Jury 1 ETL, SQLite warehouse, SQL/OLAP, dashboard and original BI assets are retained. Jury 2 includes feature definitions, the five-model benchmark, selected fitted pipeline, association mining, profiles, Streamlit, typed Orange datasets/workflows and measured result files. README, dependency files, tests, handover, viva preparation, validation records, genuine screenshots and both mandatory PDFs are included. The source dataset remains byte-identical to the initial audit.

## Ignore rules and information review

`.gitignore` excludes virtual environments, caches, temporary files, database journals, archives, local secret/configuration files, key files and unnecessary experimental model dumps. It explicitly permits the one fitted pipeline required by Live Risk Studio. Private runtime startup logs and installation logs remain on the workstation and are excluded from GitHub.

The publication check scans candidate source/document text, extracted PDF text, workflow settings bytes and readable BI archive metadata for common credential patterns and non-loopback IPv4 addresses. It also checks suspicious credential-file names, required assets, file sizes and representative ignore rules. Findings are reported by file and category without printing credential values. Pattern scanning is not a guarantee that every possible secret format is detected.

## Artifact sizes and unchanged predictions

The required fitted model was compressed losslessly from 68.37 MiB to approximately 18.74 MiB. Predictions and probabilities on 500 source encounters, metadata and all fitted tree arrays match the original. Reproduction code now writes compressed joblib output. The source CSV is approximately 17.40 MiB. Both PDFs, the warehouse and original BI assets are retained.

GitHub warns above 50 MiB and blocks regular Git files above 100 MiB, according to the [official GitHub file-size documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), checked 21 October 2026. The publication check rejects files above the hard limit and records any soft-limit warnings. Binary/data Git attributes preserve the exact source and PDF bytes on Windows.

## Recovery and history

The prior unpublished finalization commit `c23de28dba02d5543d0eb43cb4d7b47b326d947b` is preserved in the verified external `prepublication-finalization.bundle`, inside the existing backup directory. Local finalization is consolidated onto the existing remote-main base so excluded runtime logs and the uncompressed intermediate model are not reachable from the published branch. No remote work is deleted or overwritten; no force push is used. The recovery bundle stays local.

## Verification records

`deliverables/logs/publication_checks.json` records compression equivalence. `deliverables/logs/prepublish_audit.json` records the publication file/secret/ignore checks, and pytest XML/log files record the test rerun. Exact final commit and remote ref verification are recorded after pushing in local `docs/FINAL_GIT_STATE.txt` and in the user's completion message. Inspect the branch using `git log -1 --oneline`, `git status --short --branch` and `git ls-remote --heads origin refs/heads/codex/jury2-finalization`.
