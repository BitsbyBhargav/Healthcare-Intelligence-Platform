"""Measured final-jury mining, three classifiers, and four clustering methods."""
from pathlib import Path
import sys, json, time, inspect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'))
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import silhouette_score,davies_bouldin_score,calinski_harabasz_score,roc_auc_score
from sklearn.cluster import KMeans,AgglomerativeClustering,DBSCAN
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori,fpgrowth,association_rules
from threadpoolctl import threadpool_limits
from augmentation_pilot import NUM,CAT,LABELS,diagnosis_group,metrics

OUT=ROOT/'outputs';OUT.mkdir(exist_ok=True)
def dump(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
def features(raw):
    f=raw.copy();f['primary_diagnosis_group']=diagnosis_group(f['diag_1'])
    for c in NUM:f[c]=pd.to_numeric(f[c],errors='coerce')
    for c in CAT:f[c]=f[c].fillna('Missing').astype(str)
    return f[NUM+CAT]
def real_cohort():
    raw=pd.read_parquet(ROOT/'data/processed/uci_supervised.parquet')
    split=pd.read_parquet(ROOT/'data/processed/augmentation_pilot/real_patient_splits.parquet')
    f=raw.merge(split[['encounter_id','split']],on='encounter_id',how='inner',validate='one_to_one')
    assert len(f)==99343 and f.groupby('patient_nbr')['split'].nunique().max()==1
    return f
def classification():
    out=OUT/'classification';out.mkdir(exist_ok=True)
    f=real_cohort();x=features(f);y=f['readmitted'].astype(str)
    masks={s:f['split'].eq(s).to_numpy() for s in ['train','validation','test']}
    preprocess=ColumnTransformer([
       ('numeric',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),NUM),
       ('categorical',OneHotEncoder(handle_unknown='ignore'),CAT)])
    estimators={'Logistic Regression':LogisticRegression(max_iter=500,C=.5,class_weight='balanced'),
        'Decision Tree':DecisionTreeClassifier(max_depth=10,min_samples_leaf=40,class_weight='balanced',random_state=42),
        'Random Forest':RandomForestClassifier(n_estimators=120,max_depth=14,min_samples_leaf=8,class_weight='balanced_subsample',n_jobs=4,random_state=42)}
    fitted={};validation={};elapsed={}
    for name,est in estimators.items():
        start=time.perf_counter();model=Pipeline([('prepare',preprocess),('classifier',est)])
        # Independent preprocessing object per fitted pipeline.
        from sklearn.base import clone
        model=clone(model);model.fit(x.loc[masks['train']],y.loc[masks['train']])
        validation[name]=metrics(y.loc[masks['validation']],model.predict(x.loc[masks['validation']]))
        fitted[name]=model;elapsed[name]=time.perf_counter()-start
        print(name,'validation macro F1',round(validation[name]['macro_f1'],4),flush=True)
    selected=max(validation,key=lambda n:validation[n]['macro_f1'])
    results={};predictions=f.loc[masks['test'],['encounter_id','patient_nbr','readmitted']].copy()
    # Comparison is fixed from validation before examining any test metrics.
    for name,model in fitted.items():
        pred=model.predict(x.loc[masks['test']]);result=metrics(y.loc[masks['test']],pred)
        result['macro_ovr_roc_auc']=float(roc_auc_score(y.loc[masks['test']],model.predict_proba(x.loc[masks['test']]),multi_class='ovr',average='macro',labels=model.classes_))
        results[name]=result;predictions[name]=pred
    dummy=DummyClassifier(strategy='most_frequent').fit(x.loc[masks['train']],y.loc[masks['train']])
    baseline=metrics(y.loc[masks['test']],dummy.predict(x.loc[masks['test']]))
    model=fitted[selected];joblib.dump(model,out/'selected_pipeline.joblib')
    predictions.to_parquet(out/'test_predictions.parquet',index=False)
    table=pd.DataFrame([{'algorithm':n,'validation_macro_f1':validation[n]['macro_f1'],
        'test_macro_f1':results[n]['macro_f1'],'test_accuracy':results[n]['accuracy'],
        'test_macro_precision':results[n]['per_class']['macro avg']['precision'],
        'test_macro_recall':results[n]['per_class']['macro avg']['recall'],
        'test_early_recall':results[n]['per_class']['<30']['recall'],
        'test_roc_auc':results[n]['macro_ovr_roc_auc'],'fit_seconds':elapsed[n]} for n in fitted])
    table.to_csv(out/'comparison.csv',index=False)
    fig,ax=plt.subplots(figsize=(7,5));matrix=np.array(results[selected]['confusion_matrix'])
    ax.imshow(matrix,cmap='Blues');ax.set_xticks(range(3),LABELS);ax.set_yticks(range(3),LABELS)
    for i in range(3):
        for j in range(3):ax.text(j,i,f'{matrix[i,j]:,}',ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else '#152b3a')
    ax.set(xlabel='Predicted class',ylabel='Published class',title=f'{selected}: real held-out patients');fig.tight_layout();fig.savefig(out/'confusion_matrix.png',dpi=160);plt.close(fig)
    report={'selected':selected,'selection':'Validation macro F1; no test-set tuning','split_rows':{s:int(v.sum()) for s,v in masks.items()},
        'patient_overlap':0,'predictors':NUM+CAT,'target_classes':LABELS,'validation':validation,'test':results,
        'majority_baseline':baseline,'class_counts':f.readmitted.value_counts().to_dict(),
        'source':'Observed UCI outcomes only; 2423 death/hospice encounters excluded',
        'limits':['Discharge-stage retrospective model','One prespecified patient-group split','Not a matched comparison with prior jury models','No clinical calibration or deployment validation']}
    dump(out/'results.json',report)
    dump(OUT/'supervised_dataset.json',{'name':'UCI Diabetes 130-US Hospitals','original_records':101766,'raw_columns':50,'eligible_records':len(f),'predictor_count':len(NUM+CAT),'target':'readmitted','source':'https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008','splits':report['split_rows'],'missingness':'Source ? becomes null; None laboratory categories are retained'})
    print('Classification complete:',selected,flush=True)
