from pathlib import Path
import sys,json,hashlib,sqlite3,subprocess
import numpy as np
import pandas as pd
import pytest
import joblib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'jury_2_dw')); sys.path.insert(0,str(ROOT/'jury_1_dw'))
from jury2_features import build_features,diagnosis_group,FEATURES,LABELS
from benchmark_models import prepare,fit_model,classifiers,preprocessing
from mine_associations import build_transactions
from clinical_profiling import cohort_table
from etl_and_olap import build_warehouse
from streamlit.testing.v1 import AppTest
@pytest.fixture(autouse=True)
def release_app_memory():
    yield
    import streamlit as st, gc
    st.cache_resource.clear()
    st.cache_data.clear()
    gc.collect()
@pytest.fixture(scope='module')
def raw(): return pd.read_csv(ROOT/'data/diabetes_130_us.csv',low_memory=False)

def test_source_preserved(raw):
    manifest=json.loads((ROOT/'docs/initial_inventory.json').read_text())
    original=next(x for x in manifest if x['path'].replace('\\','/')=='data/diabetes_130_us.csv')
    assert hashlib.sha256((ROOT/'data/diabetes_130_us.csv').read_bytes()).hexdigest()==original['sha256']
    assert raw.shape==(101766,50) and raw.patient_nbr.nunique()==71518

@pytest.mark.parametrize('code,group',[('250.83','Diabetes'),('3.0','Infectious'),('001','Infectious'),('V45','Supplementary_V'),('E900','External_Cause_E'),('?','Unknown'),(np.nan,'Unknown')])
def test_diagnosis(code,group): assert diagnosis_group(code)==group

def test_features_and_missing(raw):
    x=build_features(raw.head(100)); assert list(x)==FEATURES
    assert not {'patient_nbr','encounter_id','readmitted','discharge_disposition_id'}&set(x)
    x=build_features(pd.DataFrame({'diag_1':['?'],'age':['?'],'num_medications':['bad']}))
    assert x.age.iloc[0]=='Unknown' and np.isnan(x.num_medications.iloc[0])

def test_splits(raw):
    X,y,a,b,c=prepare(raw)
    groups=[set(raw.patient_nbr.iloc[z]) for z in [a,b,c]]
    assert not(groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])
    assert len(a)+len(b)+len(c)==len(raw)
    with pytest.raises(ValueError): prepare(raw.drop(columns='patient_nbr'))

@pytest.mark.parametrize('name',list(classifiers()))
def test_training_and_unseen_categories(raw,name):
    sample=raw.groupby('readmitted',group_keys=False).sample(n=100,random_state=42)
    x=build_features(sample); y=sample.readmitted.map({v:i for i,v in enumerate(LABELS)})
    pipe=fit_model(name,classifiers()[name],x,y)
    unseen=x.head(2).copy(); unseen['age']='unseen'; unseen['num_medications']=np.nan
    p=pipe.predict_proba(unseen)
    assert p.shape==(2,3) and np.isfinite(p).all() and np.allclose(p.sum(axis=1),1)

def test_model_artifact(raw):
    artifact=joblib.load(ROOT/'jury_2_dw/outputs/best_model.joblib')
    assert artifact['labels']==LABELS and artifact['features']==FEATURES
    p=artifact['pipeline'].predict_proba(build_features(raw.head(4)))
    assert np.allclose(p.sum(axis=1),1)

