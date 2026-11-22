"""Unified, SQL-backed HealthLine application with reusable Jury 2 views."""
import importlib.util
import json
from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

from healthline import warehouse as w
from healthline.intelligence import OUT, load_classifier, enrichment
from healthline.scenarios import simulate, save_scenario

PAGES = ['Executive Overview','Data Pipeline','Warehouse Explorer',
         'Patient Intelligence','Capacity Scenarios','System Evidence']
STAGES = ['Data source','Validation','Transformation','Warehouse','Analytics','Dashboard']

CSS = """
<style>
.stApp {background:#f7f9f8;color:#203b3a}
.block-container {max-width:1460px;padding-top:3.5rem;padding-bottom:3rem}
h1,h2,h3 {letter-spacing:-.035em;color:#193d38}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #dce7e2}
[data-testid="stMetric"] {background:#fff;border:1px solid #dce7e2;border-radius:12px;padding:15px}
.eyebrow {font-size:12px;font-weight:650;color:#247966;letter-spacing:.15em;text-transform:uppercase}
.hero {border-bottom:1px solid #dce7e2;padding-bottom:18px;margin-bottom:22px}
.hero h1 {font-size:32px;margin:6px 0}.hero p {color:#657975;margin:0}
.flow {display:flex;gap:9px;align-items:center;margin:22px 0;flex-wrap:wrap}
.node {flex:1;min-width:120px;border:1px solid #ceddd6;border-radius:10px;padding:18px 10px;background:#fff;font-size:13px}
.node small {display:block;font-size:10px;letter-spacing:.08em;margin-bottom:6px;color:#657975}
.node.active {border:2px solid #16836e;background:#e8f7f0;animation:pulse 1s infinite}
.node.done {background:#edf6f0;border-color:#8ec3a6}.arrow {color:#75a99b}
@keyframes pulse {50% {box-shadow:0 0 0 5px #16836e16}}
@media(prefers-reduced-motion:reduce){.node.active{animation:none}}
</style>
"""


@st.cache_resource
def legacy():
    spec = importlib.util.spec_from_file_location('healthline_legacy',w.ROOT/'jury_2_dw/app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource
def models():
    return joblib.load(OUT/'clusters.joblib'),load_classifier()


@st.cache_data
def artifact_csv(name):
    return pd.read_csv(OUT/name)


def hero(title, description):
    st.markdown(f'<div class="hero"><div class="eyebrow">HealthLine 2.0 / Hospital intelligence</div><h1>{title}</h1><p>{description}</p></div>',unsafe_allow_html=True)


def plot(fig):
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial',color='#29433d'),margin=dict(l=15,r=15,t=45,b=20),
                      colorway=['#16836e','#db9f49','#728fc0','#aa7190','#69a89e','#9eae60'])
    st.plotly_chart(fig,width='stretch')


