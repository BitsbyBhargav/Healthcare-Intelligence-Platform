#!/usr/bin/env python3
import sqlite3
import pandas as pd
import os

# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Connect to database
conn = sqlite3.connect(os.path.join(parent_dir, 'healthcare_dw.db'))

# Extract tables matching your Star Schema
tables = ['Fact_Admissions', 'Dim_Patient', 'Dim_Admission', 'Dim_Diagnosis']

print("Exporting DW tables to CSV format...")
for table in tables:
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    output_path = os.path.join(parent_dir, 'data', f'{table}.csv')
    df.to_csv(output_path, index=False)
    print(f"-> Exported {table}.csv ({len(df)} records)")

conn.close()
print("All tables successfully exported to data/ folder!")