def mining():
    out=OUT/'mining';out.mkdir(exist_ok=True)
    f=real_cohort();f=f[f.split.eq('train')].sample(n=15000,random_state=42).copy()
    f['diagnosis_group']=diagnosis_group(f.diag_1)
    use=['age','diagnosis_group','insulin','change','diabetesMed','A1Cresult','readmitted']
    transactions=[[f'{c}={row[c] if pd.notna(row[c]) else "Missing"}' for c in use] for _,row in f.iterrows()]
    encoder=TransactionEncoder();basket=pd.DataFrame(encoder.fit_transform(transactions),columns=encoder.columns_)
    summaries={};sets={}
    for name,method in [('Apriori',apriori),('FP-Growth',fpgrowth)]:
        start=time.perf_counter();freq=method(basket,min_support=.03,use_colnames=True,max_len=3)
        params={'metric':'confidence','min_threshold':.35}
        if 'num_itemsets' in inspect.signature(association_rules).parameters:params['num_itemsets']=len(basket)
        rules=association_rules(freq,**params)
        rules=rules[rules.lift.gt(1.05)].copy()
        rules=rules.sort_values(['lift','confidence'],ascending=False)
        freq['itemsets']=freq.itemsets.map(lambda s:' & '.join(sorted(s)))
        for c in ['antecedents','consequents']:rules[c]=rules[c].map(lambda s:' & '.join(sorted(s)))
        freq.to_csv(out/f'{name.lower()}_itemsets.csv',index=False)
        rules.to_csv(out/f'{name.lower()}_rules.csv',index=False)
        sets[name]=set(freq.itemsets)
        summaries[name]={'itemsets':len(freq),'rules':len(rules),'seconds':time.perf_counter()-start}
    assert sets['Apriori']==sets['FP-Growth']
    dump(out/'results.json',{'rows':15000,'seed':42,'source':'Real UCI training encounters only','min_support':.03,'min_confidence':.35,'min_lift':1.05,'max_itemset_length':3,'algorithms':summaries,'itemsets_agree':True,'limits':'Associations are descriptive; common categories can dominate. No causal effects are inferred.'})
    print('Mining complete',summaries,flush=True)