def command_center(db):
    hero('Executive Overview','Historical encounters, utilization, and replay activity in one view.')
    row = w.query(w.QUERIES['Summary'],db).iloc[0]
    cols = st.columns(4)
    cols[0].metric('Warehouse encounters',f'{int(row.encounters):,}')
    for col,key,label in zip(cols[1:],['average_stay','average_medications','average_diagnoses'],
                             ['Historical stay · days','Medications / encounter','Diagnoses / encounter']):
        col.metric(label,'—' if pd.isna(row[key]) else f'{row[key]:.2f}')
    if not row.encounters:
        st.info('Your replay warehouse is empty. Open Data Pipeline and run a real historical batch, or select the full historical warehouse in the sidebar.')
        return
    left,right = st.columns([1.25,1])
    age = w.query(w.QUERIES['Encounters by age'],db)
    outcomes = w.query(w.QUERIES['Readmission distribution'],db)
    with left:
        plot(px.bar(age,x='age',y='encounters',color='average_stay',color_continuous_scale='Teal',title='Encounter volume by age',labels={'age':'Age group'}))
    with right:
        plot(px.pie(outcomes,names='readmitted',values='encounters',hole=.65,title='Observed readmission outcomes'))
    left,right=st.columns(2)
    with left:
        st.subheader('Operational observations')
        top = age.loc[age.encounters.idxmax()]
        st.write(f"The largest age cohort is {top.age}: {int(top.encounters):,} encounters, with {top.average_stay:.2f} historical days per stay.")
        st.caption('Bed days describe historical utilization. This dataset has no encounter dates suitable for an occupancy time series.')
        if db == w.DEMO:
            clusters=w.query('SELECT cluster, count(*) encounters FROM patient_clusters GROUP BY cluster',db)
        else:
            clusters=artifact_csv('cluster_profiles.csv')[['cluster','encounters']]
        if not clusters.empty:
            plot(px.bar(clusters,x='cluster',y='encounters',title='Retrospective encounter segments'))
    with right:
        if db != w.DEMO:
            st.subheader('Historical analysis scope')
            st.write('This workspace reads the preserved historical warehouse. Simulation batches do not change these totals or the saved model evaluation.')
            st.caption('Use Simulation Studio for isolated ingestion counts and processing history.')
            return
        st.subheader('Latest replay activity')
        runs=w.query(w.QUERIES['Recent ingestion'])
        if runs.empty:
            st.info('No replay runs yet.')
        else:
            latest=runs.iloc[0]
            st.success(f"{latest.status.upper()} · {latest.loaded_rows} loaded · {latest.duration_seconds:.2f}s") if latest.status=='success' else st.error(latest.error_details)
            st.caption(f'Actual ingestion timestamp (UTC): {latest.ended_at}')
            st.dataframe(runs[['started_at','loaded_rows','duplicate_rows','status']].head(5),hide_index=True,width='stretch')


def flow(active=-1, completed=False):
    nodes=[]
    for i,name in enumerate(STAGES):
        state='done' if completed or i<active else 'active' if i==active else ''
        nodes.append(f'<div class="node {state}"><small>0{i+1} / {"DONE" if completed or i<active else "RUNNING" if i==active else "READY"}</small>{name.upper()}</div>')
    return '<div class="flow">'+ '<span class="arrow">→</span>'.join(nodes)+'</div>'


def pipeline_studio():
    hero('Data Pipeline','Replay actual historical records through a transactional ETL pipeline.')
    st.info('Historical data replay / Simulation. These are not new admissions. Only the isolated replay warehouse changes.')
    st.caption('Batch size controls ingestion work per run. Saved classifier and clustering models are only used for inference; training data, fitted models, and evaluation scores do not change. Repeated encounter IDs are skipped. Replay summaries can change as the demo cohort grows.')
    cols=st.columns([1,2,1])
    batch=cols[0].select_slider('Batch size',options=[50,100,200,500],value=100)
    cursor=int(w.query("SELECT value FROM demo_metadata WHERE key='cursor'").value.iloc[0])
    cursor_metric=cols[1].empty()
    count_metric=cols[2].empty()
    cursor_metric.metric('Next source row (zero-based)',f'{cursor:,}')
    count_metric.metric('Replay encounters',int(w.query('SELECT count(*) n FROM Fact_Admissions').n.iloc[0]))
    animation=st.empty(); animation.markdown(flow(),unsafe_allow_html=True)
    progress=st.progress(0,text='Ready for historical replay')
    logs=st.empty()
    if st.button('Run Hospital Data Replay',type='primary',disabled=cursor>=101766):
        events=[]
        def update(name):
            index=STAGES.index(name)
            events.append(f'{w.now()} | {name} started')
            animation.markdown(flow(index),unsafe_allow_html=True)
            progress.progress(index/len(STAGES),text=f'Executing {name.lower()}')
            logs.code('\n'.join(events),language=None)
        try:
            cluster,classifier=models()
            result=w.ingest(batch_size=batch,callback=update,enrich=enrichment(cluster,classifier))
        except (OSError,ValueError,KeyError) as exc:
            st.error(f'Cannot initialize analytics artifacts: {exc}')
            return
        st.session_state['last_run']=result
        if result['status']=='success':
            cursor_metric.metric('Next source row (zero-based)',f"{cursor+result['input_rows']:,}")
            count_metric.metric('Replay encounters',result['after_count'])
            animation.markdown(flow(completed=True),unsafe_allow_html=True)
            progress.progress(1.,text='Committed. Warehouse and analytics refreshed.')
            events.append(f'{w.now()} | Commit verified: {result["after_count"]} encounters')
            logs.code('\n'.join(events),language=None)
        else:
            st.error(f"Rolled back: {result['error_details']}")
    if 'last_run' in st.session_state:
        r=st.session_state.last_run
        cols=st.columns(4)
        cols[0].metric('Before → after',f"{r['before_count']:,} → {r['after_count']:,}")
        cols[1].metric('Loaded / duplicates',f"{r['loaded_rows']} / {r['duplicate_rows']}")
        cols[2].metric('Rejected',r['rejected_rows'])
        cols[3].metric('Measured duration',f"{r['duration_seconds']:.3f}s")
        with st.expander('Full execution record'):
            st.json(r)
    st.button('Refresh analytics')
    st.subheader('Run history · actual execution')
    st.dataframe(w.query(w.QUERIES['Recent ingestion']),hide_index=True,width='stretch')
    with st.expander('Inspect rejected records'):
        st.dataframe(w.query('SELECT * FROM rejected_records ORDER BY rowid DESC LIMIT 500'),hide_index=True)
    with st.expander('Start a fresh demo session'):
        st.caption('Clears replay encounters and replay logs only. Original data, trained models, and saved hypothetical scenarios are preserved.')
        confirm=st.checkbox('Reset the isolated replay session')
        if st.button('Reset demo session',disabled=not confirm):
            w.reset_demo(); st.session_state.pop('last_run',None); st.rerun()


