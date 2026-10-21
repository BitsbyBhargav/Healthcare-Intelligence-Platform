"""Record reproducibility evidence without retraining or changing predictions."""
from pathlib import Path
import sys, json, hashlib, platform, math, importlib.metadata as metadata
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'jury_2_dw'))
from benchmark_models import prepare, SEED, classifiers

def main():
    out=R/'jury_2_dw/outputs'
    source=R/'data/diabetes_130_us.csv'
    raw=pd.read_csv(source,low_memory=False)
    X,y,train,val,test=prepare(raw)
    model_report=json.loads((out/'best_model_report.json').read_text())
    full_run=all(model_report[key]==len(indices) for key,indices in [('train_rows_used',train),('validation_rows_used',val),('holdout_test_rows_used',test)])
    baseline=np.zeros(len(test),dtype=int)
    summary={
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_shape':list(raw.shape),'python':platform.python_version(),
        'versions':{p:metadata.version(p) for p in ['pandas','numpy','scikit-learn','xgboost','mlxtend','streamlit','joblib']},
        'seed':SEED,'validation_group_seed':SEED+1,
        'run_mode':'full data; train-cap=0 val-cap=0 test-cap=0' if full_run else 'capped samples; see best_model_report.json for rows used',
        'patient_counts':{name:int(raw.patient_nbr.iloc[idx].nunique()) for name,idx in [('train',train),('validation',val),('test',test)]},
        'split_row_index_sha256':{name:hashlib.sha256(np.asarray(idx,dtype='<i8').tobytes()).hexdigest() for name,idx in [('train',train),('validation',val),('test',test)]},
        'test_majority_NO_baseline':{'accuracy':accuracy_score(y.iloc[test],baseline),'f1_macro':f1_score(y.iloc[test],baseline,average='macro',zero_division=0)},
        'class_counts':{str(k):int(v) for k,v in raw.readmitted.value_counts().items()},
        'fixed_candidates':{name:{k:('NaN' if isinstance(v,float) and math.isnan(v) else v) for k,v in model.get_params().items() if isinstance(v,(str,int,float,bool,type(None)))} for name,model in classifiers().items()},
        'source_limitations':['Historical 1999-2008 cohort','Local CSV has empty A1C entries; treat as Unknown','No temporal or external validation','Encounter-weighted mining/profiles include repeated patients'],
    }
    (out/'run_provenance.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
    for name in ['apriori_rules','fp_growth_rules','profile_age','profile_diagnosis','profile_medications','profile_prior_inpatient','profile_stay','model_comparison']:
        pd.read_csv(out/f'{name}.csv').to_json(out/f'{name}.json',orient='records',indent=2)
    print(json.dumps(summary['test_majority_NO_baseline'],indent=2))
if __name__=='__main__': main()
