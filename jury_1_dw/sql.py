import sqlite3
from pathlib import Path
import pandas as pd

# Resolve the actual warehouse database in the data folder
project_root = Path(__file__).resolve().parent.parent
db_path = project_root / 'data' / 'healthcare_dw.db'

if not db_path.exists():
    raise FileNotFoundError(f"Data warehouse not found at {db_path}. Run the ETL pipeline first.")

# Connect to our local Data Warehouse
conn = sqlite3.connect(db_path)

# 1. Execute Roll-Up SQL Query
rollup_query = """
SELECT 
    p.age,
    COUNT(f.encounter_id) AS Total_Admissions,
    ROUND(AVG(f.time_in_hospital), 2) AS Avg_Stay_Days
FROM Fact_Admissions f
JOIN Dim_Patient p ON f.patient_nbr = p.patient_nbr
GROUP BY p.age
ORDER BY p.age ASC;
"""
print("=== ROLL-UP RESULT ===")
df_rollup = pd.read_sql_query(rollup_query, conn)
print(df_rollup.to_string(index=False))

print("\n" + "="*40 + "\n")

# 2. Execute Slice SQL Query
slice_query = """
SELECT 
    f.readmitted,
    COUNT(f.encounter_id) AS patient_count,
    ROUND(AVG(f.num_lab_procedures), 1) AS avg_lab_tests
FROM Fact_Admissions f
WHERE f.num_medications > 15
GROUP BY f.readmitted;
"""
print("=== SLICE RESULT ===")
df_slice = pd.read_sql_query(slice_query, conn)
print(df_slice.to_string(index=False))

conn.close()