def warehouse_explorer(db):
    hero('Warehouse Explorer','Inspect the star schema and execute predefined, read-only SQL analytics.')
    left,right=st.columns([1,2])
    with left:
        st.subheader('Live table counts')
        st.dataframe(w.counts(db),hide_index=True,width='stretch')
    with right:
        options=[k for k in w.QUERIES if db==w.DEMO or k not in ['Readmission by cluster','Recent ingestion']]
        name=st.selectbox('Analytical query',options)
        st.code(w.QUERIES[name],language='sql')
        st.dataframe(w.query(w.QUERIES[name],db),hide_index=True,width='stretch')
    with st.expander('Schema and constraints'):
        schema=w.query("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name",db)
        for r in schema.itertuples():
            st.code(r.sql,language='sql')
    table=st.selectbox('Preview table',w.counts(db)['table'].tolist())
    st.caption('First 100 rows; historical patient and encounter numbers are dataset linkage keys, not names.')
    st.dataframe(w.query(f'SELECT * FROM "{table}" LIMIT 100',db),hide_index=True,width='stretch')
    st.caption('Original warehouse uses unique key indexes. Replay schema adds primary keys, foreign keys, range checks, and atomic ingestion.')


def clustering():
    report=json.loads((OUT/'clustering_report.json').read_text())
    profiles=artifact_csv('cluster_profiles.csv')
    assigned=artifact_csv('cluster_assignments.csv')
    st.caption('Unsupervised, retrospective encounter segmentation across the full historical source. Includes length of stay; not admission-time risk prediction or medically validated phenotypes.')
    cols=st.columns(4)
    cols[0].metric('Selected K',report['selected_k'])
    cols[1].metric('Silhouette',f"{report['silhouette']:.3f}")
    cols[2].metric('Encounters assigned',f"{report['encounters']:,}")
    cols[3].metric('Scoring sample',f"{report['silhouette_sample']:,}")
    left,right=st.columns([1.6,1])
    sample=assigned.sample(min(3000,len(assigned)),random_state=42).copy()
    sample['segment']=sample.cluster.astype(str)
    with left:
        plot(px.scatter(sample,x='pc1',y='pc2',color='segment',opacity=.5,title='PCA projection · reproducible 3,000-encounter sample'))
        st.caption(f"Two PCs explain {sum(report['pca_explained_variance']):.1%} of scaled feature variance. Projection overlap is expected.")
    with right:
        plot(px.bar(profiles,x='cluster',y='encounters',title='Cluster sizes · all encounters'))
        plot(px.line(pd.DataFrame(report['k_comparison']),x='k',y='silhouette',markers=True,title='K selection · same fixed sample'))
    st.subheader('Measured segment profiles')
    st.dataframe(profiles,hide_index=True,width='stretch')
    for r in profiles.itertuples():
        st.write(f'Segment {r.cluster}: {r.encounters:,} encounters; mean medications {r.num_medications:.1f}, prior inpatient visits {r.number_inpatient:.1f}, stay {r.time_in_hospital:.1f} days; observed <30-day readmission {r.readmission_under_30_pct:.1f}%.')
    distribution=assigned.groupby(['cluster','readmitted']).size().reset_index(name='encounters')
    plot(px.bar(distribution,x='cluster',y='encounters',color='readmitted',barmode='group',title='Observed outcomes by segment'))
    plot(px.bar(profiles,x='cluster',y='time_in_hospital',title='Mean historical stay by segment',labels={'time_in_hospital':'Days'}))
    st.caption('Repeated patients contribute multiple encounters. K maximizes a sampled silhouette, not clinical validity. All assignments, PCA, imputer, scaler, and fitted K-Means are saved locally.')