def test_association_metrics(raw):
    out=ROOT/'jury_2_dw/outputs'
    a=pd.read_csv(out/'apriori_itemsets.csv').sort_values('itemsets').reset_index(drop=True)
    b=pd.read_csv(out/'fp_growth_itemsets.csv').sort_values('itemsets').reset_index(drop=True)
    pd.testing.assert_frame_equal(a,b)
    a=pd.read_csv(out/'apriori_rules.csv').drop(columns='algorithm').sort_values(['antecedents','consequents']).reset_index(drop=True)
    b=pd.read_csv(out/'fp_growth_rules.csv').drop(columns='algorithm').sort_values(['antecedents','consequents']).reset_index(drop=True)
    pd.testing.assert_frame_equal(a,b)
    transactions=list(map(set,build_transactions(raw)))
    row=b.iloc[0]; left=set(row.antecedents.split(' | ')); right=set(row.consequents.split(' | '))
    both=sum((left|right)<=t for t in transactions)/len(transactions)
    pl=sum(left<=t for t in transactions)/len(transactions)
    pr=sum(right<=t for t in transactions)/len(transactions)
    assert row.support==pytest.approx(both)
    assert row.confidence==pytest.approx(both/pl)
    assert row.lift==pytest.approx(both/pl/pr)

def test_profiles(raw):
    for file in ['profile_age.csv','profile_medications.csv','profile_prior_inpatient.csv','profile_stay.csv']:
        t=pd.read_csv(ROOT/'jury_2_dw/outputs'/file)
        assert t.encounters.sum()==len(raw)
        assert t.readmitted_within_30.sum()==raw.readmitted.eq('<30').sum()

def test_etl_integrity(tmp_path,raw):
    source=tmp_path/'sample.csv'; raw.head(100).to_csv(source,index=False)
    db=tmp_path/'test.db'; sizes=build_warehouse(source,db)
    assert sizes['Fact_Admissions']==100
    with sqlite3.connect(db) as c:
        assert c.execute('select count(*) from Fact_Admissions f join Dim_Patient p using(patient_nbr) join Dim_Admission a using(admission_id) join Dim_Diagnosis d using(diag_id)').fetchone()[0]==100
        assert {r[0] for r in c.execute('select encounter_id from Fact_Admissions')}==set(raw.encounter_id.head(100))

def test_warehouse():
    with sqlite3.connect(ROOT/'data/healthcare_dw.db') as c:
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert c.execute('select count(*) from Fact_Admissions f join Dim_Patient p using(patient_nbr) join Dim_Admission a using(admission_id) join Dim_Diagnosis d using(diag_id)').fetchone()[0]==101766

@pytest.mark.parametrize('page',['Overview','Model Benchmark','Best Model','Association Mining','Clinical Profiling','Live Risk Studio'])
def test_dashboard_pages(page):
    at=AppTest.from_file(str(ROOT/'jury_2_dw/app.py'),default_timeout=30).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception and not at.error
    if page=='Live Risk Studio':
        at.button[0].click().run(); assert not at.exception and len(at.metric)==3
    if page=='Association Mining':
        at.radio[0].set_value('FP-Growth').run(); assert not at.exception
    if page=='Model Benchmark':
        at.selectbox[0].select('roc_auc_ovr_macro').run(); assert not at.exception
    if page=='Clinical Profiling':
        for option in at.selectbox[0].options:
            at.selectbox[0].select(option).run(); assert not at.exception

def test_missing_and_invalid_artifacts(tmp_path):
    script=(ROOT/'jury_2_dw/app.py').read_text(encoding='utf-8')
    script=script.replace('OUT = ROOT / "jury_2_dw" / "outputs"',f'OUT = Path({str(tmp_path)!r})')
    at=AppTest.from_string(script,default_timeout=30).run()
    assert not at.exception and at.error
    (tmp_path/'best_model_report.json').write_text('bad json')
    at.sidebar.radio[0].set_value('Best Model').run()
    assert not at.exception and 'Cannot read' in at.error[0].value

def test_jury1_dashboard():
    at=AppTest.from_file(str(ROOT/'jury_1_dw/dashboard.py'),default_timeout=30).run()
    assert not at.exception and len(at.metric)==4

def test_foreign_cwd(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'jury_2_dw/clinical_profiling.py'),'--output',str(tmp_path/'profiles')],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'profiles/clinical_summary.json').exists()
