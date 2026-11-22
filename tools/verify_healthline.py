"""Assemble measured review evidence without touching original artifacts."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
import joblib
from healthline import warehouse as w
from healthline.intelligence import OUT, enrichment, load_classifier
from tools.prepublish_check import scan


def main():
    baseline=ROOT/'docs/healthline_protected_hashes.json'
    expected=json.loads(baseline.read_text())
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in expected}
    assert hashes==expected,'Original artifact changed'
    suite=ET.parse(ROOT/'deliverables/logs/healthline_all_tests.xml').getroot().find('testsuite')
    assert suite is not None
    test_results={key:suite.attrib[key] for key in ['tests','failures','errors','skipped','time','timestamp']}
    assert int(test_results['failures'])==int(test_results['errors'])==0
    browser=json.loads((ROOT/'deliverables/healthline_evidence/browser_checks.json').read_text())
    assert not browser['page_errors']
    with tempfile.TemporaryDirectory(prefix='healthline-evidence-') as directory:
        db=Path(directory)/'replay.db'
        raw=pd.read_csv(w.SOURCE,nrows=100,low_memory=False)
        enrich=enrichment(joblib.load(OUT/'clusters.joblib'),load_classifier())
        first=w.ingest(raw,db,enrich=enrich)
        duplicate=w.ingest(raw,db,enrich=enrich)
        assert first['loaded_rows']==100 and duplicate['loaded_rows']==0 and duplicate['duplicate_rows']==100
        count_evidence=w.counts(db).to_dict(orient='records')
        sql_evidence=w.query(w.QUERIES['Readmission distribution'],db).to_dict(orient='records')
        w.reset_demo(db)
        assert w.query('SELECT count(*) n FROM Fact_Admissions',db).n.iloc[0]==0
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    findings=[]; scanned=0
    for name in sorted(set(names)):
        path=ROOT/name
        if path.is_file() and path.suffix in ['.py','.md','.txt','.json','.toml','.csv','.xml','.yml','.yaml']:
            scan(name,path.read_bytes(),findings); scanned+=1
    assert not findings,findings
    ignore_checks={p:subprocess.run(['git','check-ignore','--no-index','-q',p],cwd=ROOT).returncode==0
                   for p in ['runtime/replay.db','.env','.streamlit/secrets.toml','archive/healthline2_before/example','__pycache__/example.pyc']}
    assert all(ignore_checks.values())
    report={'generated_at_utc':w.now(),'tests':test_results,'browser':browser,
            'protected_artifacts_sha256':hashes,'original_artifacts_unchanged':True,
            'real_batch':first,'same_batch_repeated':duplicate,'temporary_warehouse_counts':count_evidence,
            'sql_readmission_distribution':sql_evidence,'isolated_reset_verified':True,
            'clustering':json.loads((OUT/'clustering_report.json').read_text()),
            'publication_scan':{'text_files_scanned':scanned,'findings':findings,'ignored_runtime_and_secrets':ignore_checks,
                                'scope':'Text candidates: common credential and non-loopback IP patterns. Not a comprehensive privacy guarantee. Original source hash unchanged; no new patient input files.'},
            'git_branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            'publication':'Not committed or pushed. Await explicit user authorization.'}
    (ROOT/'docs/healthline_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'tests':test_results,'real_loaded':first['loaded_rows'],'repeat_loaded':duplicate['loaded_rows'],
                      'duplicates':duplicate['duplicate_rows'],'original_artifacts_unchanged':True,
                      'secret_pattern_findings':len(findings)},indent=2))


if __name__=='__main__': main()