def patient_intelligence():
    hero('Patient Intelligence','Retrospective risk modeling, encounter segmentation, and observed patterns.')
    view=st.radio('Intelligence workspace',['Patient segments','Discharge risk','Model comparison','Model evidence','Pattern mining','Clinical profiles'],horizontal=True)
    if view=='Patient segments':
        clustering()
    else:
        views=legacy()
        if view=='Discharge risk':
            st.caption('Three outcome classes: NO, >30 days, <30 days. Decision rule: maximum predicted probability; no binary threshold. Probabilities are not calibrated clinical confidence.')
            views.show_risk_studio()
        elif view=='Model comparison': views.show_benchmark()
        elif view=='Model evidence': views.show_best_model()
        elif view=='Pattern mining': views.show_associations()
        else: views.show_profiling()


def scenarios():
    hero('Capacity Scenarios','Simulation / Scenario · hypothetical capacity assumptions, never a clinical forecast.')
    st.warning('All outputs below are hypothetical. Admissions and bed capacity are user assumptions, not measured hospital operations.')
    cols=st.columns(5)
    beds=cols[0].number_input('Available beds',10,5000,200,10)
    admissions=cols[1].number_input('Admissions / day',0,1000,35)
    stay=cols[2].number_input('Assumed average stay',1.,30.,5.,.5)
    rate=cols[3].slider('Discharge realization',0.,1.,1.,.05)
    initial=cols[4].number_input('Initial bed demand',0,10000,150,10)
    assumptions=dict(beds=beds,admissions=admissions,stay=stay,discharge_rate=rate,initial=initial)
    frame=simulate(**assumptions)
    cols=st.columns(3)
    cols[0].metric('Hypothetical day-14 demand',f'{frame.hypothetical_bed_demand.iloc[-1]:.1f} beds')
    cols[1].metric('Hypothetical peak pressure',f'{frame.pressure_pct.max():.1f}%')
    cols[2].metric('Hypothetical peak excess',f'{frame.excess_demand.max():.1f} beds')
    plot(px.line(frame,x='day',y=['hypothetical_bed_demand','capacity'],title='Hypothetical demand and available capacity'))
    st.caption('Daily discharges = min(current demand, current demand ÷ assumed stay × discharge realization). Next demand = current demand + admissions − discharges. Demand can exceed physical beds; it is not actual occupancy. Fractional beds represent expected demand. No seasonality, queues, acuity, staffing, or uncertainty model.')
    if st.button('Save hypothetical scenario'):
        save_scenario(assumptions,frame)
        st.success('Hypothetical scenario saved separately from clinical records.')
    saved=w.query('SELECT * FROM operational_scenarios ORDER BY created_at DESC LIMIT 10')
    if not saved.empty:
        comparison=[]
        for r in saved.itertuples():
            result=json.loads(r.results)
            comparison.append({'created_at':r.created_at,'label':r.label,**json.loads(r.assumptions),'day_14_demand':result[-1]['hypothetical_bed_demand']})
        st.subheader('Saved hypothetical scenarios')
        st.dataframe(pd.DataFrame(comparison),hide_index=True,width='stretch')
    with st.expander('Daily hypothetical calculations'):
        st.dataframe(frame,hide_index=True)


