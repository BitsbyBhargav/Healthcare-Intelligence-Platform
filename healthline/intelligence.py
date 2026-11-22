"""Reproducible retrospective clustering and validated saved-model inference."""
import hashlib
import json
from pathlib import Path
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from healthline.warehouse import ROOT, SOURCE, now

sys.path.insert(0, str(ROOT/'jury_2_dw'))
from jury2_features import FEATURES, LABELS, build_features

OUT = ROOT/'healthline/artifacts'
CLUSTER_FEATURES = ['age_midpoint','num_medications','number_diagnoses','num_lab_procedures',
                    'num_procedures','number_inpatient','number_emergency','number_outpatient','time_in_hospital']


def cluster_features(raw):
    df = raw.copy()
    df['age_midpoint'] = pd.to_numeric(df.age.astype(str).str.extract(r'^\[(\d+)-',expand=False),errors='coerce')+5
    return df.reindex(columns=CLUSTER_FEATURES).apply(pd.to_numeric,errors='coerce')


def train_clusters(raw=None, output=OUT):
    """Fit on all real encounters; compare K=2..6 on the same seeded sample."""
    start = time.perf_counter()
    raw = pd.read_csv(SOURCE,low_memory=False) if raw is None else raw
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    x = cluster_features(raw)
    preprocess = make_pipeline(SimpleImputer(strategy='median'),StandardScaler())
    z = preprocess.fit_transform(x)
    n_sample = min(2000,len(z))
    indices = np.random.default_rng(42).choice(len(z),size=n_sample,replace=False)
    scores, candidates = [], {}
    with threadpool_limits(limits=2):
        for k in range(2,7):
            model = KMeans(n_clusters=k,random_state=42,n_init=10,max_iter=200).fit(z)
            score = float(silhouette_score(z[indices],model.labels_[indices]))
            scores.append({'k':k,'silhouette':score})
            candidates[k] = model
        k = max(scores,key=lambda v:v['silhouette'])['k']
        model = candidates[k]
        pca = PCA(n_components=2,random_state=42).fit(z)
        coords = pca.transform(z)
    version = hashlib.sha256(pd.util.hash_pandas_object(x,index=False).values.tobytes()).hexdigest()[:12]
    assigned = pd.DataFrame({'encounter_id':raw.encounter_id.values,'cluster':model.labels_,
                             'pc1':coords[:,0],'pc2':coords[:,1],'readmitted':raw.readmitted.values})
    profile = x.assign(cluster=model.labels_).groupby('cluster').mean().round(3)
    profile['encounters'] = assigned.groupby('cluster').size()
    profile['readmission_under_30_pct'] = assigned.assign(under30=assigned.readmitted.eq('<30')).groupby('cluster').under30.mean()*100
    summary = {'version':version,'trained_at':now(),'encounters':len(raw),'features':CLUSTER_FEATURES,
               'selected_k':k,'silhouette':max(v['silhouette'] for v in scores),
               'silhouette_sample':n_sample,'seed':42,'k_comparison':scores,
               'pca_explained_variance':pca.explained_variance_ratio_.tolist(),
               'duration_seconds':time.perf_counter()-start,
               'method':'Full-data KMeans; median imputation; StandardScaler; age bin midpoint; retrospective LOS'}
    joblib.dump({'preprocess':preprocess,'model':model,'pca':pca,'version':version,
                 'features':CLUSTER_FEATURES},output/'clusters.joblib',compress=3)
    assigned.to_csv(output/'cluster_assignments.csv',index=False)
    profile.to_csv(output/'cluster_profiles.csv')
    (output/'clustering_report.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def load_classifier():
    artifact = joblib.load(ROOT/'jury_2_dw/outputs/best_model.joblib')
    pipe = artifact['pipeline']
    if artifact['features'] != FEATURES or artifact['labels'] != LABELS:
        raise ValueError('Classifier feature or label contract mismatch')
    if list(pipe.feature_names_in_) != FEATURES or list(pipe.classes_) != [0,1,2]:
        raise ValueError('Classifier input or probability column order mismatch')
    if artifact['prediction_point'] != 'discharge':
        raise ValueError('Unexpected prediction point')
    return artifact


def infer(raw, artifact):
    x = build_features(raw)
    probabilities = artifact['pipeline'].predict_proba(x)
    if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1),1):
        raise ValueError('Invalid probabilities')
    return probabilities


def enrichment(cluster_artifact=None, classifier=None):
    def run(conn, raw):
        if cluster_artifact is not None:
            z = cluster_artifact['preprocess'].transform(cluster_features(raw))
            labels = cluster_artifact['model'].predict(z)
            conn.executemany('INSERT INTO patient_clusters VALUES (?,?,?)',
                             [(int(eid),int(label),cluster_artifact['version']) for eid,label in zip(raw.encounter_id,labels)])
        if classifier is not None:
            probs = infer(raw,classifier)
            stamp = now()
            conn.executemany('INSERT INTO model_predictions VALUES (?,?,?,?,?,?)',
                [(int(eid),LABELS[int(p.argmax())],json.dumps(p.tolist()),classifier['model_name'],
                  'discharge',stamp) for eid,p in zip(raw.encounter_id,probs)])
    return run


if __name__ == '__main__':
    print(json.dumps(train_clusters(),indent=2))