def clustering():
    out=OUT/'clustering';out.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'A_warehouse_design/data_preparation/preparation_report.json').read_text())
    sample=None;eligible=0
    keep=['encounter_key','source_key','age_band_common','los_days_lower_bound','los_top_coded','total_costs_usd','total_charges_usd','severity_code']
    for record in manifest['outputs']:
        if 'SPARCS' not in record['file']:continue
        f=pq.ParquetFile(ROOT/record['file']).read(columns=keep).to_pandas()
        f['severity']=pd.to_numeric(f.severity_code,errors='coerce')
        valid=(~f.los_top_coded)&f.los_days_lower_bound.gt(0)&f.total_costs_usd.gt(0)&f.severity.between(1,4)&f.age_band_common.notna()
        f=f.loc[valid].copy();eligible+=len(f)
        f['_sample_key']=pd.util.hash_pandas_object(f.encounter_key,index=False).to_numpy()
        f=f.nsmallest(5000,'_sample_key')
        sample=f if sample is None else pd.concat([sample,f],ignore_index=True).nsmallest(5000,'_sample_key')
    sample=sample.sort_values('_sample_key').reset_index(drop=True);sample.to_parquet(out/'prepared_sample.parquet',index=False)
    numeric=np.column_stack([np.log1p(sample.los_days_lower_bound),np.log1p(sample.total_costs_usd),sample.severity])
    scale=StandardScaler();num=scale.fit_transform(numeric)
    encoder=OneHotEncoder(sparse_output=False,handle_unknown='ignore');age=encoder.fit_transform(sample[['age_band_common']])
    x=np.column_stack([num,age]);pca=PCA(n_components=2,random_state=42);xy=pca.fit_transform(x)
    score_idx=np.random.default_rng(42).choice(len(x),min(2000,len(x)),replace=False)
    choices=[]
    for k in range(2,7):
        labels=KMeans(n_clusters=k,n_init=10,random_state=42).fit_predict(x)
        choices.append({'k':k,'silhouette':float(silhouette_score(x[score_idx],labels[score_idx]))})
    k=max(choices,key=lambda z:z['silhouette'])['k']
    models={'K-Means':KMeans(n_clusters=k,n_init=10,random_state=42),
        'Hierarchical':AgglomerativeClustering(n_clusters=k,linkage='ward'),
        'GMM':GaussianMixture(n_components=k,covariance_type='full',reg_covar=1e-6,random_state=42)}
    db=[]
    for eps in [.5,.8,1.1,1.4]:
        labels=DBSCAN(eps=eps,min_samples=15,n_jobs=4).fit_predict(x);valid=labels!=-1;n=len(set(labels[valid]))
        if n>=2 and n<50 and valid.sum()>200:
            ix=score_idx[valid[score_idx]]
            if len(set(labels[ix]))>=2:db.append({'eps':eps,'score':float(silhouette_score(x[ix],labels[ix]))*float(valid.mean())})
    eps=max(db,key=lambda d:d['score'])['eps'] if db else .8
    models['DBSCAN']=DBSCAN(eps=eps,min_samples=15,n_jobs=4)
    results={};profiles=[];fig,axes=plt.subplots(2,2,figsize=(11,8))
    for (name,model),ax in zip(models.items(),axes.flat):
        start=time.perf_counter();labels=model.fit_predict(x);valid=labels!=-1;unique=set(labels[valid]);ix=score_idx[valid[score_idx]]
        usable=len(unique)>1 and len(set(labels[ix]))>1 and len(unique)<len(ix)
        result={'clusters':len(unique),'noise':int((~valid).sum()),'coverage':float(valid.mean()),'seconds':time.perf_counter()-start,
            'silhouette':float(silhouette_score(x[ix],labels[ix])) if usable else None,
            'davies_bouldin':float(davies_bouldin_score(x[valid],labels[valid])) if usable else None,
            'calinski_harabasz':float(calinski_harabasz_score(x[valid],labels[valid])) if usable else None,
            'parameters':{'k':k} if name!='DBSCAN' else {'eps':eps,'min_samples':15}}
        results[name]=result;sample[name+'_cluster']=labels
        profile=sample.groupby(name+'_cluster').agg(records=('encounter_key','size'),mean_stay=('los_days_lower_bound','mean'),mean_estimated_cost=('total_costs_usd','mean'),mean_severity=('severity','mean')).reset_index().rename(columns={name+'_cluster':'cluster'})
        profile['algorithm']=name;profiles.append(profile)
        ax.scatter(xy[:,0],xy[:,1],c=labels,cmap='tab10',s=5,alpha=.45);ax.set_title(f'{name}: {len(unique)} clusters, {result["noise"]} noise')
        ax.set_xlabel('PCA 1');ax.set_ylabel('PCA 2')
    eligible_names=[n for n,v in results.items() if v['noise']==0 and v['silhouette'] is not None]
    chosen=max(eligible_names,key=lambda n:results[n]['silhouette'])
    fig.suptitle('Same 5,000 encounters and common PCA display');fig.tight_layout();fig.savefig(out/'four_algorithms.png',dpi=150);plt.close(fig)
    sample.to_parquet(out/'assignments.parquet',index=False);pd.concat(profiles).to_csv(out/'profiles.csv',index=False)
    joblib.dump({'model':models[chosen],'scaler':scale,'age_encoder':encoder,'pca':pca},out/'selected_clustering.joblib')
    dump(out/'results.json',{'sample_records':len(sample),'eligible_full_records':eligible,'source':'SPARCS 2023 and 2024; real encounters',
        'features':['log1p(length of stay)','log1p(estimated cost)','severity 1-4','one-hot common age band'],
        'selection':'Highest silhouette among methods assigning every encounter; DBSCAN noise reported separately',
        'selected':chosen,'k_search':choices,'k':k,'dbscan_search':db,'algorithms':results,
        'pca_explained_variance':float(pca.explained_variance_ratio_.sum()),
        'limits':['Fixed reproducible hash sample; algorithms fit identical records/features','Internal metrics, not clinical validation','DBSCAN scores exclude noise; coverage must accompany them','Cost methodologies differ by source year','No readmission labels or identifiers used as clustering features','Charges retained for profiles but excluded as correlated with cost']})
    print('Four clustering algorithms complete:',chosen,flush=True)
if __name__=='__main__':
    with threadpool_limits(limits=4):
        classification();mining();clustering()