def evidence():
    hero('System Evidence','A traceable path from historical records to analytical decision support.')
    st.markdown(flow(completed=True),unsafe_allow_html=True)
    st.markdown('**Source CSV → validated replay → star-schema SQLite → SQL analytics + saved ML → Streamlit**')
    st.write('UCI Diabetes 130-US Hospitals, 1999–2008: 101,766 encounters from 71,518 patients in the preserved local source. No original encounter dates are invented; ingestion timestamps are current UTC execution times.')
    st.markdown('[Dataset provenance: UCI repository](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008)')
    st.subheader('Data engineering')
    st.write('Fact_Admissions joins patient, admission-combination and diagnosis-combination dimensions. Patient demographics use first observation, not a slowly changing dimension. Missing categorical values normalize to Unknown; invalid required numeric fields and outcomes are rejected. A transaction commits facts, dimensions, assignments, predictions, cursor, and logs together. Encounter keys prevent double counting.')
    st.subheader('Model methodology and measured results')
    report=json.loads((w.ROOT/'jury_2_dw/outputs/best_model_report.json').read_text())
    st.write(f"Preserved {report['selected_model']}, selected by validation macro F1; patient-disjoint train/validation/test. Discharge-stage assessment uses length of stay and treatment variables. Three classes, maximum-probability decision; no legacy hard-coded risk formula.")
    st.json(report)
    st.json(json.loads((OUT/'clustering_report.json').read_text()))
    st.subheader('Verification')
    verification=w.ROOT/'docs/healthline_verification.json'
    if verification.exists():
        record=json.loads(verification.read_text())
        st.json({key:record[key] for key in ['tests','original_artifacts_unchanged','real_batch','same_batch_repeated','clustering']})
    else: st.info('Run the documented verification command to generate current local test evidence.')
    st.subheader('Limits and contribution')
    st.write('This integration adds real incremental ingestion, observability, encounter segmentation, SQL exploration, and explicit capacity scenarios while preserving the original benchmark and association mining. It is a functional prototype, not a clinical diagnostic system. Historical population bias, modest discrimination, uncalibrated probabilities, and absent temporal/external validation prevent clinical deployment claims.')
    st.write('Real deployment would require governance and access controls, secure clinical-system integration, temporal and external validation, calibration, monitoring, and prospective evaluation. SQLite serializes local replay writes; this is not a distributed streaming system.')
    with st.expander('Reproducibility'):
        st.code('python -m streamlit run app.py --server.port 8530\npython -m healthline.intelligence\npython -m pytest -q',language='bash')


def main():
    st.set_page_config(page_title='HealthLine 2.0 | Hospital Intelligence Platform',layout='wide')
    st.markdown(CSS,unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('## HealthLine 2.0')
        st.caption('HOSPITAL INTELLIGENCE PLATFORM')
        workspace=st.selectbox('Workspace',['Clinical Analytics','Simulation Studio'])
        simulation=workspace=='Simulation Studio'
        pages=([PAGES[1],PAGES[0],PAGES[2],PAGES[4]] if simulation else
               list(legacy().PAGES)+[PAGES[0],PAGES[2],PAGES[5]])
        page=st.radio('Navigate',pages,label_visibility='collapsed',key='simulation_page' if simulation else 'jury_page')
        st.divider()
        st.caption('Isolated historical replay and hypothetical scenarios.' if simulation else
                   'Model evaluation, inference, pattern analysis, and patient segmentation. Full historical data; no retraining during replay.')
        st.caption('Prototype for evaluation. Not for patient care.')
    if simulation:
        w.initialize()
    db=w.DEMO if simulation else w.HISTORICAL
    if page in [PAGES[0],PAGES[2]]:
        st.caption('QUERY SOURCE: REPLAY DEMO DATABASE' if simulation else 'QUERY SOURCE: FULL HISTORICAL WAREHOUSE (READ-ONLY)')
    if page==PAGES[0]: command_center(db)
    elif page==PAGES[1]: pipeline_studio()
    elif page==PAGES[2]: warehouse_explorer(db)
    elif page==PAGES[4]: scenarios()
    elif page==PAGES[5]: evidence()
    else:
        views=legacy()
        {'Overview':views.show_overview,'Model Comparison':views.show_benchmark,
         'Model Performance':views.show_best_model,'Association Analysis':views.show_associations,
         'Population Profiles':views.show_profiling,'Readmission Assessment':views.show_risk_studio,
         'Patient Segmentation':views.show_clustering}[page]()
