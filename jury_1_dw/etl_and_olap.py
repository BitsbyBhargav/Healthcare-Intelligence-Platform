"""Build the Jury 1 star schema from the preserved local dataset.
The source CSV is read-only. Outputs default to data/healthcare_dw.db.
"""
from pathlib import Path
import argparse
import sqlite3
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
TABLES = ['Dim_Patient', 'Dim_Admission', 'Dim_Diagnosis', 'Fact_Admissions']

def build_warehouse(data=ROOT/'data/diabetes_130_us.csv', output=ROOT/'data/healthcare_dw.db'):
    df = pd.read_csv(data, low_memory=False).replace('?', None)
    required = {'patient_nbr', 'encounter_id', 'readmitted'}
    if not required.issubset(df):
        raise ValueError('Source requires original encounter and patient identifiers')
    if df.encounter_id.duplicated().any() or df.patient_nbr.isna().any():
        raise ValueError('Invalid encounter keys or missing patient keys')
    patient = df[['patient_nbr','race','gender','age']].drop_duplicates('patient_nbr')
    admission_cols = ['admission_type_id','discharge_disposition_id','admission_source_id']
    admission = df[admission_cols].drop_duplicates().copy()
    admission['admission_id'] = range(1,len(admission)+1)
    df = df.merge(admission,on=admission_cols,how='left',validate='many_to_one')
    diagnosis_cols = ['diag_1','diag_2','medical_specialty']
    diagnosis = df[diagnosis_cols].drop_duplicates().copy()
    diagnosis['diag_id'] = range(1,len(diagnosis)+1)
    df = df.merge(diagnosis,on=diagnosis_cols,how='left',validate='many_to_one')
    fact = df[['encounter_id','patient_nbr','admission_id','diag_id','time_in_hospital',
               'num_lab_procedures','num_procedures','num_medications','number_diagnoses','readmitted']]
    output = Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(output) as conn:
        for name, frame in zip(TABLES,[patient,admission,diagnosis,fact]):
            frame.to_sql(name,conn,if_exists='replace',index=False)
        for table,key in [('Dim_Patient','patient_nbr'),('Dim_Admission','admission_id'),
                          ('Dim_Diagnosis','diag_id'),('Fact_Admissions','encounter_id')]:
            conn.execute(f'CREATE UNIQUE INDEX idx_{table}_key ON {table}({key})')
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    return dict(zip(TABLES,map(len,[patient,admission,diagnosis,fact])))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=ROOT/'data/diabetes_130_us.csv')
    parser.add_argument('--output',type=Path,default=ROOT/'data/healthcare_dw.db')
    args=parser.parse_args()
    print(build_warehouse(args.data,args.output))
    print('Warehouse:',args.output)
    print('Run python jury_1_dw/sql.py to demonstrate OLAP queries.')
if __name__=='__main__': main()
