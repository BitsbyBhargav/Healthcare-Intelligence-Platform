"""Isolated incremental replay warehouse. Original artifacts are always read-only.

All batch data, cursor changes, and success logs commit together. BEGIN IMMEDIATE
serializes concurrent replay requests. Encounter primary keys guarantee idempotency.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import time
import uuid

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/diabetes_130_us.csv'
HISTORICAL = ROOT / 'data/healthcare_dw.db'
RUNTIME = ROOT / 'runtime'
DEMO = RUNTIME / 'replay.db'
AGES = [f'[{n}-{n+10})' for n in range(0, 100, 10)]
NUMERIC_RANGES = {
    'encounter_id': (1, 10**12), 'patient_nbr': (1, 10**12),
    'time_in_hospital': (1, 14), 'num_lab_procedures': (0, 132),
    'num_procedures': (0, 6), 'num_medications': (0, 81),
    'number_diagnoses': (1, 16), 'number_inpatient': (0, 21),
    'number_emergency': (0, 76), 'number_outpatient': (0, 42),
    'admission_type_id': (1, 8), 'discharge_disposition_id': (1, 30),
    'admission_source_id': (1, 25),
}
REQUIRED = list(NUMERIC_RANGES) + ['age', 'race', 'gender', 'diag_1', 'diag_2',
                                        'medical_specialty', 'readmitted']
SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Dim_Patient (
 patient_nbr INTEGER PRIMARY KEY, race TEXT, gender TEXT, age TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Dim_Admission (
 admission_id INTEGER PRIMARY KEY, admission_type_id INTEGER NOT NULL,
 discharge_disposition_id INTEGER NOT NULL, admission_source_id INTEGER NOT NULL,
 UNIQUE(admission_type_id,discharge_disposition_id,admission_source_id));
CREATE TABLE IF NOT EXISTS Dim_Diagnosis (
 diag_id INTEGER PRIMARY KEY, diag_1 TEXT NOT NULL, diag_2 TEXT NOT NULL,
 medical_specialty TEXT NOT NULL, UNIQUE(diag_1,diag_2,medical_specialty));
CREATE TABLE IF NOT EXISTS Fact_Admissions (
 encounter_id INTEGER PRIMARY KEY, patient_nbr INTEGER NOT NULL REFERENCES Dim_Patient,
 admission_id INTEGER NOT NULL REFERENCES Dim_Admission, diag_id INTEGER NOT NULL REFERENCES Dim_Diagnosis,
 time_in_hospital INTEGER NOT NULL CHECK(time_in_hospital BETWEEN 1 AND 14),
 num_lab_procedures INTEGER, num_procedures INTEGER, num_medications INTEGER,
 number_diagnoses INTEGER, number_inpatient INTEGER, number_emergency INTEGER,
 number_outpatient INTEGER, readmitted TEXT CHECK(readmitted IN ('NO','>30','<30')),
 ingested_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pipeline_runs (
 run_id TEXT PRIMARY KEY, started_at TEXT, ended_at TEXT, source_batch TEXT,
 input_rows INTEGER, accepted_rows INTEGER, rejected_rows INTEGER,
 duplicate_rows INTEGER, loaded_rows INTEGER, duration_seconds REAL,
 status TEXT, error_details TEXT, before_count INTEGER, after_count INTEGER);
CREATE TABLE IF NOT EXISTS ingestion_batches (
 run_id TEXT PRIMARY KEY REFERENCES pipeline_runs, source_start INTEGER,
 source_end INTEGER, source_file TEXT);
CREATE TABLE IF NOT EXISTS rejected_records (
 run_id TEXT REFERENCES pipeline_runs, source_row TEXT, encounter_id TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS patient_clusters (
 encounter_id INTEGER PRIMARY KEY REFERENCES Fact_Admissions, cluster INTEGER NOT NULL, model_version TEXT);
CREATE TABLE IF NOT EXISTS model_predictions (
 encounter_id INTEGER PRIMARY KEY REFERENCES Fact_Admissions, prediction TEXT,
 probabilities TEXT, model_version TEXT, prediction_point TEXT, generated_at TEXT);
CREATE TABLE IF NOT EXISTS operational_scenarios (
 scenario_id TEXT PRIMARY KEY, created_at TEXT, label TEXT, assumptions TEXT, results TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def assert_demo_path(path):
    path = Path(path).resolve()
    # No writes anywhere in original data/model/archive locations, including symlinks.
    for protected in [ROOT/'data', ROOT/'jury_1_dw', ROOT/'jury_2_dw', ROOT/'archive']:
        if path.is_relative_to(protected.resolve()):
            raise ValueError('Replay cannot write to original artifact directories')
    if path == (ROOT/'healthcare_dw.db').resolve():
        raise ValueError('Original warehouse is protected')
    return path


@contextmanager
def connect(path=DEMO, readonly=False):
    path = Path(path).resolve()
    conn = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=30) if readonly else sqlite3.connect(assert_demo_path(path), timeout=30)
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
    finally:
        conn.close()


def initialize(path=DEMO):
    path = assert_demo_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and 'demo_metadata' not in tables:
            raise ValueError('Refusing to initialize a non-demo database')
        c.executescript(SCHEMA)
        with c:
            c.execute("INSERT OR IGNORE INTO demo_metadata VALUES ('kind','healthline-replay-v1')")
            c.execute("INSERT OR IGNORE INTO demo_metadata VALUES ('cursor','0')")


def reset_demo(path=DEMO):
    """Reset only a marked demo DB; never delete a file or accept original paths."""
    assert_demo_path(path)
    with connect(path) as c, c:
        marker = c.execute("SELECT value FROM demo_metadata WHERE key='kind'").fetchone()
        if marker != ('healthline-replay-v1',):
            raise ValueError('Not a HealthLine replay database')
        c.execute('BEGIN IMMEDIATE')
        for table in ['model_predictions','patient_clusters','rejected_records','ingestion_batches',
                      'Fact_Admissions','Dim_Patient','Dim_Admission','Dim_Diagnosis','pipeline_runs']:
            c.execute(f'DELETE FROM {table}')
        c.execute("UPDATE demo_metadata SET value='0' WHERE key='cursor'")


def query(sql, path=DEMO, params=()):
    with connect(path, readonly=True) as c:
        return pd.read_sql_query(sql, c, params=params)


def validate(raw):
    missing = set(REQUIRED) - set(raw.columns)
    if missing:
        raise ValueError('Missing required columns: '+', '.join(sorted(missing)))
    df = raw.reset_index(drop=True).copy().replace('?', pd.NA)
    reasons = pd.Series('', index=df.index)
    for col, (low, high) in NUMERIC_RANGES.items():
        df[col] = pd.to_numeric(df[col], errors='coerce')
        bad = ~(df[col].between(low, high) & df[col].mod(1).eq(0))
        reasons.loc[bad] += col+' missing/out of range; '
    for col in ['age','race','gender','diag_1','diag_2','medical_specialty','readmitted']:
        df[col] = df[col].astype('string').str.strip().replace('', pd.NA).fillna('Unknown')
    reasons.loc[~df.age.isin(AGES)] += 'invalid age; '
    reasons.loc[~df.readmitted.isin(['NO','>30','<30'])] += 'invalid outcome; '
    rejected = pd.DataFrame({'source_row': raw.index.astype(str),
                             'encounter_id': raw.encounter_id.astype(str).values, 'reason': reasons})
    rejected = rejected.loc[reasons.ne('')]
    good = df.loc[reasons.eq('')].copy()
    good[list(NUMERIC_RANGES)] = good[list(NUMERIC_RANGES)].astype('int64')
    return good, rejected


def ingest(raw=None, path=DEMO, batch_size=100, callback=None, enrich=None):
    """Replay next batch, or ingest explicit rows for deterministic idempotency tests.

    A callback announces the operation about to run. Analytics enrichments execute
    inside the transaction, so an exception cannot leave partial encounter loads.
    """
    initialize(path)
    started, tick, run_id = now(), time.perf_counter(), uuid.uuid4().hex
    report = dict(run_id=run_id, started_at=started, ended_at=None, source_batch='explicit',
                  input_rows=0, accepted_rows=0, rejected_rows=0, duplicate_rows=0,
                  loaded_rows=0, duration_seconds=0., status='failed', error_details='',
                  before_count=0, after_count=0)
    def stage(name):
        if callback:
            callback(name)
    with connect(path) as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            report['before_count'] = c.execute('SELECT count(*) FROM Fact_Admissions').fetchone()[0]
            report['after_count'] = report['before_count']
            stage('Data source')
            cursor = int(c.execute("SELECT value FROM demo_metadata WHERE key='cursor'").fetchone()[0])
            replay = raw is None
            if replay:
                if not 50 <= batch_size <= 500:
                    raise ValueError('Batch size must be 50–500')
                raw = pd.read_csv(SOURCE, skiprows=range(1,cursor+1), nrows=batch_size, low_memory=False)
                report['source_batch'] = f'CSV rows {cursor}–{cursor+len(raw)} (end exclusive)'
            report['input_rows'] = len(raw)
            stage('Validation')
            good, rejected = validate(raw)
            report['accepted_rows'], report['rejected_rows'] = len(good), len(rejected)
            stage('Transformation')
            unique = good.drop_duplicates('encounter_id')
            new_rows = []
            stamp = now()
            stage('Warehouse')
            for idx, r in unique.iterrows():
                eid = int(r.encounter_id)
                if c.execute('SELECT 1 FROM Fact_Admissions WHERE encounter_id=?', (eid,)).fetchone():
                    continue
                c.execute('INSERT OR IGNORE INTO Dim_Patient VALUES (?,?,?,?)',
                          (int(r.patient_nbr),r.race,r.gender,r.age))
                av = tuple(int(r[k]) for k in ['admission_type_id','discharge_disposition_id','admission_source_id'])
                c.execute('INSERT OR IGNORE INTO Dim_Admission(admission_type_id,discharge_disposition_id,admission_source_id) VALUES (?,?,?)',av)
                aid = c.execute('SELECT admission_id FROM Dim_Admission WHERE admission_type_id=? AND discharge_disposition_id=? AND admission_source_id=?',av).fetchone()[0]
                dv = (r.diag_1,r.diag_2,r.medical_specialty)
                c.execute('INSERT OR IGNORE INTO Dim_Diagnosis(diag_1,diag_2,medical_specialty) VALUES (?,?,?)',dv)
                did = c.execute('SELECT diag_id FROM Dim_Diagnosis WHERE diag_1=? AND diag_2=? AND medical_specialty=?',dv).fetchone()[0]
                nums = [int(r[k]) for k in ['time_in_hospital','num_lab_procedures','num_procedures','num_medications','number_diagnoses','number_inpatient','number_emergency','number_outpatient']]
                c.execute('INSERT INTO Fact_Admissions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                          (eid,int(r.patient_nbr),aid,did,*nums,r.readmitted,stamp))
                new_rows.append(idx)
            report['loaded_rows'] = len(new_rows)
            report['duplicate_rows'] = len(good)-len(new_rows)
            stage('Analytics')
            if enrich and new_rows:
                # Preserve the training-time missing-diagnosis semantics. Warehouse
                # dimension sentinels must never replace raw model inputs.
                enrich(c, raw.reset_index(drop=True).loc[new_rows])
            report['after_count'] = c.execute('SELECT count(*) FROM Fact_Admissions').fetchone()[0]
            if replay:
                c.execute("UPDATE demo_metadata SET value=? WHERE key='cursor'",(str(cursor+len(raw)),))
            report.update(ended_at=now(),duration_seconds=time.perf_counter()-tick,status='success')
            c.execute('INSERT INTO pipeline_runs VALUES ('+','.join('?'*len(report))+')',tuple(report.values()))
            c.execute('INSERT INTO ingestion_batches VALUES (?,?,?,?)',
                      (run_id,cursor if replay else None,cursor+len(raw) if replay else None,SOURCE.name))
            c.executemany('INSERT INTO rejected_records VALUES (?,?,?,?)',
                          [(run_id,*r) for r in rejected.itertuples(index=False,name=None)])
            c.commit()
        except Exception as exc:
            c.rollback()
            report.update(ended_at=now(),duration_seconds=time.perf_counter()-tick,
                          loaded_rows=0,after_count=report['before_count'],error_details=str(exc))
            with c:
                c.execute('INSERT INTO pipeline_runs VALUES ('+','.join('?'*len(report))+')',tuple(report.values()))
            return report
    stage('Dashboard')
    return report


QUERIES = {
    'Summary': 'SELECT count(*) encounters, round(avg(time_in_hospital),2) average_stay, round(avg(num_medications),2) average_medications, round(avg(number_diagnoses),2) average_diagnoses FROM Fact_Admissions',
    'Encounters by age': 'SELECT p.age, count(*) encounters, round(avg(f.time_in_hospital),2) average_stay FROM Fact_Admissions f JOIN Dim_Patient p USING(patient_nbr) GROUP BY p.age ORDER BY p.age',
    'Readmission distribution': 'SELECT readmitted, count(*) encounters FROM Fact_Admissions GROUP BY readmitted',
    'Medication and diagnosis complexity': 'SELECT number_diagnoses, count(*) encounters, round(avg(num_medications),2) average_medications, round(avg(time_in_hospital),2) average_stay FROM Fact_Admissions GROUP BY number_diagnoses',
    'Utilization by segment': 'SELECT p.age, f.readmitted, count(*) encounters, sum(time_in_hospital) historical_bed_days FROM Fact_Admissions f JOIN Dim_Patient p USING(patient_nbr) GROUP BY p.age, f.readmitted',
    'Readmission by cluster': 'SELECT c.cluster, f.readmitted, count(*) encounters, round(avg(f.time_in_hospital),2) average_stay FROM Fact_Admissions f JOIN patient_clusters c USING(encounter_id) GROUP BY c.cluster, f.readmitted',
    'Recent ingestion': 'SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 30',
}


def counts(path=DEMO):
    tables = query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",path).name
    return pd.DataFrame([{'table': t,'rows':int(query(f'SELECT count(*) n FROM "{t}"',path).n.iloc[0])} for t in tables])
