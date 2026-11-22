"""HealthLine acceptance checks; writes use temporary, isolated databases."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from healthline import warehouse as w
from healthline.intelligence import OUT, cluster_features, load_classifier, infer, enrichment, train_clusters
from healthline.scenarios import simulate, save_scenario


@pytest.fixture
def batch():
    return pd.read_csv(w.SOURCE,nrows=100,low_memory=False)


def test_real_batch_idempotency_and_sql(tmp_path,batch):
    db=tmp_path/'replay.db'
    cluster=joblib.load(OUT/'clusters.joblib')
    classifier=load_classifier()
    stages=[]
    first=w.ingest(batch,db,callback=stages.append,enrich=enrichment(cluster,classifier))
    assert first['status']=='success',first
    assert first['loaded_rows']==100 and first['before_count']==0 and first['after_count']==100
    assert stages==['Data source','Validation','Transformation','Warehouse','Analytics','Dashboard']
    second=w.ingest(batch,db,enrich=enrichment(cluster,classifier))
    assert second['loaded_rows']==0 and second['duplicate_rows']==100 and second['after_count']==100
    for name in ['Fact_Admissions','patient_clusters','model_predictions']:
        assert w.query(f'SELECT count(*) n FROM {name}',db).n.iloc[0]==100
    assert len(w.query(w.QUERIES['Recent ingestion'],db))==2
    for sql in w.QUERIES.values(): assert not w.query(sql,db).empty
    with w.connect(db,readonly=True) as c:
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
    pred=w.query('SELECT * FROM model_predictions ORDER BY encounter_id',db)
    actual=infer(batch.sort_values('encounter_id'),classifier)
    np.testing.assert_allclose(np.array([json.loads(x) for x in pred.probabilities]),actual)


def test_invalid_duplicate_and_missing_schema(tmp_path,batch):
    db=tmp_path/'invalid.db'
    dirty=pd.concat([batch.head(5),batch.head(1)],ignore_index=True)
    dirty.loc[1,'time_in_hospital']=999
    dirty.loc[2,'readmitted']='invalid'
    dirty.loc[3,'patient_nbr']=np.nan
    result=w.ingest(dirty,db)
    assert result['status']=='success'
    assert (result['input_rows'],result['loaded_rows'],result['duplicate_rows'],result['rejected_rows'])==(6,2,1,3)
    assert len(w.query('SELECT * FROM rejected_records',db))==3
    bad=w.ingest(batch.drop(columns='age'),db)
    assert bad['status']=='failed' and 'Missing required' in bad['error_details']
    assert w.query('SELECT count(*) n FROM Fact_Admissions',db).n.iloc[0]==2


def test_rollback_and_replay_cursor(tmp_path):
    db=tmp_path/'rollback.db'
    def fail(conn,raw): raise RuntimeError('injected enrichment failure')
    result=w.ingest(path=db,batch_size=50,enrich=fail)
    assert result['status']=='failed' and result['loaded_rows']==0
    assert w.query('SELECT count(*) n FROM Dim_Patient',db).n.iloc[0]==0
    assert w.query("SELECT value FROM demo_metadata WHERE key='cursor'",db).value.iloc[0]=='0'
    a=w.ingest(path=db,batch_size=50)
    b=w.ingest(path=db,batch_size=50)
    assert a['after_count']==50 and b['after_count']==100
    assert w.query("SELECT value FROM demo_metadata WHERE key='cursor'",db).value.iloc[0]=='100'


def test_concurrent_replay(tmp_path):
    db=tmp_path/'concurrent.db'; w.initialize(db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:w.ingest(path=db,batch_size=50),range(2)))
    assert all(r['status']=='success' for r in results),results
    assert w.query('SELECT count(*) n FROM Fact_Admissions',db).n.iloc[0]==100
    assert w.query("SELECT value FROM demo_metadata WHERE key='cursor'",db).value.iloc[0]=='100'


def test_reset_protection_and_preservation(tmp_path,batch):
    protected=[w.SOURCE,w.HISTORICAL,w.ROOT/'jury_2_dw/outputs/best_model.joblib']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    for path in [w.HISTORICAL,w.ROOT/'healthcare_dw.db',w.ROOT/'archive/warehouses/healthcare_dw.db']:
        with pytest.raises(ValueError): w.reset_demo(path)
        with pytest.raises(ValueError): w.initialize(path)
    db=tmp_path/'reset.db'; w.ingest(batch,db)
    w.reset_demo(db)
    assert w.query('SELECT count(*) n FROM Fact_Admissions',db).n.iloc[0]==0
    assert w.query('SELECT count(*) n FROM pipeline_runs',db).n.iloc[0]==0
    assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}


def test_clustering_artifacts_and_fit(tmp_path,batch):
    report=train_clusters(batch,output=tmp_path/'clusters')
    assert report['selected_k'] in range(2,7) and len(report['k_comparison'])==5
    model=joblib.load(OUT/'clusters.joblib')
    z=model['preprocess'].transform(cluster_features(batch))
    assigned=pd.read_csv(OUT/'cluster_assignments.csv')
    assert len(assigned)==101766 and not assigned.encounter_id.duplicated().any()
    np.testing.assert_array_equal(model['model'].predict(z),assigned.head(100).cluster)
    assert model['pca'].transform(z).shape==(100,2)
    assert not {'patient_nbr','encounter_id','readmitted'}&set(model['features'])


def test_scenarios_separate(tmp_path):
    db=tmp_path/'scenarios.db'; w.initialize(db)
    args=dict(beds=200,admissions=35,stay=5,discharge_rate=1,initial=150)
    frame=simulate(**args)
    assert frame.hypothetical_bed_demand.iloc[0]==155
    assert len(frame)==14 and (frame.hypothetical_bed_demand>=0).all()
    save_scenario(args,frame,db)
    assert w.query('SELECT label FROM operational_scenarios',db).label.iloc[0]=='Hypothetical / Simulation'
    assert w.query('SELECT count(*) n FROM Fact_Admissions',db).n.iloc[0]==0
    w.reset_demo(db)
    assert len(w.query('SELECT * FROM operational_scenarios',db))==1


@pytest.fixture
def app(tmp_path,monkeypatch):
    # Redirect function defaults too, so UI tests never mutate the demonstration DB.
    db=tmp_path/'ui.db'
    monkeypatch.setattr(w,'DEMO',db)
    for name in ['initialize','query','counts','reset_demo','ingest']:
        original=getattr(w,name)
        def wrapped(*args,_fn=original,**kwargs):
            if 'path' not in kwargs and (not args or _fn.__name__ in ['query','ingest'] and len(args)<2):
                kwargs['path']=db
            return _fn(*args,**kwargs)
        monkeypatch.setattr(w,name,wrapped)
    return AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()


@pytest.mark.parametrize('page',['Executive Overview','Data Pipeline','Warehouse Explorer',
                                  'Patient Segmentation','Capacity Scenarios','System Evidence'])
def test_pages(app,page):
    if page in ['Data Pipeline','Capacity Scenarios']:
        app.sidebar.selectbox[0].select('Simulation Studio').run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception and not app.error
    if page=='Patient Segmentation':
        assert len(app.get('plotly_chart'))>=5
        for view in ['Readmission Assessment','Model Comparison','Model Performance','Association Analysis','Population Profiles']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception and not app.error
    if page=='Capacity Scenarios':
        assert any('hypothetical' in x.value.lower() for x in app.warning)


def test_replay_ui_updates(app):
    app.sidebar.selectbox[0].select('Simulation Studio').run()
    app.sidebar.radio[0].set_value('Data Pipeline').run()
    app.button[0].click().run()
    assert not app.exception and not app.error
    assert app.session_state['last_run']['loaded_rows']==100
    app.sidebar.radio[0].set_value('Executive Overview').run()
    assert not app.exception and app.metric[0].value=='100'
    app.sidebar.selectbox[0].select('Clinical Analytics').run()
    app.sidebar.radio[0].set_value('Executive Overview').run()
    assert app.metric[0].value=='101,766'
    assert 'Data Pipeline' not in app.sidebar.radio[0].options
    assert 'Patient Segmentation' in app.sidebar.radio[0].options


def test_batch_size_preserves_models_and_assignments(tmp_path,batch):
    paths=[OUT/'clusters.joblib',OUT/'clustering_report.json',w.ROOT/'jury_2_dw/outputs/best_model.joblib',
           w.ROOT/'jury_2_dw/outputs/best_model_report.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    enrich=enrichment(joblib.load(OUT/'clusters.joblib'),load_classifier())
    whole=tmp_path/'whole.db'; split=tmp_path/'split.db'
    assert w.ingest(batch,whole,enrich=enrich)['status']=='success'
    for chunk in [batch.iloc[:50],batch.iloc[50:]]:
        assert w.ingest(chunk,split,enrich=enrich)['status']=='success'
    for table,cols in [('patient_clusters','encounter_id,cluster'),('model_predictions','encounter_id,prediction,probabilities')]:
        left=w.query(f'SELECT {cols} FROM {table} ORDER BY encounter_id',whole)
        right=w.query(f'SELECT {cols} FROM {table} ORDER BY encounter_id',split)
        if 'probabilities' in left:
            # Parallel tree reductions can differ at floating-point roundoff scale.
            np.testing.assert_allclose([json.loads(p) for p in left.pop('probabilities')],
                                       [json.loads(p) for p in right.pop('probabilities')],rtol=0,atol=1e-12)
        pd.testing.assert_frame_equal(left,right)
    assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
