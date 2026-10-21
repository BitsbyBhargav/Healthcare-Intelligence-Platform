from pathlib import Path
import sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    database=ROOT/'data/healthcare_dw.db'
    if not database.is_file(): raise FileNotFoundError(database)
    with sqlite3.connect(database) as conn:
        for table in ['Fact_Admissions','Dim_Patient','Dim_Admission','Dim_Diagnosis']:
            df=pd.read_sql_query(f'SELECT * FROM {table}',conn)
            df.to_csv(ROOT/'data'/f'{table}.csv',index=False)
            print(table,len(df))
if __name__=='__main__': main()
