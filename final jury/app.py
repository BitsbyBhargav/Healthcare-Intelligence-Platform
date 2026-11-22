"""Independent A-J final jury demonstration; all results come from saved runs."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import streamlit as st
import joblib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from complete_analytics import NUM, CAT

st.set_page_config(page_title='Healthcare Intelligence - Final Jury',page_icon='🏥',layout='wide')
st.markdown('<style>'+(ROOT/'assets/dashboard.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)
st.markdown('''<div class="hero"><div class="eyebrow">HEALTHCARE INTELLIGENCE / FINAL JURY</div>
<h1>Better insight. Better planning.</h1><p>Explore hospital data, predict readmission outcomes and understand resource-use patterns.</p>
<div class="hero-tags"><span>UCI + SPARCS</span><span>Snowflake warehouse</span><span>4.42M real encounters</span></div></div>''',unsafe_allow_html=True)
@st.cache_data
def load_json(relative):return json.loads((ROOT/relative).read_text(encoding='utf-8'))
@st.cache_data
def load_csv(relative):return pd.read_csv(ROOT/relative,keep_default_na=False)
@st.cache_data
def uci():return pd.read_parquet(ROOT/'data/processed/uci_supervised.parquet')
@st.cache_data
def cluster_sample():return pd.read_parquet(ROOT/'outputs/clustering/assignments.parquet')
@st.cache_resource
def classifier():return joblib.load(ROOT/'outputs/classification/selected_pipeline.joblib')
classes=load_json('outputs/classification/results.json')
clusters=load_json('outputs/clustering/results.json')
mining=load_json('outputs/mining/results.json')
manifest=load_json('A_warehouse_design/data_preparation/modelled_csv_manifest.json')
labels=['NO','>30','<30']
options=['A - Warehouse design','B - Snowflake deployment','C - Supervised dataset',
 'D - Apriori and FP-Growth','E - Classifier comparison','F - Classification implementation',
 'G - Unsupervised dataset','H - Four clustering algorithms','I - Selected clustering method','J - Performance metrics']
st.sidebar.markdown('''<div class="sidebar-brand"><span class="brand-mark">+</span><div>Healthcare<span>INTELLIGENCE PLATFORM</span></div></div>''',unsafe_allow_html=True)
st.sidebar.caption('FINAL JURY • A–J WORKSPACE')
page=st.sidebar.radio('Explore the project',options)
st.sidebar.divider();st.sidebar.caption('4,424,257 real source records\n\nObserved readmission outcomes: UCI only\n\nNo generated labels are used in final results.')
block=page[0]
st.markdown(f'<div class="section-kicker">BLOCK {block} / {options.index(page)+1:02d} OF 10</div>',unsafe_allow_html=True)
st.header(page[4:])
def metric_row(values):
    for col,(name,value) in zip(st.columns(len(values)),values):col.metric(name,value)
def compare_clusters():
    return pd.DataFrame([{'algorithm':n,**v,'parameters':str(v['parameters'])} for n,v in clusters['algorithms'].items()])

def prediction_form():
    """Collect the same 19 predictors used by the saved training pipeline."""
    model=classifier()
    encoder=model.named_steps['prepare'].named_transformers_['categorical']
    categories=dict(zip(CAT,[list(values) for values in encoder.categories_]))
    admission={'1':'Emergency','2':'Urgent','3':'Elective','4':'Newborn','5':'Not available','6':'Unspecified','7':'Trauma center','8':'Not mapped'}
    source={'1':'Physician referral','2':'Clinic referral','3':'HMO referral','4':'Transfer from hospital','5':'Transfer from skilled nursing','6':'Transfer from other health facility','7':'Emergency room','8':'Court / law enforcement','9':'Not available','10':'Transfer from critical access hospital','11':'Normal delivery','13':'Sick baby','17':'Unspecified','20':'Not mapped','22':'Transfer within same facility / separate claim','25':'Ambulatory surgery center'}
    names={'age':'Age band','gender':'Gender','race':'Race / ethnicity (UCI category)','admission_type_id':'Admission type','admission_source_id':'Admission source','insulin':'Insulin dosage change','change':'Diabetes medication changed','diabetesMed':'Diabetes medication prescribed','A1Cresult':'HbA1c result','max_glu_serum':'Maximum serum glucose','primary_diagnosis_group':'Primary diagnosis group'}
    defaults={'age':'[60-70)','gender':'Female','race':'Caucasian','admission_type_id':'1','admission_source_id':'7','insulin':'Steady','change':'No','diabetesMed':'Yes','A1Cresult':'None','max_glu_serum':'None','primary_diagnosis_group':'Diabetes'}
    numeric={'time_in_hospital':('Hospital stay (days)',1,14,4),'num_lab_procedures':('Laboratory procedures',1,132,40),'num_procedures':('Other procedures',0,6,1),'num_medications':('Medications administered',1,81,12),'number_outpatient':('Outpatient visits in prior year',0,42,0),'number_emergency':('Emergency visits in prior year',0,76,0),'number_inpatient':('Inpatient visits in prior year',0,21,0),'number_diagnoses':('Recorded diagnoses',1,16,5)}
    def display(field,value):
        if field=='admission_type_id':return admission.get(value,value)
        if field=='admission_source_id':return source.get(value,value)
        if field=='age':
            lower,upper=value.strip('[)').split('-');return f'{lower}–{int(upper)-1} years'
        if value=='None':return 'Not tested'
        if value=='Norm':return 'Normal'
        if field=='change':return 'Changed' if value=='Ch' else 'No change'
        if field=='insulin':return {'No':'Not prescribed','Steady':'Steady dose','Up':'Dose increased','Down':'Dose decreased'}[value]
        return value
    values={}
    st.subheader('Patient readmission prediction')
    st.write('Enter a discharge-stage patient profile, then select **Predict readmission**. All fields are editable.')
    with st.form('patient_prediction'):
        st.markdown('#### 01 · Patient & admission')
        fields=['age','gender','race','admission_type_id','admission_source_id','primary_diagnosis_group']
        columns=st.columns(3)
        for index,field in enumerate(fields):
            with columns[index%3]:
                values[field]=st.selectbox(names[field],categories[field],index=categories[field].index(defaults[field]),format_func=lambda value,field=field:display(field,value),key='manual_'+field)
        st.markdown('#### 02 · Hospital stay & previous encounters')
        columns=st.columns(4)
        for index,(field,(label,minimum,maximum,default)) in enumerate(numeric.items()):
            with columns[index%4]:values[field]=st.number_input(label,min_value=minimum,max_value=maximum,value=default,step=1,key='manual_'+field)
        st.caption('Visit counts refer to the year before this encounter. Numeric ranges follow the original UCI dataset.')
        st.markdown('#### 03 · Medication & laboratory results')
        columns=st.columns(3)
        for index,field in enumerate(['insulin','change','diabetesMed','A1Cresult','max_glu_serum']):
            with columns[index%3]:
                values[field]=st.selectbox(names[field],categories[field],index=categories[field].index(defaults[field]),format_func=lambda value,field=field:display(field,value),key='manual_'+field)
        submitted=st.form_submit_button('Predict readmission',type='primary',width='stretch')
    if submitted:
        prepared=pd.DataFrame([values],columns=NUM+CAT)
        probabilities=model.predict_proba(prepared)[0]
        st.session_state['manual_prediction']={'class':str(model.classes_[int(np.argmax(probabilities))]),'probabilities':dict(zip(model.classes_,map(float,probabilities))),'inputs':values}
    result=st.session_state.get('manual_prediction')
    if result:
        descriptions={'NO':'No recorded readmission','>30':'Readmission after 30 days','<30':'Readmission within 30 days'}
        tones={'NO':'teal','>30':'violet','<30':'amber'}
        predicted=result['class']
        st.markdown(f'<div class="prediction-result {tones[predicted]}"><div class="eyebrow">PREDICTED OUTCOME</div><h2>{descriptions[predicted]}</h2><p>Random Forest · class {predicted.replace("<","&lt;").replace(">","&gt;")} · highest model probability</p></div>',unsafe_allow_html=True)
        for column,label in zip(st.columns(3),labels):
            with column:
                st.metric(descriptions[label],f"{result['probabilities'][label]:.1%}")
                st.progress(result['probabilities'][label])
        st.caption('Results reflect the last submitted profile. These are uncalibrated model probabilities for an academic demonstration, not a clinical diagnosis or treatment recommendation.')
        with st.expander('Review the submitted model inputs'):
            st.dataframe(pd.DataFrame([result['inputs']])[NUM+CAT],hide_index=True,width='stretch')
    else:
        st.info('Your prediction will appear here after you submit the patient profile.')

if block=='A':
    st.write('Business problem: combine larger hospital encounter data with the original diabetes readmission foundation, supporting follow-up review and retrospective resource segmentation.')
    metric_row([('Records',f"{manifest['rows']:,}"),('Source columns',manifest['columns']),('Dimensions',7),('Fact tables',1)])
    st.write('**Grain:** one published encounter/discharge record. Source-qualified encounter keys prevent cross-source collisions. Patient records are not matched across unrelated datasets.')
    image=ROOT/'outputs/warehouse_star.png'
    if image.exists():st.image(str(image),width='stretch')
    contract=load_json('A_warehouse_design/star_schema_contract.json')
    st.dataframe(pd.DataFrame([{'dimension':'DIM_'+n,'attributes':', '.join(a)} for n,a in contract['dimensions'].items()]),hide_index=True,width='stretch')
    st.write('Every dimension has a surrogate primary key; FACT_ENCOUNTER stores seven foreign keys and encounter measures. Cost, readmission, and clinical fields remain null where unavailable.')
    with st.expander('Master dataset preview and source boundaries'):
        st.dataframe(pd.read_csv(ROOT/'modelled.csv',nrows=20,keep_default_na=False),hide_index=True)
        st.write('UCI and SPARCS have different populations, periods and diagnosis systems. Retain source filters. Capped stays are lower bounds, not exact values. No encounter dates were invented.')
elif block=='B':
    status=load_json('B_snowflake_deployment/warehouse_status.json')
    metric_row([('Snowflake status',status['status']),('Fact rows',f"{status['fact_rows']:,}"),('Dimensions',status['dimension_tables']),('Failed checks',status['failed_checks'])])
    st.write('Warehouse FINAL_JURY_WH | Database HEALTHCARE_FINAL_JURY | Schemas STAGING and DW')
    st.caption('Cloud status was confirmed by the user after executing SQL. This local dashboard displays saved evidence; use the Snowflake worksheet to show live tables and queries.')
    st.dataframe(pd.DataFrame([{'source':k,'rows':v} for k,v in manifest['source_counts'].items()]),hide_index=True)
    choice=st.selectbox('Show SQL',['06_build_dimensional_warehouse.sql','07_demo_queries.sql','05_verify_staging.sql'])
    st.code((ROOT/'B_snowflake_deployment'/choice).read_text(),language='sql')
    with st.expander('Actual Snowflake staging evidence'):
        for p in sorted((ROOT/'B_snowflake_deployment/evidence').glob('*.png')):st.image(str(p),caption=p.stem)
elif block=='C':
    card=load_json('outputs/supervised_dataset.json')
    metric_row([('Original UCI encounters',101766),('Eligible encounters',card['eligible_records']),('Selected predictors',card['predictor_count']),('Target classes',3)])
    st.write('Source: [UCI Diabetes 130-US Hospitals](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008). Original CSV: 50 columns; death/hospice exclusions: 2,423 encounters.')
    st.write('Target **readmitted**: NO = no recorded readmission; >30 = later readmission; <30 = early readmission. These are retrospective discharge-stage labels.')
    st.dataframe(pd.DataFrame([{'partition':k,'real_encounters':v} for k,v in classes['split_rows'].items()]),hide_index=True)
    st.write('Patient-disjoint train/validation/test split. Imputation, scaling and encoding are fitted on training patients only. No identifiers are predictors.')
    st.bar_chart(pd.Series(classes['class_counts'],name='encounters'))
    with st.expander('Predictor list'):st.write(classes['predictors'])
    st.dataframe(uci().head(20),hide_index=True)
elif block=='D':
    metric_row([('Transactions',mining['rows']),('Min. support',mining['min_support']),('Min. confidence',mining['min_confidence']),('Min. lift',mining['min_lift'])])
    st.write('Each transaction is one real training encounter, with categorical age, diagnosis group, insulin, medication change, diabetes medication, HbA1c result and readmission label. Fixed sample seed: 42; maximum itemset size: 3.')
    st.dataframe(pd.DataFrame([{'algorithm':n,**v} for n,v in mining['algorithms'].items()]),hide_index=True)
    method=st.selectbox('Mining algorithm',['Apriori','FP-Growth'])
    rules=load_csv(f'outputs/mining/{method.lower()}_rules.csv')
    st.dataframe(rules[['antecedents','consequents','support','confidence','lift']].head(30),hide_index=True,width='stretch')
    st.write('Support = fraction containing both sides. Confidence = fraction of antecedent encounters also containing the consequent. Lift = confidence / consequent prevalence. Lift above one is association, not causation.')
    st.caption('Apriori extends frequent candidates level by level. FP-Growth compresses transactions into a frequent-pattern tree. Both returned the same frequent itemsets at identical thresholds.')
    with st.expander('Frequent itemsets'):st.dataframe(load_csv(f'outputs/mining/{method.lower()}_itemsets.csv').head(50),hide_index=True)
elif block=='E':
    st.write('Three distinct classifiers use the same 59,565 real training encounters, 19,917 validation encounters and 19,861 real test encounters. Class weighting addresses imbalance. Winner selection uses validation macro F1 before test evaluation.')
    st.dataframe(load_csv('outputs/classification/comparison.csv'),hide_index=True,width='stretch')
    st.success('Selected using validation: '+classes['selected'])
    baseline=classes['majority_baseline'];st.write(f"Majority-class test baseline: accuracy {baseline['accuracy']:.3f}, macro F1 {baseline['macro_f1']:.3f}.")
    st.write('Logistic Regression fits class decision scores; Decision Tree learns feature thresholds; Random Forest averages many randomized trees. Higher accuracy alone can hide poor minority-class detection.')
elif block=='F':
    st.write('Selected classifier: **'+classes['selected']+'**. Numeric median imputation and StandardScaler precede one-hot encoding of categorical features. Training uses observed real UCI outcomes; SPARCS and synthetic labels are not classifier ground truth.')
    st.write('Random Forest settings: 120 trees, maximum depth 14, minimum leaf size 8, balanced subsample weights, seed 42. Training and comparison code is in tools/complete_analytics.py.')
    prediction_form()
    with st.expander('How the model was trained'):
        st.write('Fit preprocessing and 120 trees on 59,565 training encounters. Compare validation macro F1 on 19,917 encounters, select the winner, then evaluate it on 19,861 held-out encounters. Patient groups do not overlap. Each tree votes for a class; the forest averages the tree probabilities and selects the largest score.')
        source=(ROOT/'tools/complete_analytics.py').read_text(encoding='utf-8')
        st.code('def classification():'+source.split('def classification():',1)[1].split('\ndef mining():',1)[0],language='python')
elif block=='G':
    metric_row([('Eligible full-source encounters',f"{clusters['eligible_full_records']:,}"),('Common benchmark sample',clusters['sample_records']),('Logical predictors',4)])
    st.write('Real SPARCS 2023/2024 discharges. Fixed uniform hash sample from eligible records; all four algorithms use identical encounters and representation.')
    st.markdown('Sources: New York State SPARCS [2023 discharge dataset](https://health.data.ny.gov/d/46xm-urtu) and [2024 discharge dataset](https://health.data.ny.gov/d/sf4k-39ay). Four logical predictors expand to seven model columns after age encoding.')
    st.write('Features: log1p(stay), log1p(estimated cost), illness severity 1-4, and one-hot common age band. Numeric features are standardized. IDs, outcomes and source-year labels are excluded from clustering inputs. Charges are excluded as redundant with cost.')
    st.write('Eligibility: positive exact stay, positive estimated cost, severity 1-4, known age band. Capped stays and unavailable required features are excluded. No readmission target is needed for unsupervised learning.')
    st.dataframe(cluster_sample()[['source_key','age_band_common','los_days_lower_bound','total_costs_usd','severity']].head(30),hide_index=True)
elif block=='H':
    st.dataframe(compare_clusters(),hide_index=True,width='stretch')
    st.image(str(ROOT/'outputs/clustering/four_algorithms.png'),width='stretch')
    st.write('K-Means minimizes within-cluster squared distances; Ward hierarchical clustering merges groups; GMM fits probabilistic Gaussian components; DBSCAN groups dense neighborhoods and flags noise.')
    st.write('K=2..6 was compared for K-Means; the selected K is also used for Ward/GMM. DBSCAN explored eps 0.5/0.8/1.1/1.4 with min_samples=15. Compare coverage and internal metrics together; DBSCAN scores exclude noise.')
    st.dataframe(pd.DataFrame([
        {'method':'K-Means','strength':'Fast centroid segmentation','limitation':'Assumes compact groups; sensitive to scaling, outliers and K'},
        {'method':'Hierarchical','strength':'Nested hierarchy; no centroid initialization','limitation':'Pairwise memory makes large datasets expensive'},
        {'method':'GMM','strength':'Soft membership and elliptical groups','limitation':'Gaussian assumptions and covariance sensitivity'},
        {'method':'DBSCAN','strength':'Density groups and explicit noise','limitation':'Sensitive to eps and varying density; may leave cases unassigned'}]),hide_index=True,width='stretch')
    st.caption('Parameters: K-Means n_init=10; Ward linkage; GMM full covariance with regularization 1e-6; random seed 42 where applicable. All methods use the same seven-dimensional representation.')
    st.caption(f"Shared PCA display explains {clusters['pca_explained_variance']:.1%} of representation variance. PCA is for visualization; algorithms fit the full representation.")
elif block=='I':
    chosen=clusters['selected'];st.subheader(chosen)
    st.write(clusters['selection'])
    st.write('Implementation: preprocess the common sample, initialize K centroids, assign each point to its nearest centroid, recompute centroids, and repeat to convergence. Ten initializations reduce dependence on the starting centroids. K=2 was chosen from the recorded 2-6 search.')
    profiles=load_csv('outputs/clustering/profiles.csv');profiles=profiles[profiles.algorithm.eq(chosen)]
    st.dataframe(profiles,hide_index=True,width='stretch')
    sample=cluster_sample();st.bar_chart(sample[chosen+'_cluster'].value_counts().sort_index())
    st.info('Business use: review the longer-stay, higher-cost segment for discharge coordination and resource planning, and compare its care pathways with the shorter-stay segment. These historical profiles support a planning review; they do not estimate live bed demand or establish why costs differ.')
    st.write('Interpret segments using observed stay, estimated cost, severity and age profiles. Cluster IDs are arbitrary. These are descriptive resource-use groups, not clinically validated patient phenotypes.')
    with st.expander('Parameter search'):st.dataframe(pd.DataFrame(clusters['k_search']),hide_index=True)
elif block=='J':
    selected=classes['test'][classes['selected']]
    metric_row([('Test accuracy',f"{selected['accuracy']:.3f}"),('Macro F1',f"{selected['macro_f1']:.3f}"),('Early-readmission recall',f"{selected['per_class']['<30']['recall']:.3f}"),('Macro ROC AUC',f"{selected['macro_ovr_roc_auc']:.3f}")])
    st.image(str(ROOT/'outputs/classification/confusion_matrix.png'),width=650)
    st.dataframe(pd.DataFrame({label:selected['per_class'][label] for label in labels}).T,width='stretch')
    st.write('Accuracy: fraction correct. Precision: correct positives among predicted positives. Recall: detected cases among actual cases. F1: harmonic mean of precision and recall. Macro averaging gives each class equal weight.')
    st.dataframe(compare_clusters(),hide_index=True,width='stretch')
    st.write('Silhouette: higher is better separation. Davies-Bouldin: lower is better. Calinski-Harabasz: larger indicates stronger between-group separation relative to within-group spread. These are internal indices, not clinical outcomes.')
